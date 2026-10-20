import importlib.util, pathlib, tempfile, unittest, os, sys, json
from decision import decide
import generator

class GeneratorTests(unittest.TestCase):
    def test_music_specification_is_complete(self):
        spec=generator.build_specification('Créer une application musicale premium blanc et rose')
        self.assertTrue(generator.validate_specification(spec))
        self.assertEqual(spec['name'],'Musea')
        self.assertEqual(spec['application_type'],'music-library')
        self.assertTrue({'Accueil','Recherche','Bibliothèque'}.issubset(spec['pages']))
    def test_music_files_have_no_request_tracker_contamination(self):
        spec=generator.build_specification('Créer une application musicale premium blanc et rose')
        files=generator.build_files(spec,'a'*32,'1.0.0')
        rendered='\n'.join(files[name].casefold() for name in ('prototype.html','prototype.js','style.css'))
        for forbidden in ('queuepilot','maison rivage','atelier boréal','studio lune','demande','client','priorité','statut'):
            self.assertNotIn(forbidden,rendered)
        self.assertIn('naya sol',rendered);self.assertIn('dÉmo locale'.casefold(),rendered)
    def test_domains_generate_different_products(self):
        music=generator.build_files(generator.build_specification('application musicale'),'b'*32,'1.0.0')
        requests=generator.build_files(generator.build_specification('gestion des demandes clients'),'c'*32,'1.0.0')
        for name in ('prototype.html','prototype.js','style.css','product.py'):
            self.assertNotEqual(music[name],requests[name])
    def test_semantic_version_rules(self):
        self.assertEqual(generator.bump_version('1.0.0','patch'),'1.0.1')
        self.assertEqual(generator.bump_version('1.0.1','minor'),'1.1.0')
        self.assertEqual(generator.bump_version('1.7.4','major'),'2.0.0')

class DecisionTests(unittest.TestCase):
    def base(self,**overrides):
        return dict(dict(source='real',technical_pass=True,tests=3,visitors=500,conversions=0,repeatable_runs=0,minutes=1,budget_minutes=15),**overrides)
    def test_technical_failure(self): self.assertEqual(decide(self.base(technical_pass=False))['choice'],'MODIFIE')
    def test_synthetic_cannot_scale(self): self.assertEqual(decide(self.base(source='synthetic',conversions=100,repeatable_runs=3,unit_economics_positive=True))['choice'],'CONTINUE')
    def test_synthetic_cannot_abandon(self): self.assertEqual(decide(self.base(source='synthetic',distinct_hypotheses=3,negative_feedback_confirmed=True))['choice'],'CONTINUE')
    def test_low_distribution(self): self.assertEqual(decide(self.base(visitors=10,tests=30))['choice'],'CONTINUE')
    def test_too_few_tests(self): self.assertEqual(decide(self.base(tests=1,visitors=1000))['choice'],'CONTINUE')
    def test_pivot(self): self.assertEqual(decide(self.base(problem_confirmed=True))['choice'],'PIVOTE')
    def test_abandon_with_evidence(self): self.assertEqual(decide(self.base(distinct_hypotheses=3,negative_feedback_confirmed=True))['choice'],'ABANDONNE')
    def test_no_blind_abandon(self): self.assertEqual(decide(self.base())['choice'],'MODIFIE')
    def test_scale_with_repeatability(self): self.assertEqual(decide(self.base(conversions=30,repeatable_runs=3,unit_economics_positive=True))['choice'],'SCALE')
    def test_no_blind_scale(self): self.assertEqual(decide(self.base(conversions=30,repeatable_runs=1,unit_economics_positive=True))['choice'],'MODIFIE')
    def test_budget_stops_persistence(self): self.assertEqual(decide(self.base(minutes=16))['choice'],'MODIFIE')
    def test_external_always_blocked(self): self.assertFalse(decide(self.base(conversions=30,repeatable_runs=3,unit_economics_positive=True))['external_execution'])
    def test_bad_numbers(self):
        for v in [-1,float('nan'),float('inf'),True,'5']:
            with self.assertRaises(ValueError): decide(self.base(visitors=v))
        with self.assertRaises(ValueError): decide(self.base(conversions=501))

class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); os.environ['ATLAS_CONTROL_STATE']=self.tmp.name
        spec=importlib.util.spec_from_file_location('control_test',pathlib.Path(__file__).with_name('control.py'))
        self.c=importlib.util.module_from_spec(spec); spec.loader.exec_module(self.c); self.c.init()
    def tearDown(self): self.tmp.cleanup()
    def test_recovery(self):
        p=self.c.start({'idea':'A fake request tracker'})
        self.c.save(p['id'],'building'); self.c.init()
        self.assertEqual(self.c.project(p['id'])['status'],'paused')
        self.assertEqual(len(self.c.snapshot()['tasks']),8)
    def test_budget(self):
        for _ in range(3): self.c.start({'idea':'A fake request tracker'})
        with self.assertRaises(ValueError): self.c.start({'idea':'A fake request tracker'})
    def test_agent_cannot_approve(self):
        with self.assertRaises(ValueError): self.c.action('/api/approvals',{'id':'x','decision':'approve'},True)
    def test_memories_survive(self):
        p=self.c.start({'idea':'A fake request tracker'})
        import time
        self.c.learn(p['id'],time.monotonic(),True,[],[]); self.c.init()
        self.assertEqual(len(self.c.memories()),1)
        self.assertEqual(self.c.memories()[0]['decision']['choice'],'CONTINUE')
    def test_approval_never_executes(self):
        with self.c.conn() as c: c.execute('INSERT INTO approvals VALUES(?,?,?,?,?,?,?)',('a',None,'publish','test','pending',self.c.now(),None))
        result=self.c.action('/api/approvals',{'id':'a','decision':'approve'})
        self.assertEqual(result['status'],'approved_blocked');self.assertFalse(result['external_execution'])
        with self.assertRaises(ValueError):self.c.action('/api/approvals',{'id':'a','decision':'approve'})
    def test_n8n_only_one_pending(self):
        job=self.c.action('/api/n8n/test',{})
        self.assertEqual(job['status'],'queued')
        with self.assertRaises(ValueError):self.c.action('/api/n8n/test',{})
    def test_n8n_daily_limit(self):
        for _ in range(3):
            job=self.c.action('/api/n8n/test',{})
            with self.c.conn() as c:c.execute("UPDATE n8n_jobs SET status='success' WHERE id=?",(job['id'],))
        with self.assertRaises(ValueError):self.c.action('/api/n8n/test',{})
    def test_ledger_is_persistent_and_empty_by_default(self):
        self.assertEqual(self.c.finance(),[])
        p=self.c.start({'idea':'A fake request tracker'})
        with self.c.conn() as c:c.execute('INSERT INTO ledger VALUES(?,?,?,?,?,?,?,?,?)',('l',p['id'],1250,'expense','hosting',self.c.now(),'coût vérifié','facture locale','verified'))
        self.c.init()
        self.assertEqual(self.c.finance()[0]['amount_cents'],1250)
        self.assertEqual(self.c.snapshot()['data_contract']['ledger_source'],'SQLite ledger table')
    def test_synthetic_projects_are_identifiable(self):
        p=self.c.start({'idea':'A fake request tracker'})
        self.assertTrue(p['data']['synthetic'])
    def test_improvement_reuses_project_and_increments_version(self):
        p=self.c.start({'idea':'Créer une application musicale locale premium'})
        improved=self.c.start({'idea':"Améliore l'application musicale avec une nouvelle fonctionnalité de mix"})
        self.assertEqual(p['id'],improved['id'])
        self.assertEqual(improved['data']['version'],'1.1.0')
        self.assertEqual(len(self.c.snapshot()['projects']),1)
    def test_daily_new_project_limit_does_not_block_version(self):
        projects=[self.c.start({'idea':f'Créer outil local générique numéro {i}'}) for i in range(3)]
        updated=self.c.start({'project_id':projects[0]['id'],'idea':'Ajoute une nouvelle fonctionnalité à cet outil local'})
        self.assertEqual(updated['id'],projects[0]['id'])
        self.assertEqual(updated['data']['version'],'1.1.0')

if __name__=='__main__': unittest.main(verbosity=2)
