"""Inference-only runner. Reads no ground truth values. Every trial uses one shared calculator."""
import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from src.common import ROOT,load_json,save_json,sha256,utcnow
from src.ai import GroqClient,APIError,PredictionError
from src.prompts import VERSION
from nutrition_engine.ingredient_matcher import IngredientMatcher
from nutrition_engine.calculator import calculate
from methods import single_llm,multi_agent,ensemble

METHODS={'single':single_llm.predict,'multi':multi_agent.predict,'ensemble':ensemble.predict}

def load_config(config_dir=None):
    d=Path(config_dir or ROOT/'config')
    # Files use JSON syntax, a valid subset of YAML, avoiding a platform dependency.
    parts=[load_json(d/f) for f in ('experiment.yaml','models.yaml','database.yaml')]
    merged={}
    for p in parts:merged.update(p)
    validate_config(merged);return merged

def validate_config(c):
    if c.get('rounds')!=3:raise ValueError('Controlled benchmark requires exactly three rounds')
    if c.get('methods')!=['single','multi','ensemble']:raise ValueError('Core methods must be single, multi, ensemble')
    for k in ('multi_models','ensemble_models'):
        if not isinstance(c.get(k),list) or len(c[k])!=3 or any(not isinstance(m,str) or not m for m in c[k]):raise ValueError('Three configured model IDs required for '+k)
    if not isinstance(c.get('single_model'),str) or not c['single_model']:raise ValueError('single_model missing')
    if c.get('ensemble_mode') not in ('self_consistency','multi_model'):raise ValueError('Invalid ensemble mode')
    if c['ensemble_mode']=='self_consistency' and len(set(c['ensemble_models']))!=1:raise ValueError('Self-consistency uses one model')
    if c['ensemble_mode']=='multi_model' and len(set(c['ensemble_models']))<2:raise ValueError('Multi-model ensemble needs multiple distinct model IDs')
    if not isinstance(c.get('temperature'),(int,float)) or not 0<=c['temperature']<=2:raise ValueError('Temperature out of range')
    if c['ensemble_mode']=='self_consistency' and c['temperature']==0:raise ValueError('Self-consistency sampling requires temperature >0')
    all_models={c['single_model'],*c['multi_models'],*c['ensemble_models']}
    if not all_models<=set(c.get('vision_confirmed_models',[])):raise ValueError('Each configured model needs vision support checked in vision_confirmed_models')
    for rates in c.get('api',{}).get('prices',{}).values():
        for k in ('input_usd_per_million','output_usd_per_million'):
            if not isinstance(rates.get(k),(int,float)) or rates[k]<0:raise ValueError('Invalid configured token price')

def validate_manifest(manifest,mock):
    if set(manifest)!={'schema_version','mode','seed','image_count','images'}:raise ValueError('Inference manifest contains unexpected fields')
    if manifest['mode']!=('MOCK' if mock else 'REAL'):raise ValueError('MOCK and REAL inputs must remain separate')
    if len(manifest['images'])!=manifest['image_count'] or not manifest['images']:raise ValueError('Image count mismatch')
    seen=set()
    for r in manifest['images']:
        if set(r)!={'dish_id','image_path','image_sha256'}:raise ValueError('Image manifest contains unexpected label fields')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',r['dish_id']) or r['dish_id'] in seen:raise ValueError('Duplicate/invalid dish ID')
        seen.add(r['dish_id'])
        if sha256(r['image_path'])!=r['image_sha256']:raise ValueError('Image bytes changed after selection: '+r['dish_id'])
        if mock and not (Path(r['image_path']).parent.parent/'SYNTHETIC_TEST_ONLY.txt').is_file():raise ValueError('Mock mode accepts synthetic fixtures only')

def fingerprint(prepared,config,db,manifest):
    code={str(p.relative_to(ROOT)).replace('\\','/'):sha256(p)
          for d in ('src','scripts','methods','nutrition_engine','evaluation','fixtures') for p in (ROOT/d).rglob('*.py')}
    integrity=Path(prepared)/'truth_integrity.json'
    value={'config':config,'manifest_sha256':sha256(Path(prepared)/'manifest.json'),
           'database_sha256':sha256(db),'code_sha256':code,'prompt_version':VERSION,
           'truth_sha256':load_json(integrity)['sha256'] if integrity.exists() else None,
           'mode':manifest['mode']}
    value['fingerprint']=hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()
    return value

def run_experiment(prepared,config,run_dir,db_path,mock=False,rounds=None,methods=None,retry_failed=False,client_factory=None):
    prepared,run_dir,db_path=Path(prepared),Path(run_dir),Path(db_path)
    validate_config(config);manifest=load_json(prepared/'manifest.json');validate_manifest(manifest,mock)
    freeze=fingerprint(prepared,config,db_path,manifest)
    run_dir.mkdir(parents=True,exist_ok=True)
    if (run_dir/'frozen.json').exists():
        old=load_json(run_dir/'frozen.json')
        if old['fingerprint']!=freeze['fingerprint']:raise ValueError('Frozen run changed (config, code, database, selection or label seal). Use a new run ID.')
    else:
        freeze.update(created_at=utcnow(),images=manifest['images'],seed=manifest['seed'],rounds=config['rounds'],methods=config['methods'])
        save_json(run_dir/'frozen.json',freeze)
    rounds=rounds or list(range(1,config['rounds']+1));methods=methods or config['methods']
    if any(r not in range(1,4) for r in rounds) or any(m not in METHODS for m in methods):raise ValueError('Invalid round/method selection')
    if client_factory is None:
        if mock:
            from fixtures.mock_client import MockClient
            client_factory=MockClient
        else:client_factory=lambda:GroqClient(config['api'])
    matcher=IngredientMatcher(db_path,config.get('source_priority',['SR_Legacy','Foundation','FNDDS']));completed=0
    try:
        for rnd in rounds:
            for image in manifest['images']:
                for method in methods:
                    p=run_dir/'records'/f'round_{rnd}'/(image['dish_id']+'_'+method+'.json')
                    previous=load_json(p) if p.exists() else None
                    if previous and (previous['status']!='FAILED' or not retry_failed):continue
                    client=client_factory();start=time.perf_counter()
                    record={'mode':'MOCK' if mock else 'REAL','round':rnd,'dish_id':image['dish_id'],'method':method,
                            'status':'FAILED','fingerprint':freeze['fingerprint'],'started_at':utcnow(),
                            'prediction':None,'nutrition':None,'error_type':'IN_PROGRESS','error':'Trial has not finished.', 'nominal_model_calls':1 if method=='single' else 3}
                    def checkpoint():
                        record['call_metadata']=(previous.get('call_metadata',[]) if previous else [])+list(client.events)
                        record['latency_seconds']=time.perf_counter()-start
                        record['cumulative_latency_seconds']=record['latency_seconds']+(previous.get('cumulative_latency_seconds',previous.get('latency_seconds',0)) if previous else 0)
                        save_json(p,record)
                    client.on_event=checkpoint
                    checkpoint();interrupted=False
                    try:
                        pred=METHODS[method](image['image_path'],config,client,matcher)
                        nutrition=calculate(pred['ingredients'],matcher)
                        record.update(prediction=pred,nutrition=nutrition,status=nutrition['status'],error_type=None,error=None)
                        if method=='ensemble':
                            # A predetermined equal-call comparison: averaging independently calculated totals.
                            members=[calculate(x['ingredients'],matcher) for x in pred['members']]
                            record['member_nutrition']=members
                            record['budget_control_mean_nutrients']={k:sum(x['nutrients'][k] for x in members)/3 for k in members[0]['nutrients']} if all(x['status']=='SUCCESS' for x in members) else None
                    except (APIError,PredictionError,ValueError) as e:
                        record.update(error_type='API_ERROR' if isinstance(e,APIError) else ('PREDICTION_ERROR' if isinstance(e,PredictionError) else 'VALIDATION_ERROR'),error=str(e))
                    except KeyboardInterrupt:
                        record.update(error_type='INTERRUPTED',error='User interrupted trial; billed/unknown attempts retained. Use --retry-failed to retry.')
                        interrupted=True
                    except Exception as e:
                        record.update(error_type='INTERNAL_ERROR',error=type(e).__name__)
                    record['latency_seconds']=time.perf_counter()-start
                    current_events=list(client.events)
                    if previous:
                        history=p.parent/'history'/(p.stem+'_'+str(previous.get('trial_attempt',1))+'.json')
                        save_json(history,previous)
                    record['trial_attempt']=(previous.get('trial_attempt',1)+1) if previous else 1
                    record['call_metadata']=(previous.get('call_metadata',[]) if previous else [])+current_events
                    record['current_attempt_call_count']=len(current_events)
                    record['cumulative_latency_seconds']=record['latency_seconds']+(previous.get('cumulative_latency_seconds',previous.get('latency_seconds',0)) if previous else 0)
                    save_json(p,record);completed+=1
                    if interrupted:raise KeyboardInterrupt()
                    print(f"[{record['mode']}] round={rnd} {image['dish_id']} {method}: {record['status']} calls={len(current_events)}",flush=True)
    finally:matcher.close()
    return completed

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['mock','real'],default='mock')
    p.add_argument('--prepared',type=Path);p.add_argument('--run-id',default='smoke-v1');p.add_argument('--config-dir',type=Path)
    p.add_argument('--round',dest='rounds',type=int,nargs='+');p.add_argument('--method',dest='methods',choices=list(METHODS),nargs='+')
    p.add_argument('--retry-failed',action='store_true');a=p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',a.run_id):p.error('Use letters, numbers, underscores or hyphens for run-id')
    cfg=load_config(a.config_dir);mock=a.mode=='mock'
    if mock:
        from fixtures.make_fixture import make_fixture
        from src.dataset import prepare_dataset
        fixture=make_fixture(ROOT/'fixtures/dataset');prepared=a.prepared or ROOT/'fixtures/prepared'
        if not (prepared/'manifest.json').exists():prepare_dataset(fixture,prepared,5,cfg['seed'],mock=True)
    else:
        prepared=a.prepared or ROOT/'data/prepared/smoke'
    db=Path(cfg['database_path']);db=db if db.is_absolute() else ROOT/db
    n=run_experiment(prepared,cfg,ROOT/'results'/a.mode/a.run_id,db,mock,a.rounds,a.methods,a.retry_failed)
    print(f'Wrote {n} new trial records. Real API is called only with --mode real.')
if __name__=='__main__':main()
