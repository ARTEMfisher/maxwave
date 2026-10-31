import hashlib,io,json,pathlib,subprocess,tarfile,tempfile,unittest,zipfile
from unittest.mock import patch
from maxwave import common as c

class CommonTests(unittest.TestCase):
 def test_platforms(self):
  for system,machine,expected in [('Darwin','arm64','macos-arm64'),('Darwin','x86_64','macos-x64'),('Windows','AMD64','windows-x64'),('Windows','ARM64','windows-arm64'),('Linux','aarch64','linux-arm64'),('Linux','x86_64','linux-x64')]:
   with self.subTest(expected=expected),patch.object(c.platform,'system',return_value=system),patch.object(c.platform,'machine',return_value=machine):self.assertEqual(c.host_platform(),expected)
 def test_address(self):
  self.assertEqual(c.target_address('192.168.1.50'),'192.168.1.50:5555')
  self.assertEqual(c.target_address('192.168.1.50:1234'),'192.168.1.50:1234')
  for value in ['192.168.1.50; echo x','http://192.168.1.1','foo.local','0.0.0.0','239.1.1.1','192.168.1.1:0','192.168.1.1:99999','[::1]:5555']:
   with self.subTest(value=value),self.assertRaises(c.UserError):c.target_address(value)
 def test_profile_and_relative_tool(self):
  with tempfile.TemporaryDirectory() as d,patch.object(c,'ROOT',pathlib.Path(d)),patch.object(c,'STATE',pathlib.Path(d)/'.station'):
   tool=pathlib.Path(d)/'tools/adb';tool.parent.mkdir();tool.write_bytes(b'placeholder')
   cfg={'target':'192.168.1.50','tools':{'adb':'tools/adb'}};c.save_config(cfg)
   self.assertEqual(c.load_config()['target'],'192.168.1.50:5555');self.assertEqual(c.tool(cfg,'adb'),str(tool))
 def test_safe_zip(self):
  with tempfile.TemporaryDirectory() as d:
   d=pathlib.Path(d);z=d/'a.zip'
   with zipfile.ZipFile(z,'w') as f:f.writestr('nested/a.txt','hello')
   c.extract(z,d/'out');self.assertEqual((d/'out/nested/a.txt').read_text(),'hello')
 def test_zip_traversal_and_symlink(self):
  for name in ['../escape','/absolute','C:/escape','nested\\..\\escape']:
   with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
    d=pathlib.Path(d);z=d/'a.zip'
    with zipfile.ZipFile(z,'w') as f:f.writestr(name,'bad')
    with self.assertRaises(c.UserError):c.extract(z,d/'out')
  with tempfile.TemporaryDirectory() as d:
   d=pathlib.Path(d);z=d/'a.zip';i=zipfile.ZipInfo('link');i.external_attr=0o120777<<16
   with zipfile.ZipFile(z,'w') as f:f.writestr(i,'../../outside')
   with self.assertRaises(c.UserError):c.extract(z,d/'out')
 def test_safe_tar_and_reject_links(self):
  with tempfile.TemporaryDirectory() as d:
   d=pathlib.Path(d);z=d/'a.tar.gz'
   with tarfile.open(z,'w:gz') as f:
    i=tarfile.TarInfo('bin/tool');i.size=3;i.mode=0o755;f.addfile(i,io.BytesIO(b'abc'))
   c.extract(z,d/'out');self.assertEqual((d/'out/bin/tool').read_bytes(),b'abc')
   with tarfile.open(z,'w:gz') as f:
    i=tarfile.TarInfo('link');i.type=tarfile.SYMTYPE;i.linkname='../../outside';f.addfile(i)
   with self.assertRaises(c.UserError):c.extract(z,d/'bad')
 def test_existing_symlink_destination(self):
  with tempfile.TemporaryDirectory() as d:
   d=pathlib.Path(d);out=d/'out';out.mkdir();external=d/'external';external.mkdir()
   try:(out/'sub').symlink_to(external,target_is_directory=True)
   except OSError:self.skipTest('Symlink privilege unavailable')
   z=d/'x.zip'
   with zipfile.ZipFile(z,'w') as f:f.writestr('sub/file','bad')
   with self.assertRaises(c.UserError):c.extract(z,out)
   self.assertFalse((external/'file').exists())
 def test_download_checksum(self):
  class Response(io.BytesIO):
   def geturl(self):return 'https://example.com/a'
  with tempfile.TemporaryDirectory() as d,patch.object(c.urllib.request,'urlopen',side_effect=lambda *a,**k:Response(b'valid')):
   p=pathlib.Path(d)/'asset';c.download('https://example.com/a',p,hashlib.sha256(b'valid').hexdigest());self.assertEqual(p.read_bytes(),b'valid')
   with self.assertRaises(c.UserError):c.download('https://example.com/a',p,'0'*64)
   self.assertFalse(p.with_suffix('.part').exists())
  with self.assertRaises(c.UserError):c.download('http://example.com/a','unused','0'*64)
 def test_remote_quoting(self):
  with patch.object(c,'tool',return_value='adb'):
   a=c.Adb({'target':'192.168.1.50'})
  with patch.object(c.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'ok','')) as run:
   a.shell('am','start','-d','https://music.youtube.com/watch?v=abc&list=xyz')
   command=run.call_args.args[0];self.assertEqual(command[1:3],['-s','192.168.1.50:5555']);self.assertIn("'https://music.youtube.com/watch?v=abc&list=xyz'",command[-1])
 def test_root_and_firmware_checks(self):
  with patch.object(c,'tool',return_value='adb'):
   a=c.Adb({'target':'192.168.1.50'})
  with patch.object(a,'prop',side_effect=['yandexstation_2','5000000921']),patch.object(a,'root',return_value='uid=2000(shell)'):
   with self.assertRaises(c.UserError):a.verify(root=True)
  with patch.object(a,'prop',side_effect=['other','5000000921']),patch.object(a,'root') as root:
   with self.assertRaises(c.UserError):a.verify(root=True)
   root.assert_not_called()
  with patch.object(a,'prop',side_effect=['yandexstation_2','5000000921']),patch.object(a,'root',return_value='uid=0(root)'):
   self.assertEqual(a.verify(root=True),('yandexstation_2','5000000921'))
