import unittest, tempfile, pathlib, threading
from product import create, update, listing, seed, validate

class ProductTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(pathlib.Path(self.tmp.name)/'test.sqlite')
    def tearDown(self): self.tmp.cleanup()
    def test_create_persist_update(self):
        item = create(self.path, dict(client='Fictif', title='Test'))
        self.assertEqual(listing(self.path)[0]['id'], item['id'])
        update(self.path, item['id'], dict(client='Fictif', title='Test', status='done'))
        self.assertEqual(listing(self.path)[0]['status'], 'done')
    def test_seed_idempotent(self):
        seed(self.path); seed(self.path)
        self.assertEqual(len(listing(self.path)), 3)
    def test_validation(self):
        for data in [{}, {'client':' ', 'title':'x'}, {'client':'x', 'title':'x'*201}, {'client':'x','title':'x','priority':'bad'}, {'client':'x','title':'x','status':'bad'}, {'client':10,'title':'x'}]:
            with self.assertRaises(ValueError): validate(data)
    def test_unknown_update(self):
        with self.assertRaises(KeyError): update(self.path, 'missing', dict(client='x',title='x'))
    def test_sql_literal(self):
        create(self.path, dict(client="Robert'); DROP TABLE requests;--", title='<script>alert(1)</script>'))
        self.assertEqual(len(listing(self.path)), 1)
    def test_concurrent_writes(self):
        seed(self.path)
        errors=[]
        def insert():
            try: create(self.path,dict(client='Fictif',title='Concurrent'))
            except Exception as e: errors.append(str(e))
        threads=[threading.Thread(target=insert) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors,[])
        self.assertEqual(len(listing(self.path)),8)

if __name__ == '__main__': unittest.main(verbosity=2)
