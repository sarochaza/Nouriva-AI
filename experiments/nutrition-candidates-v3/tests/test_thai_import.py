import tempfile,unittest,sqlite3
from pathlib import Path
from src.common import write_csv
import tests.test_engine
from scripts.import_reviewed_thai import import_reviewed_thai
from nutrition_engine.ingredient_matcher import IngredientMatcher
class ThaiImportTests(unittest.TestCase):
    setUp=tests.test_engine.EngineTests.setUp
    def row(self):return {'local_food_id':'T001','name_en':'Verified test food','name_th':'อาหารทดสอบ','state':'cooked','basis_g':100,'kcal_100g':100,'protein_g_100g':1,'carbs_g_100g':20,'fat_g_100g':2,'source_page':12,'source_sha256':'a'*64,'review_status':'VERIFIED','verified_by':'human reviewer','verified_on':'2026-10-13'}
    def test_unreviewed_rows_rejected(self):
        row=self.row();row['review_status']='PENDING';p=self.root/'thai.csv';write_csv(p,list(row),[row])
        with self.assertRaises(ValueError):import_reviewed_thai(self.db,p)
    def test_verified_thai_name_searchable(self):
        row=self.row();p=self.root/'thai.csv';write_csv(p,list(row),[row]);import_reviewed_thai(self.db,p)
        m=IngredientMatcher(self.db);self.addCleanup(m.close)
        r=m.match('อาหารทดสอบ','cooked');self.assertEqual(r['status'],'MATCHED');self.assertEqual(r['food']['source_id'],'THAI_FCT:2018')
