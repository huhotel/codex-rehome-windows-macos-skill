import os,json,subprocess,threading,queue,time,hashlib
from pathlib import Path
CLI=None
class Rpc:
 def __init__(self,home,cli=CLI):
  if not cli:raise ValueError("Explicit target-compatible --codex path required")
  home=Path(home).resolve();home.mkdir(parents=True,exist_ok=True)
  env=os.environ.copy();env['CODEX_HOME']=str(home);env['HOME']=str(home.parent);env['USERPROFILE']=str(home.parent)
  env['APPDATA']=str(home.parent/'appdata');env['LOCALAPPDATA']=str(home.parent/'localappdata')
  for k in list(env):
   if any(x in k.upper() for x in ['API_KEY','ACCESS_TOKEN','AUTH_TOKEN']):env.pop(k,None)
  self.err=(home.parent/'app-server-stderr.log').open('wb')
  self.p=subprocess.Popen([str(cli),'app-server','--stdio','-c','analytics.enabled=false'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,env=env,cwd=home.parent)
  self.q=queue.Queue();self.seq=0
  def read():
   for line in self.p.stdout:
    try:self.q.put(json.loads(line))
    except Exception:self.q.put({'parse_error':True})
   self.q.put({'eof':True})
  threading.Thread(target=read,daemon=True).start()
  self.initialized=self.call('initialize',{'clientInfo':{'name':'rehome_verified_reader','version':'2.0'},'capabilities':{'experimentalApi':True}})
  self.send({'method':'initialized','params':{}})
 def send(self,obj):self.p.stdin.write((json.dumps(obj)+'\n').encode());self.p.stdin.flush()
 def call(self,method,params,timeout=120):
  self.seq+=1;rid=self.seq;self.send({'id':rid,'method':method,'params':params});deadline=time.monotonic()+timeout
  while True:
   msg=self.q.get(timeout=max(.1,deadline-time.monotonic()))
   if msg.get('eof'):raise RuntimeError('app-server exited')
   if msg.get('id')==rid:
    if 'error' in msg:raise RuntimeError(json.dumps(msg['error'],ensure_ascii=False))
    return msg.get('result')
 def close(self):
  self.p.terminate()
  try:self.p.wait(timeout=10)
  except subprocess.TimeoutExpired:self.p.kill();self.p.wait()
  self.err.close()
def pages(rpc,method,tid,limit=100):
 cursor=None;seen=set();result=[];n=0
 while True:
  args={'threadId':tid,'limit':limit,'sortDirection':'asc'}
  if method=='thread/turns/list':args['itemsView']='full'
  if cursor:args['cursor']=cursor
  page=rpc.call(method,args);n+=1
  data=page.get('data',page.get('turns',page.get('items',[])));result.extend(data)
  cursor=page.get('nextCursor')
  if not cursor:break
  if cursor in seen:raise RuntimeError('repeated cursor')
  seen.add(cursor)
 return result,n
