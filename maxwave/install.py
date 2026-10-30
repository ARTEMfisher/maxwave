"""Step 1: download/extract desktop tools, install bundled APKs, open apps + scrcpy."""
import argparse,json,os,pathlib,shutil,subprocess
from .common import *

APPS={'1':('Happ VPN','su.happ.proxyutility'),'2':('YouTube Music',PACKAGE),'3':('GmsCore','app.revanced.android.gms'),'4':('ReVanced Manager','app.revanced.manager.flutter'),'5':('Настройки Android','com.android.tv.settings')}

def choose_platform():
 keys=list(PLATFORMS);current=host_platform()
 print('\nПлатформа компьютера (определена: '+PLATFORMS[current]+')')
 for i,k in enumerate(keys,1):print(f' {i}. {PLATFORMS[k]}'+(' [по умолчанию]' if k==current else ''))
 choice=input('Номер или Enter: ').strip()
 if not choice:return current
 if not choice.isdigit() or not 1<=int(choice)<=len(keys):raise UserError('Неверный номер платформы.')
 return keys[int(choice)-1]

def find_tool(directory,name):
 candidates=list(directory.rglob(name))
 if not candidates:raise UserError(name+' не найден в распакованном ресурсе.')
 if len(candidates)>1:candidates.sort(key=lambda p:len(p.parts))
 p=candidates[0]
 if os.name!='nt':p.chmod(p.stat().st_mode|0o111)
 return str(p.relative_to(ROOT))

def resources(platform_key):
 manifest=json.loads((ROOT/'resources.json').read_text())
 tools={};cache=ROOT/'.cache';out=ROOT/'tools'/platform_key
 for name in ('adb','scrcpy'):
  spec=manifest['platforms'][platform_key].get(name)
  if spec is None:
   found=shutil.which(name)
   if not found:raise UserError('Для Linux ARM64 установите системные пакеты adb и scrcpy: sudo apt install adb scrcpy. Затем повторите установку.')
   tools[name]=found;continue
  path=download(spec['url'],cache/spec['url'].split('/')[-1],spec['sha256'])
  folder=out/name
  stamp=folder/'.maxwave-sha256'
  if not stamp.exists() or stamp.read_text()!=spec['sha256']:
   if folder.exists():shutil.rmtree(folder)
   extract(path,folder);stamp.write_text(spec['sha256'])
  tools[name]=find_tool(folder,name+('.exe' if platform_key.startswith('windows') else ''))
 return tools

def verify_apps():
 manifest=json.loads((ROOT/'apps-manifest.json').read_text())
 if not all((ROOT/a['file']).exists() for a in manifest['apps']):
  r=json.loads((ROOT/'resources.json').read_text())['apps_bundle']
  print('Загружаю готовые APK из релиза MaxWave…')
  z=download(r['url'],ROOT/'.cache/apps.zip',r['sha256']);extract(z,ROOT)
 for a in manifest['apps']:
  if sha256(ROOT/a['file'])!=a['sha256']:raise UserError('APK повреждён или подменён: '+a['file'])
 return manifest['apps']

def install_apps(cfg):
 adb=Adb(cfg);adb.connect();adb.verify()
 apps=verify_apps();baseline=cfg.setdefault('baseline',{})
 for a in apps:
  if a['package'] not in baseline:baseline[a['package']]={'existed_before':adb.package_installed(a['package'])}
 save_config(cfg)
 for a in apps:
  print('Установка '+pathlib.Path(a['file']).name+'…')
  print(adb.run('install','-r',str(ROOT/a['file']),timeout=240))
  cfg.setdefault('installed_by_project',[])
  if a['package'] not in cfg['installed_by_project']:cfg['installed_by_project'].append(a['package'])
  save_config(cfg)
 # This is the one power-management change; save it for conditional rollback.
 before=adb.shell('dumpsys','deviceidle','whitelist')
 if 'gms_whitelisted_before' not in cfg:cfg['gms_whitelisted_before']='app.revanced.android.gms' in before;save_config(cfg)
 adb.shell('dumpsys','deviceidle','whitelist','+app.revanced.android.gms')
 print('APK установлены. Подписку Happ и вход Google настройте в приложениях.')

def open_app(adb,package):
 component=adb.shell('cmd','package','resolve-activity','--brief','-a','android.intent.action.MAIN','-c','android.intent.category.LAUNCHER',package).splitlines()
 value=next((x.strip() for x in reversed(component) if x.strip().startswith(package+'/')),None)
 if value:adb.shell('am','start','-n',value)
 else:adb.shell('monkey','-p',package,'-c','android.intent.category.LAUNCHER','1')

def mirror(cfg):
 # Amlogic H.264 stalled on the tested Station; software VP8 works.
 return subprocess.Popen([tool(cfg,'scrcpy'),'-s',cfg['target'],'--no-audio','--video-codec=vp8','--video-encoder=OMX.google.vp8.encoder','--max-size=960','--max-fps=15','--window-title=MaxWave — Station Max'])

def app_menu(cfg):
 adb=Adb(cfg);screen=None
 while True:
  choice=menu('Настройка приложений',[(k,v[0]+' + экран scrcpy') for k,v in APPS.items()]+[('6','Только экран станции'),('9','Подготовить и запустить голосовой мост'),('0','Выход')])
  if choice=='0':return
  if choice=='9':
   ensure_runtime(False)
   subprocess.run([str(runtime_python()),str(ROOT/'02_station.py'),'--prepare-and-run'],check=True);return
  if choice in APPS:open_app(adb,APPS[choice][1])
  if choice in APPS or choice=='6':
   if screen is None or screen.poll() is not None:screen=mirror(cfg)


def main():
 ap=argparse.ArgumentParser(description='MaxWave: APK и инструменты');ap.add_argument('--platform',choices=PLATFORMS);ap.add_argument('--ip');ap.add_argument('--download-only',action='store_true');ap.add_argument('--open-only',action='store_true');args=ap.parse_args()
 if args.open_only:app_menu(load_config());return
 selected=args.platform or choose_platform()
 old=load_config() if (STATE/'config.json').exists() else {}
 ip=args.ip or input('IPv4 Яндекс Станции'+(' ['+old['target']+']' if old.get('target') else '')+': ').strip() or old.get('target','')
 cfg={**old,'target':target_address(ip),'platform':selected,'frida_port':27043,'root_dir':REMOTE,'tools':resources(selected)}
 save_config(cfg);verify_apps()
 if args.download_only or selected!=host_platform():
  print('Ресурсы скачаны и распакованы. Установка на станцию не запускалась.');return
 install_apps(cfg);app_menu(cfg)
