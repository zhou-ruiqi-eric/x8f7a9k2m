#!/usr/bin/env python3
import csv,gzip,io,json,os,urllib.request,zipfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
from common import decrypt_bytes,encrypt_bytes
API=os.environ.get("GITHUB_API_URL","https://api.github.com")
def req(url,token):
 r=urllib.request.Request(url,headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json","User-Agent":"x8f7a9k2m"}); return urllib.request.urlopen(r).read()
def main():
 token=os.environ["GH_TOKEN"]; repo=os.environ["GITHUB_REPOSITORY"]; secret=os.environ["DATA_ENCRYPTION_KEY"]; now=datetime.now(timezone.utc)
 clock=json.loads(Path("state/clock.json").read_text()); due=clock.get("next_prepare_at")
 if due and now < datetime.fromisoformat(due.replace("Z","+00:00")): print("not due"); return
 cutoff=clock.get("artifact_cutoff_at"); cutoff_dt=datetime.fromisoformat(cutoff.replace("Z","+00:00")) if cutoff else now-timedelta(hours=3)
 data=json.loads(req(f"{API}/repos/{repo}/actions/artifacts?per_page=100",token)); selected=[]
 for a in data.get("artifacts",[]):
  created=datetime.fromisoformat(a["created_at"].replace("Z","+00:00")); name=a["name"]
  if not a.get("expired") and created>cutoff_dt and (name.startswith("e-") or name.startswith("g-")): selected.append(a)
 if not selected: print("no artifacts"); return
 latest={}; tmp=Path("tmp"); tmp.mkdir(exist_ok=True)
 for a in selected:
  blob=req(a["archive_download_url"],token); z=zipfile.ZipFile(io.BytesIO(blob))
  for member in z.namelist():
   if not member.endswith(".enc"): continue
   plain=decrypt_bytes(z.read(member),secret)
   with gzip.GzipFile(fileobj=io.BytesIO(plain),mode="rb") as gz:
    rows=csv.DictReader(io.TextIOWrapper(gz,encoding="utf-8"))
    priority=2 if a["name"].startswith("e-") else 1
    for x in rows:
     rid=int(x["repo_id"]); cand=(int(x["valid_date"]),priority,x["username"],x["repo_name"])
     if rid not in latest or cand[:2]>=latest[rid][:2]: latest[rid]=cand
 out=io.StringIO(); w=csv.writer(out,lineterminator="\n"); w.writerow(["repo_id","username","repo_name","valid_date"])
 for rid in sorted(latest): d,p,u,rn=latest[rid]; w.writerow([rid,u,rn,f"{d:08d}"])
 packed=io.BytesIO()
 with gzip.GzipFile(filename="",mode="wb",fileobj=packed,compresslevel=6,mtime=0) as gz: gz.write(out.getvalue().encode())
 Path("output").mkdir(exist_ok=True); Path("output/prepared.csv.gz.enc").write_bytes(encrypt_bytes(packed.getvalue(),secret)); print(f"artifacts={len(selected)} repos={len(latest)}")
if __name__=="__main__":main()
