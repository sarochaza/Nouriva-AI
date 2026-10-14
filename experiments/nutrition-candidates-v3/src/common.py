"""Small dependency-free helpers. No access to ground truth in inference modules."""
from pathlib import Path
import csv, json, os, hashlib, time, tempfile
ROOT = Path(__file__).resolve().parents[1]

def load_json(path):
    with open(path,encoding='utf-8') as f: return json.load(f)

def save_json(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(data,indent=2,ensure_ascii=False)
    # Close the temporary file before replacing on Windows. Unique names also
    # prevent separate writers from sharing one temporary file.
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                                     prefix=path.name+'.',suffix='.tmp',delete=False) as f:
        p=Path(f.name)
        try:
            f.write(text)
        except BaseException:
            f.close()
            p.unlink(missing_ok=True)
            raise
    try:
        for attempt in range(7):
            try:
                p.replace(path)
                return
            except PermissionError:
                if attempt == 6: raise
                time.sleep(0.02 * 2**attempt)
    finally:
        try: p.unlink(missing_ok=True)
        except OSError: pass  # Keep the original failure if cleanup is denied.

def file_error_details(error):
    """Safe file diagnostics without exception text, credentials or user paths."""
    details={}
    if isinstance(error,OSError):
        for field in ('errno','winerror'):
            value=getattr(error,field,None)
            if isinstance(value,int): details[field]=value
        for field in ('filename','filename2'):
            value=getattr(error,field,None)
            if isinstance(value,(str,bytes)):
                details[field]=str(Path(os.fsdecode(value)).name)
    return details

def write_csv(path,fields,rows):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with open(path,'w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(rows)

def read_csv(path):
    with open(path,newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))

def read_env():
    p=ROOT/'.env'
    if p.exists():
        for raw in p.read_text(encoding='utf-8-sig').splitlines():
            s=raw.strip()
            if s and not s.startswith('#') and '=' in s:
                k,v=s.split('=',1)
                if k.strip() not in os.environ: os.environ[k.strip()] = v.strip().strip('"').strip("'")

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for c in iter(lambda:f.read(2**20),b''): h.update(c)
    return h.hexdigest()

def utcnow():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
