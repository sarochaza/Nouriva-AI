"""Optional future Thai FCT integration. No automatic OCR or unreviewed values."""
import argparse,json,re,sqlite3
from pathlib import Path
from contextlib import closing
from src.common import ROOT,read_csv,sha256
from scripts.prepare_database import numeric,CORE
from nutrition_engine.normalization import STATES,normalize

def import_reviewed_thai(db_path,csv_path,source_pdf=None):
    rows=read_csv(csv_path)
    if not rows:raise ValueError('No verified Thai rows provided. The shipped template is intentionally empty.')
    checked=[]
    for r in rows:
        if r.get('review_status')!='VERIFIED' or not r.get('verified_by') or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',r.get('verified_on','')):raise ValueError('Every Thai row requires a human verification record')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}',r.get('local_food_id','')):raise ValueError('Invalid Thai local food ID')
        if r.get('state') not in STATES or not r.get('name_en') or not r.get('name_th'):raise ValueError('Thai/English name and explicit state required')
        if float(r.get('basis_g',0))!=100 or int(r.get('source_page',0))<1:raise ValueError('Verified source page and 100g basis required')
        if not re.fullmatch(r'[a-f0-9]{64}',r.get('source_sha256','')):raise ValueError('Source PDF SHA256 required')
        if source_pdf and r['source_sha256']!=sha256(source_pdf):raise ValueError('Thai source file hash mismatch')
        vals=[numeric(r.get(k),k) for k in CORE]
        provenance=json.dumps({'source':'Food Composition Table of Thai Foods 2018','source_page':int(r['source_page']),
                               'source_sha256':r['source_sha256'],'verified_by':r['verified_by'],'verified_on':r['verified_on'],
                               'import_csv_sha256':sha256(csv_path)},ensure_ascii=False)
        fid='THAI_FCT:2018:'+r['local_food_id']
        checked.append((fid,'THAI_FCT:2018',r['local_food_id'],r['name_en'],r['name_th'],normalize(r['name_en']),r['state'],
                        'human_verified_source_page',*vals,'reported_source_kcal',provenance,100))
    with closing(sqlite3.connect(db_path)) as c, c:
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('INSERT OR IGNORE INTO sources VALUES (?,?,?,?,?)',('THAI_FCT:2018','Food Composition Table of Thai Foods','2018','Bureau of Nutrition, Department of Health, Ministry of Public Health, Thailand. September 2018.',100))
        c.executemany('INSERT INTO foods VALUES ('+','.join('?'*15)+')',checked)
    return len(checked)

def main():
    p=argparse.ArgumentParser();p.add_argument('--csv',type=Path,required=True);p.add_argument('--database',type=Path,default=ROOT/'nutrition_database/ingredients.sqlite');p.add_argument('--source-pdf',type=Path);a=p.parse_args()
    print('Imported verified rows:',import_reviewed_thai(a.database,a.csv,a.source_pdf))
    print('Database bytes changed. Start a new experiment run ID.')
if __name__=='__main__':main()
