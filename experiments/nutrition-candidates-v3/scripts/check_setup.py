import argparse,json,os,sqlite3,sys
from pathlib import Path
from contextlib import closing
from src.common import ROOT,read_env
from scripts.run_experiment import load_config
from src.ai import GroqClient

def main():
    p=argparse.ArgumentParser();p.add_argument('--list-models',action='store_true');p.add_argument('--dataset-root',type=Path);a=p.parse_args()
    if sys.version_info<(3,10):raise SystemExit('Python 3.10+ required')
    cfg=load_config();db=Path(cfg['database_path']);db=db if db.is_absolute() else ROOT/db
    if not db.is_file():raise SystemExit('Database missing. Run python -m scripts.prepare_database')
    with closing(sqlite3.connect(db)) as c:
        integrity=c.execute('PRAGMA integrity_check').fetchone()[0];n=c.execute('SELECT count(*) FROM foods').fetchone()[0]
    if integrity!='ok':raise SystemExit('SQLite integrity check failed')
    read_env();has_key=bool(os.environ.get('GROQ_API_KEY')) and not os.environ.get('GROQ_API_KEY','').startswith('PASTE_')
    print(json.dumps({'python':sys.version.split()[0],'sqlite_integrity':integrity,'reference_foods':n,'api_key_present':has_key,
                      'default_model':cfg['single_model'],'ensemble_mode':cfg['ensemble_mode'],'real_api_validation':'NOT VERIFIED'},indent=2))
    if a.dataset_root:print('Dataset directory exists: '+str(a.dataset_root.is_dir()))
    if a.list_models:
        ids=GroqClient(cfg['api']).list_models();print('\n'.join(ids));print('Availability alone does not prove vision or JSON support. Check Groq vision documentation.')
if __name__=='__main__':main()
