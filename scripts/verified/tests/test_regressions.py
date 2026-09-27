"""Synthetic data only; python -m unittest discover -s scripts/verified/tests -v."""
import ast,copy,json,sqlite3,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lineage import catalog,resolve,export
from history_runtime import encode,digest,dump,boundary_check,connect_rw
from migration_safety import rewrite_structural,forbidden
from rpc_reader import pages
from restore_verified import receipt_name,referenced_by_unselected,project_merge,plan_files,guard_physical_collisions
from unittest.mock import patch

A='11111111-1111-4111-8111-111111111111'
B='22222222-2222-4222-8222-222222222222'
C='33333333-3333-4333-8333-333333333333'
def header(tid,ordinal=0,base=None):
 p={'id':tid,'history_mode':'paginated'}
 if base:p['history_base']=base
 return {'ordinal':ordinal,'type':'session_meta','payload':p}

class Regressions(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.home=self.root/'home';(self.home/'sessions').mkdir(parents=True)
 def tearDown(self):self.tmp.cleanup()
 def write(self,stable,physical,rows):
  p=self.home/'sessions'/('rollout-2000-01-01T00-00-00-'+stable+('_'+physical if physical!=stable else '')+'.jsonl');p.write_bytes(b''.join(encode(r) for r in rows));return p
 def chain(self):
  parent=self.write(A,A,[header(A),{'ordinal':1,'type':'event_msg','payload':{'text':'中文 原文'}}])
  base={'thread_id':A,'end_byte_offset':parent.stat().st_size,'end_ordinal_exclusive':2}
  leaf=self.write(A,B,[header(A,2,base),{'ordinal':3,'type':'event_msg','payload':{'text':'next'}}]);return parent,leaf,base
 def test_physical_same_stable_is_not_cycle(self):
  parent,leaf,_=self.chain();chain=resolve(catalog(self.home),leaf);self.assertEqual([x['physical_id'] for x in chain],[A,B])
 def test_standalone_order_proof(self):
  _,leaf,_=self.chain();chain=resolve(catalog(self.home),leaf)
  report={'structural_pass':True,'errors':[],'threads':{A:{'segments':chain}}};ledger=export(report,self.root/'flat')
  rows=[json.loads(x) for x in (self.root/'flat'/ledger[0]['file']).read_bytes().splitlines()]
  self.assertEqual([r['ordinal'] for r in rows],[0,1,3]);self.assertEqual(rows[1]['payload']['text'],'中文 原文');self.assertNotIn('history_base',rows[0]['payload'])
  boundary_check(self.root/'flat'/ledger[0]['file'],A)
 def test_missing_dependency(self):
  parent,leaf,_=self.chain();parent.unlink()
  with self.assertRaisesRegex(RuntimeError,'Missing source'):resolve(catalog(self.home),leaf)
 def test_past_eof_and_record_split_and_wrong_ordinal(self):
  parent,leaf,base=self.chain()
  for key,value,pattern in [('end_byte_offset',parent.stat().st_size+1,'past-EOF'),('end_byte_offset',parent.stat().st_size-2,'splits'),('end_ordinal_exclusive',4,'ordinal')]:
   changed={**base,key:value};self.write(A,B,[header(A,changed['end_ordinal_exclusive'],changed),{'ordinal':changed['end_ordinal_exclusive']+1,'type':'event_msg','payload':{}}])
   with self.subTest(key=key,value=value),self.assertRaisesRegex(RuntimeError,pattern):resolve(catalog(self.home),leaf)
 def test_duplicate_physical_id(self):
  parent,_,_=self.chain();(self.home/'archived_sessions').mkdir();(self.home/'archived_sessions'/parent.name).write_bytes(parent.read_bytes())
  with self.assertRaisesRegex(RuntimeError,'Ambiguous'):resolve(catalog(self.home),parent)
 def test_source_changes_after_audit(self):
  parent,leaf,_=self.chain();chain=resolve(catalog(self.home),leaf);parent.write_bytes(parent.read_bytes()+b'\n')
  with self.assertRaisesRegex(RuntimeError,'changed'):export({'structural_pass':True,'errors':[],'threads':{A:{'segments':chain}}},self.root/'flat')
 def test_crlf_byte_boundaries(self):
  parent,_,_=self.chain();parent.write_bytes(parent.read_bytes().replace(b'\n',b'\r\n'));chain=resolve(catalog(self.home),parent);self.assertEqual(chain[0]['included_bytes'],parent.stat().st_size)
 def test_file_uri_unicode_and_historical_text(self):
  row={'cwd':'file:///C:/Work/%E4%B8%AD%E6%96%87','text':'C:\\Work\\中文','path':'C:\\Work\\中文\\a.txt'}
  result=rewrite_structural(row,[('C:\\Work','/Users/demo/Project')]);self.assertEqual(result['cwd'],'file:///Users/demo/Project/%E4%B8%AD%E6%96%87');self.assertEqual(result['text'],row['text'])
 def test_foreign_command_context_preserved(self):
  row={'type':'CommandExecution','cwd':'C:\\Work','parsed_cmd':[{'type':'read','path':'D:\\outside.txt'},{'type':'read','path':'C:\\Work\\a.txt'}]}
  self.assertEqual(rewrite_structural(row,[('C:\\Work','/Users/demo/Project')]),row)
  self.assertEqual(rewrite_structural({'cwd':'C:\\Work'},[('C:\\Work','/Users/demo/Project')])['cwd'],'/Users/demo/Project')
 def test_full_paging_and_repeated_cursor(self):
  class Fake:
   def __init__(self):self.n=0
   def call(self,method,args):
    self.n+=1;return {'data':[self.n],'nextCursor':'repeat'}
  with self.assertRaisesRegex(RuntimeError,'repeated cursor'):pages(Fake(),'thread/turns/list',A)
 def test_filters(self):
  for p in ['.env','.env.local','.git/config','node_modules/a','venv/bin/python','.ssh/id_ed25519','auth.json','Cookies','a.pem']:
   self.assertTrue(forbidden(p),p)
  self.assertFalse(forbidden('src/main.py'))
 def test_receipts_separate_projects(self):self.assertNotEqual(receipt_name('/a'),receipt_name('/b'))
 def test_untouched_selected_dependency_guard(self):
  parent,_,base=self.chain();self.write(C,C,[header(C,2,base),{'ordinal':3,'type':'event_msg','payload':{}}])
  self.assertIn(A,referenced_by_unselected(self.home,{A}))
 def test_project_manifest_binding(self):
  dump(self.root/'project-files.json',{'files':[{'path':'projects/Test/a.txt','sha256':'not-the-manifest'}]});dump(self.root/'manifest.json',{'sha256':{}})
  with self.assertRaisesRegex(RuntimeError,'manifest'):project_merge(self.root,self.root/'target')
 def test_python39_grammar_and_report_writer(self):
  for p in Path(__file__).resolve().parents[1].glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),feature_version=(3,9))
  dump(self.root/'unicode.json',{'text':'中文'});self.assertEqual(json.loads((self.root/'unicode.json').read_bytes()),{'text':'中文'})
 def test_unrelated_legacy_identity_does_not_block_selection(self):
  parent,_,_=self.chain();legacy=header(C);legacy['payload']['session_id']='legacy-session'
  self.write(C,C,[legacy]);self.assertEqual(len(resolve(catalog(self.home),parent)),1)
 def test_multiple_state_databases_refused(self):
  from history_runtime import state_db
  (self.home/'state_5.sqlite').touch();(self.home/'state_6.sqlite').touch()
  with self.assertRaisesRegex(RuntimeError,'one state_5'):state_db(self.home)
 def test_partial_expected_map_refused(self):
  from native_verify import verify,PROFILE_VERSION
  dump(self.home/'.rehome-isolated.json',{'purpose':'migration-verification','source_home':str(self.root/'source')})
  dump(self.home/'probe-threads.json',[{'id':A,'title':'Synthetic','file':'unused'}])
  with patch('native_verify.subprocess.check_output',return_value=PROFILE_VERSION),self.assertRaisesRegex(RuntimeError,'exactly all selected'):verify(self.home,'unused',self.root,[],{})
 def test_unknown_native_version_refused(self):
  from native_verify import verify
  dump(self.home/'.rehome-isolated.json',{'purpose':'migration-verification','source_home':str(self.root/'source')})
  with patch('native_verify.subprocess.check_output',return_value='codex-cli 9.99'),self.assertRaisesRegex(RuntimeError,'Unknown reader'):verify(self.home,'unused',self.root,[])
 def test_projection_cutoff_must_be_record_boundary(self):
  parent,_,_=self.chain();db=self.root/'history.sqlite'
  with connect_rw(db) as c:
   c.execute('CREATE TABLE thread_history_projection_state(thread_id TEXT,next_rollout_byte_offset INTEGER,next_rollout_ordinal INTEGER)')
   c.execute('INSERT INTO thread_history_projection_state VALUES(?,?,?)',(A,parent.stat().st_size-1,2))
  with self.assertRaisesRegex(RuntimeError,'matching record boundary'):boundary_check(parent,A,db)
 def test_preserved_segmented_history_fails_before_rewrite(self):
  _,leaf,_=self.chain();before=digest(leaf);stage=self.root/'stage';stage.mkdir()
  with patch('restore_verified.selected_existing',return_value={A:{'rollout_path':str(leaf)}}),self.assertRaisesRegex(RuntimeError,'segmented history'):
   plan_files(self.root,self.home,stage,[{'id':A,'file':'histories/leaf.jsonl'}],self.root,[],{},set())
  self.assertEqual(digest(leaf),before)
 def test_native_leaf_only_baseline_rejected_by_conversion_proof(self):
  from prove_conversion import prove
  from native_verify import PROFILE_VERSION
  private=self.root/'private';sanitized=self.root/'sanitized'
  dump(private/'export-ledger.json',{'sanitized':False});dump(sanitized/'export-ledger.json',{'sanitized':True})
  raw={'native_full_history_pass':True,'cli_version':PROFILE_VERSION,'normalization_map':[],'source_audit_sha256':'same-source','raw_dependency_probe':True,'threads':[{'id':A,'turns':1,'items':2,'turns_sha256':'leaf','items_sha256':'leaf'}]}
  flat=copy.deepcopy(raw);flat['raw_dependency_probe']=False;flat['threads'][0].update(turns=10,items=20,turns_sha256='full',items_sha256='full')
  dump(self.root/'raw.json',raw);dump(self.root/'flat.json',flat)
  with self.assertRaisesRegex(RuntimeError,'content/order differs'):prove(self.root/'raw.json',self.root/'flat.json',private,sanitized,self.root/'proof.json')
 def test_new_standalone_must_not_shadow_existing_physical_ancestor(self):
  _,leaf,_=self.chain()
  with self.assertRaisesRegex(RuntimeError,'different physical ancestor'):guard_physical_collisions(self.home,{A:{'rollout_path':str(leaf)}},[A])

if __name__=='__main__':unittest.main()
