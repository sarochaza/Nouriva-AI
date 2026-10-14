import unittest,tempfile,json
from pathlib import Path
from src.dataset import load_dataset,prepare_dataset
from src.common import save_json,load_json

class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name)
        (self.root/'test').mkdir()
        self.row={'file_name':'test/dish_0001.png','id':'dish_0001','split':'test','ingredients':[{'id':'ingr_1','name':'fixture rice','grams':100,'calories':130,'fat':0.3,'carb':28,'protein':2.7}], 'total_calories':130,'total_mass':100,'total_fat':0.3,'total_carb':28,'total_protein':2.7}
        from fixtures.make_fixture import write_png
        write_png(self.root/'test/dish_0001.png',1)
        self.metadata=self.root/'metadata.jsonl'
    def write(self,rows):self.metadata.write_text('\n'.join(json.dumps(x) for x in rows),encoding='utf-8')
    def test_fields_and_image_id_join(self):
        self.write([self.row]);rows,audit=load_dataset(self.root)
        self.assertEqual(rows[0]['kcal'],130);self.assertEqual(rows[0]['carbs_g'],28);self.assertEqual(audit['valid_records'],1)
    def test_unknown_schema_not_guessed(self):
        self.write([{'id':'a','image':'x','energy':123}]);rows,audit=load_dataset(self.root)
        self.assertEqual(rows,[]);self.assertEqual(audit['invalid_records'],1)
    def test_duplicate_ids_not_silent(self):
        self.write([self.row,self.row]);rows,audit=load_dataset(self.root)
        self.assertEqual(audit['duplicate_ids'],1);self.assertEqual(len(rows),1)
    def test_path_traversal_rejected(self):
        self.write([{**self.row,'file_name':'../secrets.png'}]);rows,audit=load_dataset(self.root)
        self.assertEqual(len(rows),0)
    def test_id_filename_mismatch_rejected(self):
        self.write([{**self.row,'id':'wrong_id'}]);rows,audit=load_dataset(self.root)
        self.assertEqual(len(rows),0)
    def test_missing_nutrient_not_imputed(self):
        self.write([{**self.row,'total_protein':None}]);rows,audit=load_dataset(self.root)
        self.assertEqual(len(rows),0)
    def test_inference_manifest_contains_no_labels(self):
        self.write([self.row]);out=self.root/'prepared';prepare_dataset(self.root,out,n=1,seed=12)
        manifest=load_json(out/'manifest.json');s=json.dumps(manifest)
        for forbidden in ['ingredients','total_calories','protein','kcal']:self.assertNotIn(forbidden,s)
        self.assertTrue((out/'ground_truth.json').exists())
