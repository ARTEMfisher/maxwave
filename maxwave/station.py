"""Step 2: prepare the already-rooted 0921 Station; never flash partitions."""
import argparse,json,lzma,pathlib,shlex,subprocess,tempfile,time
from .common import *
MARKER='maxwave-v1'

def _root_script(adb,content):
 with tempfile.TemporaryDirectory(prefix='maxwave-') as td:
  p=pathlib.Path(td)/'action.sh';p.write_text('#!/system/bin/sh\nset -eu\n'+content+'\n',encoding='utf-8')
  adb.push(p,REMOTE+'/action.sh');return adb.root('/system/bin/sh',REMOTE+'/action.sh')

def owned(adb):
 result=adb.shell('sh','-c',f'if [ -d {REMOTE} ]; then cat {REMOTE}/owner 2>/dev/null || true; else echo absent; fi')
 if result not in (MARKER,'absent'):raise UserError('Каталог '+REMOTE+' уже занят чужой установкой. Он не будет заменён.')
 return result==MARKER

def prepare(cfg,dry_run=False):
 adb=Adb(cfg);adb.connect();device,fw=adb.verify(root=True)
 if not adb.package_installed(PACKAGE):raise UserError('Сначала установите YouTube Music: шаг 1.')
 package=adb.shell('dumpsys','package',PACKAGE)
 if not re.search(r'\bversionName=8\.12\.54(?:\s|$)',package):raise UserError('Агент проверен только с YouTube Music 8.12.54 из пакета MaxWave.')
 exists=owned(adb)
 print(f'Проверено: {device}, прошивка {fw}, root. Разделы Android не прошиваются.')
 print('Будет подготовлен '+REMOTE+', Frida ARM64 на loopback:27043 и диагностический probe.dex.')
 if dry_run:print('DRY RUN: ничего на станции не изменено.');return
 adb.shell('mkdir','-p',REMOTE)
 if not exists:adb.shell('sh','-c',f'printf %s {shlex.quote(MARKER)} > {REMOTE}/owner')
 manifest=json.loads((ROOT/'resources.json').read_text());spec=manifest['frida_server']
 archive=download(spec['url'],ROOT/'.cache/frida-server.xz',spec['sha256'])
 unpacked=ROOT/'.cache/frida-server'
 with lzma.open(archive) as src,unpacked.open('wb') as dst:shutil.copyfileobj(src,dst)
 adb.push(unpacked,REMOTE+'/frida-server')
 adb.push(ROOT/'station/NetworkProbe.dex',REMOTE+'/NetworkProbe.dex')
 # Only runtime path variables, never a full environment dump or account configuration.
 exports=[]
 for key in ['BOOTCLASSPATH','SYSTEMSERVERCLASSPATH','ANDROID_ROOT','ANDROID_DATA']:
  val=adb.shell('printenv',key)
  if val:exports.append('export '+key+'='+shlex.quote(val))
 if not any(x.startswith('export ANDROID_ROOT=') for x in exports):exports.append('export ANDROID_ROOT=/system')
 if not any(x.startswith('export ANDROID_DATA=') for x in exports):exports.append('export ANDROID_DATA=/data')
 with tempfile.TemporaryDirectory() as td:
  env=pathlib.Path(td)/'env.sh';env.write_text('\n'.join(exports)+'\n');adb.push(env,REMOTE+'/env.sh')
 for f in ('start.sh','stop.sh'):adb.push(ROOT/'station'/f,REMOTE+'/'+f)
 _root_script(adb,f'chmod 755 {REMOTE}/frida-server {REMOTE}/start.sh {REMOTE}/stop.sh\nchmod 644 {REMOTE}/NetworkProbe.dex {REMOTE}/env.sh')
 cfg['prepared']=True;cfg['device']={'device':device,'firmware':fw};save_config(cfg)
 print('Станция подготовлена. Автозапуск на станции и системные параметры не менялись.')

def start_server(cfg):
 adb=Adb(cfg);adb.connect();adb.verify(root=True)
 if not owned(adb):raise UserError('Сначала подготовьте станцию: пункт 1.')
 print(adb.root('/system/bin/sh',REMOTE+'/start.sh'))
 port=int(cfg.get('frida_port',27043))
 adb.run('forward','tcp:'+str(port),'tcp:27043')
 return adb

def request_stop(wait=12):
 from .lock import is_running
 if not is_running():return True
 (STATE/'stop.request').write_text('stop',encoding='ascii')
 end=time.monotonic()+wait
 while time.monotonic()<end:
  if not is_running():return True
  time.sleep(.25)
 return False

def start_background(cfg):
 from .lock import is_running
 if is_running():print('Мост уже запущен.');return
 STATE.mkdir(exist_ok=True);out=(STATE/'supervisor.log').open('a',encoding='utf-8')
 kwargs={'stdin':subprocess.DEVNULL,'stdout':out,'stderr':subprocess.STDOUT,'cwd':ROOT}
 if os.name=='nt':kwargs['creationflags']=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP
 else:kwargs['start_new_session']=True
 subprocess.Popen([sys.executable,str(ROOT/'02_station.py'),'--run-only'],**kwargs);out.close()
 for _ in range(30):
  if is_running():print('Мост запущен в фоне. Для остановки — пункт 3; диагностика — пункт 5.');return
  time.sleep(.1)
 raise UserError('Фоновый процесс не запустился; смотрите .station/supervisor.log.')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--dry-run',action='store_true');ap.add_argument('--prepare-and-run',action='store_true');ap.add_argument('--run-only',action='store_true');args=ap.parse_args()
 if args.dry_run:prepare(load_config(),True);return
 ensure_runtime();cfg=load_config()
 if args.run_only:
  from .runner import run
  run(cfg);return
 if args.prepare_and_run:prepare(cfg);start_background(cfg)
 while True:
  c=menu('Настройка MaxWave: нужна прошивка 0921 с mysudo/root', [('1','Проверить и подготовить станцию'),('2','Запустить голосовой мост в фоне'),('3','Остановить мост'),('4','Снова открыть меню приложений и scrcpy'),('5','Перейти к диагностике (включая VPN)'),('0','Выход')])
  if c=='0':return
  if c=='1':prepare(cfg)
  elif c=='2':start_background(cfg)
  elif c=='3':print('Мост остановлен.' if request_stop() else 'Мост не завершился. Не запускайте второй экземпляр.')
  elif c=='4':
   from .install import app_menu
   app_menu(cfg)
  elif c=='5':subprocess.run([sys.executable,str(ROOT/'03_diagnostics.py')],check=True)

