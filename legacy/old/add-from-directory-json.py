#!/usr/bin/env python3
import requests
import json
import argparse
import os

parser = argparse.ArgumentParser(description='Add chain data to database')
parser.add_argument('-d', '--directory', type=str, help='Directory containing JSON files')
parser.add_argument('-f', '--files', nargs='+', type=str, help='List of JSON files')
args = parser.parse_args()

if args.directory is not None and args.files is not None:
    raise ValueError('Cannot specify both directory and files')
elif args.directory is not None:
    file_paths = [os.path.join(args.directory, f) for f in os.listdir(args.directory) if f.endswith('.json')]
elif args.files is not None:
    file_paths = args.files
else:
    raise ValueError('Must specify either directory or files')

# Define the API endpoint
url = 'http://localhost:5000/create'

created_chains = []

# Add the chains to the database
for path in file_paths:
    with open(path, 'r') as f:
        chain = json.load(f)
        response = requests.post(url, json=chain)
        if response.status_code == 201:
            print(f'Added chain with ID {response.json()["id"]}')
            created_chains.append(response.json()["id"])
        else:
            print(f'Error adding chain from {f.name}: {response.json()}')
