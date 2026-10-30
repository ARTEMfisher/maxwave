import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from maxwave.common import load_config,tool,STATE
CFG=load_config()
ADB=tool(CFG,"adb")
TARGET=CFG["target"]
import argparse,frida,pathlib,time,json,queue,threading,subprocess
from java_agent import JavaAgent
from announce import announce
from resolver import search,mood_flow
p=pathlib.Path(__file__).parent
ap=argparse.ArgumentParser();ap.add_argument('--pid',type=int,required=True);ap.add_argument('--seconds',type=int,default=0);ap.add_argument('--search');ap.add_argument('--route',action='store_true');args=ap.parse_args()
stop=threading.Event()
d=frida.get_device_manager().add_remote_device('127.0.0.1:'+str(CFG.get('frida_port',27043)));s=d.attach(args.pid)
def detached(*args):
 print('DETACHED',args,flush=True);stop.set()
s.on('detached',detached)
a=s.create_script("var chunks=[];rpc.exports={append:function(s){chunks.push(s);},run:function(){(0,eval)(chunks.join(''));chunks=[];}};")
work=queue.Queue(maxsize=4);latest_request=None
def message(m,data):
 global latest_request
 print(json.dumps(m,ensure_ascii=False),flush=True)
 payload=m.get('payload',{})
 if payload.get('event') in ('accepted','passed','quick_dispatched') and payload.get('request'):
  latest_request=payload['request']
  while True:
   try:work.get_nowait()
   except queue.Empty:break
 if m.get('type')=='send' and payload.get('event')=='accepted' and payload.get('intent',{}).get('kind') in ('search','flow','personal','mode','announce','rating'):
  try:work.put_nowait((time.monotonic(),payload))
  except queue.Full:print('SEARCH_QUEUE_FULL',flush=True)
a.on('message',message);a.load()
def worker():
 player_agent=None;player_pid=None
 while not stop.is_set():
  try:stamp,event=work.get(timeout=.5)
  except queue.Empty:continue
  if time.monotonic()-stamp>10 or latest_request!=event['request']:continue
  try:
   intent=event['intent']
   if intent['kind']=='mode':
    was_paused=a.exports_sync.inspect()['player'].get('state')==2
    if intent['mode']=='video':a.exports_sync.foregroundplayer()
    pid=int(subprocess.check_output([ADB,'-s',TARGET,'shell','pidof','app.rvx.android.apps.youtube.music'],timeout=5).strip())
    if player_agent is None or player_pid!=pid:
     if player_agent:player_agent.close()
     player_agent=JavaAgent(pid,(p/'player-agent.js').read_text());player_pid=pid
    if latest_request!=event['request']:continue
    print('MODE_REQUESTED',player_agent.script.exports_sync.setmode(intent['mode']),flush=True)
    time.sleep(.7)
    states=player_agent.script.exports_sync.inspect()
    confirmed=any(x['audio']==(intent['mode']=='audio') for x in states if x['shown'])
    print('MODE_CONFIRMED' if confirmed else 'MODE_UNCONFIRMED',intent['mode'],flush=True)
    if was_paused and latest_request==event['request']:a.exports_sync.dispatch({'kind':'pause'})
    continue
   elif intent['kind']=='announce':
    st=a.exports_sync.inspect()['player']
    print('ANNOUNCEMENT',announce(a,event['request'],st.get('artist'),st.get('title')),flush=True)
    continue
   elif intent['kind']=='rating':
    expected='unrated' if intent['value'] is None else ('rating=1.0' if intent['value'] else 'rating=0.0')
    for _ in range(8):
     time.sleep(.3);st=a.exports_sync.inspect()['player']
     if expected in (st.get('rating') or ''):print('RATING_CONFIRMED',intent['value'],flush=True);break
    else:print('RATING_UNCONFIRMED',flush=True)
    continue
   elif intent['kind']=='flow':song=mood_flow(intent['mood'])
   elif intent['kind']=='personal':
    a.exports_sync.openmix(event['request'],'RDTMAK5uy_kset8DisdE7LSD4TNjEVvrKRTmG7a56sY')
    print('PERSONAL_MIX_OPENED',flush=True)
    continue
   else:song=search(intent['query'],intent.get('mediaType','auto'),intent.get('channel'))
   a.exports_sync.openvideo(event['request'],song['id'],song.get('playlistId'))
   print('OPENED',json.dumps(song,ensure_ascii=False),flush=True)
   deadline=time.monotonic()+12
   while time.monotonic()<deadline and not stop.is_set():
    if latest_request!=event['request']:break
    st=a.exports_sync.inspect()['player']
    if st.get('state')==3 and st.get('title')==song['title']:
     print('PLAYING',json.dumps(st,ensure_ascii=False),flush=True);break
    time.sleep(.5)
   else:print('PLAYBACK_UNCONFIRMED',flush=True)
  except Exception as e:
   print('COMMAND_FAILED',type(e).__name__,str(e),flush=True)
   if intent.get('kind')=='mode' and player_agent:
    player_agent.close();player_agent=None
 if player_agent:player_agent.close()
threading.Thread(target=worker,daemon=True).start()
b=__import__('importlib.resources',fromlist=['files']).files('frida_tools').joinpath('bridges/java.js').read_text()+'\nvar Java=bridge;\n'+(p/'music-core.js').read_text()+'\n'+(p/'agent.js').read_text()
try:
 for i in range(0,len(b),6000):a.exports_sync.append(b[i:i+6000])
 a.exports_sync.run()
 for _ in range(30):
  try:
   r=a.exports_sync.inspect()
   if r['ready']:break
  except frida.RPCException:pass
  time.sleep(.2)
 else:raise RuntimeError('Agent not ready')
 print('INSPECT',json.dumps(r,ensure_ascii=False),flush=True)
 if args.search:print('SEARCH',a.exports_sync.dispatch({'kind':'search','query':args.search}),flush=True)
 if args.route:print('MODE',a.exports_sync.mode('route'),flush=True)
 end=time.monotonic()+args.seconds if args.seconds>0 else float('inf')
 while time.monotonic()<end and not stop.wait(1):
  if (STATE/'stop.request').exists():break
 print('TEST_WINDOW_COMPLETE',flush=True)
finally:
 stop.set()
 try:a.exports_sync.shutdown()
 except Exception:pass
 try:s.detach()
 except Exception:pass
