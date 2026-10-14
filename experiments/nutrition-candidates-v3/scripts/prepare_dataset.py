import argparse,json
from pathlib import Path
from src.common import ROOT
from src.dataset import prepare_dataset

def main():
    p=argparse.ArgumentParser(description='Use an already-downloaded local dataset. Never downloads images.')
    p.add_argument('--dataset-root',type=Path,required=True);p.add_argument('--metadata',type=Path)
    p.add_argument('--count',type=int,choices=[5,30],default=5);p.add_argument('--seed',type=int,default=20261013)
    p.add_argument('--out',type=Path);p.add_argument('--schema',type=Path)
    a=p.parse_args();out=a.out or ROOT/'data/prepared'/('smoke' if a.count==5 else 'pilot')
    images,audit=prepare_dataset(a.dataset_root,out,a.count,a.seed,a.metadata,json.loads(a.schema.read_text()) if a.schema else None)
    print(f"Prepared {len(images)} images in {out}. Valid rows={audit['valid_records']}, rejected={audit['invalid_records']}. No image download.")
if __name__=='__main__':main()
