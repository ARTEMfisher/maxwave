#!/usr/bin/env python3
"""Build deterministic APK and complete bundles, plus self-unpacking starters.
Only an explicit source allowlist enters a release. No publishing happens here.
"""
import hashlib,json,pathlib,stat,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1];DIST=ROOT/'dist';VERSION='0.1.0'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(z,path,name):
 info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(stat.S_IFREG|0o644)<<16
 z.writestr(info,path.read_bytes(),compresslevel=1)
def build():
 DIST.mkdir(exist_ok=True);manifest=json.loads((ROOT/'apps-manifest.json').read_text());app_paths=[]
 for a in manifest['apps']:
  p=ROOT/a['file']
  if not p.exists() or sha(p)!=a['sha256']:raise SystemExit('Missing or wrong APK: '+a['file'])
  app_paths.append(p)
 apps=DIST/f'maxwave-apps-v{VERSION}.zip'
 with zipfile.ZipFile(apps,'w') as z:
  for p in app_paths:put(z,p,p.relative_to(ROOT).as_posix())
 resources=json.loads((ROOT/'resources.json').read_text());repo=resources['repository']
 resources['apps_bundle']={'url':f'https://github.com/{repo}/releases/download/v{VERSION}/{apps.name}','sha256':sha(apps)}
 (ROOT/'resources.json').write_text(json.dumps(resources,indent=2)+'\n')
 files=set()
 for pattern in ['main.py','01_install.py','02_station.py','03_diagnostics.py','04_restore.py','README.md','THIRD_PARTY.md','LICENSE','requirements.txt','resources.json','apps-manifest.json','.maxwave-project','.maxwave-version','maxwave/*.py','bridge/*.py','bridge/*.js','station/*.sh','station/*.java','station/*.dex','docs/*.md','tests/*.py','scripts/*.py','scripts/templates/*.in','.github/workflows/*.yml']:
  files.update(ROOT.glob(pattern))
 files.update(app_paths)
 # Fail closed if a private runtime/config accidentally enters the allowlist.
 for p in files:
  rel=p.relative_to(ROOT)
  if any(x in rel.parts for x in ('.station','.cache','.venv','tools','.git')) or p.suffix in ('.key','.pem','.jks','.keystore'):raise SystemExit('Private file in release: '+str(rel))
 bundle=DIST/f'maxwave-v{VERSION}-bundle.zip'
 with zipfile.ZipFile(bundle,'w') as z:
  for p in sorted(files):
   if p.is_file():put(z,p,'MaxWave/'+p.relative_to(ROOT).as_posix())
 replacements={'@BUNDLE_URL@':f'https://github.com/{repo}/releases/download/v{VERSION}/{bundle.name}','@BUNDLE_SHA@':sha(bundle)}
 posix_cases=[];windows_cases=[]
 for key,spec in resources['portable_python'].items():
  if key.startswith('windows'):
   arch='ARM64' if key.endswith('arm64') else 'AMD64'
   windows_cases.append(f" '{arch}' {{ $key='{key}'; $pythonUrl='{spec['url']}'; $pythonSha='{spec['sha256']}' }}")
  else:posix_cases.append(f" {key}) python_url='{spec['url']}';python_sha='{spec['sha256']}';;")
 for filename,template,cases in [('MaxWave-macOS.command','start-posix.in',posix_cases),('MaxWave-Linux.sh','start-posix.in',posix_cases),('MaxWave-Windows.cmd','start-windows.in',windows_cases)]:
  text=(ROOT/'scripts/templates'/template).read_text().replace('@PYTHON_CASES@','\n'.join(cases))
  for key,value in replacements.items():text=text.replace(key,value)
  data=text.replace('\n','\r\n').encode('utf-8') if filename.endswith('.cmd') else text.encode('utf-8')
  p=DIST/filename;p.write_bytes(data);p.chmod(0o755)
 assets=[apps,bundle,*[DIST/x for x in ('MaxWave-macOS.command','MaxWave-Linux.sh','MaxWave-Windows.cmd')],*app_paths]
 (DIST/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in assets))
 print('\n'.join(str(p) for p in assets));return assets
if __name__=='__main__':build()
