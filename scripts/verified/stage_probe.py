"""Build a fresh isolated native-reader home; never copy credentials/config."""
import argparse,json,shutil,hashlib
from pathlib import Path
from history_runtime import connect_ro,connect_rw,state_db,put_row,dump,require,digest,merge_history
from rpc_reader import Rpc

def stage(source,audit,dest,cli,flat=None):
 source=Path(source).resolve();dest=Path(dest).resolve()
 require(not dest.exists() and not dest.is_relative_to(source),'Use a new directory outside source home')
 require(audit.get('structural_pass') and not audit.get('errors'),'Need complete lineage audit')
 dest.mkdir(parents=True);(dest/'sessions').mkdir()
 dump(dest/'.rehome-isolated.json',{'purpose':'migration-verification','source_home':str(source)})
 copied={};targets={};export_hashes={}
 for tid,t in audit['threads'].items():
  if flat:
   entries=json.loads((Path(flat)/'export-ledger.json').read_text(encoding='utf-8'))['threads'];entry=next(e for e in entries if e['id']==tid)
   src=Path(flat)/entry['file'];require(digest(src)==entry['sha256'],'Candidate checksum mismatch')
   target=dest/'sessions'/src.name;shutil.copy2(src,target);targets[tid]=target
   export_hashes[tid]=entry['sha256']
  else:
   for s in t['segments']:
    require(digest(s['path'])==s['source_sha256'],'Source changed since audit')
    rid=s['physical_id'];copied[rid]=max([copied.get(rid,s),s],key=lambda x:x['included_bytes'])
   targets[tid]=dest/'sessions'/Path(t['segments'][-1]['path']).name
 for s in copied.values():
  with Path(s['path']).open('rb') as fi,(dest/'sessions'/Path(s['path']).name).open('xb') as fo:
   remaining=s['included_bytes']
   while remaining:
    data=fi.read(min(remaining,8*1024*1024));require(bool(data),'Source shortened while staging');fo.write(data);remaining-=len(data)
  require(digest(s['path'])==s['source_sha256'],'Source changed during staging')
 rpc=Rpc(dest,cli);rpc.close()
 if not flat and any(len(t['segments'])>1 for t in audit['threads'].values()):
  # In this native profile source lineage paging needs existing ancestor
  # projections; a fresh cache may otherwise silently return the leaf only.
  # Copy only closure physical IDs, only to this private raw reference probe.
  history=source/'thread_history_1.sqlite'
  require(history.is_file(),'Raw dependency reference requires source projection for this profile; do not accept leaf-only pages as a baseline')
  with connect_ro(history) as a,connect_rw(dest/'thread_history_1.sqlite') as b:
   for row in a.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND type='table' AND name NOT LIKE 'sqlite_%'"):
    b.execute(row[0].replace('CREATE TABLE ','CREATE TABLE IF NOT EXISTS ',1))
   for row in a.execute('SELECT * FROM _sqlx_migrations'):put_row(b,'_sqlx_migrations',dict(row))
  merge_history(history,dest/'thread_history_1.sqlite',list(copied))
 threads=[]
 with connect_ro(state_db(source)) as a,connect_rw(state_db(dest)) as b:
  for tid in audit['threads']:
   row=dict(a.execute('SELECT * FROM threads WHERE id=?',(tid,)).fetchone());row['rollout_path']=str(targets[tid])
   row['project_id']=None;row['thread_section_id']=None;row['section_position']=None;row['section_entered_at_ms']=None
   put_row(b,'threads',row);threads.append({'id':tid,'title':row['title'],'file':str(targets[tid])})
 dump(dest/'probe-threads.json',threads)
 dump(dest/'.rehome-isolated.json',{'purpose':'migration-verification','source_home':str(source),'source_export_sha256':export_hashes,'source_audit_sha256':hashlib.sha256(json.dumps(audit,sort_keys=True).encode()).hexdigest()})
 return threads

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source-home',required=True);ap.add_argument('--audit',required=True);ap.add_argument('--output',required=True);ap.add_argument('--codex',required=True);ap.add_argument('--flat-dir')
 a=ap.parse_args();stage(a.source_home,json.loads(Path(a.audit).read_text(encoding='utf-8')),a.output,a.codex,a.flat_dir)
 print('Isolated probe prepared. No native history verification claimed yet.')
