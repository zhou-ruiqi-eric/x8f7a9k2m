#!/usr/bin/env python3
import argparse,base64,csv,gzip,hashlib,io,json,mimetypes,os,shutil,tempfile,urllib.parse,urllib.request,zipfile,zlib
from datetime import datetime,timezone,timedelta
from pathlib import Path
from common import decrypt_bytes
BASE="https://fiatdock-data.pages.dev"; SHARDS=10000
def api(url,token,method="GET",data=None,headers=None):
 h={"Authorization":f"Bearer {token}","User-Agent":"x8f7a9k2m"}; h.update(headers or {})
 r=urllib.request.Request(url,data=data,method=method,headers=h); return urllib.request.urlopen(r).read()
def get_upload_jwt(account,project,token): return json.loads(api(f"https://api.cloudflare.com/client/v4/accounts/{account}/pages/projects/{project}/upload-token",token))["result"]["jwt"]
def cf(jwt,path,data): return json.loads(api(f"https://api.cloudflare.com/client/v4/pages/assets/{path}",jwt,"POST",json.dumps(data).encode(),{"Content-Type":"application/json"}))
def md5(b): return hashlib.md5(b).hexdigest()
def name_shard(k): return (zlib.crc32(k.encode())&0xffffffff)%SHARDS
def read_csv_gz(b): return list(csv.reader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(b)),encoding="utf-8")))
def make_gz(rows):
 s=io.StringIO(); csv.writer(s,lineterminator="\n").writerows(rows); out=io.BytesIO()
 with gzip.GzipFile(filename="",mode="wb",fileobj=out,compresslevel=6,mtime=0) as g:g.write(s.getvalue().encode())
 return out.getvalue()
def fetch(path): return urllib.request.urlopen(BASE+path).read()
def download_prepared():
 token=os.environ["GH_TOKEN"]; repo=os.environ["GITHUB_REPOSITORY"]; run=os.environ.get("PREPARE_RUN_ID")
 data=json.loads(api(f"https://api.github.com/repos/{repo}/actions/runs/{run}/artifacts",token)); a=next(x for x in data["artifacts"] if x["name"].startswith("p-"))
 blob=api(a["archive_download_url"],token); z=zipfile.ZipFile(io.BytesIO(blob)); Path("output").mkdir(exist_ok=True); Path("output/prepared.csv.gz.enc").write_bytes(z.read(next(n for n in z.namelist() if n.endswith(".enc"))))
def init_manifest(directory):
 root=Path(directory); m={}
 for p in sorted(root.rglob("*.csv.gz")): m["/"+p.relative_to(root).as_posix()]=md5(p.read_bytes())
 if len(m)!=20000: raise SystemExit(f"expected 20000 files, got {len(m)}")
 Path("state/index.json").write_text(json.dumps(m,separators=(",",":"),sort_keys=True)+"\n"); print("manifest=20000")
def publish():
 secret=os.environ["DATA_ENCRYPTION_KEY"]; account=os.environ["CLOUDFLARE_ACCOUNT_ID"]; token=os.environ["CLOUDFLARE_API_TOKEN"]; project=os.getenv("CLOUDFLARE_PROJECT_NAME","fiatdock-data")
 enc=Path("output/prepared.csv.gz.enc").read_bytes(); plain=decrypt_bytes(enc,secret)
 with gzip.GzipFile(fileobj=io.BytesIO(plain)) as g: pending=list(csv.DictReader(io.TextIOWrapper(g,encoding="utf-8")))
 updates={int(x["repo_id"]):(x["username"],x["repo_name"],int(x["valid_date"])) for x in pending}; manifest=json.loads(Path("state/index.json").read_text())
 if len(manifest)!=20000: raise SystemExit("manifest must contain 20000 paths")
 repo_groups={}
 for rid,v in updates.items(): repo_groups.setdefault(rid%SHARDS,{})[rid]=v
 old_names={}; changed_assets={}
 for shard,group in repo_groups.items():
  path=f"/repo/{shard:04d}.csv.gz"; rows=read_csv_gz(fetch(path)); current={int(r[0]):r for r in rows if r}
  for rid,(u,rn,d) in group.items():
   old=current.get(rid)
   if old: old_names[rid]=(old[1],old[2])
   if not old or d>int(old[3]): current[rid]=[str(rid),u,rn,f"{d:08d}"]
  data=make_gz([current[k] for k in sorted(current)]); h=md5(data)
  if h!=manifest[path]: changed_assets[path]=(h,data); manifest[path]=h
 name_groups={}
 for rid,(u,rn,d) in updates.items():
  targets={name_shard(f"{u}/{rn}".lower())}
  if rid in old_names: targets.add(name_shard(f"{old_names[rid][0]}/{old_names[rid][1]}".lower()))
  for s in targets: name_groups.setdefault(s,set()).add(rid)
 for shard,rids in name_groups.items():
  path=f"/name/{shard:04d}.csv.gz"; rows=read_csv_gz(fetch(path)); kept=[r for r in rows if r and int(r[1]) not in rids]
  for rid in rids:
   if rid not in updates: continue
   u,rn,d=updates[rid]; key=f"{u}/{rn}".lower()
   if name_shard(key)==shard: kept.append([key,str(rid),u,rn,f"{d:08d}"])
  kept.sort(key=lambda r:(r[0],int(r[1]))); data=make_gz(kept); h=md5(data)
  if h!=manifest[path]: changed_assets[path]=(h,data); manifest[path]=h
 jwt=get_upload_jwt(account,project,token); hashes=[h for h,d in changed_assets.values()]
 missing=set()
 for i in range(0,len(hashes),500): missing.update(cf(jwt,"check-missing",{"hashes":hashes[i:i+500]})["result"])
 items=[]
 for path,(h,data) in changed_assets.items():
  if h in missing: items.append({"key":h,"value":base64.b64encode(data).decode(),"metadata":{"contentType":"application/gzip"},"base64":True})
  if len(items)==20: cf(jwt,"upload",items); items=[]
 if items: cf(jwt,"upload",items)
 boundary="----x8"+os.urandom(8).hex(); body=(f"--{boundary}\r\nContent-Disposition: form-data; name=\"manifest\"\r\n\r\n{json.dumps(manifest,separators=(',',':'))}\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"branch\"\r\n\r\nmain\r\n--{boundary}--\r\n").encode()
 result=json.loads(api(f"https://api.cloudflare.com/client/v4/accounts/{account}/pages/projects/{project}/deployments",token,"POST",body,{"Content-Type":f"multipart/form-data; boundary={boundary}"}))
 if not result.get("success"): raise SystemExit(result)
 Path("state/index.json").write_text(json.dumps(manifest,separators=(",",":"),sort_keys=True)+"\n")
 now=datetime.now(timezone.utc); clock={"last_publish_at":now.isoformat().replace("+00:00","Z"),"next_prepare_at":(now+timedelta(minutes=80)).isoformat().replace("+00:00","Z"),"next_publish_at":(now+timedelta(minutes=90)).isoformat().replace("+00:00","Z"),"artifact_cutoff_at":now.isoformat().replace("+00:00","Z")}; Path("state/clock.json").write_text(json.dumps(clock,separators=(",",":"))+"\n"); print(f"changed={len(changed_assets)} uploaded={len(missing)}")
def main():
 a=argparse.ArgumentParser(); a.add_argument("--download-prepared",action="store_true"); a.add_argument("--publish",action="store_true"); a.add_argument("--init-manifest"); x=a.parse_args()
 if x.init_manifest:init_manifest(x.init_manifest)
 elif x.download_prepared:download_prepared()
 elif x.publish:publish()
 else:a.error("choose an action")
if __name__=="__main__":main()
