"""Native paginated-history checks. No file-existence-only success path."""
import json,hashlib,sqlite3,re,shutil
from pathlib import Path
from migration_safety import rewrite_structural
from rpc_reader import Rpc,pages

HISTORY_TABLES=['thread_turns','thread_items','thread_realtime_items','thread_history_projection_state']
def require(condition,message):
 if not condition:raise RuntimeError(message)
def digest(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def dump(p,obj):
 Path(p).parent.mkdir(parents=True,exist_ok=True)
 Path(p).write_bytes((json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
def encode(obj):return (json.dumps(obj,ensure_ascii=False,separators=(',',':'))+'\n').encode()
class ClosingConnection(sqlite3.Connection):
 def __exit__(self,*args):
  try:return super().__exit__(*args)
  finally:self.close()
def connect_rw(p):return sqlite3.connect(p,factory=ClosingConnection)
def connect_ro(p):
 c=sqlite3.connect(Path(p).resolve().as_uri()+'?mode=ro',uri=True,factory=ClosingConnection);c.row_factory=sqlite3.Row;return c
def state_db(home):
 paths=list(Path(home).glob('state_*.sqlite'))
 require(bool(paths),'Initialize the Codex UI once before restoring: no state database exists.')
 require(len(paths)==1 and paths[0].name=='state_5.sqlite','This profile requires one state_5.sqlite; identify the actual database and adapt before proceeding')
 return paths[0]
def columns(c,table):return [x[1] for x in c.execute('pragma table_info("'+table+'")')]
def put_row(c,table,row):
 cols=columns(c,table);values={k:v for k,v in row.items() if k in cols}
 names=list(values);pk=[r[1] for r in c.execute('pragma table_info("'+table+'")') if r[5]]
 require(bool(pk),'No primary key for '+table)
 sql='INSERT INTO "'+table+'" ('+','.join('"'+k+'"' for k in names)+') VALUES ('+','.join('?' for _ in names)+') ON CONFLICT ('+','.join('"'+k+'"' for k in pk)+') DO UPDATE SET '+','.join('"'+k+'"=excluded."'+k+'"' for k in names if k not in pk)
 c.execute(sql,list(values.values()))
def sql_backup(src,dst):
 with connect_ro(src) as a,connect_rw(dst) as b:a.backup(b)
def merge_history(src,dst,ids):
 with connect_ro(src) as a,connect_rw(dst) as b:
  for table in HISTORY_TABLES:
   ac=columns(a,table);bc=columns(b,table)
   require(set(ac)<=set(bc),'Incompatible target history schema: '+table)
   for tid in ids:
    b.execute('DELETE FROM "'+table+'" WHERE thread_id=?',(tid,))
    for row in a.execute('SELECT * FROM "'+table+'" WHERE thread_id=?',(tid,)):put_row(b,table,dict(row))
def boundary_check(path,tid,db=None):
 starts={};ends={};records=0;last=-1;offset=0;body=hashlib.sha256();meta=None
 with Path(path).open('rb') as f:
  for line in f:
   require(line.endswith(b'\n'),'Incomplete last record: '+tid)
   row=json.loads(line);ordinal=row.get('ordinal')
   require(isinstance(ordinal,int) and ordinal>last,'Invalid ordinal order: '+tid)
   require(row.get('type')!='session_meta' or records==0,'Unexpanded metadata in body: '+tid)
   if records==0:
    meta=row;require(row['type']=='session_meta' and row['payload']['id']==tid and ordinal==0,'Header ID/ordinal mismatch: '+tid)
    require(not row['payload'].get('history_base'),'Unresolved history dependency: '+tid)
    require(row['payload'].get('history_mode')=='paginated','Unexpected history mode: '+tid)
   else:body.update(encode(row))
   starts[offset]=ordinal;offset+=len(line);ends[offset]=ordinal;last=ordinal;records+=1
 require(records>1,'Empty history: '+tid)
 checked=0
 if db:
  with connect_ro(db) as c:
   state=c.execute('SELECT * FROM thread_history_projection_state WHERE thread_id=?',(tid,)).fetchone()
   require(state is not None,'Missing native projection: '+tid)
   require(ends.get(state['next_rollout_byte_offset'])==state['next_rollout_ordinal']-1,'Projection cursor is not the matching record boundary: '+tid)
   require(state['next_rollout_byte_offset']==offset and state['next_rollout_ordinal']==last+1,'Native projection has not consumed the complete file: '+tid)
   for t in c.execute('SELECT * FROM thread_turns WHERE thread_id=?',(tid,)):
    if t['rollout_byte_offset'] is not None:require(starts.get(t['rollout_byte_offset'])==t['rollout_ordinal'],'Turn start byte/ordinal mismatch: '+tid)
    if t['rollout_end_byte_offset'] is not None:require(ends.get(t['rollout_end_byte_offset'])==t['rollout_end_ordinal'],'Turn end byte/ordinal mismatch: '+tid)
    checked+=1
   ordinalset=set(starts.values())
   for t in c.execute('SELECT rollout_ordinal,updated_at_ordinal FROM thread_items WHERE thread_id=?',(tid,)):
    require(t[0] in ordinalset and t[1] in ordinalset,'Item ordinal is missing: '+tid)
 return {'id':tid,'records':records,'bytes':offset,'last_ordinal':last,'ordered_nonmeta_sha256':body.hexdigest(),'checked_turn_boundaries':checked,'file_sha256':digest(path)}
def normalized_output(turns,items,pairs):
 # Source DB predates these two nullable wrapper columns; reconstructed native
 # timestamps are valid, but they are not part of item bodies or turn contents.
 items=[{k:v for k,v in i.items() if k not in ('startedAtMs','completedAtMs')} for i in items]
 a=rewrite_structural(turns,pairs);b=rewrite_structural(items,pairs)
 def sha(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return {'turns':len(turns),'items':len(items),'turns_sha256':sha(a),'items_sha256':sha(b)}
def native_read(home,cli,threads,project,pairs,expected=None,materialize=True,output_dir=None):
 rpc=Rpc(home,cli);report=[]
 try:
  for t in threads:
   tid=t['id']
   if materialize:rpc.call('thread/resume',{'threadId':tid,'cwd':str(project),'excludeTurns':True})
   rpc.call('thread/read',{'threadId':tid,'includeTurns':False})
   turns,tp=pages(rpc,'thread/turns/list',tid);items,ip=pages(rpc,'thread/items/list',tid)
   require(bool(turns) and bool(items),'Empty history is a failure: '+tid)
   result=normalized_output(turns,items,pairs)
   if expected and tid in expected:
    require(result==expected[tid],'Native history content/count mismatch: '+tid+' '+json.dumps(result))
   report.append({'id':tid,'title':t['title'],'passed':True,'turn_pages':tp,'item_pages':ip,**result})
   if output_dir:dump(Path(output_dir)/(tid+'.json'),{'turns':turns,'items':items})
   print('Full native history loaded:',tid,len(turns),'turns,',len(items),'items',flush=True)
 finally:rpc.close()
 return report
def clone_selected(home,dest,threads):
 dest=Path(dest);(dest/'sessions').mkdir(parents=True,exist_ok=True)
 # Only selected rows and histories are copied to the verifier. The full state
 # schema is created by its native runtime; credentials/config are never copied.
 source=state_db(home)
 with connect_ro(source) as a:
  rows=[]
  for t in threads:
   row=dict(a.execute('SELECT * FROM threads WHERE id=?',(t['id'],)).fetchone())
   p=Path(row['rollout_path']);target=dest/'sessions'/p.name;shutil.copy2(p,target)
   row['rollout_path']=str(target.resolve());rows.append(row)
 return rows
