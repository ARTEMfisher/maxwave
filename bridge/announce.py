"""Local OS voices. Metadata is not sent to an additional TTS cloud."""
import base64,pathlib,platform,shutil,subprocess,tempfile

def synthesize(text,wav,folder):
 system=platform.system()
 if system=='Darwin':
  aiff=folder/'voice.aiff'
  subprocess.run(['/usr/bin/say','-v','Milena','-o',str(aiff)],input=text,text=True,check=True,timeout=20,capture_output=True)
  subprocess.run(['/usr/bin/afconvert','-f','WAVE','-d','LEI16@22050',str(aiff),str(wav)],check=True,timeout=10,capture_output=True)
 elif system=='Windows':
  src=folder/'text.txt';src.write_text(text,encoding='utf-8')
  quote=lambda x:"'"+str(x).replace("'","''")+"'"
  code="Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; try { $v=$s.GetInstalledVoices() | Where-Object {$_.VoiceInfo.Culture.Name -eq 'ru-RU'} | Select-Object -First 1; if ($v) {$s.SelectVoice($v.VoiceInfo.Name)}; $s.SetOutputToWaveFile("+quote(wav)+"); $s.Speak([IO.File]::ReadAllText("+quote(src)+",[Text.Encoding]::UTF8)); } finally {$s.Dispose()}"
  encoded=base64.b64encode(code.encode('utf-16-le')).decode()
  subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],check=True,timeout=30,capture_output=True)
 else:
  exe=shutil.which('espeak-ng') or shutil.which('espeak')
  if not exe:raise RuntimeError('Озвучивание требует espeak-ng: установите его пакетным менеджером Linux. Остальной мост продолжает работать.')
  subprocess.run([exe,'-v','ru','-w',str(wav),'--stdin'],input=text,text=True,check=True,timeout=20,capture_output=True)

def announce(agent,request,artist,title):
 artist='' if artist in (None,'null') else artist;title='' if title in (None,'null') else title
 text=' — '.join(x for x in (artist,title) if x).strip()[:320]
 if not text:raise RuntimeError('No track metadata')
 with tempfile.TemporaryDirectory(prefix='maxwave-tts-') as d:
  folder=pathlib.Path(d);wav=folder/'voice.wav';synthesize(text,wav,folder)
  audio=wav.read_bytes()
  if len(audio)>2000000:raise RuntimeError('Announcement too large')
  agent.exports_sync.ttsbegin(request)
  for i in range(0,len(audio),4800):agent.exports_sync.ttsappend(request,base64.b64encode(audio[i:i+4800]).decode())
  return agent.exports_sync.ttsplay(request)
