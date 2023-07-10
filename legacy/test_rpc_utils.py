#!/bin/env python3

import asyncio
from rpc_utils import get_aptos, get_ethereum, get_substrate


async def main():
    print("=========== Sub =========")
    uri = "wss://rpc.polkadot.io"
    info = await get_substrate(uri)
    print(info)

    uri = "https://rpc.polkadot.io"
    info = await get_substrate(uri)
    print(info)

    print("=========== Ether =========")

    uri = "wss://ethereum.publicnode.com"
    info = await get_ethereum(uri)
    print(info)

    uri = "https://ethereum.publicnode.com"
    info = await get_ethereum(uri)
    print(info)

    print("=========== Aptos =========")

    uri = "https://aptos-mainnet-rpc.allthatnode.com/v1"
    info = await get_aptos(uri)
    print(info)

if __name__ == "__main__":
    asyncio.run(main())
