"""Explicit missing-value metrics. MAPE excludes only reference values <=0."""
import math
import statistics
from nutrition_engine.normalization import identity

def mean(values):
    v=[x for x in values if x is not None]
    return statistics.mean(v) if v else None

def numeric_metrics(truth,pred):
    if len(truth)!=len(pred):raise ValueError('Metric length mismatch')
    for v in list(truth)+list(pred):
        if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v):raise ValueError('Nonfinite metric input')
    errors=[abs(t-p) for t,p in zip(truth,pred)]
    ape=[100*abs(t-p)/t for t,p in zip(truth,pred) if t>0]
    return {'n':len(errors),'MAE':mean(errors),'RMSE':math.sqrt(mean([e*e for e in errors])) if errors else None,
            'MAPE_percent':mean(ape),'mape_n':len(ape)}

def label(name):
    remove={'raw','cooked','fried','boiled','roasted','steamed','grilled','baked','unspecified'}
    return ' '.join(t for t in identity(name).split() if t not in remove)

def ingredient_scores(expected,predicted):
    if not expected or any(label(i['name']) in ('deprecated','unknown','') for i in expected):
        return {'precision':None,'recall':None,'F1':None,'weight_MAE_g':None,'matched_identity_count':0}
    def grouped(items):
        weights={}
        for i in items:
            k=label(i['name']);weights[k]=weights.get(k,0)+i['grams']
        return weights
    gt=grouped(expected);pr=grouped(predicted);both=gt.keys()&pr.keys()
    precision=len(both)/len(pr) if pr else 0.;recall=len(both)/len(gt)
    return {'precision':precision,'recall':recall,'F1':2*precision*recall/(precision+recall) if precision+recall else 0.,
            'weight_MAE_g':mean([abs(gt[k]-pr[k]) for k in both]),'matched_identity_count':len(both)}
