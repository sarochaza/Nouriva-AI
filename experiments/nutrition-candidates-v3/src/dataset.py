"""Validate local food-nutrients JSONL. There is no dataset download code."""
import collections
import hashlib
import json
import math
import random
import re
from pathlib import Path
from src.common import save_json, write_csv, sha256

DEFAULT_FIELDS={'image':'file_name','id':'id','ingredients':'ingredients','kcal':'total_calories',
                'mass_g':'total_mass','fat_g':'total_fat','carbs_g':'total_carb','protein_g':'total_protein'}

def finite(value, name):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
        raise ValueError('Missing/invalid numeric field: '+name)
    return float(value)

def verify_image(path):
    with Path(path).open('rb') as f: head=f.read(12)
    if not (head.startswith(b'\x89PNG\r\n\x1a\n') or head.startswith(b'\xff\xd8\xff') or
            (head.startswith(b'RIFF') and head[8:12]==b'WEBP')):
        raise ValueError('Unsupported/corrupt image signature')

def load_dataset(dataset_root, metadata=None, fields=None):
    root=Path(dataset_root).expanduser().resolve()
    if not root.is_dir():raise FileNotFoundError('Dataset directory does not exist: '+str(root))
    if metadata is None:
        found=[p for p in (root/'metadata.jsonl',root/'test/metadata.jsonl') if p.is_file()]
        if len(found)!=1:raise ValueError('Expected one metadata.jsonl in root or test/. Supply --metadata if ambiguous.')
        metadata=found[0]
    metadata=Path(metadata).resolve();fields=fields or DEFAULT_FIELDS
    if set(fields)!=set(DEFAULT_FIELDS):raise ValueError('Explicit schema mapping must define every required canonical field')
    errors=[];valid=[];seen=set();duplicates=0;keys=collections.Counter();types=collections.defaultdict(collections.Counter)
    with metadata.open(encoding='utf-8-sig') as f:
        for line_no,line in enumerate(f,1):
            if not line.strip():continue
            try:
                raw=json.loads(line,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
                if not isinstance(raw,dict):raise ValueError('Metadata row must be an object')
                keys.update(raw)
                for k,v in raw.items():types[k][type(v).__name__]+=1
                if not set(fields.values())<=raw.keys():raise ValueError('Schema mismatch. Required fields: '+','.join(fields.values()))
                dish=raw[fields['id']]
                if not isinstance(dish,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',dish):raise ValueError('Invalid dish ID')
                rel=raw[fields['image']]
                if not isinstance(rel,str) or '\\' in rel or ':' in rel:raise ValueError('Image path must be a relative POSIX path')
                if Path(rel).is_absolute() or '..' in Path(rel).parts:raise ValueError('Unsafe image path')
                # Standard root metadata uses test/dish.png. A split-local metadata file can use dish.png.
                image=(metadata.parent/rel).resolve()
                if not image.is_relative_to(root):raise ValueError('Image escaped dataset directory')
                if image.stem!=dish:raise ValueError('ID does not match image filename stem')
                if not image.is_file():raise ValueError('Image file missing: '+rel)
                verify_image(image)
                totals={k:finite(raw[fields[k]],fields[k]) for k in ('kcal','mass_g','fat_g','carbs_g','protein_g')}
                ingredients=raw[fields['ingredients']]
                if not isinstance(ingredients,list) or not ingredients:raise ValueError('Missing ingredient labels')
                parsed=[]
                for i in ingredients:
                    if not isinstance(i,dict) or not isinstance(i.get('name'),str) or not i['name'].strip():raise ValueError('Invalid ingredient label')
                    grams=finite(i.get('grams'),'ingredient.grams')
                    p={'id':str(i.get('id','')),'name':i['name'],'grams':grams}
                    for src,dst in [('calories','kcal'),('fat','fat_g'),('carb','carbs_g'),('protein','protein_g')]:
                        p[dst]=finite(i[src],'ingredient.'+src) if src in i else None
                    parsed.append(p)
                if dish in seen:
                    duplicates+=1;raise ValueError('Duplicate dish ID')
                seen.add(dish)
                # Multiple frames of the same plate must not silently become independent samples.
                plate_signature=json.dumps(sorted((i['id'] or i['name'].lower(),round(i['grams'],3)) for i in parsed))
                discrepancy={k:totals[k]-sum(i[k] for i in parsed) for k in ('kcal','fat_g','carbs_g','protein_g') if all(i[k] is not None for i in parsed)}
                valid.append({'dish_id':dish,'image_path':str(image),'ingredients':parsed,**totals,
                              'plate_group':hashlib.sha256(plate_signature.encode()).hexdigest(),
                              'metadata_line':line_no,'label_sum_discrepancy':discrepancy})
            except (ValueError,KeyError,TypeError,OSError) as e:
                errors.append({'line':line_no,'reason':str(e)})
    audit={'metadata_path':str(metadata),'metadata_sha256':sha256(metadata),'valid_records':len(valid),
           'invalid_records':len(errors),'duplicate_ids':duplicates,'errors':errors,
           'observed_fields':dict(keys),'field_types':{k:dict(v) for k,v in types.items()},
           'schema_mapping':fields,'units':{'mass_g':'g','kcal':'kcal','fat_g':'g','carbs_g':'g','protein_g':'g'},
           'units_basis':'Publisher food-nutrients metadata contract; local values checked, units not inferable from numbers alone.',
           'repeated_plate_groups':len(valid)-len({r['plate_group'] for r in valid}),
           'label_sum_discrepancies':[{'dish_id':r['dish_id'],**r['label_sum_discrepancy']} for r in valid if any(abs(v)>0.02 for v in r['label_sum_discrepancy'].values())]}
    return valid,audit

def select_stratified(rows,n,seed):
    rng=random.Random(seed)
    groups={}
    for r in sorted(rows,key=lambda x:x['dish_id']):groups.setdefault(r['plate_group'],[]).append(r)
    unique=[rng.choice(group) for _,group in sorted(groups.items())]
    if len(unique)<n:raise ValueError(f'Only {len(unique)} distinct plate groups available for {n} requested images')
    # Energy quartiles crossed with three ingredient-count buckets; no inference sees these labels.
    sorted_energy=sorted(unique,key=lambda r:(r['kcal'],r['dish_id']))
    strata={}
    for rank,r in enumerate(sorted_energy):
        key=(min(3,4*rank//len(sorted_energy)),min(2,(len(r['ingredients'])-1)//3))
        strata.setdefault(key,[]).append(r)
    queues=[]
    for key,items in sorted(strata.items()):rng.shuffle(items);queues.append(items)
    rng.shuffle(queues);chosen=[]
    while len(chosen)<n:
        for q in queues:
            if q and len(chosen)<n:chosen.append(q.pop())
    return sorted(chosen,key=lambda x:x['dish_id'])

def prepare_dataset(dataset_root,out,n=5,seed=20261013,metadata=None,fields=None,mock=False):
    out=Path(out)
    if (out/'manifest.json').exists():raise ValueError('Prepared selection already exists. Use a new output directory to preserve selection.')
    rows,audit=load_dataset(dataset_root,metadata,fields)
    out.mkdir(parents=True,exist_ok=True);save_json(out/'dataset_audit.json',audit)
    if not rows:raise ValueError('No valid metadata records. Read dataset_audit.json before running.')
    selected=select_stratified(rows,n,seed)
    images=[{'dish_id':r['dish_id'],'image_path':r['image_path'],'image_sha256':sha256(r['image_path'])} for r in selected]
    save_json(out/'manifest.json',{'schema_version':1,'mode':'MOCK' if mock else 'REAL','seed':seed,
                                 'image_count':n,'images':images})
    write_csv(out/'selected_images.csv',['dish_id','image_path','image_sha256'],images)
    truth={'mode':'MOCK' if mock else 'REAL','source':'SYNTHETIC_TEST_ONLY' if mock else 'LOCAL_FOOD_NUTRIENTS_METADATA',
           'metadata_sha256':audit['metadata_sha256'],'schema_mapping':audit['schema_mapping'],
           'records':[{k:v for k,v in r.items() if k not in ('image_path','plate_group')} for r in selected]}
    save_json(out/'ground_truth.json',truth)
    save_json(out/'truth_integrity.json',{'sha256':sha256(out/'ground_truth.json')})
    save_json(out/'selection_audit.json',{'selection_rule':'seeded representative per exact ingredient/gram plate group, balanced energy-quartile x ingredient-count strata',
                                         'seed':seed,'n':n,'appearance_diversity':'Not evaluated automatically. Nutritional/ingredient diversity only.'})
    return images,audit
