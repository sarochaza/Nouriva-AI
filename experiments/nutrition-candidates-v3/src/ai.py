"""Configurable Groq adapter. Records every HTTP attempt; no paid calls in tests."""
import base64
import hashlib
import json
import math
import mimetypes
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from src.common import read_env,utcnow,sha256
from src.dataset import verify_image
from src.prompts import VERSION,COMMON,TASKS
from nutrition_engine.normalization import STATES,identity

class APIError(Exception):pass
class PredictionError(Exception):pass

def validate_prediction(v):
    if not isinstance(v,dict) or not isinstance(v.get('ingredients'),list):raise PredictionError('Expected JSON ingredients array')
    if not 1<=len(v['ingredients'])<=65:raise PredictionError('Ingredient list size out of range')
    items=[];seen=set()
    for r in v['ingredients']:
        if not isinstance(r,dict):raise PredictionError('Ingredient must be an object')
        if not isinstance(r.get('name'),str) or not r['name'].strip() or len(r['name'])>250:raise PredictionError('Missing/invalid ingredient name')
        state=r.get('state');g=r.get('grams');conf=r.get('confidence')
        if state not in STATES:raise PredictionError('Invalid or missing preparation state')
        if isinstance(g,bool) or not isinstance(g,(int,float)) or not math.isfinite(g) or not 0<=g<=3000:raise PredictionError('Mass must be finite numeric grams in [0,3000]')
        if r.get('evidence') not in ('visible','inferred','uncertain'):raise PredictionError('Missing evidence classification')
        if isinstance(conf,bool) or not isinstance(conf,(int,float)) or not math.isfinite(conf) or not 0<=conf<=1:raise PredictionError('Invalid confidence')
        if not isinstance(r.get('uncertainty'),str):raise PredictionError('Missing uncertainty text')
        key=(identity(r['name']),state)
        if key in seen:raise PredictionError('Duplicate ingredient identity/state in a member')
        seen.add(key)
        items.append({'name':r['name'].strip(),'name_th':str(r.get('name_th',''))[:250], 'state':state,'grams':float(g),
                      'evidence':r['evidence'],'confidence':float(conf),'uncertainty':r['uncertainty'][:2000]})
    if sum(r['grams'] for r in items)>6000:raise PredictionError('Implausible total serving mass >6000g')
    return {'dish_name':str(v.get('dish_name',''))[:250],'ingredients':items}

def parse_prediction(text):
    try:
        # JSON mode is strict: prose/code fences are prediction errors, never silently repaired.
        return validate_prediction(json.loads(text,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON'))))
    except (ValueError,TypeError,json.JSONDecodeError) as e:raise PredictionError('Invalid JSON prediction') from e

def default_transport(payload,headers,timeout,url):
    req=urllib.request.Request(url,data=json.dumps(payload,allow_nan=False).encode('utf-8') if payload is not None else None,
                               headers=headers,method='POST' if payload is not None else 'GET')
    with urllib.request.urlopen(req,timeout=timeout) as response:return json.loads(response.read().decode('utf-8'))

def http_error_details(error,authorization=''):
    """Keep only safe provider classifications; never retain raw bodies or credentials."""
    secret=authorization[7:] if authorization.startswith('Bearer ') else authorization
    try:
        raw=(error.read(8192) or b'').decode('utf-8',errors='replace')
    except (OSError,AttributeError,ValueError,TypeError):
        raw=''
    finally:
        error.close()
    if re.search(r'error\s+code\s*:\s*1010\b',raw,re.I):
        return {'provider_error_code':'CLOUDFLARE_1010','provider_error_type':'edge_access_denied'}
    try:
        obj=json.loads(raw);details=obj.get('error',{}) if isinstance(obj,dict) else {}
    except (ValueError,TypeError):
        details={}
    if not isinstance(details,dict):details={}
    def safe(value):
        if not isinstance(value,str) or (secret and secret in value):return None
        if re.search(r'gsk_|sk-|\bbearer\b',value,re.I):return None
        return value if re.fullmatch(r'[A-Za-z0-9_.-]{1,120}',value) else None
    return {'provider_error_code':safe(details.get('code')),'provider_error_type':safe(details.get('type'))}

def http_error_name(status,details):
    code=details.get('provider_error_code')
    return 'HTTP_'+str(status)+(':'+code if code else '')

def retry_delay(header,attempt,maximum):
    delay=min(2**attempt+1,maximum)
    if header:
        try:delay=float(header)
        except (ValueError,TypeError):
            try:delay=(parsedate_to_datetime(header)-datetime.now(timezone.utc)).total_seconds()
            except (ValueError,TypeError):pass
    if not math.isfinite(delay) or delay>maximum:raise APIError('RATE_LIMIT_WAIT_EXCEEDS_CAP; resume later with same frozen run')
    return max(0,delay)

class GroqClient:
    def __init__(self,config,transport=None,sleep=None,prediction_parser=None,prompt_builder=None,prompt_version=None):
        self.config=config;self.transport=transport or default_transport;self.sleep=sleep or time.sleep;self.events=[];self.on_event=None
        self.prediction_parser=prediction_parser or parse_prediction
        self.prompt_builder=prompt_builder;self.prompt_version=prompt_version or VERSION
    def checkpoint(self):
        if self.on_event:self.on_event()
    def headers(self):
        read_env();key=os.environ.get('GROQ_API_KEY','')
        if not key or key.startswith('PASTE_'):raise APIError('GROQ_API_KEY missing in .env')
        return {'Authorization':'Bearer '+key,'Content-Type':'application/json',
                'Accept':'application/json','User-Agent':'NouraNutritionBenchmark/3.0'}
    def list_models(self):
        headers=self.headers()
        try:resp=self.transport(None,headers,self.config.get('timeout_seconds',90),'https://api.groq.com/openai/v1/models')
        except urllib.error.HTTPError as e:
            details=http_error_details(e,headers.get('Authorization',''))
            raise APIError(http_error_name(e.code,details)) from e
        except (urllib.error.URLError,TimeoutError,OSError) as e:raise APIError('MODEL_LIST_REQUEST_FAILED') from e
        return sorted(r['id'] for r in resp.get('data',[]) if r.get('active',True))
    def chat(self,model,image,stage,prior=None,temperature=0.7):
        if not isinstance(model,str) or not model or model.startswith('CHANGE_ME'):raise APIError('Set a vision model ID in config/models.yaml')
        image=Path(image);verify_image(image)
        if image.stat().st_size>self.config.get('max_image_bytes',10*1024*1024):raise APIError('Image exceeds configured byte limit')
        mime=mimetypes.guess_type(image.name)[0] or 'image/png'
        if self.prompt_builder:
            prompt=self.prompt_builder(stage,prior)
        else:
            prompt=COMMON+'\n'+TASKS[stage]
            if prior is not None:prompt+='\nPrior AI estimates (not verified labels): '+json.dumps(prior,ensure_ascii=False,allow_nan=False)
        content=[{'type':'text','text':prompt},{'type':'image_url','image_url':{'url':f'data:{mime};base64,'+base64.b64encode(image.read_bytes()).decode()}}]
        payload={'model':model,'messages':[{'role':'user','content':content}], 'temperature':temperature,
                 'max_completion_tokens':self.config.get('max_completion_tokens',2500),'response_format':{'type':'json_object'},'stream':False}
        if self.config.get('reasoning_effort') is not None:payload['reasoning_effort']=self.config['reasoning_effort']
        request_hash=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        headers=self.headers();last=None
        for attempt in range(self.config.get('max_retries',2)+1):
            event={'model':model,'stage':stage,'attempt':attempt+1,'prompt_version':self.prompt_version,
                   'started_at':utcnow(),'image_sha256':sha256(image),'request_sha256':request_hash,
                   'status':'IN_FLIGHT','prompt_tokens':None,'completion_tokens':None,'total_tokens':None,'cost_usd':None}
            self.events.append(event);start=time.perf_counter()
            self.checkpoint()
            transport_pending=True
            try:
                response=self.transport(payload,headers,self.config.get('timeout_seconds',90),'https://api.groq.com/openai/v1/chat/completions')
                transport_pending=False
                event['latency_seconds']=time.perf_counter()-start;event['response_id']=response.get('id')
                usage=response.get('usage') or {}
                for key in ('prompt_tokens','completion_tokens','total_tokens'):
                    val=usage.get(key)
                    if isinstance(val,int) and not isinstance(val,bool) and val>=0:event[key]=val
                rates=self.config.get('prices',{}).get(model)
                if rates and event['prompt_tokens'] is not None and event['completion_tokens'] is not None:
                    event['cost_usd']=(event['prompt_tokens']*rates['input_usd_per_million']+event['completion_tokens']*rates['output_usd_per_million'])/1e6
                self.checkpoint()
                try:
                    raw=response['choices'][0]['message']['content']
                    result=self.prediction_parser(raw)
                except (KeyError,IndexError,TypeError,PredictionError) as e:
                    reason=str(e) if isinstance(e,PredictionError) else 'Missing or invalid choices[0].message.content'
                    event.update(status='PREDICTION_ERROR',validation_error=reason)
                    self.checkpoint()
                    raise PredictionError('Response does not meet ingredient JSON schema: '+reason) from e
                event['status']='SUCCESS';self.checkpoint();return result
            except urllib.error.HTTPError as e:
                header=e.headers.get('Retry-After') if e.headers else None
                details=http_error_details(e,headers.get('Authorization',''))
                event.update(status='API_ERROR',http_status=e.code,error_type='HTTP_ERROR',latency_seconds=time.perf_counter()-start,**details)
                self.checkpoint()
                retry=e.code in (429,500,502,503,504);last=http_error_name(e.code,details)
                if not retry or attempt>=self.config.get('max_retries',2):raise APIError(last) from e
                delay=retry_delay(header,attempt,self.config.get('max_retry_wait_seconds',60));event['retry_wait_seconds']=delay;self.sleep(delay)
            except (urllib.error.URLError,TimeoutError,OSError) as e:
                # File checkpoint failures must not trigger another paid request.
                if not transport_pending: raise
                event.update(status='API_ERROR',error_type='NETWORK_OR_TIMEOUT',latency_seconds=time.perf_counter()-start)
                self.checkpoint()
                last='NETWORK_OR_TIMEOUT'
                if attempt>=self.config.get('max_retries',2):raise APIError(last) from e
                delay=retry_delay(None,attempt,self.config.get('max_retry_wait_seconds',60));event['retry_wait_seconds']=delay;self.sleep(delay)
        raise APIError(last or 'API_ERROR')
