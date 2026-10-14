"""Pre-registered 2-of-3 ingredient/state vote and median mass of present supporters."""
import statistics
from src.ai import PredictionError,validate_prediction
from nutrition_engine.normalization import identity

def merge_predictions(predictions,matcher=None):
    if len(predictions)!=3:raise ValueError('Ensemble requires exactly three independent members')
    votes={}
    for member,p in enumerate(predictions):
        p=validate_prediction(p)
        for item in p['ingredients']:
            key=matcher.consensus_key(item['name'],item['state']) if matcher else identity(item['name'])+'|'+item['state']
            if member in votes.get(key,{}):raise PredictionError('Member contains duplicate canonical identity')
            votes.setdefault(key,{})[member]=item
    merged=[];trace=[]
    for key,supporters in sorted(votes.items()):
        keep=len(supporters)>=2;trace.append({'identity':key,'member_indices':list(supporters),'vote_count':len(supporters),'kept':keep,
                                           'member_weights_g':[i['grams'] for i in supporters.values()]})
        if keep:
            vals=list(supporters.values());representative=vals[0]
            merged.append({**representative,'grams':statistics.median(i['grams'] for i in vals),
                           'confidence':statistics.mean(i['confidence'] for i in vals),
                           'evidence':representative['evidence'] if len({i['evidence'] for i in vals})==1 else 'uncertain',
                           'uncertainty':'Ensemble median of present supporters; '+ '; '.join(i['uncertainty'] for i in vals)})
    if not merged:raise PredictionError('No ingredient/state reached two-of-three consensus')
    final=validate_prediction({'dish_name':predictions[0].get('dish_name',''),'ingredients':merged})
    return {**final,'members':predictions,'merge_trace':trace}

def predict(image,config,client,matcher=None):
    models=config['ensemble_models'];mode=config['ensemble_mode']
    if len(models)!=3 or mode not in ('self_consistency','multi_model'):raise ValueError('Invalid ensemble configuration')
    if mode=='multi_model' and len(set(models))<2:raise ValueError('Multi-model requires at least two distinct model IDs')
    if mode=='self_consistency' and len(set(models))!=1:raise ValueError('Self-consistency requires one shared model ID')
    members=[client.chat(m,image,'ensemble',temperature=config['temperature']) for m in models]
    r=merge_predictions(members,matcher)
    r['ensemble_type']='multi_model_ensemble' if mode=='multi_model' else 'single_model_self_consistency'
    return r
