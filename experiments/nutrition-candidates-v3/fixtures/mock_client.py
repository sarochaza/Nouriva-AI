"""Offline scripted responses. Does not read labels or model outputs from another call."""
import hashlib,json
from src.common import utcnow,sha256
from src.ai import validate_prediction
from src.prompts import VERSION

class MockClient:
    def __init__(self):self.events=[];self.ensemble_index=0
    def chat(self,model,image,stage,prior=None,temperature=0.7):
        if stage=='ensemble':
            grams=[100,110,120][self.ensemble_index%3];self.ensemble_index+=1
        else:grams={'single':100,'vision':100,'portion':110,'critic':105}[stage]
        result=validate_prediction({'dish_name':'MOCK fixture','ingredients':[{'name':'Carrots, raw','name_th':'แครอทดิบ','state':'raw','grams':grams,
                                   'evidence':'visible','confidence':0.8,'uncertainty':'SCRIPTED MOCK; no actual food recognition'}]})
        self.events.append({'model':'MOCK:'+model,'stage':stage,'attempt':1,'prompt_version':VERSION,'started_at':utcnow(),
                            'status':'SUCCESS','latency_seconds':0,'prompt_tokens':10,'completion_tokens':10,'total_tokens':20,
                            'cost_usd':0,'image_sha256':sha256(image),'request_sha256':hashlib.sha256(json.dumps({'stage':stage,'prior':prior}).encode()).hexdigest()})
        if getattr(self,'on_event',None):self.on_event()
        return result
