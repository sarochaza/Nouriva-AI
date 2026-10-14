import tempfile,unittest,zipfile
from pathlib import Path
from src.common import write_csv
from scripts.audit_sources import audit_sources
class SourceAuditTests(unittest.TestCase):
    def test_fndds_legacy_nutrient_numbers_are_joined_explicitly(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);row={'source':'FNDDS','release':'2021-2023','fdc_id':'1','name_en':'Carrots, raw','kcal_100g':41,'energy_method':'Energy_1008','protein_g_100g':0.93,'fat_g_100g':0.24,'carbs_g_100g':9.58}
            write_csv(p/'nouriva_usda_food_nutrition.csv',list(row),[row])
            with zipfile.ZipFile(p/'FoodData_Central_survey_test.zip','w') as z:
                z.writestr('x/food.csv','fdc_id,data_type,description\n1,survey_fndds_food,"Carrots, raw"\n')
                z.writestr('x/nutrient.csv','id,name,unit_name,nutrient_nbr\n1008,Energy,KCAL,208\n1003,Protein,G,203\n1004,Fat,G,204\n1005,Carbohydrate,G,205\n')
                z.writestr('x/food_nutrient.csv','fdc_id,nutrient_id,amount\n1,208,41\n1,203,0.93\n1,204,0.24\n1,205,9.58\n')
            a=audit_sources(p);self.assertEqual(a['mismatches'],[]);self.assertEqual(a['original_archives'][0]['nutrient_id_domain'],'legacy_nutrient_number')
    def test_raw_reference_reconciles_and_mismatch_detected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            row={'source':'SR_Legacy','release':'2018-04','fdc_id':'1','name_en':'Carrots, raw','kcal_100g':41,'energy_method':'Energy_1008','protein_g_100g':0.93,'fat_g_100g':0.24,'carbs_g_100g':9.58}
            write_csv(p/'nouriva_usda_food_nutrition.csv',list(row),[row])
            with zipfile.ZipFile(p/'FoodData_Central_sr_legacy_test.zip','w') as z:
                z.writestr('x/food.csv','fdc_id,data_type,description\n1,sr_legacy_food,"Carrots, raw"\n')
                z.writestr('x/nutrient.csv','id,name,unit_name\n1008,Energy,KCAL\n1003,Protein,G\n1004,Fat,G\n1005,Carbohydrate,G\n')
                z.writestr('x/food_nutrient.csv','fdc_id,nutrient_id,amount\n1,1008,41\n1,1003,0.93\n1,1004,0.24\n1,1005,9.58\n')
            a=audit_sources(p);self.assertEqual(a['raw_nutrient_value_checks'],4);self.assertEqual(a['mismatches'],[])
            row['kcal_100g']=999;write_csv(p/'nouriva_usda_food_nutrition.csv',list(row),[row])
            a=audit_sources(p);self.assertEqual(len(a['mismatches']),1)
