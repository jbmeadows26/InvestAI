"""Official Treasury data with provenance, QA and benchmark-gated research."""
import argparse, hashlib, json, math, urllib.request, xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
BASE='https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value='
DOC='https://home.treasury.gov/treasury-daily-interest-rate-xml-feed'
def parse(raw):
    rows=[]
    for p in ET.fromstring(raw).iter():
        if p.tag.split('}')[-1]!='properties': continue
        v={c.tag.split('}')[-1]:c.text for c in p}
        if not v.get('NEW_DATE') or v.get('BC_10YEAR') is None or v.get('BC_2YEAR') is None: continue
        rows.append({'date':v['NEW_DATE'][:10],'y10':float(v['BC_10YEAR']),'y2':float(v['BC_2YEAR'])})
    if not rows: raise ValueError('No complete observations')
    return rows
def validate(rows,asof):
    dates=set()
    for r in rows:
        d=date.fromisoformat(r['date'])
        if d>asof or d in dates: raise ValueError('Future or duplicate observation')
        dates.add(d)
        for k in ('y10','y2'):
            if not math.isfinite(r[k]) or not -5<=r[k]<=30: raise ValueError('Invalid yield')
    rows=sorted(rows,key=lambda r:r['date'])
    if not rows or (asof-date.fromisoformat(rows[-1]['date'])).days>7: raise ValueError('Missing or stale series')
    return rows
def forecast(rows,horizon=5):
    y=np.array([r['y10'] for r in rows]); s=y-np.array([r['y2'] for r in rows]); n=len(y)
    if n<550: return {'status':'withheld','reason':'At least 550 complete observations required'}
    def x(i): return [y[i],s[i],y[i]-y[i-1],y[i]-y[i-5],y[i]-y[i-20],np.std(np.diff(y[i-20:i+1]))]
    def model(i):
        idx=list(range(20,i-horizon+1))
        return make_pipeline(StandardScaler(),Ridge(alpha=10)).fit([x(j) for j in idx],[y[j+horizon]-y[j] for j in idx])
    errs=[]; base=[]; residual=[]
    for i in range(n-250,n-horizon,horizon):
        p=float(model(i).predict([x(i)])[0]); actual=y[i+horizon]-y[i]
        errs.append(abs(p-actual)); base.append(abs(actual)); residual.append(actual-p)
    a=float(np.mean(errs)); b=float(np.mean(base))
    out={'status':'withheld','horizon_sessions':horizon,'model':'ridge fixed alpha=10','test_origins':len(errs),'mae_bp':100*a,'benchmark_mae_bp':100*b,'reason':'Benchmark gate requires 10% MAE improvement and 40 disjoint tests'}
    if len(errs)>=40 and b>0 and a<=.9*b:
        p=float(y[-1]+model(n-1).predict([x(n-1)])[0]); q=np.quantile(residual,[.1,.9])
        out.update(status='research_candidate',reason='Independent evidence and prospective calibration still required',candidate_pct=p,uncalibrated_residual_range_pct=[float(p+q[0]),float(p+q[1])])
    return out
def collect(out,asof):
    out.mkdir(parents=True,exist_ok=True); rawdir=out/'raw'; rawdir.mkdir(exist_ok=True)
    report={'source':'US Treasury daily par yield curve','documentation':DOC,'retrieved_utc':datetime.now(timezone.utc).isoformat(),'as_of':asof.isoformat(),'requests':[],'status':'blocked','forecast':{'status':'withheld'}}
    try:
        rows=[]
        for yr in range(asof.year-3,asof.year+1):
            url=BASE+str(yr); req=urllib.request.Request(url,headers={'User-Agent':'InvestAI research pilot/0.1'})
            with urllib.request.urlopen(req,timeout=20) as response: raw=response.read(10_000_001)
            if len(raw)>10_000_000: raise ValueError('Payload too large')
            sha=hashlib.sha256(raw).hexdigest(); (rawdir/(sha+'.xml')).write_bytes(raw)
            report['requests'].append({'url':url,'sha256':sha,'retrieved_utc':datetime.now(timezone.utc).isoformat()}); rows+=parse(raw)
        rows=validate(rows,asof); report.update(status='observations_validated',latest=rows[-1],observations=len(rows),forecast=forecast(rows),history=rows[-250:])
    except Exception as e: report['error']=f'{type(e).__name__}: {e}'
    payload=json.dumps(report,indent=2,allow_nan=False); stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    (out/(stamp+'.json')).write_text(payload); (out/'latest.json').write_text(payload)
    return report
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='data'); ap.add_argument('--as-of',default=date.today().isoformat()); args=ap.parse_args()
    r=collect(Path(args.out),date.fromisoformat(args.as_of)); print(json.dumps({k:v for k,v in r.items() if k!='history'},indent=2)); raise SystemExit(0 if r['status']=='observations_validated' else 1)
