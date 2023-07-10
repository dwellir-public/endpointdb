import json
import requests
import rpc_utils
import json
import sqlite3

#
# Import and export json into database.
#

def import_json_file(filename, db_filename):
    """
    Imports data from a JSON file into a SQLite database.
    Assumes the JSON file has the same format as the output of the export_json_file() function.
    """
    with open(filename, 'r') as f:
        data = json.load(f)
    conn = sqlite3.connect(db_filename)
    c = conn.cursor()
    for row in data:
        native_id = row['native_id']
        chain_name = row['chain_name']
        api_class = row['api_class']
        urls = json.dumps(row['urls'])
        c.execute("INSERT INTO chains_public_rpcs (native_id, chain_name, urls) VALUES (?, ?, ?, ?)", (native_id, chain_name, urls, api_class))
    conn.commit()
    conn.close()

def export_json_file(filename, db_filename):
    """
    Exports data from a SQLite database into a JSON file.
    The output JSON file has the same format as the input file for the import_json_file() function.
    """
    conn = sqlite3.connect(db_filename)
    c = conn.cursor()
    rows = c.execute("SELECT native_id, chain_name, urls, api_class FROM chains_public_rpcs").fetchall()
    data = []
    for row in rows:
        native_id = row[0]
        chain_name = row[1]
        urls = json.loads(row[2])
        api_class = json.loads(row[2])
        data.append({'native_id': native_id, 
                     'chain_name': chain_name, 
                     'urls': urls,
                     'api_class': api_class})
    with open(filename, 'w') as f:
        json.dump(data, f)
    conn.close()
    

# JSON-RPC request payload for getting the latest block number
payload = {
    "jsonrpc": "2.0",
    "method": "eth_blockNumber",
    "params": [],
    "id": 1
}

# Read JSON file from command line argument
filename = input("Enter JSON filename: ")
with open(filename) as f:
    data = json.load(f)

# Get latest block number from each URL
for url in data["urls"]:
    try:
        if data["chain_name"] == "Aptos Devnet" and data["native_id"] == 58:
            block_number = rpc_utils.get_block_height_aptos(url)
            print("Latest block number from", url, ":", block_number)
        if data["chain_name"] == "Aptos Mainnet" and data["native_id"] == 1:
            block_number = rpc_utils.get_block_height_aptos(url)
            print("Latest block number from", url, ":", block_number)
        else:
                response = requests.post(url, json=payload)
                if response.status_code == 200:
                    block_number_hex = response.json()["result"]
                    block_number = int(block_number_hex, 16)
                    print("Latest block number from", url, ":", block_number)
                else:
                    print("Error retrieving latest block number from", url)
    except Exception as e:
        print(f"Error retrieving latest block number from url {url}", e)
