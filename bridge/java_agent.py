import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from maxwave.common import load_config
import frida,pathlib,json
BASE=pathlib.Path(__file__).parent
class JavaAgent:
 def __init__(self,pid,code):
  self.session=frida.get_device_manager().add_remote_device('127.0.0.1:'+str(load_config().get('frida_port',27043))).attach(pid)
  self.script=self.session.create_script("var chunks=[];rpc.exports={append:s=>chunks.push(s),run:()=>{(0,eval)(chunks.join(''));chunks=[];}};")
  self.script.on('message',lambda m,d:print('PLAYER_AGENT',json.dumps(m,ensure_ascii=False),flush=True))
  self.script.load()
  bridge=__import__('importlib.resources',fromlist=['files']).files('frida_tools').joinpath('bridges/java.js').read_text()
  source=bridge+'\nvar Java=bridge;\n'+code
  for i in range(0,len(source),6000):self.script.exports_sync.append(source[i:i+6000])
  self.script.exports_sync.run()
 def close(self):
  try:self.session.detach()
  except Exception:pass
