import unittest,copy
from src.ai import validate_prediction,GroqClient,APIError,PredictionError
from methods.single_llm import predict as single
from methods.multi_agent import predict as multi
from methods.ensemble import predict as ensemble,merge_predictions

def prediction(name='carrots',state='raw',grams=100):
    return {'dish_name':'test fixture','ingredients':[{'name':name,'name_th':'','state':state,'grams':grams,'evidence':'visible','confidence':0.8,'uncertainty':'estimated portion'}]}
class Recorder:
    def __init__(self):self.calls=[];self.events=[]
    def chat(self,model,image,stage,prior=None,**kwargs):
        self.calls.append((model,image,stage,copy.deepcopy(prior)));self.events.append({'model':model,'stage':stage,'status':'SUCCESS','total_tokens':20})
        return prediction(grams=100+len(self.calls))
class MethodTests(unittest.TestCase):
    def setUp(self):self.cfg={'single_model':'vision','multi_models':['vision']*3,'ensemble_models':['vision']*3,'ensemble_mode':'self_consistency','temperature':0.7}
    def test_single_one_call(self):
        c=Recorder();single('img',self.cfg,c);self.assertEqual(len(c.calls),1)
    def test_multi_actual_dependencies(self):
        c=Recorder();p=multi('img',self.cfg,c);self.assertEqual(len(c.calls),3)
        self.assertIsNone(c.calls[0][3]);self.assertEqual(c.calls[1][3]['vision']['ingredients'][0]['grams'],101)
        self.assertEqual(c.calls[2][3]['portion']['ingredients'][0]['grams'],102)
    def test_ensemble_independent(self):
        c=Recorder();p=ensemble('img',self.cfg,c)
        self.assertTrue(all(x[3] is None for x in c.calls));self.assertEqual(p['ingredients'][0]['grams'],102)
        self.assertEqual(p['ensemble_type'],'single_model_self_consistency')
    def test_multi_model_requires_distinct_ids(self):
        with self.assertRaises(ValueError):ensemble('img',{**self.cfg,'ensemble_mode':'multi_model'},Recorder())
    def test_majority_and_state_specific_median(self):
        p=[prediction('carrot','raw',100),prediction('carrots','raw',140),prediction('carrots','cooked',200)]
        r=merge_predictions(p);self.assertEqual(len(r['ingredients']),1);self.assertEqual(r['ingredients'][0]['grams'],120)
        self.assertEqual(len(r['merge_trace']),2)
    def test_duplicate_within_member_does_not_create_votes(self):
        p=prediction();p['ingredients']*=2
        with self.assertRaises(PredictionError):validate_prediction(p)
    def test_invalid_schema(self):
        for v in [prediction(grams=float('nan')),prediction(grams=-1),{'ingredients':[]},prediction(state='magic')]:
            with self.assertRaises(PredictionError):validate_prediction(v)
