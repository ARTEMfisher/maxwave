"""Resolve public music catalogue entities without account credentials or streams."""
from __future__ import annotations
import re,requests,time
from ytmusicapi import YTMusic
class BoundedSession(requests.Session):
 def request(self,*a,**kw):
  kw['timeout']=(3,6)
  return super().request(*a,**kw)
api=YTMusic(requests_session=BoundedSession(),language='en',location='US')
cache={}
def playable(items):
 return next((x for x in items if re.fullmatch(r'[A-Za-z0-9_-]{11}',x.get('videoId') or '') and x.get('isAvailable',True)),None)
def search(query,media_type='auto'):
 key=(query,media_type)
 if key in cache and time.monotonic()-cache[key][0]<900:return cache[key][1]
 q=re.sub(r'\s+(?:группы|исполнителя)\s+',' ',query).strip()
 filters={'song':'songs','album':'albums','artist':'artists','playlist':'playlists'}
 results=api.search(q,filter=filters.get(media_type),limit=5)
 candidates=[x for x in results if x.get('resultType') in ('song','video','album','artist','playlist')]
 if not candidates:raise RuntimeError('No matching catalogue entity')
 item=candidates[0];kind=item['resultType'];playlist=None;name=item.get('title')
 if kind=='artist':
  artist_id=item.get('browseId') or next((a.get('id') for a in item.get('artists',[]) if a.get('id')),None)
  if not artist_id:raise RuntimeError('Artist has no ID')
  artist=api.get_artist(artist_id);name=artist['name'];songs=artist.get('songs',{});track=playable(songs.get('results',[]));playlist=songs.get('browseId','').removeprefix('VL') or None
  if not playlist:raise RuntimeError('Artist has no collection playlist')
 elif kind=='album':
  album=api.get_album(item['browseId']);name=album['title'];track=playable(album.get('tracks',[]));playlist=album.get('audioPlaylistId') or item.get('playlistId')
  if not playlist:raise RuntimeError('Album has no playlist')
 elif kind=='playlist':
  playlist=item.get('playlistId') or (item.get('browseId') or '').removeprefix('VL');pl=api.get_playlist(playlist,limit=5);name=pl['title'];track=playable(pl.get('tracks',[]))
 else:track=item
 if not track:raise RuntimeError('No playable tracks in selection')
 result={'id':track['videoId'],'title':track.get('title'),'selection':kind,'name':name,'playlistId':playlist}
 cache[key]=(time.monotonic(),result)
 if len(cache)>64:cache.pop(next(iter(cache)))
 return result

def youtube_upload(query,media_type='auto',channel=None):
 import yt_dlp
 opts={'quiet':True,'no_warnings':True,'extract_flat':True,'skip_download':True,'socket_timeout':5,'retries':0,'extractor_retries':0,'noplaylist':True}
 q=query+(' '+channel if channel else '')+(' альбом' if media_type=='album' else '')
 with yt_dlp.YoutubeDL(opts) as y:
  data=y.extract_info('ytsearch5:'+q,download=False)
 entries=[e for e in data.get('entries',[]) if e and re.fullmatch(r'[A-Za-z0-9_-]{11}',e.get('id','')) and not e.get('is_live')]
 norm=lambda s:re.sub(r'[^a-zа-я0-9]','',s.lower())
 if channel:
  wanted=norm(channel)
  entries=[e for e in entries if wanted in norm(e.get('channel') or e.get('uploader') or '')]
 if media_type=='album':
  entries=[e for e in entries if (e.get('duration') or 0)>=600]
  entries.sort(key=lambda e:not bool(re.search(r'альбом|album|full',e.get('title',''),re.I)))
 if not entries:raise RuntimeError('No matching channel upload')
 e=entries[0]
 return {'id':e['id'],'title':e['title'],'selection':'upload','name':e['title'],'playlistId':None,'channel':e.get('channel') or e.get('uploader'),'duration':e.get('duration')}

catalogue_search=search
def search(query,media_type='auto',channel=None):
 if channel:return youtube_upload(query,media_type,channel)
 if media_type=='video':return youtube_upload(query,media_type)
 try:return catalogue_search(query,media_type)
 except RuntimeError as e:
  if str(e)=='No matching catalogue entity':return youtube_upload(query,media_type)
  raise

flow_cache={}
def mood_flow(name):
 if name in flow_cache and time.monotonic()-flow_cache[name][0]<1800:return flow_cache[name][1]
 cats=api.get_mood_categories();category=next((x for values in cats.values() for x in values if x['title']==name),None)
 if not category:raise RuntimeError('No such YouTube Music mood')
 playlists=api.get_mood_playlists(category['params'])
 for pl in playlists[:3]:
  data=api.get_playlist(pl['playlistId'],limit=5);track=playable(data.get('tracks',[]))
  if track:
   result={'id':track['videoId'],'title':track.get('title'),'selection':'mood','name':name+' / '+pl['title'],'playlistId':pl['playlistId']}
   flow_cache[name]=(time.monotonic(),result);return result
 raise RuntimeError('Mood contains no playable tracks')
