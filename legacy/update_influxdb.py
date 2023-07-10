#!/usr/bin/env python3

import asyncio
from datetime import datetime
import json
import logging
from color_logger import ColoredFormatter
import sys
from pathlib import Path
from typing import Callable
import requests
import warnings
import argparse
import time
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
import influxdb_utils as iu

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
formatter = ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def main():
    parser = argparse.ArgumentParser(description='Continuously update the InfluxDB specified in the config file')
    parser.add_argument('config_file', type=str, help="The file with the target database's config", default='config.json')
    args = parser.parse_args()

    if not (Path.cwd() / args.config_file).exists():
        raise FileNotFoundError
    with open(args.config_file, encoding='utf-8') as f:
        config = json.load(f)

    # TODO: add validation of config through schema? rpc api and influxdb required, cache age and update interval optional

    influxdb = {
        'url': config['INFLUXDB_URL'],
        'token': config['INFLUXDB_TOKEN'],
        'org': config['INFLUXDB_ORG'],
        'bucket': config['INFLUXDB_BUCKET']
    }
    cache_max_age = config.get('CACHE_MAX_AGE', 60)
    poll_interval = config.get('POLL_INTERVAL', 10)

    # Test connection to influx before attempting to start.
    if not iu.test_influxdb_connection(influxdb['url'], influxdb['token'], influxdb['org']):
        logger.error("Couldn't connect to influxdb at url %s\nExiting.", influxdb['url'])
        sys.exit(1)

    with warnings.catch_warnings(record=True) as warn:
        loop = asyncio.get_event_loop()
        for w in warn:
            if "no current event loop" in str(w.message):
                logger.info("First startup, starting new event loop.")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                break
        warnings.simplefilter("ignore")

    while True:
        # Get all RPC endpoints from all chains.
        # Place them in a list with their corresponding class.
        # This is all the endpoints we are to query and update the influxdb with.
        # all_url_api_tuples = get_all_endpoints_from_api(rpc_flask_api)
        all_endpoints = load_endpoints(config['RPC_FLASK_API'], cache_max_age)
        # all_chains = load_chains(config['RPC_FLASK_API'], cache_max_age)
        # TODO: update how to return a none result?
        all_results = loop.run_until_complete(iu.fetch_results(all_endpoints))

        # Create block_heights dict
        block_heights = {}
        for endpoint, results in zip(all_endpoints, all_results):
            if results and results.get('latest_block_height'):
                chain = endpoint[0]
                if chain not in block_heights.keys():
                    block_heights[chain] = []
                block_heights[chain].append((endpoint[1], int(results.get('latest_block_height', -1))))
            else:
                logger.warning("Results of endpoint %s not accessible.", endpoint[1])

        # Calculate block_height diffs and append points
        block_height_diffs = {}
        for chain in block_heights:
            # print(chain)
            rpc_list = block_heights[chain]
            # print(rpc_list)
            block_height_diffs[chain] = {}
            max_height = max(rpc_list, key=lambda x: x[1])[1]
            # print("max_height: ", max_height)
            for rpc in rpc_list:
                # print("rpc: ", rpc)
                block_height_diffs[chain][rpc[0]] = max_height - rpc[1]
            # for rpc in block_height_diffs:
            #     records.append(iu.block_height_diff_point(chain=chain, url=rpc[0], block_height_diff=rpc[1], timestamp=rpc[2]))

        timestamp = datetime.utcnow()
        records = []
        # Create block_height_request points
        for endpoint, results in zip(all_endpoints, all_results):
            if results:
                try:
                    exit_code = int(results.get('exit_code', -1)) if results.get('exit_code') is not None else None
                    if exit_code is None:
                        logger.warning("None result for %s. Datapoint will not be added.", endpoint)
                    elif exit_code != 0:
                        logger.warning("Non-zero exit code found for %s. This is an indication that the endpoint isn't healthy.", endpoint)
                    else:
                        brp = iu.block_height_request_point(
                            chain=endpoint[0],
                            url=endpoint[1],
                            data=results,
                            block_height_diff=block_height_diffs[endpoint[0]][endpoint[1]],
                            timestamp=timestamp)
                        logger.info("Writing to influx %s", brp)
                        records.append(brp)
                except Exception as e:
                    logger.error("Error while accessing results for %s: %s %s", endpoint, results, str(e))
            else:
                logger.warning("Couldn't get information from %s. Skipping.", endpoint)

        write_to_influxdb(influxdb['url'], influxdb['token'], influxdb['org'], influxdb['bucket'], records)
        # Sleep between making requests to avoid triggering rate limits.
        time.sleep(poll_interval)


def write_to_influxdb(url: str, token: str, org: str, bucket: str, records: list) -> None:
    try:
        client = InfluxDBClient(url=url, token=token, org=org)
        write_api = client.write_api(write_options=SYNCHRONOUS)
        write_api.write(bucket=bucket, record=records)
    except Exception as e:
        logger.critical("Failed writing to influx. %s",  str(e))
        sys.exit(1)


def load_endpoints(rpc_flask_api: str, cache_refresh_interval: int) -> list:
    return load_from_flask_api(rpc_flask_api, get_all_endpoints, 'cache.json', cache_refresh_interval)


def load_from_flask_api(rpc_flask_api: str, rpc_flask_get_function: Callable, cache_filename: str, cache_refresh_interval: int) -> list:
    """Load endpoints from cache or refresh if cache is stale."""
    # Load cached values from file
    try:
        with open(cache_filename, 'r', encoding='utf-8') as f:
            results, last_cache_refresh = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning('Could not load values from %s', cache_filename)
        results, last_cache_refresh = None, 0

    # Check if cache is stale
    if time.time() - last_cache_refresh > cache_refresh_interval:
        refresh_cache = True
    else:
        diff = time.time() - last_cache_refresh
        remains = cache_refresh_interval - diff
        logger.info("%s will be updated in: %s", cache_filename, remains)
        refresh_cache = False

    if refresh_cache:
        try:
            logger.info("Updating cache from Flask API")
            results = rpc_flask_get_function(rpc_flask_api)
            last_cache_refresh = time.time()

            # Save updated cache to file
            with open(cache_filename, 'w', encoding='utf-8') as f:
                json.dump((results, last_cache_refresh), f)

        except Exception as e:
            # Log the error
            logger.error("An error occurred while updating cache: %s", str(e))

            # Load the previous cache value
            with open(cache_filename, 'r', encoding='utf-8') as f:
                results, last_cache_refresh = json.load(f)
    else:
        logger.info("Using cached values")
    return results


def get_all_endpoints(rpc_flask_api: str) -> list:
    url_api_tuples = []
    all_chains = requests.get(f'{rpc_flask_api}/all/chains', timeout=3)
    for chain in all_chains.json():
        chain_info = requests.get(f'{rpc_flask_api}/chain_info?chain_name={chain["name"]}', timeout=1)
        for url in chain_info.json()['urls']:
            url_api_tuples.append((chain_info.json()['chain_name'], url, chain_info.json()['api_class']))
    return url_api_tuples


if __name__ == '__main__':
    main()
