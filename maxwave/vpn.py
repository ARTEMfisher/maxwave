"""Validate the actual Android VPN UID policy, rather than trusting a TUN icon."""
import re
from .common import PACKAGE,UserError

def package_uid(adb,package):
 match=re.search(r'\buserId=(\d+)',adb.shell('dumpsys','package',package))
 if not match:raise UserError('Не найден UID приложения '+package)
 return int(match.group(1))

def ranges(line):
 match=re.search(r'Uids:\s*<\{([^}]*)\}>',line)
 if match:
  out=[]
  for token in match.group(1).split(','):
   ends=token.strip().split('-')
   if not 1<=len(ends)<=2 or not all(n.isdigit() for n in ends):return None
   out.append((int(ends[0]),int(ends[-1])))
  return out
 match=re.search(r'\bUid:\s*(\d+)\b',line)
 return [(int(match.group(1)),int(match.group(1)))] if match else None

def policy(adb):
 uid=package_uid(adb,PACKAGE)
 agents=[line for line in adb.shell('dumpsys','connectivity').splitlines() if 'NetworkAgentInfo{' in line and '[type: VPN[' in line and 'CONNECTED/CONNECTED' in line]
 return uid,[ranges(line) for line in agents]

def require_youtube_only(adb):
 uid,policies=policy(adb)
 if not policies:raise UserError('Сначала в Happ включите VPN: «Прокси для выбранных приложений → ВКЛ», только YouTube Music. Переподключитесь и повторите шаг 2.')
 if any(p!=[(uid,uid)] for p in policies):raise UserError('VPN захватывает другие приложения или его UID нельзя подтвердить. В Happ нужен режим «ВКЛ», одна галочка у YouTube Music, затем переподключение. Режимы «ВЫКЛ» и «Обход» не подходят.')
 if adb.shell('settings','get','secure','always_on_vpn_lockdown')=='1':raise UserError('Отключите «Блокировать соединения без VPN» в Android. Иначе остальные приложения могут потерять интернет.')
 return uid
