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
 from .vpn import policy
 uid,policies=policy(adb)
 print('UID YouTube Music:',uid)
 print('Always-on:',adb.shell('settings','get','secure','always_on_vpn_app'))
 print('Блокировка без VPN:',adb.shell('settings','get','secure','always_on_vpn_lockdown'))
 print('VPN Android:',policies or 'не обнаружен')
 print('Только YouTube Music:',bool(policies) and all(p==[(uid,uid)] for p in policies))
 print('Правильно: Happ → Прокси для выбранных приложений → ВКЛ; одна галочка YouTube Music. После изменений переподключите VPN. Алиса, ADB и системные службы должны идти напрямую.')


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
 text=adb.shell('dumpsys','media_session')
 lines=text.splitlines();inside=False
 for line in lines:
  if line.startswith('    ') and not line.startswith('      '):inside=PACKAGE in line
  if inside:print(line)


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
    print(adb.root('tail','-n','25',REMOTE+'/daemon.log'))
  except (UserError,subprocess.TimeoutExpired) as e:print('Ошибка теста:',e)
