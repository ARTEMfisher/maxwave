import unittest
from unittest.mock import Mock
from maxwave.vpn import ranges,require_youtube_only,UserError
class VpnTests(unittest.TestCase):
 def test_android_p_single_uid(self):self.assertEqual(ranges('Uid: 10018 EstablishingAppUid: 10001'),[(10018,10018)])
 def test_range_policy(self):self.assertEqual(ranges('Uids: <{0-10000, 10002-99999}>'),[(0,10000),(10002,99999)])
 def test_unknown_is_not_treated_as_safe(self):self.assertIsNone(ranges('EstablishingAppUid: 10001'))
 def adb(self,policy):
  a=Mock();a.shell.side_effect=['userId=10018','NetworkAgentInfo{ [type: VPN[], state: CONNECTED/CONNECTED] '+policy,'0'];return a
 def test_only_player_allowed(self):self.assertEqual(require_youtube_only(self.adb('Uid: 10018 EstablishingAppUid: 10001')),10018)
 def test_global_vpn_rejected(self):
  with self.assertRaises(UserError):require_youtube_only(self.adb('Uids: <{0-10000, 10002-99999}>'))
 def test_extra_app_rejected(self):
  with self.assertRaises(UserError):require_youtube_only(self.adb('Uids: <{10018,10039}>'))
