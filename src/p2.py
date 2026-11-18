#!/usr/bin/env python3
import csv,gzip,io,json,os,time,urllib.request
from datetime import datetime,timedelta,timezone
from pathlib import Path
from common import encrypt_file
def main():
    secret=os.environ["DATA_ENCRYPTION_KEY"].strip(); hour=(datetime.now(timezone.utc)-timedelta(hours=1)).replace(minute=0,second=0,microsecond=0)
    url=f"https://data.gharchive.org/{hour:%Y-%m-%d-%-H}.json.gz"; tmp=Path("output"); tmp.mkdir(exist_ok=True); raw=tmp/"gh.json.gz"
    for i in range(5):
      try: urllib.request.urlretrieve(url,raw); break
      except Exception:
       if i==4: raise
       time.sleep(120)
    latest={}
    with gzip.open(raw,"rt",encoding="utf-8",errors="replace") as f:
      for line in f:
       try:e=json.loads(line)
       except Exception:continue
       r=e.get("repo") or {}; rid=r.get("id"); n=str(r.get("name") or "")
       if not isinstance(rid,int) or rid<=0 or "/" not in n:continue
       u,rn=n.split("/",1); d=str(e.get("created_at") or "")[:10].replace("-","") or hour.strftime("%Y%m%d"); latest[rid]=(rid,u,rn,d)
    gz=tmp/"gharchive.csv.gz"
    with gz.open("wb") as b:
      with gzip.GzipFile(filename="",mode="wb",fileobj=b,compresslevel=6,mtime=0) as z:
       with io.TextIOWrapper(z,encoding="utf-8",newline="") as f:
        w=csv.writer(f,lineterminator="\n"); w.writerow(["repo_id","username","repo_name","valid_date"]); w.writerows(latest[k] for k in sorted(latest))
    encrypt_file(gz,tmp/"gharchive.csv.gz.enc",secret); gz.unlink(); raw.unlink(); print(f"hour={hour.isoformat()} repos={len(latest)}")
if __name__=="__main__":main()
