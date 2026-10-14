import unittest,tempfile
from pathlib import Path
from src.common import ROOT,load_json
from nutrition_engine.normalization import infer_state
from methods.ensemble import merge_predictions
from src.ai import PredictionError
from evaluation.evaluate import summarize
from fixtures.make_fixture import make_fixture
from src.dataset import prepare_dataset
from scripts.run_experiment import run_experiment,load_config
from tests.test_methods import prediction

class ReviewRegressions(unittest.TestCase):
    def test_cooked_dry_heat_is_not_dried(self):
        self.assertEqual(infer_state('Fish, salmon, Atlantic, farmed, cooked, dry heat')[0],'cooked')
        self.assertEqual(infer_state('Apples, dried, sulfured, uncooked')[0],'dried')
        self.assertEqual(infer_state('Oil, industrial, canola for salads, woks and light frying')[0],'unspecified')
    def test_merged_ensemble_must_obey_total_mass_limit(self):
        def p(a,b):
            x=prediction(a,grams=3000);x['ingredients']+=prediction(b,grams=3000)['ingredients'];return x
        with self.assertRaises(PredictionError):merge_predictions([p('A','B'),p('A','C'),p('B','C')])
    def test_common_success_ingredient_denominator_is_filtered(self):
        def row(d,precision):
            r={'method':'single','round':1,'dish_id':d,'status':'SUCCESS','ingredient_precision':precision,'ingredient_recall':precision,'ingredient_F1':precision,'ingredient_weight_MAE_g':20,
               'match_coverage':1,'complete_nutrient_coverage':1,'mass_match_coverage':1,'latency_seconds':1,'http_attempts':1,'model_responses':1,'known_tokens':1,'total_tokens':1,'known_cost_usd':0,'cost_usd':0}
            for k in ['kcal','protein_g','carbs_g','fat_g']:r[k+'_truth']=1;r[k+'_prediction']=1
            return r
        s=summarize([row('common',1),row('method_only',0)],'single',1,'common_success',{(1,'common')})
        self.assertEqual(s['ingredient_precision_mean'],1);self.assertEqual(s['ingredient_precision_n'],1)
        self.assertEqual(s['http_attempts_total'],2)
    def test_interrupted_trial_retains_billed_events(self):
        class Interrupted:
            def __init__(self):self.events=[]
            def chat(self,*args,**kw):
                if self.events:raise KeyboardInterrupt()
                self.events.append({'model':'mock','stage':'vision','status':'SUCCESS','total_tokens':100,'cost_usd':0})
                return prediction('Carrots, raw')
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);dataset=make_fixture(root/'dataset');prepared=root/'prepared';prepare_dataset(dataset,prepared,5,1,mock=True)
            with self.assertRaises(KeyboardInterrupt):run_experiment(prepared,load_config(),root/'run',ROOT/'nutrition_database/ingredients.sqlite',mock=True,rounds=[1],methods=['multi'],client_factory=Interrupted)
            p=root/'run/records/round_1/mock_0000_multi.json'
            self.assertTrue(p.exists());record=load_json(p)
            self.assertEqual(record['status'],'FAILED');self.assertEqual(record['error_type'],'INTERRUPTED')
            self.assertEqual(record['call_metadata'][0]['total_tokens'],100)
