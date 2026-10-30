import hashlib,importlib.util,json,pathlib,subprocess,sys,tempfile,unittest,zipfile
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
class ReleaseTests(unittest.TestCase):
 def test_resource_hashes_and_https(self):
  r=json.loads((ROOT/'resources.json').read_text())
  specs=[r['frida_server'],*r['portable_python'].values()]
  for platform in r['platforms'].values():specs += [v for v in platform.values() if v]
  for spec in specs:
   self.assertTrue(spec['url'].startswith('https://'));self.assertRegex(spec['sha256'],r'^[a-f0-9]{64}$')
 def test_entrypoint_help(self):
  for name in ['01_install.py','02_station.py','03_diagnostics.py','04_restore.py']:
   p=subprocess.run([sys.executable,str(ROOT/name),'--help'],capture_output=True,text=True,timeout=10)
   self.assertEqual(p.returncode,0,p.stderr)
 def test_readonly_agent_does_not_hook(self):
  text=(ROOT/'bridge/read-only-agent.js').read_text();self.assertNotIn('.implementation',text);self.assertNotIn('.setRating(',text)
 def test_build_allowlist_and_checksum(self):
  spec=importlib.util.spec_from_file_location('release_builder',ROOT/'scripts/build_release.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);(p/'apps').mkdir();apk=p/'apps/test.apk';apk.write_bytes(b'test package');(p/'.station').mkdir();(p/'.station/secret.txt').write_text('DO NOT SHIP');(p/'private.keystore').write_text('DO NOT SHIP');(p/'PRIVATE.md').write_text('DO NOT SHIP');(p/'private.py').write_text('DO NOT SHIP');(p/'README.md').write_text('demo');(p/'.maxwave-project').write_text('marker')
   (p/'scripts/templates').mkdir(parents=True)
   for name in ['start-posix.in','start-windows.in']:(p/'scripts/templates'/name).write_text('@BUNDLE_URL@ @BUNDLE_SHA@ @PYTHON_CASES@')
   (p/'apps-manifest.json').write_text(json.dumps({'apps':[{'file':'apps/test.apk','sha256':hashlib.sha256(apk.read_bytes()).hexdigest()}]}))
   (p/'resources.json').write_text(json.dumps({'repository':'example/maxwave','portable_python':{}}))
   with patch.object(b,'ROOT',p),patch.object(b,'DIST',p/'dist'):b.build()
   with zipfile.ZipFile(p/'dist/maxwave-v0.2.0-bundle.zip') as z:
    self.assertIn('MaxWave/apps/test.apk',z.namelist());self.assertNotIn('MaxWave/.station/secret.txt',z.namelist());self.assertNotIn('MaxWave/private.keystore',z.namelist());self.assertNotIn('MaxWave/PRIVATE.md',z.namelist());self.assertNotIn('MaxWave/private.py',z.namelist())
   resource=json.loads((p/'resources.json').read_text());self.assertEqual(resource['apps_bundle']['sha256'],hashlib.sha256((p/'dist/maxwave-apps-v0.2.0.zip').read_bytes()).hexdigest())
   text=(p/'dist/MaxWave-macOS.command').read_text();self.assertNotIn('@BUNDLE_SHA@',text)
