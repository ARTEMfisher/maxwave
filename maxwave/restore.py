"""Experimental return to normal music. Does not undo firmware/root/OTA modifications."""
import argparse,json
from .common import *
from .station import request_stop,owned

def restore(cfg,dry_run=False,remove_apps=False):
 print('ЭКСПЕРИМЕНТАЛЬНЫЙ ОТКАТ: плохо протестирован. Это отключение MaxWave, не восстановление заводской прошивки, root или OTA.')
 print('План: остановить мост; остановить только его Frida; закрыть ReVanced; вернуть интерфейс Яндекса.')
 if remove_apps:print('Удалить только APK, которых не было до установки MaxWave.')
 if dry_run:print('DRY RUN: ни одна команда изменения не выполнена.');return
 if not request_stop():raise UserError('Не удалось корректно остановить мост. Закройте его окно и повторите откат.')
 adb=Adb(cfg);adb.connect()
 if owned(adb):print(adb.root('/system/bin/sh',REMOTE+'/stop.sh'))
 if adb.package_installed(PACKAGE):adb.shell('am','force-stop',PACKAGE)
 if cfg.get('gms_whitelisted_before') is False:adb.shell('dumpsys','deviceidle','whitelist','-app.revanced.android.gms')
 if remove_apps:
  for package in cfg.get('installed_by_project',[]):
   if package not in {a['package'] for a in json.loads((ROOT/'apps-manifest.json').read_text())['apps']}:continue
   if cfg.get('baseline',{}).get(package,{}).get('existed_before') is False:print(adb.run('uninstall',package,timeout=60))
   else:print('Сохранено ранее установленное приложение:',package)
 adb.shell('am','start','-n','com.yandex.tv.home/.HomeActivity')
 print('MaxWave отключён. Проверьте «Алиса, включи музыку». Ранее сделанные изменения прошивки и защиты остаются.')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--dry-run',action='store_true');args=ap.parse_args();cfg=load_config()
 if args.dry_run:restore(cfg,True);return
 c=menu('Экспериментальный откат — ПЛОХО ПРОТЕСТИРОВАН',[('1','Отключить мост и вернуться к музыке Яндекса'),('2','Также удалить приложения и их данные, впервые установленные MaxWave'),('0','Отмена')])
 if c in ('1','2'):restore(cfg,remove_apps=c=='2')
