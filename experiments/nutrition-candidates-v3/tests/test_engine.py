import unittest, tempfile, sqlite3, csv
from pathlib import Path
from contextlib import closing
from src.common import write_csv
from scripts.prepare_database import build_database
from nutrition_engine.ingredient_matcher import IngredientMatcher
from nutrition_engine.calculator import calculate
from nutrition_engine.portion_conversion import convert_measure

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.sources=self.root/'sources';self.sources.mkdir()
        rows=[{'source':'TEST','release':'1','fdc_id':'1','name_en':'Rice, white, long-grain, cooked','kcal_100g':130,'protein_g_100g':2.7,'carbs_g_100g':28,'fat_g_100g':0.3},
              {'source':'TEST','release':'1','fdc_id':'2','name_en':'Rice, white, long-grain, raw','kcal_100g':365,'protein_g_100g':7,'carbs_g_100g':80,'fat_g_100g':1},
              {'source':'TEST','release':'1','fdc_id':'3','name_en':'Chicken breast, cooked, roasted','kcal_100g':165,'protein_g_100g':31,'carbs_g_100g':0,'fat_g_100g':3.6},
              {'source':'TEST','release':'1','fdc_id':'4','name_en':'Mystery food','kcal_100g':'','protein_g_100g':0,'carbs_g_100g':0,'fat_g_100g':0}]
        write_csv(self.sources/'nouriva_usda_food_nutrition.csv',list(rows[0]),rows)
        self.db=self.root/'foods.sqlite';build_database(self.sources,self.db)
        self.m=IngredientMatcher(self.db);self.addCleanup(self.m.close)
    def item(self,name,state='cooked',grams=150):
        return {'name':name,'state':state,'grams':grams,'evidence':'visible','confidence':0.8,'uncertainty':'estimated from image'}
    def test_known_arithmetic_and_provenance(self):
        r=calculate([self.item('Rice, white, long-grain, cooked'),self.item('Chicken breast, cooked, roasted','roasted',100)],self.m)
        self.assertEqual(r['status'],'SUCCESS');self.assertEqual(r['nutrients']['kcal'],360)
        self.assertAlmostEqual(r['nutrients']['protein_g'],35.05);self.assertAlmostEqual(r['nutrients']['carbs_g'],42)
        self.assertEqual(r['matched'][0]['source_id'],'TEST:1');self.assertEqual(r['matched'][0]['basis_g'],100)
    def test_wrong_state_rejected(self):
        r=self.m.match('Rice, white, long-grain, raw','cooked')
        self.assertNotEqual(r['status'],'MATCHED')
    def test_no_substitute_and_no_complete_partial_total(self):
        r=calculate([self.item('Rice, white, long-grain, cooked'),self.item('unknown special sauce')],self.m)
        self.assertEqual(r['status'],'REVIEW_REQUIRED');self.assertIsNone(r['nutrients'])
        self.assertEqual(r['match_coverage'],0.5);self.assertEqual(r['partial_nutrients']['kcal'],195)
    def test_identical_description_uses_declared_source_priority(self):
        from src.common import read_csv
        f=self.sources/'nouriva_usda_food_nutrition.csv';rows=read_csv(f)
        rows[0]['source']='SR_Legacy';rows.append({**rows[0],'source':'Foundation','fdc_id':'5','kcal_100g':132})
        write_csv(f,list(rows[0]),rows);db=self.root/'priority.sqlite';build_database(self.sources,db)
        m=IngredientMatcher(db);self.addCleanup(m.close)
        r=m.match('Rice, white, long-grain, cooked','cooked')
        self.assertEqual(r['status'],'MATCHED');self.assertEqual(r['food']['source_id'],'SR_Legacy:1')
        self.assertEqual(r['reason'],'exact_identity_declared_source_priority')
    def test_all_unmatched(self):
        r=calculate([self.item('unheard of mineral')],self.m)
        self.assertEqual(r['status'],'UNMATCHED');self.assertIsNone(r['nutrients'])
    def test_missing_is_not_zero(self):
        r=calculate([self.item('Mystery food','unspecified')],self.m)
        self.assertEqual(r['status'],'REVIEW_REQUIRED');self.assertIsNone(r['partial_nutrients']['kcal'])
        self.assertEqual(r['partial_nutrients']['protein_g'],0)
    def test_invalid_numeric_weight(self):
        for g in [float('nan'),float('inf'),-1,True]:
            with self.assertRaises(ValueError):calculate([self.item('Rice, white, long-grain, cooked',grams=g)],self.m)
    def test_ambiguous_measure_requires_review(self):
        with closing(sqlite3.connect(self.db)) as c, c:
            c.executemany('INSERT INTO measures VALUES (?,?,?,?,?,?,?,?,?)', [('a','F1','rice','cup',1,100,None,'AUSNUT:2023','1'),('b','F1','rice','cup',1,200,None,'AUSNUT:2023','2')])
        with self.assertRaises(ValueError):convert_measure(self.db,'F1','cup',1)
        r=convert_measure(self.db,'F1','cup',2,measure_id='a');self.assertEqual(r['grams'],200)
    def test_exact_duplicate_id_deduplicated(self):
        f=self.sources/'nouriva_usda_food_nutrition.csv'
        from src.common import read_csv
        rows=read_csv(f);write_csv(f,list(rows[0]),rows+[rows[0]])
        audit=build_database(self.sources,self.root/'dedup.sqlite');self.assertEqual(audit['duplicate_source_ids_collapsed'],1)
    def test_negative_source_nutrient_quarantined_not_zero(self):
        from src.common import read_csv
        f=self.sources/'nouriva_usda_food_nutrition.csv';rows=read_csv(f);rows[0]['carbs_g_100g']=-0.47505
        write_csv(f,list(rows[0]),rows)
        db=self.root/'negative.sqlite';audit=build_database(self.sources,db)
        with closing(sqlite3.connect(db)) as c:self.assertIsNone(c.execute('SELECT carbs_g_100g FROM foods WHERE source_food_id="1"').fetchone()[0])
        self.assertEqual(audit['quarantined_values'][0]['original_value'],-0.47505)
    def test_conflicting_duplicate_id_rejected(self):
        from src.common import read_csv
        f=self.sources/'nouriva_usda_food_nutrition.csv';rows=read_csv(f);bad={**rows[0],'kcal_100g':999}
        write_csv(f,list(rows[0]),rows+[bad])
        with self.assertRaises(ValueError):build_database(self.sources,self.root/'bad.sqlite')
