"""Read committed selected histories in a fresh copy, never resume the live home."""
import argparse,json,tempfile
from pathlib import Path
from history_runtime import *
from restore_verified import VERSION,closed_app_guard
import subprocess

def verify(home,root,project,cli,expected_ids):
 home=Path(home).resolve();root=Path(root).resolve();project=Path(project).resolve()
 require(subprocess.check_output([str(cli),'--version'],text=True).strip()==VERSION,'Unsupported CLI version')
 closed_app_guard()
 threads=json.loads((root/'threads.json').read_text(encoding='utf-8'))
 require(set(expected_ids)<={t['id'] for t in threads},'Expected comparison scope exceeds selection')
 before={}
 with connect_ro(state_db(home)) as c:
  for t in threads:
   row=c.execute('SELECT * FROM threads WHERE id=?',(t['id'],)).fetchone()
   require(row is not None,'Committed selected row missing: '+t['id'])
   before[row['rollout_path']]=digest(row['rollout_path'])
 scratch=Path(tempfile.mkdtemp(prefix='rehome-committed-',dir=home.parent));stage=scratch/'home'
 rows=clone_selected(home,stage,threads)
 rpc=Rpc(stage,cli);rpc.close()
 with connect_rw(state_db(stage)) as c:
  for row in rows:
   row.update(project_id=None,thread_section_id=None,section_position=None,section_entered_at_ms=None)
   put_row(c,'threads',row)
 require((home/'thread_history_1.sqlite').is_file(),'Committed native projection missing')
 # Preserve projection offsets exactly. Only selected rows enter the probe.
 # Native bootstrap creates this database when a selected history is resumed;
 # create its schema from the source using an empty schema-only copy instead.
 with connect_ro(home/'thread_history_1.sqlite') as a,connect_rw(stage/'thread_history_1.sqlite') as b:
  for row in a.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND type='table' AND name NOT LIKE 'sqlite_%'"):
   b.execute(row[0].replace('CREATE TABLE ','CREATE TABLE IF NOT EXISTS ',1))
 with connect_ro(home/'thread_history_1.sqlite') as a,connect_rw(stage/'thread_history_1.sqlite') as b:
  for row in a.execute('SELECT * FROM _sqlx_migrations'):put_row(b,'_sqlx_migrations',dict(row))
 merge_history(home/'thread_history_1.sqlite',stage/'thread_history_1.sqlite',[t['id'] for t in threads])
 aliases=json.loads((root/'path_map.json').read_text(encoding='utf-8'))['projects'][0]['source_path_variants']
 mapping=json.loads((root/'native-export-verification.json').read_text(encoding='utf-8'))['normalization_map']+[(str(project),'<PROJECT>')]
 expected=json.loads((root/'expected-native.json').read_text(encoding='utf-8'))
 result=native_read(stage,cli,threads,project,mapping,{k:expected[k] for k in expected_ids},materialize=False)
 checks=[boundary_check(r['rollout_path'],r['id'],stage/'thread_history_1.sqlite') for r in rows]
 require(all(digest(p)==sha for p,sha in before.items()),'Live histories changed during verification')
 report={'committed_native_read_pass':True,'threads':result,'boundaries':checks,'exact_expected_ids':list(expected_ids),'live_history_bytes_unchanged':True,'scratch':str(scratch),'sidebar':'pending','continuation':'pending'}
 dump(scratch/'report.json',report);return report

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__)
 for field in ['codex-home','package','project-dir','codex']:ap.add_argument('--'+field,required=True)
 ap.add_argument('--compare-thread-id',action='append',default=[],help='Only new/repaired, not subsequently continued histories')
 a=ap.parse_args();print(json.dumps(verify(a.codex_home,a.package,a.project_dir,a.codex,a.compare_thread_id),ensure_ascii=False,indent=2))
