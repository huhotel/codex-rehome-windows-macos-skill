"""Assemble a manifest-covered package from an audited, natively verified flat export.

Archive containers and symlinks are excluded, not blindly copied. Review exclusions.
"""
import argparse,json,re,shutil,zipfile,stat,shlex,os
from pathlib import Path
from lineage import clean
from migration_safety import forbidden,scrub
from history_runtime import connect_ro,state_db,digest,dump,require
from native_verify import PROFILE_VERSION

def io_path(path):
 p=Path(path).resolve()
 if os.name=='nt' and not str(p).startswith('\\\\?\\'):
  return Path('\\\\?\\UNC\\'+str(p)[2:]) if str(p).startswith('\\\\') else Path('\\\\?\\'+str(p))
 return p

ARCHIVES={'.zip','.7z','.rar','.tar','.gz','.bz2','.xz','.tgz','.whl','.jar'}

def build(home,flat,project,aliases,native_report,dest,equivalence_proof):
 home=Path(home).resolve();flat=Path(flat).resolve();project=Path(project).resolve();dest=Path(dest).resolve()
 require(project.is_dir() and not dest.exists(),'Existing project and new output directory required')
 require(not dest.is_relative_to(project) and not dest.is_relative_to(home),'Output must be outside source project and Codex home')
 name=project.name;require(re.fullmatch(r'[^/\\<>:"|?*]+',name) and name not in ('.','..'),'Unsafe project name')
 export_info=json.loads((flat/'export-ledger.json').read_text(encoding='utf-8'));require(export_info.get('sanitized') is True,'Never package an unredacted private probe');ledger=export_info['threads']
 proof=json.loads(Path(equivalence_proof).read_text(encoding='utf-8'))
 require(proof.get('conversion_equivalent') and proof.get('sanitized_ledger_sha256')==digest(flat/'export-ledger.json'),'Require native conversion proof bound to this sanitized export')
 report=json.loads(Path(native_report).read_text(encoding='utf-8'))
 require(report.get('native_full_history_pass') and report.get('cli_version')==PROFILE_VERSION and not report.get('raw_dependency_probe'),'Require standalone native verifier report')
 ids={x['id'] for x in ledger};require({x['id'] for x in report['threads']}==ids,'Native report selection mismatch')
 require(len(report.get('standalone_boundaries',[]))==len(ids),'Native boundary evidence required')
 # The expected values must come from a pristine, sanitized export probe. The
 # probe appends runtime context, so compare its ordered nonmetadata content
 # separately as specified in the workflow; do not accept a report by filename.
 require(report.get('source_export_sha256')=={x['id']:x['sha256'] for x in ledger},'Native report is not bound to these candidate export hashes')
 require(not dest.with_suffix('.zip').exists(),'Preserve existing archives')
 dest.mkdir(parents=True);(dest/'histories').mkdir();threads=[]
 with connect_ro(state_db(home)) as c:
  for item in ledger:
   src=flat/item['file'];require(digest(src)==item['sha256'],'Export changed after verification')
   target=dest/'histories'/src.name;shutil.copy2(src,target)
   row=c.execute('SELECT * FROM threads WHERE id=?',(item['id'],)).fetchone();require(row is not None,'Source row disappeared')
   row=clean(dict(row));threads.append({'id':item['id'],'title':row['title'],'file':'histories/'+src.name,'row':row})
 pairs=list(dict.fromkeys([str(project),str(project).replace('\\','/'),*aliases]))
 normal=report.get('normalization_map',[])
 require(all([alias,'<PROJECT>'] in normal or (alias,'<PROJECT>') in normal for alias in pairs),'Every declared alias must be bound into the native normalization report')
 dump(dest/'threads.json',threads)
 dump(dest/'path_map.json',{'projects':[{'source_path_variants':pairs,'package_project_name':name}]})
 dump(dest/'expected-native.json',{x['id']:{k:x[k] for k in ['turns','items','turns_sha256','items_sha256']} for x in report['threads']})
 files=[];excluded=[];redactions=[];project_io=io_path(project);dest_io=io_path(dest)
 def walk(folder):
  for src in sorted(folder.iterdir()):
   rel=src.relative_to(project_io);reason=None
   if src.is_symlink() or bool(getattr(src.lstat(),'st_file_attributes',0) & getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400)):reason='link/reparse point'
   elif forbidden(rel.as_posix()):reason='default exclusion'
   elif src.is_dir() and ((src/'pyvenv.cfg').is_file() or (src/'conda-meta').is_dir()):reason='detected virtual environment'
   elif src.suffix.lower() in ARCHIVES:reason='archive requires separate recursive safety audit'
   if reason:excluded.append({'path':rel.as_posix(),'reason':reason});continue
   if src.is_dir():walk(src);continue
   require(src.is_file(),'Unsupported filesystem entry: '+str(rel))
   before=digest(src);data=src.read_bytes()
   try:
    value=data.decode('utf-8')
    if re.search(r'-----BEGIN (?:[A-Z ]*PRIVATE KEY)-----',value):
     excluded.append({'path':rel.as_posix(),'reason':'private key content'});continue
    value,n=scrub(value)
    if n:data=value.encode('utf-8');redactions.append({'path':rel.as_posix(),'count':n})
   except UnicodeError:pass
   target=dest_io/'projects'/name/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
   require(digest(src)==before,'Project source changed during copy: '+str(rel))
   files.append({'path':target.relative_to(dest_io).as_posix(),'sha256':digest(target),'bytes':target.stat().st_size})
 walk(project_io)
 dump(dest/'project-files.json',{'files':files,'excluded':excluded,'redactions':redactions,'binary_and_unknown_secret_formats':'manual inspection required; pattern scanning is not a secret-free guarantee'})
 shutil.copy2(equivalence_proof,dest/'conversion-proof.json')
 shutil.copy2(flat/'export-ledger.json',dest/'export-ledger.json');shutil.copy2(native_report,dest/'native-export-verification.json')
 instructions=("# Mac 合并恢复说明\n\n"
 "本包仅包含清单内选定项目和对话。先在 Mac 登录并初始化目标应用，然后完全退出 ChatGPT/Codex，在独立终端进入本包目录。\n\n"
 "实际 CLI 必须与报告 profile 一致。以下是 ChatGPT.app 示例；其他发行版先确认真实路径。\n\n```bash\n"
 'CLI="/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"\n'
 '"$CLI" --version\n'
 'PROJECT_DIR="$HOME/Documents/Codex-Restored-Projects"/'+shlex.quote(name)+'\n'
 'python3 restore-tools/restore_verified.py --package "$PWD" --codex-home "$HOME/.codex" --project-dir "$PROJECT_DIR" --codex "$CLI"\n```\n\n'
 "默认保留同 ID 的现有对话。修复已确认损坏的旧导入时，由助手在以上命令追加逐条 --repair-thread-id；不要对健康或已续聊对话批量覆盖。\n\n"
 "先确认应用实际 home；如不同于 ~/.codex，请改为实际值。不可用 --replace-state 或 --replace-codex-home。备份位置和完整读取报告由脚本打印。\n\n"
 "HISTORY MERGE PASSED 仅表示原生历史和合并检查通过。重新打开应用，在 Mac 本地主机打开项目，逐条检查侧栏、历史、续聊 cwd。远程 Windows 同名项目不可代替本地验收。\n\n"
 "失败保留暂存和备份。若报告 committed_but_unverified，先读取 pending_expected_ids、备份和失败报告，不要删 receipt 后重跑。\n\n"
 "project-files.json 列出排除文件，restore-report.json 列出目标冲突。已有项目文件不同则保留，不静默覆盖。\n")
 (dest/'Mac-恢复说明.md').write_bytes(instructions.encode('utf-8'))
 runtime=dest/'restore-tools' ;shutil.copytree(Path(__file__).parent,runtime,ignore=shutil.ignore_patterns('__pycache__','*.pyc','tests'))
 dump(dest/'manifest.json',{'sha256':{p.relative_to(dest_io).as_posix():digest(p) for p in dest_io.rglob('*') if p.is_file()}})
 archive=dest.with_suffix('.zip');require(not archive.exists(),'Preserve existing archives')
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for p in dest_io.rglob('*'):
   if p.is_file():z.write(p,dest.name+'/'+p.relative_to(dest_io).as_posix())
 archive.with_suffix('.zip.sha256').write_bytes((digest(archive)+'  '+archive.name+'\n').encode('utf-8'))
 return {'archive':str(archive),'project_files':len(files),'excluded':len(excluded),'threads':len(threads)}

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source-home',required=True);ap.add_argument('--flat-dir',required=True);ap.add_argument('--project',required=True);ap.add_argument('--source-alias',action='append',default=[]);ap.add_argument('--native-report',required=True);ap.add_argument('--output',required=True);ap.add_argument('--equivalence-proof',required=True)
 a=ap.parse_args();print(json.dumps(build(a.source_home,a.flat_dir,a.project,a.source_alias,a.native_report,a.output,a.equivalence_proof),ensure_ascii=False))
