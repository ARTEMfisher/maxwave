"""Numbered diagnostics. Network checks do not change VPN/DNS/firewall settings."""
import json,re,shlex,subprocess,sys
from .common import *

HOSTS=['https://www.google.com/generate_204','https://music.youtube.com/','https://api.ipify.org/']

def info(adb):
 for prop in ['ro.product.model','ro.product.device','ro.build.version.incremental','ro.build.version.release']:
  print(prop+' = '+adb.prop(prop))
 print('root:',adb.root('id'));print('SELinux:',adb.shell('getenforce'))

def apps(adb):
 for a in json.loads((ROOT/'apps-manifest.json').read_text())['apps']:
  text=adb.shell('dumpsys','package',a['package'])
  versions=re.findall(r'\b(?:versionName|versionCode|userId)=[^\s]+',text)
  print(a['package'],', '.join(dict.fromkeys(versions)) if versions else 'НЕ УСТАНОВЛЕНО')

def app_uid(adb):
 m=re.search(r'\buserId=(\d+)',adb.shell('dumpsys','package',PACKAGE))
 if not m:raise UserError('YouTube Music не найден.')
 return int(m.group(1))

def vpn(adb):
 text=adb.shell('dumpsys','connectivity');uid=app_uid(adb)
 agents=[line for line in text.splitlines() if 'NetworkAgentInfo{' in line and 'VPN' in line]
 print('UID YouTube Music:',uid)
 print('VPN-сеть Android:','обнаружена' if agents else 'не обнаружена')
 for line in agents:
  ranges=re.search(r'Uids:\s*<\{([^}]*)\}>',line)
  routed=False
  if ranges:
   for token in ranges.group(1).split(','):
    ends=token.strip().split('-')
    if all(x.isdigit() for x in ends):
     lo=int(ends[0]);hi=int(ends[-1]);routed|=lo<=uid<=hi
  print(' VPN VALIDATED:', 'VALIDATED' in line, '; UID включён в опубликованные диапазоны:',routed if ranges else 'диапазоны не показаны')
 print('Интерфейсы:',adb.shell('ip','-o','link','show').replace('\n','\n '))
 print('Наличие tun/VPN само по себе не доказывает доступность конкретного сервера подписки. Следующий пункт делает HTTPS-проверку от UID музыкального приложения.')

def network(adb):
 from .station import owned,_root_script
 if not owned(adb):raise UserError('Для сетевого probe сначала выполните подготовку станции в шаге 2.')
 uid=app_uid(adb)
 for url in HOSTS:
  print('Проверка',url.split('/')[2])
  code=f'. {REMOTE}/env.sh\nexport CLASSPATH={REMOTE}/NetworkProbe.dex\nexec app_process /system/bin NetworkProbe {uid} {shlex.quote(url)}'
  try:print(_root_script(adb,code))
  except (UserError,subprocess.TimeoutExpired) as e:print('Недоступен:',e)
 print('Это тест маршрута UID YouTube Music, а не тест всех узлов Happ. Состояние/задержку конкретных узлов смотрите в Happ.')

def player(cfg,adb):
 from .station import start_server
 start_server(cfg)
 sys.path.insert(0,str(ROOT/'bridge'))
 from java_agent import JavaAgent
 pid=int(adb.shell('pidof','com.yandex.io.sdk').split()[0])
 agent=JavaAgent(pid,(ROOT/'bridge/read-only-agent.js').read_text())
 try:print(json.dumps(agent.script.exports_sync.inspect(),ensure_ascii=False,indent=2))
 finally:agent.close()

def main():
 ap=__import__('argparse').ArgumentParser();ap.add_argument('--test',choices=['info','apps','vpn','network','player']);args=ap.parse_args()
 cfg=load_config();adb=Adb(cfg);adb.connect()
 actions={'info':lambda:info(adb),'apps':lambda:apps(adb),'vpn':lambda:vpn(adb),'network':lambda:network(adb),'player':lambda:player(cfg,adb)}
 if args.test:
  if args.test=='player':ensure_runtime()
  actions[args.test]();return
 while True:
  c=menu('Диагностика MaxWave',[('1','ADB, прошивка, root и SELinux'),('2','Установленные APK и версии'),('3','VPN-интерфейс и диапазон UID приложения'),('4','Интернет и внешний IP от UID YouTube Music'),('5','Текущий трек, оценки и MediaSession'),('6','Открыть scrcpy'),('7','Памятка проверки голосовых команд'),('8','Последние 25 строк журнала моста'),('0','Выход')])
  if c=='0':return
  try:
   if c in ['1','2','3','4']:actions[{'1':'info','2':'apps','3':'vpn','4':'network'}[c]]()
   elif c=='5':ensure_runtime();player(cfg,adb)
   elif c=='6':
    from .install import mirror
    mirror(cfg)
   elif c=='7':print('Проверьте: «Алиса, включи Rammstein»; «пауза»; «продолжи»; «перемотай вперёд на 30 секунд»; «что играет»; «включи видео/аудио». Короткое «далее» без обращения не входит в словарь модели. Лайк/дизлайк меняют реальные оценки — тестируйте на своё усмотрение.')
   elif c=='8':
    p=STATE/'logs/bridge.log';print('\n'.join(p.read_text(encoding='utf-8').splitlines()[-25:]) if p.exists() else 'Журнала пока нет.')
  except (UserError,subprocess.TimeoutExpired) as e:print('Ошибка теста:',e)
