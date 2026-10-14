"""Offline evaluation only. Ground truth is never imported by the inference runner."""
import argparse
import collections
import json
import statistics
from pathlib import Path
from src.common import ROOT,load_json,save_json,write_csv,sha256
from evaluation.metrics import mean,numeric_metrics,ingredient_scores

CORE=('kcal','protein_g','carbs_g','fat_g')
STATUSES=('SUCCESS','FAILED','UNMATCHED','REVIEW_REQUIRED','NOT_RUN')

def summarize(rows,method,rnd,cohort='available_success',common=None):
    subset=[r for r in rows if r['method']==method and (rnd=='all' or r['round']==rnd)]
    success=[r for r in subset if r['status']=='SUCCESS' and (cohort!='common_success' or (r['round'],r['dish_id']) in common)]
    s={'method':method,'round':rnd,'cohort':cohort,'planned':len(subset),'scored':len(success),
       'success_rate':sum(r['status']=='SUCCESS' for r in subset)/len(subset) if subset else None}
    for status in STATUSES:s[status.lower()]=sum(r['status']==status for r in subset)
    for k in CORE:
        m=numeric_metrics([r[k+'_truth'] for r in success],[r[k+'_prediction'] for r in success])
        for stat in ('MAE','RMSE','MAPE_percent','mape_n'):s[k+'_'+stat]=m[stat]
    for metric in ('ingredient_precision','ingredient_recall','ingredient_F1','ingredient_weight_MAE_g','match_coverage','complete_nutrient_coverage','mass_match_coverage','latency_seconds'):
        # Accuracy follows its declared cohort. Operational coverage/resources retain all planned trials.
        accuracy_rows=success if cohort=='common_success' else subset
        group=accuracy_rows if metric.startswith('ingredient_') else subset
        vals=[r[metric] for r in group if r[metric] is not None]
        s[metric+'_mean']=mean(vals);s[metric+'_n']=len(vals)
    s['http_attempts_total']=sum(r['http_attempts'] for r in subset)
    s['model_responses_total']=sum(r['model_responses'] for r in subset)
    s['known_tokens_total']=sum(r['known_tokens'] for r in subset)
    ran=[r for r in subset if r['status']!='NOT_RUN']
    s['tokens_total']=sum(r['total_tokens'] for r in ran) if ran and all(r['total_tokens'] is not None for r in ran) else None
    s['known_cost_usd_total']=sum(r['known_cost_usd'] for r in subset)
    s['cost_usd_total']=sum(r['cost_usd'] for r in ran) if ran and all(r['cost_usd'] is not None for r in ran) else None
    s['cost_complete']=s['cost_usd_total'] is not None
    return s

def evaluate_run(run_dir,truth_path):
    run_dir=Path(run_dir);freeze=load_json(run_dir/'frozen.json');truth_path=Path(truth_path)
    if freeze.get('truth_sha256') and sha256(truth_path)!=freeze['truth_sha256']:raise ValueError('Ground truth bytes changed after dataset preparation')
    truth_file=load_json(truth_path)
    if truth_file['mode']!=freeze['mode']:raise ValueError('Mock/real evaluation mode mismatch')
    truth={r['dish_id']:r for r in truth_file['records']}
    if len(truth)!=len(truth_file['records']) or set(truth)!={r['dish_id'] for r in freeze['images']}:raise ValueError('Ground truth selection does not exactly match frozen image IDs')
    rows=[];budget=[];coverage=[]
    for rnd in range(1,freeze['rounds']+1):
        for image in freeze['images']:
            dish=image['dish_id'];gt=truth[dish]
            for method in freeze['methods']:
                row={'mode':freeze['mode'],'round':rnd,'dish_id':dish,'method':method,'status':'NOT_RUN','error_type':None,
                     'error':None,'latency_seconds':None,'http_attempts':0,'model_responses':0,'known_tokens':0,'total_tokens':None,
                     'known_cost_usd':0.,'cost_usd':None,'match_coverage':None,'complete_nutrient_coverage':None,'mass_match_coverage':None,
                     'ingredient_precision':None,'ingredient_recall':None,'ingredient_F1':None,'ingredient_weight_MAE_g':None,'matched_identity_count':None}
                for k in CORE:row.update({k+'_truth':gt[k],k+'_prediction':None,k+'_abs_error':None,k+'_ape_percent':None})
                p=run_dir/'records'/f'round_{rnd}'/(dish+'_'+method+'.json')
                if p.exists():
                    obj=load_json(p)
                    if (obj['round'],obj['dish_id'],obj['method'],obj['mode'],obj['fingerprint'])!=(rnd,dish,method,freeze['mode'],freeze['fingerprint']):raise ValueError('Wrong trial identity/fingerprint: '+str(p))
                    if obj['status'] not in STATUSES:raise ValueError('Invalid trial status')
                    row.update(status=obj['status'],error_type=obj.get('error_type'),error=obj.get('error'),latency_seconds=obj.get('cumulative_latency_seconds',obj.get('latency_seconds')))
                    events=obj.get('call_metadata',[]);row['http_attempts']=len(events)
                    row['model_responses']=sum(e['status'] in ('SUCCESS','PREDICTION_ERROR') for e in events)
                    row['known_tokens']=sum(e.get('total_tokens') or 0 for e in events)
                    row['total_tokens']=row['known_tokens'] if events and all(e.get('total_tokens') is not None for e in events) else None
                    row['known_cost_usd']=sum(e.get('cost_usd') or 0 for e in events)
                    row['cost_usd']=row['known_cost_usd'] if events and all(e.get('cost_usd') is not None for e in events) else None
                    nutrition=obj.get('nutrition')
                    if nutrition:
                        for metric in ('match_coverage','complete_nutrient_coverage','mass_match_coverage'):row[metric]=nutrition[metric]
                        for i in nutrition['matched']:
                            coverage.append({'round':rnd,'dish_id':dish,'method':method,'name':i['prediction']['name'],'state':i['prediction']['state'],'status':'MATCHED',
                                             'food_id':i['food_id'],'source_id':i['source_id'],'reason':i['match_reason'],'grams':i['grams'],'missing_nutrients':';'.join(i['missing_nutrients'])})
                        for i in nutrition['unmatched']:
                            coverage.append({'round':rnd,'dish_id':dish,'method':method,'name':i['prediction']['name'],'state':i['prediction']['state'],'status':i['status'],
                                             'food_id':None,'source_id':None,'reason':i['reason'],'grams':i['prediction']['grams'],'missing_nutrients':None})
                        if row['status']=='SUCCESS':
                            if not nutrition['complete'] or nutrition['nutrients'] is None:raise ValueError('SUCCESS contains partial calculation')
                            for k in CORE:
                                pred=nutrition['nutrients'][k];t=gt[k]
                                numeric_metrics([t],[pred])
                                row.update({k+'_prediction':pred,k+'_abs_error':abs(t-pred),k+'_ape_percent':100*abs(t-pred)/t if t>0 else None})
                    if obj.get('prediction'):
                        scores=ingredient_scores(gt['ingredients'],obj['prediction']['ingredients'])
                        row.update(ingredient_precision=scores['precision'],ingredient_recall=scores['recall'],ingredient_F1=scores['F1'],ingredient_weight_MAE_g=scores['weight_MAE_g'],matched_identity_count=scores['matched_identity_count'])
                    if method=='ensemble' and obj.get('budget_control_mean_nutrients') is not None:
                        b={'round':rnd,'dish_id':dish,'mode':freeze['mode'],'calls_shared_with_ensemble':3,'ensemble_status':obj['status']}
                        for k in CORE:
                            b[k+'_mean_members_abs_error']=abs(obj['budget_control_mean_nutrients'][k]-gt[k])
                            b[k+'_ensemble_abs_error']=row[k+'_abs_error']
                        budget.append(b)
                rows.append(row)
    success_sets=[{(r['round'],r['dish_id']) for r in rows if r['method']==m and r['status']=='SUCCESS'} for m in freeze['methods']]
    common=set.intersection(*success_sets)
    summaries=[summarize(rows,m,rnd,cohort,common) for cohort in ('available_success','common_success') for m in freeze['methods'] for rnd in (1,2,3,'all')]
    for m in freeze['methods']:
        overall=next(s for s in summaries if s['method']==m and s['round']=='all' and s['cohort']=='available_success')
        for k in CORE:
            vals=[s[k+'_MAE'] for s in summaries if s['method']==m and s['round']!='all' and s['cohort']=='available_success' and s[k+'_MAE'] is not None]
            overall[k+'_round_MAE_mean']=mean(vals);overall[k+'_round_MAE_stdev']=statistics.stdev(vals) if len(vals)>1 else None
            overall[k+'_round_MAE_n']=len(vals)
    out=run_dir/'comparison';out.mkdir(exist_ok=True)
    write_csv(out/'per_evaluation.csv',list(rows[0]),rows)
    fields=list(dict.fromkeys(k for s in summaries for k in s));write_csv(out/'summary_by_method_round.csv',fields,summaries)
    save_json(out/'summary.json',{'mode':freeze['mode'],'fingerprint':freeze['fingerprint'],'common_success_evaluations':len(common),
                                'summaries':summaries,'interpretation':'Operational SUCCESS means fully calculable, not necessarily accurate. Nutrition primary metrics score complete successes only. Mock metrics are software checks only.'})
    save_json(out/'per_evaluation.json',rows)
    cov_fields=['round','dish_id','method','name','state','status','food_id','source_id','reason','grams','missing_nutrients']
    write_csv(out/'database_coverage.csv',cov_fields,coverage)
    counts=collections.Counter(r['status'] for r in coverage)
    save_json(out/'database_coverage.json',{'mode':freeze['mode'],'prediction_ingredient_rows':len(coverage),'status_counts':dict(counts),
                                         'micro_match_coverage':counts['MATCHED']/len(coverage) if coverage else None,
                                         'note':'Coverage is over ingredient rows actually predicted, not over all real ingredients. Ingredient recall is reported separately.'})
    if budget:write_csv(out/'budget_control.csv',list(budget[0]),budget)
    title='MOCK SOFTWARE CHECK — NOT RESEARCH RESULTS' if freeze['mode']=='MOCK' else 'Noura AI controlled benchmark'
    report=['# '+title,'','|Method|Success / planned|kcal MAE|Protein MAE (g)|Carbs MAE (g)|Fat MAE (g)|HTTP attempts|','|---|---:|---:|---:|---:|---:|---:|']
    def show(v):return 'N/A' if v is None else f'{v:.4f}'
    for s in summaries:
        if s['round']=='all' and s['cohort']=='available_success':report.append(f"|{s['method']}|{s['success']}/{s['planned']}|{show(s['kcal_MAE'])}|{show(s['protein_g_MAE'])}|{show(s['carbs_g_MAE'])}|{show(s['fat_g_MAE'])}|{s['http_attempts_total']}|")
    report+=['',f'Common-success dish/round pairs across all three methods: {len(common)}. See common_success cohort in CSV.',
             'FAILED, UNMATCHED, REVIEW_REQUIRED and NOT_RUN have null error. Never interpret them as error=0.',
             'Available-success cohorts may differ between methods. Use common-success, failure rates and database coverage together.',
             'Round MAE standard deviation describes variation across only three rounds. Repeated images are not independent samples.',
             'Ingredient identities use documented spelling normalization and explicit preparation-word removal, not unrestricted semantic substitutions.',
             'Equal-call control averages nutrients from the three independently calculated ensemble members. It reuses the same three calls, excludes incomplete members and does not prove architecture causality.']
    (out/'report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    return rows,summaries

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-dir',type=Path,required=True);p.add_argument('--truth',type=Path,required=True);a=p.parse_args()
    rows,summaries=evaluate_run(a.run_dir,a.truth)
    print(f"Evaluated {len(rows)} planned trials; SUCCESS={sum(r['status']=='SUCCESS' for r in rows)}. See {a.run_dir/'comparison/report.md'}")
if __name__=='__main__':main()
