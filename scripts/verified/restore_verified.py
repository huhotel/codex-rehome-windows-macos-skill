"""Merge-only repair; native materialization precedes all live history changes."""
import argparse,datetime,json,os,shutil,sqlite3,subprocess,sys,tempfile,uuid
from pathlib import Path
from migration_safety import rewrite_structural,forbidden
from history_runtime import *

PACKAGE=Path(__file__).resolve().parent
VERSION='codex-cli 0.158.0-alpha.2.1'
MAC_CLI='/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex'

def io_path(p):
 p=Path(p)
 return Path('\\\\?\\'+str(p.resolve())) if os.name=='nt' and not str(p).startswith('\\\\?\\') else p

def verify_package(root):
 manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
 for rel,sha in manifest['sha256'].items():
  p=io_path(root/rel)
  require(not Path(rel).is_absolute() and '..' not in Path(rel).parts,'Unsafe manifest path')
  require(p.is_file() and digest(p)==sha,'Package checksum failed: '+rel)
 return len(manifest['sha256'])

def closed_app_guard():
 if sys.platform!='darwin':return
 listing=subprocess.check_output(['ps','-axo','pid=,command='],text=True)
 active=[]
 for line in listing.splitlines():
  if any(x in line for x in ['/ChatGPT.app/Contents/MacOS/ChatGPT','/Codex.app/Contents/MacOS/','codex-cli/bin/codex app-server','/Codex.app/Contents/Resources/codex app-server']):active.append(line.split()[0])
 require(not active,'Fully quit ChatGPT/Codex, then run in Terminal. Active process IDs: '+','.join(active))

def selected_existing(home,threads):
 with connect_ro(state_db(home)) as c:
  return {t['id']:dict(r) for t in threads if (r:=c.execute('SELECT * FROM threads WHERE id=?',(t['id'],)).fetchone())}

def plan_files(root,home,stage,threads,project,pairs,receipt,repair_ids):
 existing=selected_existing(home,threads);changed=[];preserved=[]
 for t in threads:
  tid=t['id'];dest=stage/'sessions'/Path(t['file']).name;dest.parent.mkdir(parents=True,exist_ok=True)
  old=existing.get(tid)
  if old and (tid not in repair_ids or tid in receipt.get('threads',{})):
   original=Path(old['rollout_path'])
   require(original.is_file(),'Preserved history is missing: '+tid)
   with original.open('rb') as f:preserved_header=json.loads(f.readline())
   require(not preserved_header.get('payload',{}).get('history_base'),'Preserved target has segmented history; this profile requires a separate dependency-aware staging adapter. Target was not rewritten: '+tid)
   # A prior repaired task may have received new turns. Never overwrite it.
   if tid in receipt.get('threads',{}):
    prior=receipt['threads'][tid]
    require(str(original.resolve())==prior['path'],'Previously repaired task now points to a different rollout; preserve it and investigate its new lineage: '+tid)
    with original.open('rb') as f:prefix=f.read(prior['bytes'])
    require(hashlib.sha256(prefix).hexdigest()==prior['sha256'],'Previously repaired history was modified; refusing to overwrite: '+tid)
   shutil.copy2(original,dest);preserved.append(tid)
  else:
   with (root/t['file']).open('rb') as fi,dest.open('wb') as fo:
    for line in fi:fo.write(encode(rewrite_structural(json.loads(line),pairs)))
   changed.append(tid)
  boundary_check(dest,tid)
 return existing,changed,preserved

def project_merge(root,target):
 copied=identical=0;conflicts=[]
 records=json.loads((root/'project-files.json').read_text(encoding='utf-8'))['files']
 manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))['sha256']
 for r in records:
  rel=Path(r['path']);require(len(rel.parts)>2 and rel.parts[0]=='projects' and '..' not in rel.parts,'Unsafe project member')
  require(manifest.get(r['path'])==r['sha256'],'Project member must match verified manifest')
  tail=Path(*rel.parts[2:]);require(not forbidden(tail.as_posix()),'Forbidden project path')
  dest=io_path(target/tail)
  require(not any(p.is_symlink() for p in [dest,*dest.parents] if p!=p.parent),'Symlink in project destination: '+str(dest))
  if dest.exists():
   if dest.is_file() and digest(dest)==r['sha256']:identical+=1
   else:conflicts.append(tail.as_posix())
   continue
  dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(io_path(root/rel),dest);copied+=1
 return {'copied':copied,'identical':identical,'existing_different_preserved':conflicts}

def native_project(stage,cli,project):
 rpc=Rpc(stage,cli)
 try:return rpc.call('project/create',{'name':project.name,'roots':[{'path':str(project)}],'idempotencyKey':'rehome-verified-'+hashlib.sha256(str(project).encode()).hexdigest()})
 finally:rpc.close()

def receipt_name(project):
 return 'rehome-verified-'+hashlib.sha256(str(project).encode()).hexdigest()[:16]+'-receipt.json'

def snapshot_files(home,existing,changed,backup,project):
 inventory={}
 for name in ['session_index.jsonl','.codex-global-state.json',receipt_name(project)]:
  p=home/name
  if p.exists():shutil.copy2(p,backup/name);inventory[str(p)]=name
  else:inventory[str(p)]=None
 for tid in changed:
  if tid in existing:
   p=Path(existing[tid]['rollout_path'])
   require(any(p.resolve().is_relative_to((home/d).resolve()) for d in ['sessions','archived_sessions']),'Selected current rollout is outside the target history directories: '+tid)
   require(p.is_file(),'Existing rollout missing: '+tid)
   # Only the selected current file is touched. Ancestor files are never removed.
   with p.open('rb') as f:meta=json.loads(f.readline())
   require(meta['payload']['id']==tid,'Existing rollout belongs to a different task: '+tid)
   rel='old-rollouts/'+tid+'.jsonl';(backup/'old-rollouts').mkdir(exist_ok=True)
   shutil.copy2(p,backup/rel);inventory[str(p)]=rel
 return inventory

def referenced_by_unselected(home,selected):
 references=set()
 for dirname in ['sessions','archived_sessions']:
  for p in (home/dirname).rglob('*.jsonl'):
   with p.open('rb') as f:
    try:meta=json.loads(f.readline())['payload']
    except (ValueError,KeyError):continue
   if meta.get('history_base'):references.add(meta['history_base']['thread_id'])
 return references

def physical_id(path):return Path(path).stem[-36:]

def guard_physical_collisions(home,existing,changed):
 for folder in ['sessions','archived_sessions']:
  for path in (home/folder).rglob('*.jsonl'):
   rid=physical_id(path)
   if rid in changed:
    old=existing.get(rid,{}).get('rollout_path')
    require(old and path.resolve()==Path(old).resolve(),'A different physical ancestor already uses the new standalone ID; preserve its lineage before importing: '+rid)

def apply_merge(home,stage,root,threads,existing,changed,preserved,project,backup,receipt,project_result):
 target_state=state_db(home);target_history=home/'thread_history_1.sqlite'
 sql_backup(target_state,backup/target_state.name)
 history_existed=target_history.exists()
 if history_existed:sql_backup(target_history,backup/target_history.name)
 inventory=snapshot_files(home,existing,changed,backup,project)
 dump(backup/'selected-rows-before.json',{k:existing[k] for k in changed if k in existing})
 new_paths={};moved=[];source_state=state_db(stage)
 try:
  guard_physical_collisions(home,existing,changed)
  references=referenced_by_unselected(home,set(changed))
  collisions=[tid for tid in changed if tid in existing and physical_id(existing[tid]['rollout_path'])==tid and tid in references]
  require(not collisions,'An unrelated Mac task depends on a rollout ID that this repair would replace. No merge will be committed; preserve its lineage and investigate: '+','.join(collisions))
  with connect_ro(source_state) as a,connect_rw(target_state) as b:
   require(set(columns(a,'threads'))<=set(columns(b,'threads')),'Target state schema is older than the matching native runtime')
   # Project registration was produced by the official API in the isolated home.
   current=b.execute('SELECT project_id FROM project_roots WHERE path=?',(str(project),)).fetchone()
   if current:project_id=current[0]
   else:
    p=dict(a.execute('SELECT * FROM projects').fetchone());project_id=p['id']
    p['position']=b.execute('SELECT COALESCE(MAX(position),-1)+1 FROM projects').fetchone()[0]
    put_row(b,'projects',p)
    for table in ['project_roots','project_idempotency_keys']:
     for row in a.execute('SELECT * FROM '+table+' WHERE project_id=?',(project_id,)):put_row(b,table,dict(row))
   for t in threads:
    tid=t['id']
    if tid not in changed:continue
    src=stage/'sessions'/Path(t['file']).name;dest=home/'sessions'/'rehome-verified'/src.name
    require(not dest.exists(),'Unexpected destination collision: '+str(dest))
    dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);new_paths[tid]=dest
    row=dict(a.execute('SELECT * FROM threads WHERE id=?',(tid,)).fetchone())
    # Keep source chronology and names, while native runtime supplies new fields.
    historical=t['row']
    for k in ['created_at','updated_at','created_at_ms','updated_at_ms','recency_at','recency_at_ms','tokens_used','first_user_message','preview']:
     if k in historical:row[k]=historical[k]
    row.update(id=tid,rollout_path=str(dest.resolve()),cwd=str(project),title=t['title'],name=t['title'],archived=0,archived_at=None,project_id=project_id,is_pinned=0,thread_section_id=None,section_position=None,section_entered_at_ms=None)
    # Existing Mac personal pin/section choice survives repair.
    for k in ['is_pinned','thread_section_id','section_position','section_entered_at_ms']:
     if tid in existing:row[k]=existing[tid].get(k,row.get(k))
    put_row(b,'threads',row)
  if history_existed:merge_history(stage/'thread_history_1.sqlite',target_history,changed)
  else:
   sql_backup(stage/'thread_history_1.sqlite',target_history)
   with connect_rw(target_history) as c:
    for table in HISTORY_TABLES:
     c.execute('DELETE FROM '+table+' WHERE thread_id NOT IN ('+','.join('?' for _ in changed)+')',changed)
  # Remove superseded current files only when no other task depends on them.
  # The byte-for-byte preimage already lives outside the discovery directories.
  for tid in changed:
   if tid in existing:
    old=Path(existing[tid]['rollout_path'])
    if physical_id(old) not in references:
     old.unlink();moved.append(str(old))
  indexpath=home/'session_index.jsonl';entries=[]
  if indexpath.exists():entries=[json.loads(s) for s in indexpath.read_text(encoding='utf-8').splitlines() if s.strip()]
  untouched=[r for r in entries if r.get('id') not in changed]
  for t in threads:
   if t['id'] in changed:
    updated=datetime.datetime.fromtimestamp(t['row']['updated_at'],datetime.timezone.utc).isoformat().replace('+00:00','Z')
    untouched.append({'id':t['id'],'thread_name':t['title'],'updated_at':updated})
  indexpath.write_bytes(b''.join(encode(r) for r in untouched))
  # Desktop membership is a separate host-aware acceptance phase. Never put
  # filesystem paths into project-order or overwrite thread-ID-only host maps.
  rows=selected_existing(home,threads);checks=[]
  for tid in changed:checks.append(boundary_check(rows[tid]['rollout_path'],tid,target_history))
  # Check the exact bytes committed, not the bytes before native materialization.
  for t in threads:
   if t['id'] in changed:require(digest(new_paths[t['id']])==digest(stage/'sessions'/Path(t['file']).name),'Committed bytes changed')
  receipt.setdefault('threads',{})
  for tid,p in new_paths.items():receipt['threads'][tid]={'path':str(p.resolve()),'sha256':digest(p),'bytes':p.stat().st_size}
  receipt.update(schema=2,project=str(project),last_backup=str(backup),cli_version=VERSION,post_commit_verified=False,pending_expected_ids=changed)
  dump(home/receipt_name(project),receipt)
  return {'committed_structure':checks,'obsolete_files_backed_up':moved,'project_id':project_id}
 except BaseException:
  # The app is required to be closed, so these snapshots are authoritative.
  sql_backup(backup/target_state.name,target_state)
  if history_existed:sql_backup(backup/target_history.name,target_history)
  elif target_history.exists():target_history.unlink()
  for p in new_paths.values():
   if p.exists():p.unlink()
  for path,rel in inventory.items():
   p=Path(path)
   if rel:p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(backup/rel,p)
   elif p.exists():p.unlink()
  raise

def run(root,home,project,cli,repair_ids=None,check_package=True):
 root=Path(root).resolve();home=Path(home).expanduser().resolve();project=Path(project).expanduser().resolve();cli=str(cli)
 require(home.is_dir(),'Codex home does not exist: '+str(home))
 version=subprocess.check_output([cli,'--version'],text=True).strip()
 require(version==VERSION,'Expected '+VERSION+', found '+version+'. No data was changed.')
 closed_app_guard()
 if check_package:print('Verified package files:',verify_package(root),flush=True)
 require(len(json.loads((root/'path_map.json').read_text(encoding='utf-8'))['projects'])==1,'Use one explicit destination project per transaction')
 threads=json.loads((root/'threads.json').read_text(encoding='utf-8'));require(threads and len({t['id'] for t in threads})==len(threads),'Expected nonempty unique selection')
 manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))['sha256']
 for t in threads:
  rel=Path(t['file']);require(not rel.is_absolute() and '..' not in rel.parts and rel.parts[0]=='histories' and t['file'] in manifest,'Invalid/unverified selected history member')
 repair_ids=set(repair_ids or []);require(repair_ids<={t['id'] for t in threads},'Repair scope exceeds selection')
 expected=json.loads((root/'expected-native.json').read_text(encoding='utf-8'))
 require(set(expected)=={t['id'] for t in threads},'Expected native hashes must cover exactly the selection')
 aliases=json.loads((root/'path_map.json').read_text(encoding='utf-8'))['projects'][0]['source_path_variants']
 pairs=[(p,str(project)) for p in aliases];normal=json.loads((root/'native-export-verification.json').read_text(encoding='utf-8'))['normalization_map']+[(str(project),'<PROJECT>')]
 receiptpath=home/receipt_name(project);receipt=json.loads(receiptpath.read_text(encoding='utf-8')) if receiptpath.exists() else {}
 require(not receipt or receipt.get('post_commit_verified') is True,'Prior merge committed but was not verified. Inspect its backup/report and run verify_committed with every pending_expected_id before any retry; do not overwrite or drop expected comparisons.')
 require(not receipt or receipt.get('project')==str(project),'Existing v2 restore uses another project directory; preserve it rather than remapping it again.')
 scratch=Path(tempfile.mkdtemp(prefix='rehome-verified-',dir=home.parent));stage=scratch/'native-home';stage.mkdir()
 stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
 backup=home/'rehome-backups'/stamp
 report={'schema':2,'cli_version':version,'target_home':str(home),'project':str(project),'scratch':str(scratch),'mac_sidebar_and_continuation':'pending UI check'}
 try:
  existing,changed,preserved=plan_files(root,home,stage,threads,project,pairs,receipt,repair_ids)
  for tid in preserved:
   require((home/'thread_history_1.sqlite').is_file(),'Preserved histories need an existing complete target projection; inspect/rebuild in isolation before merging')
   boundary_check(existing[tid]['rollout_path'],tid,home/'thread_history_1.sqlite')
  # Preserve the normalizer for the preserved tasks if an older restore used
  # a different project spelling. This does not rewrite their actual files.
  normal += [(r['cwd'],'<PROJECT>') for tid,r in existing.items() if tid in preserved and r.get('cwd')]
  print('Preparing',len(changed),'repairs/imports; preserving',len(preserved),'existing tasks.',flush=True)
  project.mkdir(parents=True,exist_ok=True)
  report['native_preflight']=native_read(stage,cli,threads,project,normal,{k:v for k,v in expected.items() if k in changed})
  report['exact_source_content_checked_ids']=changed
  report['all_selected_full_histories_loaded']=len(report['native_preflight'])==len(threads)
  report['native_boundaries']=[boundary_check(stage/'sessions'/Path(t['file']).name,t['id'],stage/'thread_history_1.sqlite') for t in threads]
  project_result=native_project(stage,cli,project);report['native_project_registration']=project_result
  closed_app_guard();backup.mkdir(parents=True)
  report['project_files']=project_merge(root,project)
  report.update(changed=changed,preserved=preserved,backup=str(backup))
  if changed:report['merge']=apply_merge(home,stage,root,threads,existing,changed,preserved,project,backup,receipt,project_result)
  else:report['merge']={'idempotent_no_history_changes':True}
  dump(backup/'restore-report.json',report);dump(home/'rehome-verified-last-report.json',report)
  report['merge_committed']=bool(changed)
  from verify_committed import verify as verify_actual
  report['committed_native']=verify_actual(home,root,project,cli,changed)
  if changed:
   receipt['post_commit_verified']=True;receipt['pending_expected_ids']=[];dump(receiptpath,receipt)
  dump(backup/'restore-report.json',report);dump(home/'rehome-verified-last-report.json',report)
  print('HISTORY MERGE PASSED: all selected full histories loaded. Sidebar/continuation pending. Changed:',len(changed),'; preserved:',len(preserved),flush=True)
  print('Backup and report:',backup,flush=True)
  print('Open ChatGPT > Codex, open the Project folder, then check sidebar and continuation.',flush=True)
  return report
 except BaseException as e:
  report['error']=str(e)
  if report.get('merge_committed'):report['status']='committed_but_unverified; preserve backup and do not retry blindly'
  dump(scratch/'failure-report.json',report)
  print('FAILED; diagnostic staging retained:',scratch,file=sys.stderr);raise
 finally:
  # Keep isolated evidence locally. It contains conversation history; never
  # upload it publicly. The instructions explain when it can be removed.
  pass

if __name__=='__main__':
 ap=argparse.ArgumentParser(description='Merge verified selected histories. Existing conversations are preserved unless explicitly selected for repair.')
 ap.add_argument('--package',required=True)
 ap.add_argument('--codex-home',default=str(Path.home()/'.codex'))
 ap.add_argument('--project-dir',required=True)
 ap.add_argument('--codex',required=True)
 ap.add_argument('--repair-thread-id',action='append',default=[])
 args=ap.parse_args()
 require(sys.platform=='darwin','Run on the verified target Mac; tests invoke run with isolated directories.')
 run(args.package,args.codex_home,args.project_dir,args.codex,args.repair_thread_id)
