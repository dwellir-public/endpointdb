#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Merge old JSON file chain data to new standard')
    parser.add_argument('-d', '--directory', type=str, help='Directory containing JSON files')
    parser.add_argument('-f', '--files', nargs='+', type=str, help='List of JSON files')
    parser.add_argument('--out_chains', type=str, help='Output file with merged chains')
    parser.add_argument('--out_urls', type=str, help='Output file with merged ROC urls')
    parser.add_argument('--include_everything', action='store_true', help='Includes all data, not just what is used in v2')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    if args.directory and args.files:
        raise ValueError('Cannot specify both directory and files')

    if args.directory:
        file_paths = [f for f in Path(args.directory).iterdir() if f.is_file() and f.suffix == '.json']
    elif args.files:
        file_paths = args.files
    else:
        raise ValueError('Must specify either directory or files')

    old_data = []
    for p in file_paths:
        with open(p, 'r', encoding='utf-8') as f:
            old_data.append(json.load(f))

    chains = []
    rpc_urls = []
    for d in old_data:
        if args.verbose:
            print('input: ', d, '\n')

        chains_entry = {
            'name': d['chain_name'],
            'api_class': d['api_class']
        }
        if args.include_everything:
            chains_entry['native_id'] = d['native_id']

        if args.verbose:
            print('chains entry: ', chains_entry, '\n')
        chains.append(chains_entry)

        for url in d['urls']:
            urls_entry = {
                'url': url,
                'chain_name': d['chain_name']
            }
            if args.verbose:
                print('rpc_urls entry: ', urls_entry, '\n')
            rpc_urls.append(urls_entry)

    out_chains_path = Path.cwd() / args.out_chains
    with open(out_chains_path, 'w', encoding='utf-8') as f:
        json.dump(chains, f, indent=4)
    out_rpc_urls_path = Path.cwd() / args.out_urls
    with open(out_rpc_urls_path, 'w', encoding='utf-8') as f:
        json.dump(rpc_urls, f, indent=4)


if __name__ == '__main__':
    main()
