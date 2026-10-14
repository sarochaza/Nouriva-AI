"""Only exact identities and reviewed aliases auto-match. Fuzzy results are suggestions."""
import difflib
import sqlite3
from functools import lru_cache
from pathlib import Path
from .normalization import normalize, identity, infer_state, compatible, STATES

class IngredientMatcher:
    def __init__(self, path, source_priority=('SR_Legacy','Foundation','FNDDS')):
        self.path=Path(path)
        self.con=sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True)
        self.con.row_factory=sqlite3.Row
        self.rows=[dict(r) for r in self.con.execute('SELECT * FROM foods')]
        self.by_name={}
        for r in self.rows:
            self.by_name.setdefault(normalize(r['name_en']),[]).append(r)
            if r.get('name_th'):self.by_name.setdefault(normalize(r['name_th']),[]).append(r)
        self.aliases={}
        for r in self.con.execute('SELECT * FROM aliases'):
            self.aliases.setdefault((r['alias'],r['state']),[]).append(dict(r))
        self.by_id={r['food_id']:r for r in self.rows}
        self.source_priority=tuple(source_priority)
    def close(self): self.con.close()
    @lru_cache(maxsize=8192)
    def match(self, name, state='unspecified'):
        if state not in STATES:raise ValueError('Unknown preparation state')
        key=normalize(name)
        inferred,evidence=infer_state(name)
        if inferred!='unspecified' and inferred!=state:
            return {'status':'REVIEW_REQUIRED','score':0,'reason':'name_state_conflict','food':None,'candidates':[]}
        candidates=[r for r in self.by_name.get(key,[]) if compatible(state,r['state'])]
        aliases=self.aliases.get((key,state),[])
        if aliases:candidates=[self.by_id[r['food_id']] for r in aliases]
        candidates={r['food_id']:r for r in candidates}
        reason='reviewed_alias' if aliases else 'exact_name_state'
        alternatives=[]
        if len(candidates)>1 and not aliases:
            for source in self.source_priority:
                preferred=[r for r in candidates.values() if r['source_id'].split(':')[0]==source]
                if preferred:
                    if len(preferred)==1:
                        alternatives=[r['food_id'] for r in candidates.values() if r['food_id']!=preferred[0]['food_id']]
                        candidates={preferred[0]['food_id']:preferred[0]};reason='exact_identity_declared_source_priority'
                    break
        if len(candidates)==1:
            food=next(iter(candidates.values()))
            return {'status':'MATCHED','score':1.0,'reason':reason,
                    'food':food,'candidates':[], 'alias_rationale':[a['rationale'] for a in aliases],
                    'alternative_source_food_ids':alternatives}
        if candidates:
            return {'status':'REVIEW_REQUIRED','score':1.0,'reason':'ambiguous_exact_identity','food':None,
                    'candidates':[{'food_id':r['food_id'],'name':r['name_en'],'state':r['state']} for r in candidates.values()]}
        # Lexical scores are not calibrated probabilities. Suggestions never substitute automatically.
        scores=sorted(((difflib.SequenceMatcher(None,identity(name),identity(r['name_en'])).ratio(),r['food_id'])
                       for r in self.rows if compatible(state,r['state'])),reverse=True)[:5]
        suggestions=[{'food_id':fid,'name':self.by_id[fid]['name_en'],'state':self.by_id[fid]['state'],
                      'lexical_score':round(score,4)} for score,fid in scores if score>=0.35]
        return {'status':'REVIEW_REQUIRED' if suggestions or key in self.by_name else 'UNMATCHED',
                'score':scores[0][0] if scores else 0,'reason':'no_reviewed_identity_match','food':None,'candidates':suggestions}
    def consensus_key(self, name, state):
        r=self.match(name,state)
        return 'food:'+r['food']['food_id'] if r['status']=='MATCHED' else identity(name)+'|'+state
