"""Identity normalization only. Never infer a species, cut or preparation."""
import re
import unicodedata

SYNONYMS = {'carrot':'carrots', 'tomato':'tomatoes', 'potato':'potatoes',
             'egg':'eggs', 'cucumber':'cucumbers', 'onions':'onion',
             'strawberry':'strawberries', 'banana':'bananas', 'chickpeas':'chickpea'}
STATES = ('raw','cooked','fried','boiled','roasted','steamed','grilled','baked','dried','unspecified')

def normalize(value):
    value = unicodedata.normalize('NFKC', str(value)).lower().strip()
    return ' '.join(re.sub(r'[^\w\s]', ' ', value, flags=re.UNICODE).split())

def identity(value):
    return ' '.join(SYNONYMS.get(t,t) for t in normalize(value).split())

def infer_state(name):
    text=normalize(name)
    # USDA 'cooked, dry heat' describes cooking, not dehydration of the ingredient.
    text=re.sub(r'\bdry\s+heat\b','cooked',text)
    n = set(text.split())
    # Dry is an explicitly different weight basis, never cooked/raw automatically.
    if 'raw' in n and n.intersection({'cooked','fried','boiled','roasted'}):
        return 'unspecified', 'conflicting_description'
    # Gerunds such as 'oil for frying' describe intended use, not its current state.
    for state, words in [('fried',{'fried'}),('boiled',{'boiled'}),
                         ('roasted',{'roasted'}),('grilled',{'grilled'}),
                         ('steamed',{'steamed'}),('baked',{'baked'}),
                         ('raw',{'raw'}),('dried',{'dried','dry','dehydrated'}),
                         ('cooked',{'cooked','stewed','braised','simmered','poached','scrambled'})]:
        if n.intersection(words): return state, 'explicit_description_keyword'
    return 'unspecified', 'no_explicit_preparation'

def compatible(predicted, stored):
    # Unknown preparation is not authority to choose a prepared variant.
    return predicted == stored
