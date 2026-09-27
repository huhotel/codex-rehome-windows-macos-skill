import re
from urllib.parse import urlsplit, unquote, quote
SKIP={'.git','node_modules','.venv','venv','env','__pycache__','.ssh','.aws','.azure','.kube','.npmrc','.pypirc','.netrc','auth.json','cookies','cookies-journal','login data','login data for account','local storage','session storage','id_rsa','id_dsa','id_ecdsa','id_ed25519','.ds_store','.tmp','tmp','process_manager','vendor_imports','singletonlock','singletoncookie','singletonsocket','cache','caches','gpucache','code cache','cachestorage','logs'}
def forbidden(path):
 parts=path.replace('\\','/').split('/')
 return any(p.lower() in SKIP or p.lower()=='.env' or p.lower().startswith('.env.') or p.lower().endswith(('.pem','.key','.p12','.pfx','.ppk','.sock','.ipc','.pyc')) for p in parts)
PATTERNS=[
 re.compile(r'-----BEGIN (?:[A-Z ]*PRIVATE KEY)-----.*?-----END (?:[A-Z ]*PRIVATE KEY)-----',re.S),
 re.compile(r'(?<![\w-])(?:sk-[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[A-Z0-9]{16})(?![\w-])'),
 re.compile(r'eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}'),
 re.compile(r'(?i)(?P<prefix>["\x27]?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password)["\x27]?\s*[:=]\s*["\x27])(?P<value>[A-Za-z0-9_./+=-]{20,})(?=["\x27])'),
]
def scrub(text):
 count=0
 for pat in PATTERNS:
  if 'prefix' in pat.groupindex:
   text,n=pat.subn(lambda m:m.group('prefix')+'[REDACTED_MIGRATION_SECRET]',text)
  else: text,n=pat.subn('[REDACTED_MIGRATION_SECRET]',text)
  count+=n
 return text,count
PATH_KEYS={'cwd','project_path','workspace_root','workspace_roots','writable_roots','root','roots','rollout_path','working_directory','workdir','path'}
def rewrite_structural(obj,pairs,key=''):
 if isinstance(obj,dict):
  # Historical executor cwd determines how Codex interprets parsed read paths.
  # A Windows absolute reference outside the migrated roots must retain that
  # historical context. It does not refer to a file below the restored project.
  # Keep the entire parsed command group in one convention, including mixed
  # local/foreign reads. Live session/turn workspace fields still map normally.
  cwd=obj.get('cwd','')
  windows_cwd=isinstance(cwd,str) and (bool(re.match(r'^file:///(?:[A-Za-z]:/)',cwd)) or bool(re.match(r'^[A-Za-z]:[\\/]',cwd)))
  foreign=False
  if obj.get('type')=='CommandExecution' and windows_cwd:
   for command in obj.get('parsed_cmd',[]):
    path=command.get('path') if isinstance(command,dict) else None
    if isinstance(command,dict) and command.get('type')=='read' and isinstance(path,str) and re.match(r'^(?:[A-Za-z]:[\\/]|\\\\)',path):
     if rewrite_structural(path,pairs,'path')==path:foreign=True
  return {k:(v if foreign and k in ('cwd','parsed_cmd') else rewrite_structural(v,pairs,k)) for k,v in obj.items()}
 if isinstance(obj,list): return [rewrite_structural(v,pairs,key) for v in obj]
 if isinstance(obj,str) and key in PATH_KEYS:
  # Codex stores some event cwd values as file URIs. Map their filesystem
  # path while retaining URI representation. Leaving a Windows cwd URI next
  # to a mapped POSIX read path makes the native reader inherit the C: drive.
  if obj.startswith('file:'):
   uri=urlsplit(obj)
   if uri.scheme=='file' and uri.netloc in ('','localhost') and not uri.query and not uri.fragment:
    native=unquote(uri.path)
    if re.match(r'^/[A-Za-z]:/',native):native=native[1:]
    for old,new in sorted(pairs,key=lambda x:len(x[0]),reverse=True):
     origin=old.replace('\\','/')
     if origin.startswith('//?/'):origin=origin[4:]
     if native==origin or native.startswith(origin+'/'):
      target=new.replace('\\','/')+native[len(origin):]
      if target.startswith('//?/'):target=target[4:]
      return 'file://'+quote('/'+target.lstrip('/'),safe='/:')
  for old,new in sorted(pairs,key=lambda x:len(x[0]),reverse=True):
   if obj==old or obj.startswith(old+'\\') or obj.startswith(old+'/'):
    return new+obj[len(old):].replace('\\','/')
 return obj
