"""Read all native history pages in an explicitly isolated verification home."""
import argparse,json,os,subprocess
from pathlib import Path
from history_runtime import native_read,boundary_check,dump,require,digest

PROFILE_VERSION='codex-cli 0.158.0-alpha.2.1'

def verify(home,cli,project,mapping,expected=None,dependency_probe=False):
 home=Path(home).resolve()
 forbidden=[Path.home()/'.codex']
 if os.environ.get('CODEX_HOME'):forbidden.append(Path(os.environ['CODEX_HOME']))
 require(all(home!=p.resolve() for p in forbidden),'Never resume the live Codex home for verification')
 marker=json.loads((home/'.rehome-isolated.json').read_text(encoding='utf-8'))
 require(marker.get('purpose')=='migration-verification','Explicit isolated probe marker required')
 require(home!=Path(marker['source_home']).resolve(),'Probe must differ from source')
 version=subprocess.check_output([str(cli),'--version'],text=True).strip()
 require(version==PROFILE_VERSION,'Unknown reader version: inspect protocol/schema and establish a new tested profile first: '+version)
 threads=json.loads((home/'probe-threads.json').read_text(encoding='utf-8'))
 require(all(len(x)==2 and x[1]=='<PROJECT>' for x in mapping),'Use explicit project-prefix to <PROJECT> mappings only')
 if expected is not None:
  require(set(expected)=={t['id'] for t in threads},'Expected map must cover exactly all selected IDs')
  require(all(set(v)=={'turns','items','turns_sha256','items_sha256'} for v in expected.values()),'Expected count/hash shape mismatch')
 if marker.get('source_export_sha256'):
  require(all(digest(t['file'])==marker['source_export_sha256'].get(t['id']) for t in threads),'Use a fresh probe: candidate bytes changed or already resumed')
 result=native_read(home,cli,threads,Path(project).resolve(),mapping,expected)
 checks=[] if dependency_probe else [boundary_check(t['file'],t['id'],home/'thread_history_1.sqlite') for t in threads]
 return {'cli_version':version,'source_audit_sha256':marker.get('source_audit_sha256'),'normalization_map':mapping,'compared_to_expected':expected is not None,'native_full_history_pass':True,'threads':result,'standalone_boundaries':checks,'source_export_sha256':marker.get('source_export_sha256',{}),'raw_dependency_probe':dependency_probe,'desktop_sidebar':'not tested','continuation':'not tested'}

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--home',required=True);ap.add_argument('--codex',required=True);ap.add_argument('--project-dir',required=True);ap.add_argument('--normalization-map',required=True,help='JSON list of explicit [path prefix, canonical token] pairs');ap.add_argument('--expected',help='Immutable ID -> native count/hash results');ap.add_argument('--report',required=True);ap.add_argument('--dependency-probe',action='store_true')
 a=ap.parse_args();out=Path(a.report);require(not out.exists(),'Preserve existing reports')
 result=verify(a.home,a.codex,a.project_dir,json.loads(Path(a.normalization_map).read_text(encoding='utf-8')),json.loads(Path(a.expected).read_text(encoding='utf-8')) if a.expected else None,a.dependency_probe)
 dump(out,result);print('All selected native histories loaded; sidebar and continuation remain pending.')
