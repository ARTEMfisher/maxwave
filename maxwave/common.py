"""Shared, dependency-free configuration, downloads, archive and ADB helpers."""
from __future__ import annotations
import hashlib,ipaddress,json,os,pathlib,platform,re,shlex,shutil,stat,subprocess,sys,tarfile,tempfile,urllib.request,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
STATE=ROOT/'.station'
REMOTE='/data/local/tmp/maxwave'
PACKAGE='app.rvx.android.apps.youtube.music'
PLATFORMS={'macos-arm64':'macOS / Apple Silicon','macos-x64':'macOS / Intel','windows-x64':'Windows / x64','windows-arm64':'Windows / ARM64','linux-x64':'Linux / x64','linux-arm64':'Linux / ARM64 (системные adb и scrcpy)'}
class UserError(RuntimeError):pass

def host_platform():
 osname={'Darwin':'macos','Windows':'windows','Linux':'linux'}.get(platform.system())
 arch={'arm64':'arm64','aarch64':'arm64','amd64':'x64','x86_64':'x64'}.get(platform.machine().lower())
 if not osname or not arch:raise UserError('Неподдерживаемая ОС или архитектура: '+platform.platform())
 return osname+'-'+arch

def target_address(value):
 value=value.strip()
 if value.count(':')==1:host,port=value.split(':')
 else:host,port=value,'5555'
 try:ip=ipaddress.IPv4Address(host);n=int(port)
 except (ValueError,TypeError):raise UserError('Нужен IPv4 станции, например 192.168.1.50, без URL и команд.')
 if not 1<=n<=65535 or ip.is_unspecified or ip.is_multicast:raise UserError('Неверный IP или порт.')
 return f'{ip}:{n}'

def save_config(cfg):
 STATE.mkdir(exist_ok=True);STATE.chmod(0o700)
 p=STATE/'config.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8');tmp.chmod(0o600);tmp.replace(p)

def load_config():
 p=STATE/'config.json'
 if not p.exists():raise UserError('Сначала запустите 01_install.py.')
 cfg=json.loads(p.read_text(encoding='utf-8'));cfg['target']=target_address(cfg['target'])
 return cfg

def tool(cfg,name):
 value=cfg.get('tools',{}).get(name)
 if value:
  p=pathlib.Path(value);p=p if p.is_absolute() else ROOT/p
  if p.is_file():return str(p)
 found=shutil.which(name)
 if found:return found
 raise UserError(f'{name} не найден. Повторите первый шаг установки.')

def sha256(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def download(url,destination,expected):
 if not url.startswith('https://'):raise UserError('Загрузка разрешена только по HTTPS.')
 if not re.fullmatch('[a-f0-9]{64}',expected):raise UserError('Нет корректной SHA256 для ресурса.')
 dst=pathlib.Path(destination);dst.parent.mkdir(parents=True,exist_ok=True)
 if dst.exists() and sha256(dst)==expected:return dst
 part=dst.with_suffix(dst.suffix+'.part')
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'MaxWave/0.1.0'})
  with urllib.request.urlopen(req,timeout=60) as r,part.open('wb') as f:
   if not r.geturl().startswith('https://'):raise UserError('Небезопасное перенаправление загрузки.')
   shutil.copyfileobj(r,f)
  if sha256(part)!=expected:raise UserError('Контрольная сумма не совпала: '+dst.name)
  part.replace(dst)
 finally:
  if part.exists():part.unlink()
 return dst

def _safe_member(name,root):
 if '\\' in name or ':' in name:raise UserError('Небезопасный путь в архиве: '+name)
 p=pathlib.PurePosixPath(name)
 if p.is_absolute() or '..' in p.parts:raise UserError('Выход за пределы каталога в архиве.')
 out=(root/name).resolve()
 if not out.is_relative_to(root.resolve()):raise UserError('Выход за пределы каталога в архиве.')
 return out

def extract(archive,destination):
 """No shell, no archive traversal, links, device nodes or writes through symlinks."""
 root=pathlib.Path(destination);root.mkdir(parents=True,exist_ok=True)
 if zipfile.is_zipfile(archive):
  with zipfile.ZipFile(archive) as z:
   members=z.infolist()
   if sum(i.file_size for i in members)>4*1024**3:raise UserError('Архив слишком велик.')
   for i in members:
    p=_safe_member(i.filename,root);mode=i.external_attr>>16
    if stat.S_ISLNK(mode):raise UserError('Символические ссылки в ZIP не поддерживаются.')
    if i.is_dir():p.mkdir(parents=True,exist_ok=True);continue
    p.parent.mkdir(parents=True,exist_ok=True)
    with z.open(i) as src,p.open('wb') as dst:shutil.copyfileobj(src,dst)
    if mode&0o111:p.chmod(0o755)
 else:
  with tarfile.open(archive,'r:*') as t:
   members=t.getmembers()
   if sum(i.size for i in members)>4*1024**3:raise UserError('Архив слишком велик.')
   for i in members:
    p=_safe_member(i.name,root)
    if i.isdir():p.mkdir(parents=True,exist_ok=True);continue
    if not i.isfile():raise UserError('Ссылки и специальные файлы TAR не поддерживаются.')
    p.parent.mkdir(parents=True,exist_ok=True)
    with t.extractfile(i) as src,p.open('wb') as dst:shutil.copyfileobj(src,dst)
    if i.mode&0o111:p.chmod(0o755)
 return root

class Adb:
 def __init__(self,cfg):self.cfg=cfg;self.exe=tool(cfg,'adb');self.target=target_address(cfg['target'])
 def run(self,*args,timeout=25,check=True):
  p=subprocess.run([self.exe,'-s',self.target,*map(str,args)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
  if check and p.returncode:raise UserError((p.stderr or p.stdout).strip() or 'Ошибка ADB')
  return p.stdout.replace('\r','').strip()
 def connect(self):
  subprocess.run([self.exe,'connect',self.target],capture_output=True,timeout=10)
  if self.run('get-state')!='device':raise UserError('Станция не подключена к ADB.')
 def shell(self,*args,timeout=25):return self.run('shell',shlex.join(list(map(str,args))),timeout=timeout)
 def root(self,*args,timeout=25):return self.run('shell','-tt',shlex.join(['mysudo',*map(str,args)]),timeout=timeout)
 def push(self,local,remote):return self.run('push',str(local),remote,timeout=180)
 def prop(self,name):return self.shell('getprop',name)
 def package_installed(self,name):return self.shell('pm','path',name).startswith('package:')
 def verify(self,root=False):
  device=self.prop('ro.product.device');fw=self.prop('ro.build.version.incremental')
  if device!='yandexstation_2' or fw!='5000000921':raise UserError(f'Не проверенная комбинация: {device} / {fw}. Нужна yandexstation_2 / 5000000921; номер 00053 проверьте по этикетке.')
  if root and not re.search(r'\buid=0\(',self.root('id')):raise UserError('mysudo не предоставил root. Получение root не входит в MaxWave.')
  return device,fw

def menu(title,items):
 print('\n'+title)
 for key,label in items:print(f' {key}. {label}')
 return input('> ').strip()

def cli(fn):
 try:fn()
 except (UserError,subprocess.TimeoutExpired,subprocess.CalledProcessError,urllib.error.URLError) as e:print('\nОшибка:',e);raise SystemExit(1)
 except KeyboardInterrupt:print('\nОстановлено пользователем.');raise SystemExit(130)

def runtime_python():return ROOT/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')

def ensure_runtime(reexec=True):
 """Install into a project venv, never into the system Python."""
 py=runtime_python()
 if pathlib.Path(sys.prefix).resolve()==(ROOT/'.venv').resolve():return
 if not py.exists():
  import venv
  print('Подготавливаю изолированные зависимости Python…');venv.EnvBuilder(with_pip=True).create(ROOT/'.venv')
 stamp=ROOT/'.venv'/'.maxwave-ready'
 reqhash=sha256(ROOT/'requirements.txt')
 if not stamp.exists() or stamp.read_text()!=reqhash:
  subprocess.run([str(py),'-m','pip','install','--disable-pip-version-check','-r',str(ROOT/'requirements.txt')],check=True)
  stamp.write_text(reqhash)
 if reexec:
  raise SystemExit(subprocess.call([str(py),*sys.argv]))
