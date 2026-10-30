"""Install the autonomous Station service; no Android flashing or host music process."""
import argparse,json,pathlib,secrets,shlex,subprocess,tempfile,time
from .common import *
MARKER='maxwave-station-native-v1'
BOOT='/data/local/tmp/myscript-max.sh'
BOOT_BLOCK=f'\n# BEGIN MaxWave autonomous\n[ -f {REMOTE}/enabled ] && /system/bin/sh {REMOTE}/start.sh\n# END MaxWave autonomous\n'

def _root_script(adb,content):
 with tempfile.TemporaryDirectory(prefix='maxwave-') as td:
  p=pathlib.Path(td)/'action.sh';p.write_text('#!/system/bin/sh\nset -eu\n'+content+'\n',encoding='utf-8')
  adb.push(p,REMOTE+'/action.sh');return adb.root('/system/bin/sh',REMOTE+'/action.sh')

def owned(adb):
 result=adb.shell('sh','-c',f'if [ -d {REMOTE} ]; then cat {REMOTE}/owner 2>/dev/null || true; else echo absent; fi')
 if result not in (MARKER,'absent'):raise UserError('Каталог '+REMOTE+' занят установкой без метки MaxWave. Автоматическая замена запрещена.')
 return result==MARKER

def assets():
 manifest=json.loads((ROOT/'native-manifest.json').read_text())
 missing=[a for a in manifest['files'] if not (ROOT/a['file']).is_file() or sha256(ROOT/a['file'])!=a['sha256']]
 if missing:
  spec=json.loads((ROOT/'resources.json').read_text()).get('native_bundle')
  if not spec:raise UserError('Нет комплектных ресурсов станции. Используйте полный пакет релиза; сборка из исходников ещё не готова.')
  archive=download(spec['url'],ROOT/'.cache/native-assets.zip',spec['sha256']);extract(archive,ROOT)
 for a in manifest['files']:
  if not (ROOT/a['file']).is_file() or sha256(ROOT/a['file'])!=a['sha256']:raise UserError('Повреждён ресурс станции: '+a['file'])
 return manifest

def prepare(cfg,dry_run=False):
 adb=Adb(cfg);adb.connect();device,fw=adb.verify(root=True)
 if not adb.package_installed(PACKAGE):raise UserError('Сначала установите YouTube Music: шаг 1.')
 if not re.search(r'\bversionName=8\.12\.54(?:\s|$)',adb.shell('dumpsys','package',PACKAGE)):raise UserError('Нужен YouTube Music 8.12.54 из комплекта.')
 from .vpn import require_youtube_only
 require_youtube_only(adb)
 exists=owned(adb)
 boot=adb.root('cat',BOOT)
 if 'myfs.ext4' not in boot or 'sepolicy-inject' not in boot:raise UserError('Неизвестный механизм постоянного root. Автозапуск не будет добавлен в неподтверждённый файл.')
 if '# BEGIN MaxWave autonomous' in boot and BOOT_BLOCK.strip() not in boot:raise UserError('В файле запуска уже есть другой блок MaxWave; нужна ручная проверка.')
 print(f'Проверено: {device}, прошивка {fw}, root. Будет установлен автономный сервис на станции.')
 if dry_run:print('DRY RUN: ничего не изменено.');return
 manifest=assets();adb.shell('mkdir','-p',REMOTE)
 if not exists:adb.shell('sh','-c',f'printf %s {shlex.quote(MARKER)} > {REMOTE}/owner')
 if exists:request_stop(cfg)
 with tempfile.TemporaryDirectory(prefix='maxwave-install-') as td:
  stage=pathlib.Path(td);stage.chmod(0o700)
  # Preserve the installation's IPC token; never display it.
  token=''
  if exists:
   try:token=adb.root('cat',REMOTE+'/token')
   except UserError:pass
  if not re.fullmatch('[a-f0-9]{64}',token):token=secrets.token_hex(32)
  p=stage/'token';p.write_text(token+'\n');p.chmod(0o600);adb.push(p,REMOTE+'/token')
  java=(ROOT/'station/java-bridge.js').read_text();transport=(ROOT/'native/transport.js').read_text()
  for role,name in [('sdk','agent.js'),('player','player-agent.js')]:
   code=(ROOT/'bridge'/name).read_text().replace('send({','emit({')
   core=(ROOT/'bridge/music-core.js').read_text() if role=='sdk' else ''
   p=stage/(role+'.js');p.write_text(java+'\nvar Java=bridge;\nconst LOCAL_ROLE='+json.dumps(role)+';const LOCAL_TOKEN='+json.dumps(token)+';\n'+transport+'\n'+core+'\n'+code);p.chmod(0o600);adb.push(p,REMOTE+'/'+p.name)
  exports=[]
  for key in ['BOOTCLASSPATH','SYSTEMSERVERCLASSPATH','ANDROID_ROOT','ANDROID_DATA']:
   value=adb.shell('printenv',key)
   if value:exports.append('export '+key+'='+shlex.quote(value))
  if not any(s.startswith('export BOOTCLASSPATH=') for s in exports):raise UserError('Окружение Android runtime недоступно.')
  p=stage/'env.sh';p.write_text('\n'.join(exports)+'\n');adb.push(p,REMOTE+'/env.sh')
 adb.push(ROOT/'station/assets',REMOTE+'/')
 _root_script(adb,f'cp -R {REMOTE}/assets/. {REMOTE}/\nrm -rf {REMOTE}/assets')
 for local,name in [('native-start.sh','start.sh'),('native-stop.sh','stop.sh'),('watchdog.sh','watchdog.sh'),('NetworkProbe.dex','NetworkProbe.dex'),('VpnAlwaysOn.dex','VpnAlwaysOn.dex')]:adb.push(ROOT/'station'/local,REMOTE+'/'+name)
 _root_script(adb,f'chmod 755 {REMOTE} {REMOTE}/maxwaved {REMOTE}/frida-inject {REMOTE}/espeak-ng\nchmod 600 {REMOTE}/token {REMOTE}/env.sh {REMOTE}/sdk.js {REMOTE}/player.js')
 if '# BEGIN MaxWave autonomous' not in boot:
  _root_script(adb,f'[ -f {BOOT} ]\n[ -f {REMOTE}/boot-before-maxwave.sh ] || cp -p {BOOT} {REMOTE}/boot-before-maxwave.sh\nprintf %s {shlex.quote(BOOT_BLOCK)} >> {BOOT}')
 if adb.package_installed('su.happ.proxyutility'):
  previous=adb.shell('settings','get','secure','always_on_vpn_app')
  cfg.setdefault('always_on_before',previous)
  if previous in ('null','','su.happ.proxyutility'):
   try:print(_root_script(adb,f'. {REMOTE}/env.sh\nexport CLASSPATH={REMOTE}/VpnAlwaysOn.dex\nexec app_process /system/bin VpnAlwaysOn enable'))
   except UserError:print('Android не подтвердил Always-on Happ. Проверьте его вручную в настройках VPN; блокировка сети не включалась.')
  else:print('Сохранён другой Always-on VPN:',previous)
 cfg['prepared']=True;cfg['device']={'device':device,'firmware':fw};save_config(cfg)
 print('Установлено на станцию. Файл постоянного root сохранён; в него добавлен только блок запуска MaxWave. Разделы Android не прошивались.')

def request_stop(cfg=None,wait=15):
 cfg=cfg or load_config();adb=Adb(cfg);adb.connect()
 if not owned(adb):return True
 adb.root('/system/bin/sh',REMOTE+'/stop.sh')
 for _ in range(wait):
  if adb.shell('sh','-c',f'cat {REMOTE}/daemon.pid 2>/dev/null || true')=='':return True
  time.sleep(1)
 raise UserError('Сервис не подтвердил завершение. Повторный экземпляр запускаться не будет.')

def start_background(cfg):
 adb=Adb(cfg);adb.connect();adb.verify(root=True)
 if not owned(adb):raise UserError('Сначала выполните пункт 1.')
 print(adb.root('/system/bin/sh',REMOTE+'/start.sh'))
 print('Обработчик запущен НА СТАНЦИИ. Это окно и компьютер можно закрыть. Автозапуск проверяйте после перезагрузки.')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--dry-run',action='store_true');ap.add_argument('--prepare-and-run',action='store_true');args=ap.parse_args();cfg=load_config()
 if args.dry_run:prepare(cfg,True);return
 if args.prepare_and_run:prepare(cfg);start_background(cfg)
 while True:
  c=menu('Автономный MaxWave: нужна прошивка 0921 с постоянным mysudo/root',[('1','Проверить и установить сервис на станцию'),('2','Включить сервис и автозапуск на станции'),('3','Отключить сервис и его автозапуск'),('4','Открыть приложения и scrcpy'),('5','Перейти к диагностике'),('0','Выход — сервис продолжает работать на станции')])
  if c=='0':return
  if c=='1':prepare(cfg)
  elif c=='2':start_background(cfg)
  elif c=='3':request_stop(cfg);print('Сервис и его автозапуск отключены.')
  elif c=='4':
   from .install import app_menu
   app_menu(cfg)
  elif c=='5':subprocess.run([sys.executable,str(ROOT/'03_diagnostics.py')],check=True)
