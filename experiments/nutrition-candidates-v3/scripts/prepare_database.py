"""Import the user's audited reference files. No network requests or imputation."""
import argparse
import collections
import csv
import json
import math
import sqlite3
from pathlib import Path
from src.common import ROOT, read_csv, save_json, sha256, write_csv
from nutrition_engine.normalization import normalize, infer_state

CORE = ('kcal_100g','protein_g_100g','carbs_g_100g','fat_g_100g')
SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE sources(source_id TEXT PRIMARY KEY, name TEXT, release TEXT, attribution TEXT, basis_g REAL);
CREATE TABLE foods(food_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources,
 source_food_id TEXT NOT NULL, name_en TEXT NOT NULL, name_th TEXT, normalized_name TEXT NOT NULL,
 state TEXT NOT NULL, state_evidence TEXT, kcal_100g REAL, protein_g_100g REAL,
 carbs_g_100g REAL, fat_g_100g REAL, energy_method TEXT, provenance TEXT, basis_g REAL NOT NULL CHECK(basis_g=100),
 UNIQUE(source_id,source_food_id));
CREATE INDEX names ON foods(normalized_name,state);
CREATE TABLE aliases(alias TEXT NOT NULL, state TEXT NOT NULL, food_id TEXT NOT NULL REFERENCES foods,
 rationale TEXT NOT NULL, reviewed_by TEXT NOT NULL, PRIMARY KEY(alias,state,food_id));
CREATE TABLE measures(measure_id TEXT PRIMARY KEY, public_food_key TEXT NOT NULL, food_name TEXT,
 descriptor TEXT, quantity REAL, grams REAL, volume_ml REAL, source_id TEXT, source_row TEXT);
CREATE INDEX measure_lookup ON measures(public_food_key,descriptor);
CREATE TABLE measure_links(food_id TEXT REFERENCES foods,public_food_key TEXT,reviewed_by TEXT,reason TEXT,
 PRIMARY KEY(food_id,public_food_key));
CREATE TABLE recipe_components(recipe_id TEXT, recipe_name TEXT, sr_code TEXT, ingredient_name TEXT,
 amount REAL, unit TEXT, gram_weight REAL, seq_num TEXT, ingredient_food_id TEXT, link_status TEXT,
 source_id TEXT, source_row TEXT);
'''

def numeric(value, field):
    if value is None or str(value).strip() == '': return None
    if isinstance(value,bool): raise ValueError('Boolean in numeric field: '+field)
    x = float(value)
    if not math.isfinite(x) or x < 0: raise ValueError('Invalid numeric field: '+field)
    return x

def build_database(sources, output, aliases=None, ndb_crosswalk=None):
    sources, output = Path(sources), Path(output)
    rows = read_csv(sources/'nouriva_usda_food_nutrition.csv')
    if not rows: raise ValueError('Empty reference nutrition file')
    required = {'source','release','fdc_id','name_en',*CORE}
    if not required <= set(rows[0]): raise ValueError('Missing reference columns: '+str(required-set(rows[0])))
    output.parent.mkdir(parents=True,exist_ok=True)
    tmp = output.with_suffix('.building.sqlite')
    if tmp.exists(): tmp.unlink()
    con = sqlite3.connect(tmp)
    seen = {}; duplicates = 0; missing = collections.Counter(); states=collections.Counter(); source_counts=collections.Counter()
    food_hash=sha256(sources/'nouriva_usda_food_nutrition.csv'); quarantined=[]
    original_types = {k:collections.Counter() for k in required}
    try:
        con.executescript(SCHEMA)
        for index,r in enumerate(rows,2):
            for k in original_types: original_types[k][type(r.get(k)).__name__] += 1
            sid = r['source']+':'+r['release']; fid=sid+':'+r['fdc_id']
            vals=[]; rejected={}
            for k in CORE:
                try:v=numeric(r.get(k),k)
                except ValueError:
                    original=float(r[k])
                    if not math.isfinite(original):raise
                    quarantined.append({'food_id':fid,'field':k,'original_value':original,'reason':'negative_source_value','row':index})
                    rejected[k]=original;v=None
                vals.append(v)
            state, evidence = infer_state(r['name_en'])
            record=(fid,sid,r['fdc_id'],r['name_en'],None,normalize(r['name_en']),state,evidence,
                    *vals,r.get('energy_method'),json.dumps({'file':'nouriva_usda_food_nutrition.csv','row':index,
                    'record_origin':r.get('record_origin'),'file_sha256':food_hash,'quarantined_original_values':rejected},ensure_ascii=False),100)
            # provenance row differs for duplicates. Compare substantive columns.
            substantive=record[:13]+record[14:]
            if fid in seen:
                if seen[fid] != substantive: raise ValueError('Conflicting duplicate source ID: '+fid)
                duplicates += 1; continue
            seen[fid]=substantive
            con.execute('INSERT OR IGNORE INTO sources VALUES (?,?,?,?,?)',(sid,r['source'],r['release'],'U.S. Department of Agriculture, Agricultural Research Service. FoodData Central.',100))
            con.execute('INSERT INTO foods VALUES ('+','.join('?'*15)+')',record)
            states[state]+=1;source_counts[sid]+=1
            for k,v in zip(CORE,vals): missing[k]+=int(v is None)
        count_measures=0
        measure_file=sources/'ausnut_2023_food_measures_only.csv'
        if measure_file.exists():
            for index,r in enumerate(read_csv(measure_file),2):
                con.execute('INSERT INTO measures VALUES (?,?,?,?,?,?,?,?,?)',(
                    r['Measure ID'],r['Public food key'],r['Food name'],
                    ' / '.join(str(r.get('Descriptor '+str(i),'')).strip() for i in range(1,5) if r.get('Descriptor '+str(i))),
                    numeric(r['Quantity'],'measure_quantity'),numeric(r['Gram amount'],'measure_grams'),
                    numeric(r.get('Volume'),'measure_volume'),'AUSNUT:2023',str(index)))
                count_measures+=1
        count_recipes=0
        crosswalk=ndb_crosswalk or {}
        recipe_file=sources/'fndds_recipe_ingredients.csv'
        units=collections.Counter(); linked=0
        if recipe_file.exists():
            for index,r in enumerate(read_csv(recipe_file),2):
                target=crosswalk.get(str(r['ingredient_sr_code']).zfill(5))
                if target and not con.execute('SELECT 1 FROM foods WHERE food_id=?',(target,)).fetchone(): target=None
                con.execute('INSERT INTO recipe_components VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(
                    r['recipe_fdc_id'],r['recipe_name_en'],r['ingredient_sr_code'],r['ingredient_description'],
                    numeric(r['amount'],'recipe_amount'),r['unit'],numeric(r['gram_weight'],'recipe_grams'),r['seq_num'],
                    target,'LINKED_NDB' if target else 'UNLINKED_NDB',r['source'],str(index)))
                count_recipes+=1;units[r['unit']]+=1;linked+=int(target is not None)
        alias_count=0
        if aliases and Path(aliases).exists():
            for r in read_csv(aliases):
                f=con.execute('SELECT state FROM foods WHERE food_id=?',(r['food_id'],)).fetchone()
                if not f or f[0]!=r['state']: raise ValueError('Alias target missing or preparation incompatible: '+r['alias'])
                if not r.get('rationale') or not r.get('reviewed_by'):raise ValueError('Unreviewed alias')
                con.execute('INSERT OR IGNORE INTO aliases VALUES (?,?,?,?,?)', (normalize(r['alias']),r['state'],r['food_id'],r['rationale'],r['reviewed_by']))
                alias_count+=1
        duplicate_names=[{'normalized_name':n,'state':s,'records':cnt} for n,s,cnt in con.execute('SELECT normalized_name,state,count(*) FROM foods GROUP BY normalized_name,state HAVING count(*)>1')]
        null_core=con.execute('SELECT count(*) FROM foods WHERE kcal_100g IS NULL OR protein_g_100g IS NULL OR carbs_g_100g IS NULL OR fat_g_100g IS NULL').fetchone()[0]
        audit={'input_food_rows':len(rows),'foods':len(seen),'complete_core_foods':len(seen)-null_core,
               'missing_core_foods':null_core,'missing_by_column':dict(missing),'source_counts':dict(source_counts),
               'state_counts':dict(states),'duplicate_source_ids_collapsed':duplicates,
               'duplicate_normalized_name_groups':duplicate_names,'measure_rows':count_measures,
               'recipe_component_rows':count_recipes,'recipe_unit_counts':dict(units),'recipe_components_linked_by_ndb':linked,
               'aliases':alias_count,'quarantined_values':quarantined,'csv_column_types':{k:dict(v) for k,v in original_types.items()},
               'sqlite_columns':{'foods':[{'name':x[1],'type':x[2]} for x in con.execute('PRAGMA table_info(foods)')]},
               'input_hashes':{p.name:sha256(p) for p in sources.glob('*') if p.is_file()},
               'notes':['No missing nutrient is converted to zero. Exact duplicate IDs collapse only if values agree.',
                        'Same-name foods from different sources remain separately addressable, never summed or merged.',
                        'Preparation is reclassified from description. Original SQLite state labeled many fried/boiled foods only cooked.',
                        'FNDDS recipe grams are source ingredient recipe weights, not a measured test-plate ground truth.',
                        'AUSNUT public food keys are not USDA IDs. Conversion requires explicit measure ID or a reviewed food link.']}
        con.commit()
        check=con.execute('PRAGMA integrity_check').fetchone()[0]
        if check != 'ok': raise ValueError('SQLite integrity check failed')
    finally: con.close()
    tmp.replace(output)
    save_json(output.parent/'normalized/database_audit.json',audit)
    write_csv(output.parent/'database_audit.csv',['source_id','rows'],[{'source_id':k,'rows':v} for k,v in source_counts.items()])
    return audit

def main():
    p=argparse.ArgumentParser();p.add_argument('--sources',type=Path,default=ROOT/'nutrition_database/sources');p.add_argument('--output',type=Path,default=ROOT/'nutrition_database/ingredients.sqlite');p.add_argument('--aliases',type=Path,default=ROOT/'nutrition_database/aliases.csv');a=p.parse_args()
    xwalk_file=a.sources/'ndb_crosswalk.json';xwalk=json.loads(xwalk_file.read_text()) if xwalk_file.exists() else None
    audit=build_database(a.sources,a.output,a.aliases,xwalk);print(json.dumps({k:audit[k] for k in ['foods','complete_core_foods','measure_rows','recipe_component_rows']},indent=2))
if __name__=='__main__':main()
