#!/usr/bin/env python3
"""One entrypoint for downloaded starters; four numbered steps remain standalone."""
import subprocess,sys,argparse,json
from maxwave.common import ROOT,STATE,cli,menu,runtime_python,sha256,UserError

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--self-test',action='store_true');args=ap.parse_args()
 if args.self_test:
  manifest=json.loads((ROOT/'apps-manifest.json').read_text())
  for app in manifest['apps']:
   p=ROOT/app['file']
   if not p.is_file() or sha256(p)!=app['sha256']:raise UserError('Invalid packaged APK: '+app['file'])
  print('MaxWave package self-test: all bundled APK checksums match. No station connection or changes.');return
 if not (STATE/'config.json').exists():
  subprocess.run([sys.executable,str(ROOT/'01_install.py')],check=True)
 while True:
  choice=menu('MaxWave',[('1','Приложения, настройка и scrcpy'),('2','Команды станции и запуск моста'),('3','Диагностика и VPN'),('4','Экспериментальный возврат к Яндекс Музыке'),('0','Выход')])
  files={'1':'01_install.py','2':'02_station.py','3':'03_diagnostics.py','4':'04_restore.py'}
  if choice=='0':return
  if choice in files:
   py=runtime_python() if runtime_python().exists() else sys.executable
   subprocess.run([str(py),str(ROOT/files[choice])],check=True)
if __name__=='__main__':cli(main)
