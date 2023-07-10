from datetime import datetime
import asyncio
from influxdb_client import InfluxDBClient, Point

from rpc_utils import get_aptos, get_ethereum, get_substrate


def block_height_request_point(chain: str, url: str, data: dict, block_height_diff: int, timestamp: datetime) -> Point:
    time_total = float(data.get('time_total') or 0)
    latest_block_height = int(data.get('latest_block_height') or -1)

    return Point("block_height_request") \
        .tag("chain", chain) \
        .tag("url", url) \
        .field("block_height", latest_block_height) \
        .field("block_height_diff", block_height_diff) \
        .field("request_time_total", time_total) \
        .time(timestamp)


def test_influxdb_connection(url: str, token: str, org: str) -> bool:
    """
    Test the connection to the database.
    """
    client = InfluxDBClient(url=url, token=token, org=org)
    try:
        return client.ping()
    except Exception as e:
        print(e)
        return False


async def send_request(api_url: str, api_class: str):
    if api_class == 'aptos':
        info = await get_aptos(api_url)
    elif api_class == 'substrate':
        info = await get_substrate(api_url)
    elif api_class == 'ethereum':
        info = await get_ethereum(api_url)
    else:
        raise ValueError('Invalid api_class:', api_class)
    return info


async def fetch_results(all_url_api_tuples: list):
    loop = asyncio.get_event_loop()  # Reuse the current event loop
    tasks = []
    for _, url, api_class in all_url_api_tuples:
        tasks.append(loop.create_task(send_request(url, api_class)))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
