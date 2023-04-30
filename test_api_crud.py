import os
import sqlite3
import tempfile
import unittest
import json
from app import app, create_table

class CRUDTestCase(unittest.TestCase):


    def setUp(self):
        app.config['TESTING'] = True

        self.db_fd, app.config['DATABASE'] = tempfile.mkstemp(prefix='unittest_database_', suffix='.db')

        # Initialize the test database with schema and test data
        with app.app_context():
            self.init_db()
            self.populate_db()

        self.app = app.test_client()
        
        # Reference data.
        self.data_1 = {
            'chain_id': 1,
            'chain_name': 'Ethereum',
            'urls': [
                'https://foo/bar',
                'wss://fish/dog:9000'
            ]
        }
        self.data_2 = {
            'chain_id': 2,
            'chain_name': 'Bitcoin',
            'urls': [
                'https://bit/bar',
                'wss://smoke/hammer:1234'
            ]
        }

        
    def tearDown(self):
        # Close the database connection and remove the temporary test database
        os.close(self.db_fd)
        os.unlink(app.config['DATABASE'])
        print(app.config['DATABASE'])


    def init_db(self):
        # Use the same create_table as for the live database.
        create_table()

    def populate_db(self):
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute("INSERT INTO chain_data (chain_id, chain_name, urls) VALUES (?, ?, ?)",
                (1, "Ethereum", '["https://eth1-archive-1.dwellir.com", "wss://eth1-archive-2.dwellir.com"]'))
        c.execute("INSERT INTO chain_data (chain_id, chain_name, urls) VALUES (?, ?, ?)",
                (2, "Binance Smart Chain", '["https://bsc-dataseed1.binance.org","https://bsc.publicnode.com","wss://bsc-ws-node.nariox.org"]'))
        conn.commit()
        conn.close()


    def test_create_record_missing_entry(self):
        # Send a request without the urls entry
        data = {'chain_id': 1, 'chain_name': 'Ethereum'}
        response = self.app.post('/create', json=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json)

        # Send a request without the chain_name entry
        data = {'chain_id': 1, 'urls': ['https://mainnet.infura.io/v3/...', 'https://ropsten.infura.io/v3/...']}
        response = self.app.post('/create', json=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json)

        # Send a request without the chain_id entry
        data = {'chain_name': 'Ethereum', 'urls': ['https://mainnet.infura.io/v3/...', 'https://ropsten.infura.io/v3/...']}
        response = self.app.post('/create', json=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json)

    def test_create_record_no_duplicate_names(self):
        # Send a request with all three entries
        data = {'chain_id': 1, 'chain_name': 'Ethereum', 'urls': ['https://mainnet.infura.io/v3/...', 'https://ropsten.infura.io/v3/...']}
        response = self.app.post('/create', json=data)
        self.assertEqual(response.status_code, 400)

    def test_create_record_success(self):
        # Send a request with all three entries
        data = {'chain_id': 999, 'chain_name': 'TESTNAME', 'urls': ['https://foo.bar', 'https://foo.bar']}
        response = self.app.post('/create', json=data)
        self.assertEqual(response.status_code, 201)
        self.assertIn('message', response.json)
        
        # Check that the record was inserted into the database
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('SELECT * FROM chain_data WHERE id = ?', (response.json['id'],))
        record = c.fetchone()
        conn.close()
        self.assertIsNotNone(record)
        self.assertEqual(record[1], data['chain_id'])
        self.assertEqual(record[2], data['chain_name'])
        self.assertEqual(json.loads(record[3]), data['urls'])

    def test_get_all_records(self):
        response = self.app.get('/all')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json, list)

    def test_get_record_by_id(self):
        chaindata = {
            'chain_id': 2,
            'chain_name': 'Bitcoin',
            'urls': [
                'https://bit/bar',
                'wss://smoke/hammer:1234'
            ]
        }
        response = self.app.post('/create', json=chaindata)
        record_id = response.json['id']
        response = self.app.get(f'/get/{record_id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['chain_name'], chaindata['chain_name'])

    def test_update_record(self):
        # Create a new record
        chaindata = {
            'chain_id': 2,
            'chain_name': 'Bitcoin 2',
            'urls': [
                'https://bit/bar',
                'wss://smoke/hammer:1234'
            ]
        }
        create_response = self.app.post('/create', json=chaindata)
        record_id = create_response.json['id']

        # Update the record
        new_data = {'chain_id': 2, 'chain_name': 'test-update-chainName', 'urls': ['test-update-url']}
        update_response = self.app.put('/update/{}'.format(record_id), json=new_data)
        assert update_response.status_code == 200

        # Get the updated record and check its values
        get_response = self.app.get('/get/{}'.format(record_id))
        updated_record = get_response.json
        assert updated_record['chain_id'] == new_data['chain_id']
        assert updated_record['chain_name'] == new_data['chain_name']
        actual_urls = updated_record['urls']
        self.assertListEqual(new_data['urls'], actual_urls)

    def test_delete_record(self):
        chaindata = {
            'chain_id': 2,
            'chain_name': 'Bitcoin 2',
            'urls': [
                'https://bit/bar',
                'wss://smoke/hammer:1234'
            ]
        }
        response = self.app.post('/create', json=chaindata)
        record_id = response.json['id']
        response = self.app.delete(f'/delete/{record_id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['message'], 'Record deleted successfully')

    def test_get_chain_info_by_chain_name(self):
        response = self.app.get('/chain_info?chain_name=Ethereum')
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json, msg='Response is not valid JSON')
        self.assertGreaterEqual(len(response.json), 1)
        self.assertEqual(response.json[0]['id'], 1)
        self.assertEqual(response.json[0]['chain_id'], 1)
        self.assertEqual(response.json[0]['chain_name'], 'Ethereum')
        self.assertIsInstance(response.json[0]['urls'], list)

    def test_get_chain_info_by_chain_id(self):
        response = self.app.get('/chain_info?chain_id=1')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json), 1)
        self.assertIsNotNone(response.json, msg='Response is not valid JSON')
        self.assertEqual(response.json[0]['id'], 1)
        self.assertEqual(response.json[0]['chain_id'], 1)
        self.assertEqual(response.json[0]['chain_name'], 'Ethereum')
        self.assertIsInstance(response.json[0]['urls'], list)

    def test_get_chain_info_missing_params(self):
        response = self.app.get('/chain_info')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['error'], 'Missing required parameters')

    def test_get_chain_info_not_found(self):
        response = self.app.get('/chain_info?chain_name=Foo')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json['error'], 'Chain not found')


if __name__ == '__main__':
    unittest.main()