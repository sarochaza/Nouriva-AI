import argparse,json
from src.common import ROOT
from nutrition_engine.ingredient_matcher import IngredientMatcher

def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--state',required=True);a=p.parse_args()
    m=IngredientMatcher(ROOT/'nutrition_database/ingredients.sqlite')
    try:print(json.dumps(m.match(a.name,a.state),indent=2,ensure_ascii=False))
    finally:m.close()
if __name__=='__main__':main()
