#!/bin/env python3

import os
from collections import OrderedDict
import json
from flask import Flask, jsonify, request, Response
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
import sqlite3
import logging
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
# logging.basicConfig(filename='app.log', level=logging.INFO)

app = Flask(__name__)
app.config['DATABASE'] = os.path.join(os.path.dirname(__file__), 'live_database.db')
# TODO: change this to a file-based secret?
app.config['JWT_SECRET_KEY'] = 'super-secret'
jwt = JWTManager(app)


# CONSTANTS
# TODO: move to their own file in cleanup (perhaps?)
TABLE_CHAINS = 'chains'
TABLE_RPC_URLS = 'rpc_urls'


# DATABASE SETUP
# TODO: perhaps move table creation SQL to its own file? Lookup recommended setup
# Create the database table if it doesn't exist
def create_tables_if_not_exist():
    app.logger.info("CREATING database and tables %s", app.config['DATABASE'])
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS chains
                      (name TEXT PRIMARY KEY UNIQUE NOT NULL,
                       api_class TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS rpc_urls
                      (url TEXT PRIMARY KEY UNIQUE NOT NULL,
                       chain_name TEXT NOT NULL,
                       FOREIGN KEY(chain_name) REFERENCES chains(name))''')
    conn.commit()
    conn.close()


# API ROUTES
# Create a route to authenticate your users and return JWTs. The
# create_access_token() function is used to actually generate the JWT.
@app.route("/token", methods=["POST"])
def login():
    username = request.json.get("username", None)
    password = request.json.get("password", None)
    # TODO: figure out what to do with users
    if username != "tmp" or password != "tmp":
        return jsonify({"msg": "Bad username or password"}), 401

    access_token = create_access_token(identity=username)
    return jsonify(access_token=access_token)


# TODO: temporary, for tests. Remove and decide which other routes should be protected (all?)
# Protect a route with jwt_required, which will kick out requests
# without a valid JWT present.
@app.route("/protected", methods=["GET"])
@jwt_required()
def protected():
    # Access the identity of the current user with get_jwt_identity
    current_user = get_jwt_identity()
    return jsonify(logged_in_as=current_user), 200


def insert_into_database(table: str, request_data: dict) -> Response:
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        columns = ', '.join(request_data.keys())
        placeholders = ':' + ', :'.join(request_data.keys())
        query = f'INSERT INTO {table} ({columns}) VALUES ({placeholders})'
        cursor.execute(query, request_data)
        record_id = cursor.lastrowid  # TODO: remove?
        conn.commit()
        conn.close()
        return jsonify({'message': 'Record created successfully', 'id': record_id}), 201
    except sqlite3.IntegrityError as e:
        conn.rollback()  # Roll back the transaction
        conn.close()
        return jsonify({'error': str(e)}), 400
    # TODO: refine this exception
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Create a new database record
@app.route('/create/<string:table>', methods=['POST'])
def create_record(table: str) -> Response:
    if table not in [TABLE_CHAINS, TABLE_RPC_URLS]:
        return jsonify({'error': f'unknown table {table}'}), 400
    # Get the data from the request provided by flask
    data = request.get_json()
    app.logger.info('create_record from data: %s', data)

    if table == TABLE_CHAINS:
        # Check that the correct entries are present
        if not all(key in data for key in ('name', 'api_class')):
            return jsonify({'error': 'Both name and api_class entries are required'}), 400
        # Extract the data from the request
        values = {
            'name': data['name'],
            'api_class': data['api_class']
        }
        # Validate the API class
        if not is_valid_api(values['api_class']):
            return jsonify({'error': {'error': "Invalid api"}}), 500
        # Insert the record into the app.config['DATABASE']
        return insert_into_database(TABLE_CHAINS, values)

    if table == TABLE_RPC_URLS:
        # Check that the correct entries are present
        if not all(key in data for key in ('url', 'chain_name')):
            return jsonify({'error': 'Both url and chain_name entries are required'}), 400
        # Extract the data from the request
        values = {
            'url': data['url'],
            'chain_name': data['chain_name']
        }
        # Validate the url
        if not is_valid_url(values['url']):
            return jsonify({'error': {'error': "Invalid url."}}), 500
        # Insert the record into the app.config['DATABASE']
        return insert_into_database(TABLE_RPC_URLS, values)


# Get all records
@app.route('/all/<string:table>', methods=['GET'])
def get_all_records(table: str) -> Response:
    if table not in [TABLE_CHAINS, TABLE_RPC_URLS]:
        return jsonify({'error': f'unknown table {table}'}), 400
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()

    if table == TABLE_CHAINS:
        cursor.execute('SELECT name, api_class FROM chains')
    if table == TABLE_RPC_URLS:
        cursor.execute('SELECT url, chain_name FROM rpc_urls')

    records = cursor.fetchall()
    conn.close()
    results = []

    if table == TABLE_CHAINS:
        for record in records:
            results.append({'name': record[0], 'api_class': record[1]})
    if table == TABLE_RPC_URLS:
        for record in records:
            results.append({'url': record[0], 'chain_name': record[1]})
    return jsonify(results)


# Get a specific chain by chain name
@app.route('/get_chain_by_name/<string:name>', methods=['GET'])
def get_chain_by_name(name: str) -> Response:
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('SELECT name, api_class FROM chains WHERE name=?', (name,))
    record = cursor.fetchone()
    conn.close()
    if record:
        return jsonify({'name': record[0], 'api_class': record[1]})
    return jsonify({'error': 'Record not found'}), 404


# Get a specific chain by url
@app.route('/get_chain_by_url', methods=['GET'])
def get_chain_by_url() -> Response:
    """
    Gets the chain entry corresponding to the input url.

    Requires that url parameters 'protocol' and 'address' are present in the request, example:

    curl 'http://localhost:5000/get_chain_by_url?protocol=http&address=chain5.com'
    """
    try:
        url = url_from_request_args()
    except TypeError as e:
        app.logger.error('TypeError when trying to build RPC url from parameters: %s', str(e))
        return jsonify({'error': "url parameters 'protocol' and 'address' required for get_chain_by_url request"}), 400

    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('SELECT url, chain_name FROM rpc_urls WHERE url=?', (url,))
    url_record = cursor.fetchone()
    if url_record:
        cursor.execute('SELECT name, api_class FROM chains WHERE name = ?', (url_record[1],))
        chain_record = cursor.fetchone()
        if chain_record:
            return jsonify({'name': chain_record[0], 'api_class': chain_record[1]})
    conn.close()
    return jsonify({'error': 'Record not found'}), 404


# Get urls for a specific chain
@app.route('/get_urls/<string:chain_name>', methods=['GET'])
def get_urls(chain_name: str) -> Response:
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('SELECT url, chain_name FROM rpc_urls WHERE chain_name=?', (chain_name,))
    records = cursor.fetchall()
    conn.close()
    urls = []
    for record in records:
        urls.append(record[0])
    if len(urls) > 0:
        return jsonify(urls)
    return jsonify({'error': f'No urls found for chain {chain_name}'}), 404


# Update an existing url record
@app.route('/update_url', methods=['PUT'])
def update_url_record() -> Response:
    """
    Updates the rpc_urls entry corresponding to the input url.

    Requires that url parameters 'protocol' and 'address' are present in the request, example:

    curl -X PUT -H 'Content-Type: application/json' -d '{"url": "http://chain6.com", "chain_name": "chain6"}' \
        'http://localhost:5000/update_url?protocol=http&address=chain4.com'
    """
    try:
        url_old = url_from_request_args()
    except TypeError as e:
        app.logger.error('TypeError when trying to build RPC url from parameters: %s', str(e))
        return jsonify({'error': "url parameters 'protocol' and 'address' required for update_url_record request"}), 400

    try:
        url_new = request.json['url']
        chain_name = request.json['chain_name']
    except KeyError as e:
        return jsonify({'error': f'Missing required parameters, {e}'}), 400
    if not is_valid_url(url_new):
        return jsonify({'error': "Invalid url"}), 500

    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE rpc_urls SET url=?, chain_name=? WHERE url=?', (url_new, chain_name, url_old))
    except sqlite3.IntegrityError as e:
        conn.rollback()  # Roll back the transaction
        conn.close()
        return jsonify({'error': str(e)}), 400
    # TODO: refine this exception
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        rval = jsonify({'error': 'No such record'})
    else:
        rval = jsonify({'url': url_new, 'chain_name': chain_name})
    return rval


# TODO: verify
# Delete a chain record by name
@app.route('/delete_chain/<string:name>', methods=['DELETE'])
def delete_chain_record(name: str) -> Response:
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM chains WHERE name=?', (name,))
    except sqlite3.IntegrityError as e:
        return jsonify({'error': str(e)}), 400
    conn.commit()
    conn.close()
    return jsonify({'message': 'Record deleted successfully'})


# Delete a url record by url
@app.route('/delete_url', methods=['DELETE'])
def delete_url_record() -> Response:
    """
    Deletes the rpc_urls entry corresponding to the input url.

    Requires that url parameters 'protocol' and 'address' are present in the request, example:

    curl -X DELETE 'http://localhost:5000/delete_url?protocol=http&address=chain5.com'
    """
    try:
        url = url_from_request_args()
    except TypeError as e:
        app.logger.error('TypeError when trying to build RPC url from parameters: %s', str(e))
        return jsonify({'error': "url parameters 'protocol' and 'address' required for delete_url request"}), 400

    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM rpc_urls WHERE url=?', (url,))
    except sqlite3.IntegrityError as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': str(e)}), 400
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        rval = jsonify({'error': 'Record not found'})
    else:
        rval = jsonify({'message': 'Record deleted successfully'})
    return rval


# TODO: verify
# Delete url records by chain name
@app.route('/delete_url/<string:chain_name>', methods=['DELETE'])
def delete_url_records(chain_name: str) -> Response:
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM rpc_urls WHERE chain_name=?', (chain_name,))
    except sqlite3.IntegrityError as e:
        return jsonify({'error': str(e)}), 400
    conn.commit()
    conn.close()
    return jsonify({'message': 'Records deleted successfully'})


# TODO: verify
# Get all available info on a chain
@app.route('/chain_info', methods=['GET'])
def get_chain_info():
    # Get parameters from the request URL
    name = request.args.get('name')
    # Connect to the app.config['DATABASE']
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    # Query the app.config['DATABASE'] based on whether chain name or chain ID was provided
    if name:
        cursor.execute("SELECT * FROM chains WHERE name=?", (name,))
    else:
        return jsonify({'error': 'Missing required parameter "name"'}), 400
    # Fetch the chain record from the query
    chain_record = cursor.fetchone()  # TODO: fetchone() should be enough here, right? Only one should exist
    # If no result was found, return an error
    if not chain_record:
        return jsonify({'error': 'Chain not found'}), 404  # TODO: can this error happen, since we found it in the previous if?

    cursor.execute('''SELECT url, chain_name FROM rpc_urls WHERE chain_name=?''', (name,))
    url_records = cursor.fetchall()
    conn.close()
    urls = []
    for ur in url_records:
        urls.append(ur[0])
    result = {
        'chain_name': chain_record[0],
        'api_class': chain_record[1],
        'urls': urls
    }
    # Return the chain info as JSON
    return jsonify(result), 200


# UTILITIES
# TODO: move to their own file in cleanup

def is_valid_api(api):
    """ Test that api string is valid. """
    return api in ['substrate', 'ethereum', 'aptos']


def is_valid_url(url):
    """ Test that a url is valid, e.g. only http(s) and ws(s). """
    ALLOWED_SCHEMES = {'http', 'https', 'ws', 'wss'}
    try:
        result = urlparse(url)
        return all([result.scheme in ALLOWED_SCHEMES, result.netloc])
    except ValueError:
        return False


def url_from_request_args() -> str:
    """
    Return a full url from url parameters 'protocol' and 'address'.

    Caller is responsible for excepting any errors.
    """
    protocol = request.args.get('protocol')
    address = request.args.get('address')
    return protocol + '://' + address


# MAIN

if __name__ == '__main__':
    create_tables_if_not_exist()
    # TODO: add argument parser for things like host?
    app.run(debug=True, host='0.0.0.0')
