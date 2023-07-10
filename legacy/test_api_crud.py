#!/bin/env python3

import os
import sqlite3
import tempfile
from pathlib import Path
import unittest
from app import app, create_tables_if_not_exist


class CRUDTestCase(unittest.TestCase):

    access_token = ""
    username = 'dwellir_endpointdb'
    with (Path(__file__).resolve().parent / 'auth_password').open() as pw_file:
        password = pw_file.read().strip()

    def setUp(self):
        app.config['TESTING'] = True
        self.db_fd, app.config['DATABASE'] = tempfile.mkstemp(prefix='unittest_database_', suffix='.db')

        # Initialize the test database with schema and test data
        with app.app_context():
            self.init_db()
            self.populate_db()

        self.app = app.test_client()
        self.access_token = self.app.post('/token', json={'username': self.username, 'password': self.password}).json['access_token']
        self.auth_header = {'Authorization': f'Bearer {self.access_token}'}

    def tearDown(self):
        # Close the database connection and remove the temporary test database
        os.close(self.db_fd)
        os.unlink(app.config['DATABASE'])

    def init_db(self):
        # Use the same create_table as for the live database.
        create_tables_if_not_exist()

    def populate_db(self):
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('INSERT INTO chains (name, api_class) VALUES (?, ?)', ('Ethereum mainnet', 'ethereum'))
        c.execute('INSERT INTO chains (name, api_class) VALUES (?, ?)', ('Polkadot', 'substrate'))
        c.execute('INSERT INTO rpc_urls (url, chain_name) VALUES (?, ?)', ('https://cloudflare-eth.com', 'Ethereum mainnet'))
        c.execute('INSERT INTO rpc_urls (url, chain_name) VALUES (?, ?)', ('wss://rpc.polkadot.io', 'Polkadot'))
        c.execute('INSERT INTO rpc_urls (url, chain_name) VALUES (?, ?)', ('https://rpc.polkadot.io', 'Polkadot'))
        conn.commit()
        conn.close()

    def test_create_chain_record_missing_entry(self):
        # Send a request without the api_class entry
        data = {'name': 'Ethereum mainnet'}
        response = self.app.post('/create_chain', json=data, headers=self.auth_header)
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json)

        # Send a request without the name entry
        data = {'api_class': 'ethereum'}
        response = self.app.post('/create_chain', json=data, headers=self.auth_header)
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json)

    def test_create_rpc_url_record_missing_entry(self):
        # Send a request without the chain_name entry
        data = {'url': 'https://cloudflare-eth.com'}
        response = self.app.post('/create_rpc_url', json=data, headers=self.auth_header)
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json)

        # Send a request without the url entry
        data = {'chain_name': 'Ethereum mainnet'}
        response = self.app.post('/create_rpc_url', json=data, headers=self.auth_header)
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json)

    def test_create_record_no_duplicate_names(self):
        # Send a create chain request with all three entries
        data = {'name': 'Ethereum mainnet', 'api_class': 'ethereum'}
        response = self.app.post('/create_chain', json=data, headers=self.auth_header)
        self.assertEqual(response.status_code, 400)

        # Send a create rpc url request with all three entries
        data = {'url': 'https://cloudflare-eth.com', 'chain_name': 'Ethereum mainnet'}
        response = self.app.post('/create_rpc_url', json=data, headers=self.auth_header)
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json)

    def test_create_chain_record_success(self):
        # Send a request with valid JSON data
        chain_data = {
            'name': 'Kusama',
            'api_class': 'substrate'
        }
        response = self.app.post('/create_chain', json=chain_data, headers=self.auth_header)
        self.assertEqual(response.status_code, 201)
        self.assertIn('message', response.json)

        # Check that the record was inserted into the database
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('SELECT * FROM chains WHERE name = ?', ('Kusama',))
        record = c.fetchone()
        conn.close()
        self.assertIsNotNone(record)
        self.assertEqual(record[1], chain_data['api_class'])

    def test_create_url_record_success(self):
        # Send a request with valid JSON data
        url_data = {
            'url': 'http://rpc.polkadot.io',
            'chain_name': 'Polkadot'
        }
        response = self.app.post('/create_rpc_url', json=url_data, headers=self.auth_header)
        self.assertEqual(response.status_code, 201)
        self.assertIn('message', response.json)

        # Check that the record was inserted into the database
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('SELECT * FROM rpc_urls WHERE url = ?', ('wss://rpc.polkadot.io',))
        record = c.fetchone()
        conn.close()
        self.assertIsNotNone(record)
        self.assertEqual(record[1], url_data['chain_name'])

    def test_get_all_chain_records(self):
        response = self.app.get('/all/chains')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json, list)

    def test_get_all_rpc_url_records(self):
        response = self.app.get('/all/rpc_urls')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json, list)

    def test_get_chain_record_by_name(self):
        chain_data = {'name': 'Polkadot', 'api_class': 'substrate'}
        response = self.app.get(f'/get_chain_by_name/{chain_data["name"]}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['api_class'], chain_data['api_class'])

    def test_get_chain_record_by_url(self):
        url_params = {'protocol': 'wss', 'address': 'rpc.polkadot.io'}  # Defined in setUp()
        response = self.app.get('/get_chain_by_url', query_string=url_params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['api_class'], 'substrate')

    def test_get_url(self):
        url_params = {'protocol': 'wss', 'address': 'rpc.polkadot.io'}  # Defined in setUp()
        response = self.app.get('/get_url', query_string=url_params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['url'], 'wss://rpc.polkadot.io')
        self.assertEqual(response.json['chain_name'], 'Polkadot')

    def test_get_urls(self):
        chain = 'Polkadot'
        response = self.app.get(f'/get_urls/{chain}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 2)
        self.assertIn('wss://rpc.polkadot.io', response.json)  # Defined in setUp()
        self.assertIn('https://rpc.polkadot.io', response.json)  # Defined in setUp()

    def test_update_url_record(self):
        # Create a new record
        url_data = {
            'url': 'wss://rpc-2.polkadot.io',
            'chain_name': 'Polkadot'
        }
        create_response = self.app.post('/create_rpc_url', json=url_data, headers=self.auth_header)
        self.assertEqual(create_response.status_code, 201)

        # Update the record
        new_url_data = {
            'url': 'https://rpc-2.polkadot.io',
            'chain_name': 'Polkadot'
        }
        old_url_params = {'protocol': 'wss', 'address': 'rpc-2.polkadot.io'}
        update_response = self.app.put('/update_url', query_string=old_url_params, json=new_url_data, headers=self.auth_header)
        self.assertEqual(update_response.status_code, 200)

        # Get the updated record and check its values
        new_url_params = {'protocol': 'https', 'address': 'rpc-2.polkadot.io'}
        get_response = self.app.get('/get_url', query_string=new_url_params)
        updated_record = get_response.json
        self.assertEqual(updated_record['url'], new_url_data['url'])
        self.assertEqual(updated_record['chain_name'], new_url_data['chain_name'])

    def test_delete_chain_record(self):
        query_string = {'name': 'Polkadot'}  # Added in setUp()
        response = self.app.delete('/delete_chain', query_string=query_string, headers=self.auth_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['message'], 'Chain record deleted successfully')
        all_chains_response = self.app.get('/all/chains')
        self.assertNotIn(query_string['name'], all_chains_response.json)

    def test_delete_url_record(self):
        query_string = {'protocol': 'wss', 'address': 'rpc.polkadot.io'}  # Added in setUp()
        delete_response = self.app.delete('/delete_url', query_string=query_string, headers=self.auth_header)
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json['message'], 'RPC url record deleted successfully')
        urls_response = self.app.get('/get_urls/Polkadot')
        self.assertNotIn(query_string['protocol'] + '://' + query_string['address'], urls_response.json)

    def test_delete_url_records(self):
        query_string = {'chain_name': 'Polkadot'}  # Added in setUp(), with two URL:s
        delete_response = self.app.delete('/delete_urls', query_string=query_string, headers=self.auth_header)
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json['message'], 'RPC url records deleted successfully')
        urls_response = self.app.get(f'/get_urls/{query_string["chain_name"]}')
        self.assertIn('error', urls_response.json)
        self.assertIn('No urls found for chain Polkadot', urls_response.json['error'])

    def test_get_chain_info_by_chain_name(self):
        chain_data = {
            'name': 'Polkadot',
            'api_class': 'substrate'
        }
        _ = self.app.post('/create_chain', json=chain_data)
        url_data_1 = {
            'url': 'wss://rpc.polkadot.io',
            'chain_name': 'Polkadot'
        }
        url_data_2 = {
            'url': 'https://rpc.polkadot.io',
            'chain_name': 'Polkadot'
        }
        _ = self.app.post('/create_rpc_url', json=url_data_1, headers=self.auth_header)
        _ = self.app.post('/create_rpc_url', json=url_data_2, headers=self.auth_header)
        response = self.app.get('/chain_info', query_string={'chain_name': chain_data['name']})
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json, msg='Response is not valid JSON')
        self.assertEqual(response.json['api_class'], 'substrate')
        self.assertEqual(response.json['chain_name'], 'Polkadot')
        self.assertEqual(len(response.json['urls']), 2)

    def test_get_chain_info_missing_params(self):
        response = self.app.get('/chain_info')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Missing required parameter', response.json['error'])

    def test_get_chain_info_not_found(self):
        response = self.app.get('/chain_info', query_string={'chain_name': 'Foo'})
        self.assertEqual(response.status_code, 404)
        self.assertIn('not found', response.json['error'])

    def test_jwt_protection(self):
        url_data = {'url': 'http://some.chain.rpc', 'chain_name': 'SomeChain'}
        response_failure = self.app.post('/create_rpc_url', json=url_data)  # No auth header leads to failure
        self.assertEqual(response_failure.status_code, 401)


if __name__ == '__main__':
    unittest.main()
