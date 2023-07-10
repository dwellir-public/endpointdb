#!/bin/env python3

import requests

# Define the API endpoint
url = 'http://localhost:5000/create'

# Define the chain data to add
chains = [
    {
        'native_id': 1,
        'chain_name': 'Ethereum',
        'urls': ['https://ethereum.com', 'wss://eth.se']
    },
    {
        'native_id': 1,
        'chain_name': 'Bitcoin',
        'urls': ['https://bitcoin.com', 'wss://btc.se']
    },
    {
        'native_id': 1,
        'chain_name': 'Polkadot',
        'urls': ['https://polkadot.com', 'wss://dot.se']
    }
]


created_chains = []

# Add the chains to the database
for chain in chains:
    response = requests.post(url, json=chain)
    if response.status_code == 201:
        print('Added chain with ID "{response.json()["id"]}"')

        # print(f"Added chain with ID {response.json()['id']}")
        created_chains.append(response.json()["id"])
    else:
        print('Error adding chain:', response.json())

# Print all chains
response = requests.get('http://localhost:5000/all')
if response.status_code == 200:
    for chain in response.json():
        print('Chain("{chain["id"]}") "{chain["chain_name"]}" with native_id "{chain["native_id"]}" has URLs:')
        for url in chain['urls']:
            print('{url}')
else:
    print('"Error retrieving chains: "{response.json()}"')

# Delete all created chains
for id in created_chains:
    response = requests.delete(f'http://localhost:5000/delete/{id}')
    if response.status_code == 200:
        print(f'Deleted chain with ID {id}')
    else:
        print(f'Error deleting chain: {response.json()}')
