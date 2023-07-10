import time
from urllib.parse import urlparse
import aiohttp

# TODO: clean up, e.g. reusage


def is_valid_url(url):
    valid_schemes = ['ws', 'wss', 'http', 'https']
    parsed_url = urlparse(url)
    return parsed_url.scheme in valid_schemes


async def get_aptos(api_url):
    async with aiohttp.ClientSession() as session:
        try:
            start_time = time.monotonic()
            response = None
            async with session.get(api_url) as resp:
                end_time = time.monotonic()
                response = await resp.json()
            highest_block = int(response['block_height'])
            latency = (end_time - start_time)
            http_code = resp.status
            exit_code = 0
        except aiohttp.ClientError as e:
            print(f"Error in get_aptos for url {api_url}", response, e)
            return {'latest_block_height': None, 'time_total': None, 'http_code': None, 'exit_code': None}
        except Exception as ee:
            print(f"Error in get_aptos for url {api_url}", response, ee)
            return {'latest_block_height': None, 'time_total': None, 'http_code': None, 'exit_code': None}

        info = {
            'http_code': http_code,
            'time_total': latency,
            'exit_code': exit_code,
            'latest_block_height': highest_block
        }

        return info


async def get_substrate(api_url):
    async with aiohttp.ClientSession() as session:
        try:
            start_time = time.monotonic()
            response = None
            async with session.post(api_url, json={"jsonrpc": "2.0", "id": 1, "method": "chain_getHeader", "params": []}) as resp:
                end_time = time.monotonic()
                response = await resp.json()
            highest_block = int(response['result']['number'], 16)
            latency = (end_time - start_time)
            http_code = resp.status
            exit_code = 0
        except aiohttp.ClientError as e:
            print(f"Error in get_substrate for url {api_url}", response, e)
            return {'latest_block_height': None, 'time_total': None, 'http_code': None, 'exit_code': None}
        except Exception as ee:
            print(f"Error in get_substrate for url {api_url}", response, ee)
            return {'latest_block_height': None, 'time_total': None, 'http_code': None, 'exit_code': None}

        info = {
            'http_code': http_code,
            'time_total': latency,
            'exit_code': exit_code,
            'latest_block_height': highest_block
        }

        return info


async def get_ethereum(api_url, chain_id=1):
    async with aiohttp.ClientSession() as session:
        try:
            start_time = time.monotonic()
            response = None
            async with session.post(api_url, json={'jsonrpc': '2.0', 'method': 'eth_blockNumber', 'params': [], 'id': str({chain_id})}) as resp:
                end_time = time.monotonic()
                response = await resp.json()
            highest_block = int(response['result'], 16)
            latency = (end_time - start_time)
            http_code = resp.status
            exit_code = 0
        except aiohttp.ClientError as e:
            print(f"Error in get_ethereum for url {api_url}", response, e)
            return {'latest_block_height': None, 'time_total': None, 'http_code': None, 'exit_code': None}
        except Exception as ee:
            print(f"Error in get_ethereum for url {api_url}", response, ee)
            return {'latest_block_height': None, 'time_total': None, 'http_code': None, 'exit_code': None}

        info = {
            'http_code': http_code,
            'time_total': latency,
            'exit_code': exit_code,
            'latest_block_height': highest_block
        }

        return info
