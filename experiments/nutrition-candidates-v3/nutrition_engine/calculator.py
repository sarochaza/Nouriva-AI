"""One formula shared by all methods. Partial estimates never become complete totals."""
import math
CORE={'kcal':'kcal_100g','protein_g':'protein_g_100g','carbs_g':'carbs_g_100g','fat_g':'fat_g_100g'}

def calculate(ingredients, matcher):
    if not isinstance(ingredients,list) or not ingredients: raise ValueError('No ingredient estimates')
    sums={k:0. for k in CORE}; missing=set(); matched=[]; unmatched=[]
    total_mass=0.; matched_mass=0.; complete=0
    for item in ingredients:
        g=item.get('grams')
        if isinstance(g,bool) or not isinstance(g,(int,float)) or not math.isfinite(g) or not 0<=g<=3000:
            raise ValueError('Ingredient mass must be finite grams in [0,3000]')
        total_mass+=g; result=matcher.match(item['name'],item['state'])
        if result['status']!='MATCHED':
            unmatched.append({'prediction':item,**result});continue
        food=result['food'];missing_fields=[k for k,col in CORE.items() if food[col] is None]
        nutrients={k:(g/100*food[col] if food[col] is not None else None) for k,col in CORE.items()}
        for k,v in nutrients.items():
            if v is None: missing.add(k)
            else:sums[k]+=v
        matched_mass+=g;complete+=int(not missing_fields)
        matched.append({'prediction':item,'food_id':food['food_id'],'source_id':food['source_id'],
                        'source_food_id':food['source_food_id'],'matched_name':food['name_en'],'reference_state':food['state'],
                        'grams':g,'basis_g':100,'per_100g':{k:food[col] for k,col in CORE.items()},
                        'contribution':nutrients,'missing_nutrients':missing_fields,'provenance':food['provenance'],
                        'match_reason':result['reason'],'match_score':result['score'],
                        'alias_rationale':result.get('alias_rationale',[]),
                        'alternative_source_food_ids':result.get('alternative_source_food_ids',[])})
    partial={k:(None if k in missing or not matched else round(v,6)) for k,v in sums.items()}
    status='SUCCESS' if not unmatched and not missing else ('UNMATCHED' if not matched and all(x['status']=='UNMATCHED' for x in unmatched) else 'REVIEW_REQUIRED')
    return {'status':status,'nutrients':partial if status=='SUCCESS' else None,'partial_nutrients':partial,
            'matched':matched,'unmatched':unmatched,'match_coverage':len(matched)/len(ingredients),
            'complete_nutrient_coverage':complete/len(ingredients),
            'mass_match_coverage':matched_mass/total_mass if total_mass>0 else None,
            'predicted_ingredient_count':len(ingredients),'matched_ingredient_count':len(matched),
            'total_estimated_mass_g':total_mass,'complete':status=='SUCCESS'}
