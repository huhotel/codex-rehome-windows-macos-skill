"""Read-only lineage audit and staged standalone export for paginated rollouts.

Profile: observed 0.158.0-alpha.2.1 physical filename/header/ordinal semantics.
Exports are candidates, never a claim of native readability or a live restore.
"""
import argparse,copy,hashlib,json,re,sqlite3
from pathlib import Path
from migration_safety import scrub
from history_runtime import digest,encode,dump,require,state_db,connect_ro

UUID=r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
NAME=re.compile(r'rollout-\d{4}-\d\d-\d\dT\d\d-\d\d-\d\d-('+UUID+r')(?:_('+UUID+r'))?\.jsonl$')

def catalog(home):
 home=Path(home).resolve();out={}
 for folder in ['sessions','archived_sessions']:
  for path in (home/folder).rglob('*.jsonl'):
   match=NAME.fullmatch(path.name)
   if not match:continue
   require(path.resolve().is_relative_to(home),'Rollout escapes source home: '+str(path))
   with path.open('rb') as f:
    try:first=json.loads(f.readline())
    except (ValueError,UnicodeError):continue
   if first.get('type')!='session_meta':continue
   meta=first.get('payload',{});stable=match[1];physical=match[2] or stable
   issues=[]
   if meta.get('id')!=stable:issues.append('Filename/header stable ID mismatch')
   if meta.get('session_id',stable)!=stable:issues.append('Header session identity mismatch')
   if physical in out:
    out[physical]['issues'].append('Ambiguous duplicate physical rollout ID');continue
   out[physical]={'physical_id':physical,'stable_id':stable,'path':str(path),'base':meta.get('history_base'),'history_mode':meta.get('history_mode'),'issues':issues}
 return out

def records(path,stop):
 offset=0
 with Path(path).open('rb') as f:
  while offset<stop:
   start=offset;line=f.readline()
   require(bool(line) and line.endswith(b'\n'),'Incomplete record at byte '+str(offset)+' in '+str(path))
   offset+=len(line)
   require(offset<=stop,'Cutoff splits a UTF-8 JSONL record: '+str(path))
   yield start,offset,json.loads(line)
 require(offset==stop,'Cutoff is past source EOF: '+str(path))

def resolve(index,leaf):
 found=[s for s in index.values() if Path(s['path']).samefile(leaf)]
 require(len(found)==1,'Selected current rollout must resolve uniquely: '+str(leaf))
 current=found[0];chain=[];seen=set();cutoff=None
 while True:
  require(not current.get('issues'),'; '.join(current.get('issues',[]))+': '+current['path'])
  rid=current['physical_id'];require(rid not in seen,'Physical lineage cycle: '+rid);seen.add(rid)
  require(current['history_mode']=='paginated','Unsupported history mode; preserve original and inspect version: '+rid)
  p=Path(current['path']);before=digest(p);size=p.stat().st_size
  stop=cutoff['end_byte_offset'] if cutoff else size
  require(type(stop) is int and 0<stop<=size,'Invalid/past-EOF byte cutoff for '+rid)
  first=None;last=None;count=0;body=hashlib.sha256();nonmeta=0
  for _,_,r in records(p,stop):
   ordinal=r.get('ordinal');require(type(ordinal) is int,'Missing integer ordinal: '+rid)
   require(last is None or ordinal==last+1,'Noncontiguous source ordinals: '+rid)
   if count==0:
    require(r.get('type')=='session_meta','Missing segment header: '+rid);first=ordinal
   else:
    require(r.get('type')!='session_meta','Unexpected metadata inside segment: '+rid)
    body.update(encode(r));nonmeta+=1
   count+=1;last=ordinal
  base=current['base']
  require(first==(base['end_ordinal_exclusive'] if base else 0),'Segment start/parent ordinal mismatch: '+rid)
  if cutoff:require(last+1==cutoff['end_ordinal_exclusive'],'Cutoff byte/ordinal mismatch: '+rid)
  require(digest(p)==before,'Source changed during audit: '+rid)
  chain.append({**current,'included_bytes':stop,'included_records':count,'nonmeta_records':nonmeta,'first_ordinal':first,'end_ordinal_exclusive':last+1,'source_sha256':before,'ordered_nonmeta_sha256':body.hexdigest()})
  if not base:break
  parent=base.get('thread_id');require(parent in index,'Missing source rollout: '+str(parent))
  cutoff=base;current=index[parent]
 chain.reverse();return chain

def audit(home,ids):
 require(ids and len(ids)==len(set(ids)),'Select a nonempty unique list of thread IDs')
 index=catalog(home);result={'profile':'paginated-0.158','threads':{},'errors':[],'native_verified':False}
 with connect_ro(state_db(Path(home))) as c:
  for tid in ids:
   try:
    row=c.execute('SELECT * FROM threads WHERE id=?',(tid,)).fetchone()
    require(row is not None,'Selected thread missing from state: '+tid)
    chain=resolve(index,row['rollout_path'])
    require(chain[-1]['stable_id']==tid,'Selected row/leaf identity mismatch: '+tid)
    result['threads'][tid]={'title':row['title'],'segments':chain}
   except (ValueError,RuntimeError,OSError,KeyError,TypeError) as e:
    result['errors'].append({'selected_thread_id':tid,'error':str(e)})
 result['structural_pass']=not result['errors'];return result

def clean(obj):
 if isinstance(obj,str):return scrub(obj)[0]
 if isinstance(obj,list):return [clean(v) for v in obj]
 if isinstance(obj,dict):return {k:clean(v) for k,v in obj.items()}
 return obj

def export(report,dest,redact=True):
 require(report.get('structural_pass') and not report['errors'],'Refuse partial export with missing/broken histories')
 dest=Path(dest);require(not dest.exists(),'Use a new staging directory');dest.mkdir(parents=True)
 ledger=[]
 for tid,t in report['threads'].items():
  segments=t['segments'];leaf=segments[-1]
  for s in segments:require(digest(s['path'])==s['source_sha256'],'Source changed since audit: '+s['physical_id'])
  with Path(leaf['path']).open('rb') as f:header=json.loads(f.readline())
  header=copy.deepcopy(header);header['ordinal']=0
  # Only after validated closure. Actual body equivalence and native reads
  # are separately required before this candidate can be restored.
  header['payload'].pop('history_base',None)
  path=dest/('rollout-2000-01-01T00-00-00-'+tid+'.jsonl')
  raw=hashlib.sha256();transformed=hashlib.sha256();n=0;last=0
  with path.open('xb') as fo:
   fo.write(encode(clean(header) if redact else header))
   for s in segments:
    for _,_,row in records(s['path'],s['included_bytes']):
     if row['type']=='session_meta':continue
     require(row['ordinal']>last,'Non-increasing expanded record order: '+tid);last=row['ordinal']
     raw.update(encode(row));data=encode(clean(row) if redact else row);transformed.update(data);fo.write(data);n+=1
  require(n==sum(s['nonmeta_records'] for s in segments),'Expanded history count mismatch')
  for s in segments:require(digest(s['path'])==s['source_sha256'],'Source changed during export: '+s['physical_id'])
  ledger.append({'id':tid,'file':path.name,'records':n,'source_ordered_sha256':raw.hexdigest(),'sanitized_ordered_sha256':transformed.hexdigest(),'sha256':digest(path),'bytes':path.stat().st_size})
 dump(dest/'export-ledger.json',{'native_verified':False,'sanitized':redact,'history_format_conversion':'candidate; native equivalence still required','threads':ledger})
 return ledger

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--home',required=True);ap.add_argument('--thread-id',action='append',required=True);ap.add_argument('--report',required=True);ap.add_argument('--export-dir');ap.add_argument('--private-unredacted-probe',action='store_true',help='Local-only equivalence probe. Never transfer or package this output.')
 a=ap.parse_args();home=Path(a.home).expanduser().resolve();out=Path(a.report).resolve()
 require(not out.is_relative_to(home),'Write reports outside the original Codex home')
 if a.export_dir:require(not Path(a.export_dir).resolve().is_relative_to(home),'Export outside original Codex home')
 r=audit(home,a.thread_id);require(not out.exists(),'Preserve existing audit reports');dump(out,r)
 if not r['structural_pass']:raise SystemExit('Lineage FAILED; see per-thread errors in '+str(out))
 if a.export_dir:export(r,a.export_dir,not a.private_unredacted_probe)
 print('Lineage structure passed for',len(a.thread_id),'threads. Native compatibility and UI acceptance remain pending.')
