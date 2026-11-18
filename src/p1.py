#!/usr/bin/env python3
import argparse, asyncio, csv, gzip, io, os, time
from datetime import datetime, timezone
from pathlib import Path
import aiohttp
from common import encrypt_file
URL="https://api.github.com/events?per_page=100"
def row(e):
    r=e.get("repo") or {}; rid=r.get("id"); n=str(r.get("name") or ""); eid=str(e.get("id") or "")
    if not eid or not isinstance(rid,int) or rid<=0 or "/" not in n:return None
    u,rn=n.split("/",1); d=str(e.get("created_at") or "")
    try: vd=datetime.fromisoformat(d.replace("Z","+00:00")).strftime("%Y%m%d")
    except ValueError: vd=datetime.now(timezone.utc).strftime("%Y%m%d")
    return eid,rid,u,rn,vd
async def collect(token,count,interval):
    h={"Accept":"application/vnd.github+json","Authorization":f"Bearer {token}","X-GitHub-Api-Version":"2022-11-28","User-Agent":"x8f7a9k2m"}
    seen=set(); latest={}; start=time.monotonic()
    async with aiohttp.ClientSession(headers=h,timeout=aiohttp.ClientTimeout(total=30)) as s:
      for i in range(count):
        wait=start+i*interval-time.monotonic()
        if wait>0: await asyncio.sleep(wait)
        async with s.get(URL) as resp:
          if resp.status in (403,429):
            delay=int(resp.headers.get("Retry-After","60")); print(f"limited {resp.status} wait={delay}",flush=True); await asyncio.sleep(delay); continue
          resp.raise_for_status(); events=await resp.json(); rem=int(resp.headers.get("X-RateLimit-Remaining","1"))
        added=0
        for e in events:
          x=row(e)
          if not x or x[0] in seen: continue
          seen.add(x[0]); latest[x[1]]=x[1:]; added+=1
        print(f"request={i+1}/{count} new={added} repos={len(latest)} remaining={rem}",flush=True)
        if rem<=0: break
    return latest
def main():
    a=argparse.ArgumentParser(); a.add_argument("--requests",type=int,default=int(os.getenv("REQUESTS_TARGET","5000"))); a.add_argument("--interval",type=float,default=.72); x=a.parse_args()
    token=os.environ["GH_EVENTS_PAT"].strip(); secret=os.environ["DATA_ENCRYPTION_KEY"].strip(); out=Path("output"); out.mkdir(exist_ok=True)
    latest=asyncio.run(collect(token,x.requests,x.interval)); gz=out/"events.csv.gz"
    with gz.open("wb") as raw:
      with gzip.GzipFile(filename="",mode="wb",fileobj=raw,compresslevel=6,mtime=0) as z:
       with io.TextIOWrapper(z,encoding="utf-8",newline="") as f:
        w=csv.writer(f,lineterminator="\n"); w.writerow(["repo_id","username","repo_name","valid_date"]); w.writerows(latest[k] for k in sorted(latest))
    encrypt_file(gz,out/"events.csv.gz.enc",secret); gz.unlink(); print(f"repos={len(latest)}")
if __name__=="__main__":main()
