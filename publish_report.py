"""Export a public audit view, never experimental forecast numbers."""
import json
from pathlib import Path
src=Path('data/latest.json')
if src.exists():
    r=json.loads(src.read_text())
else:
    r={'status':'blocked','error':'No collection report generated','forecast':{'status':'withheld'}}
f=r.get('forecast',{})
r['forecast']={k:v for k,v in f.items() if k in {'status','reason','horizon_sessions','model','test_origins','mae_bp','benchmark_mae_bp','benchmark'}}
r['forecast']['status']='withheld'
Path('site/latest.json').write_text(json.dumps(r,indent=2,allow_nan=False))
