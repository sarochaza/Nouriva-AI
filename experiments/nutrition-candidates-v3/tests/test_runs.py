import unittest,tempfile,json,os,urllib.error
from pathlib import Path
from unittest.mock import patch
from src.common import ROOT,save_json,load_json
from fixtures.make_fixture import make_fixture
from src.dataset import prepare_dataset
from scripts.run_experiment import run_experiment,load_config
from evaluation.evaluate import evaluate_run
from evaluation.metrics import numeric_metrics,ingredient_scores
from src.ai import GroqClient,APIError,PredictionError
from tests.test_methods import prediction

class MetricTests(unittest.TestCase):
    def test_known_metrics_and_zero_mape_exclusion(self):
        r=numeric_metrics([0,10,20],[2,12,16])
        self.assertAlmostEqual(r['MAE'],8/3);self.assertAlmostEqual(r['RMSE'],(24/3)**.5)
        self.assertEqual(r['MAPE_percent'],20);self.assertEqual(r['mape_n'],2)
    def test_empty_not_zero(self):
        self.assertIsNone(numeric_metrics([],[])['MAE'])
    def test_ingredient_weights_only_on_matched_identity(self):
        r=ingredient_scores([{'name':'carrots','grams':100},{'name':'rice','grams':200}], [{'name':'carrot, raw','state':'raw','grams':120}])
        self.assertEqual(r['precision'],1);self.assertEqual(r['recall'],0.5);self.assertEqual(r['weight_MAE_g'],20)

class RunTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name)
        dataset=make_fixture(self.root/'dataset');self.prepared=self.root/'prepared'
        prepare_dataset(dataset,self.prepared,5,1,mock=True)
        self.cfg=load_config();self.db=ROOT/'nutrition_database/ingredients.sqlite'
        self.run=self.root/'mock_run'
    def test_45_mock_evaluations_and_105_calls(self):
        run_experiment(self.prepared,self.cfg,self.run,self.db,mock=True)
        rows,summaries=evaluate_run(self.run,self.prepared/'ground_truth.json')
        self.assertEqual(len(rows),45);self.assertEqual(sum(r['http_attempts'] for r in rows),105)
        self.assertEqual({r['status'] for r in rows},{'SUCCESS'});self.assertEqual(load_json(self.run/'frozen.json')['mode'],'MOCK')
    def test_resume_is_idempotent(self):
        run_experiment(self.prepared,self.cfg,self.run,self.db,mock=True,rounds=[1],methods=['single'])
        p=self.run/'records/round_1/mock_0000_single.json';first=p.read_bytes()
        run_experiment(self.prepared,self.cfg,self.run,self.db,mock=True,rounds=[1],methods=['single'])
        self.assertEqual(p.read_bytes(),first)
    def test_freeze_rejects_configuration_change(self):
        run_experiment(self.prepared,self.cfg,self.run,self.db,mock=True,rounds=[1],methods=['single'])
        with self.assertRaises(ValueError):run_experiment(self.prepared,{**self.cfg,'temperature':0.9},self.run,self.db,mock=True)
    def test_not_run_and_failed_have_no_error_zero(self):
        run_experiment(self.prepared,self.cfg,self.run,self.db,mock=True,rounds=[1],methods=['single'])
        p=self.run/'records/round_1/mock_0000_single.json';r=load_json(p);r['status']='FAILED';r['error_type']='API_ERROR';save_json(p,r)
        rows,_=evaluate_run(self.run,self.prepared/'ground_truth.json')
        missing=[r for r in rows if r['status'] in ['NOT_RUN','FAILED']]
        self.assertEqual(len(missing),41);self.assertTrue(all(r['kcal_abs_error'] is None for r in missing))
    def test_no_ground_truth_needed_for_inference(self):
        (self.prepared/'ground_truth.json').unlink()
        run_experiment(self.prepared,self.cfg,self.run,self.db,mock=True,rounds=[1],methods=['single'])
        self.assertTrue((self.run/'records/round_1/mock_0000_single.json').exists())
    def test_mock_real_separation(self):
        with self.assertRaises(ValueError):run_experiment(self.prepared,self.cfg,self.run,self.db,mock=False)

class APITests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.img=Path(self.t.name)/'dish.png'
        from fixtures.make_fixture import write_png
        write_png(self.img,1)
    def test_payload_only_image_and_prompt_no_filename_or_labels(self):
        seen=[]
        def transport(payload,headers,timeout,url):
            seen.append(payload);return {'choices':[{'message':{'content':json.dumps(prediction())}}], 'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}}
        c=GroqClient({},transport=transport)
        with patch.dict(os.environ,{'GROQ_API_KEY':'SECRET_TEST_VALUE'}):c.chat('vision',self.img,'single')
        s=json.dumps(seen);self.assertNotIn('dish.png',s);self.assertNotIn('SECRET_TEST_VALUE',json.dumps(c.events));self.assertNotIn('total_calories',s)
        self.assertEqual(seen[0]['response_format']['type'],'json_object')
    def test_retry_retains_all_attempts(self):
        attempts=[];wait=[]
        def transport(*args):
            attempts.append(1)
            if len(attempts)==1:
                error=urllib.error.HTTPError('url',429,'limit',{'Retry-After':'2'},None)
                self.addCleanup(error.close)
                raise error
            return {'choices':[{'message':{'content':json.dumps(prediction())}}]}
        c=GroqClient({'max_retries':2},transport=transport,sleep=wait.append)
        with patch.dict(os.environ,{'GROQ_API_KEY':'SECRET'}):c.chat('vision',self.img,'single')
        self.assertEqual(len(c.events),2);self.assertEqual(wait,[2]);self.assertEqual(c.events[0]['http_status'],429)
    def test_failed_prediction_keeps_billed_tokens(self):
        def transport(*args):return {'choices':[{'message':{'content':'not JSON'}}],'usage':{'prompt_tokens':10,'completion_tokens':2,'total_tokens':12}}
        c=GroqClient({},transport=transport)
        with patch.dict(os.environ,{'GROQ_API_KEY':'SECRET'}):
            with self.assertRaises(PredictionError):c.chat('vision',self.img,'single')
        self.assertEqual(c.events[0]['total_tokens'],12);self.assertEqual(c.events[0]['status'],'PREDICTION_ERROR')
