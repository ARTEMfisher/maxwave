"""Cross-platform supervisor. Explicit launch only; no login service is installed."""
import logging,logging.handlers,os,signal,subprocess,sys,threading,time
from .common import *
from .lock import RunningLock

def run(cfg):
 try:
  with RunningLock():_run(cfg)
 except BlockingIOError:print('Мост уже запущен в другом окне.')

def _run(cfg):
 from .station import start_server
 STATE.mkdir(exist_ok=True);stopfile=STATE/'stop.request'
 if stopfile.exists():stopfile.unlink()
 logs=STATE/'logs';logs.mkdir(exist_ok=True)
 log=logging.getLogger('maxwave');log.setLevel(logging.INFO)
 handler=logging.handlers.RotatingFileHandler(logs/'bridge.log',maxBytes=2000000,backupCount=2,encoding='utf-8');log.addHandler(handler)
 try:(logs/'bridge.log').chmod(0o600)
 except OSError:pass
 closing=threading.Event();child=None
 def finish(*args):
  closing.set();stopfile.write_text('stop',encoding='ascii')
 previous={}
 for sig in [signal.SIGINT,signal.SIGTERM]+([signal.SIGHUP] if hasattr(signal,'SIGHUP') else []):previous[sig]=signal.signal(sig,finish)
 def watcher():
  while not closing.wait(.5):
   if stopfile.exists():closing.set()
 threading.Thread(target=watcher,daemon=True).start()
 print('Мост работает через этот компьютер. Не усыпляйте компьютер; остановка доступна из меню шага 2.')
 failures=0
 try:
  while not closing.is_set():
   began=time.monotonic()
   try:
    adb=start_server(cfg);pid=int(adb.shell('pidof','com.yandex.io.sdk').split()[0]);time.sleep(.5)
    env=os.environ.copy();env['MAXWAVE_ROOT']=str(ROOT)
    child=subprocess.Popen([sys.executable,str(ROOT/'bridge/worker.py'),'--pid',str(pid),'--seconds','0','--route'],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',bufsize=1)
    for line in child.stdout:
     log.info(line.rstrip())
     if line.startswith('MODE route'):print('Готово: музыкальные команды направляются в YouTube Music.',flush=True)
    child.wait()
    if closing.is_set():break
    failures=0 if time.monotonic()-began>60 else failures+1
    if failures>=3:raise UserError('Агент трижды не подключился. Проверьте .station/logs/bridge.log и совместимость.')
   except UserError as e:
    print(e)
    if 'Не проверенная комбинация' in str(e) or failures>=3:break
   except Exception:log.exception('Bridge connection failed')
   if closing.wait(5):break
   print('Пробую восстановить соединение…')
 finally:
  finish()
  if child and child.poll() is None:
   try:child.wait(timeout=10)
   except subprocess.TimeoutExpired:child.terminate();child.wait(timeout=5)
  for sig,old in previous.items():signal.signal(sig,old)
  log.removeHandler(handler);handler.close()
  print('Мост отключён. Штатная Алиса продолжает работать.')
