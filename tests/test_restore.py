import unittest
from unittest.mock import Mock,patch
from maxwave import restore as r
class RestoreTests(unittest.TestCase):
 def test_dry_run_never_connects(self):
  with patch.object(r,'Adb') as adb,patch.object(r,'request_stop') as stop:
   r.restore({},dry_run=True,remove_apps=True);adb.assert_not_called();stop.assert_not_called()
 def test_stop_failure_prevents_changes(self):
  with patch.object(r,'request_stop',return_value=False),patch.object(r,'Adb') as adb:
   with self.assertRaises(r.UserError):r.restore({})
   adb.assert_not_called()
 def test_preserve_existing_apps(self):
  packages=['su.happ.proxyutility','app.rvx.android.apps.youtube.music']
  cfg={'installed_by_project':packages+['com.yandex.io.sdk'],'baseline':{packages[0]:{'existed_before':True},packages[1]:{'existed_before':False}}}
  adb=Mock();adb.package_installed.return_value=True
  with patch.object(r,'Adb',return_value=adb),patch.object(r,'request_stop',return_value=True),patch.object(r,'owned',return_value=True):r.restore(cfg,remove_apps=True)
  adb.run.assert_called_once_with('uninstall',packages[1],timeout=60)
  self.assertNotIn(('am','force-stop','com.yandex.io.sdk'),[x.args for x in adb.shell.call_args_list])
 def test_default_retains_apps(self):
  adb=Mock();adb.package_installed.return_value=True
  with patch.object(r,'Adb',return_value=adb),patch.object(r,'request_stop',return_value=True),patch.object(r,'owned',return_value=False):r.restore({})
  adb.run.assert_not_called();adb.root.assert_not_called()
