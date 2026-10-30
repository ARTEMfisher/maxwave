/* Music command router. Recognition stays with native Alice. */
(function(root){'use strict';
const home=['замок','двер','ворот','кран','воду','вода','духовк','плит','свет','освещен','ламп','люстр','торшер','ночник','розет','телевиз','тв','кондиционер','вентилятор','обогревател','пылесос','робот','чайник','будильник','таймер','блютуз','bluetooth','режим','экран','микрофон','громк','звук','отоплен','увлажнител','очистител','зарядк','видео','фильм','новост','камер','штор','сценар','сцену','сцену','торшер','компьютер','приставк','сигнализац','ютубер'];
function normalize(s){return String(s).toLowerCase().replace(/ё/g,'е').replace(/[.,!?;«»"“”]/g,' ').replace(/\s+/g,' ').trim().replace(/^алиса\s+/,'');}
function timeValue(s){
 s=s.trim().replace(/ё/g,'е');if(/^\d{1,2}:\d{2}(?::\d{2})?$/.test(s)){const a=s.split(':').map(Number);return a.reduce((r,n)=>r*60+n,0);}
 const nums={'ноль':0,'один':1,'одна':1,'одну':1,'две':2,'два':2,'три':3,'четыре':4,'пять':5,'шесть':6,'семь':7,'восемь':8,'девять':9,'десять':10,'одиннадцать':11,'двенадцать':12,'тринадцать':13,'четырнадцать':14,'пятнадцать':15,'шестнадцать':16,'семнадцать':17,'восемнадцать':18,'девятнадцать':19,'двадцать':20,'тридцать':30,'сорок':40,'пятьдесят':50,'шестьдесят':60,'полторы':1.5,'полтора':1.5};
 s=s.replace(/полминуты/g,'30 секунд').replace(/полчаса/g,'30 минут');let total=0,n=0,found=false;
 for(const w of s.split(/\s+/)){if(/^\d+$/.test(w)){n+=Number(w);continue;}if(w in nums){n+=nums[w];continue;}let k=/^час/.test(w)?3600:/^минут/.test(w)?60:/^секунд/.test(w)?1:0;if(k){total+=(n||1)*k;n=0;found=true;}else if(w!=='и')return null;}
 if(n)total+=n;return(found||total>0)&&total<=86400?total:null;
}
function seekIntent(s){
 if(/^(?:сначала|с начала|начни сначала|начни (?:песню|трек) сначала|включи с начала)$/.test(s))return{kind:'seek',position:0};
 const m=s.match(/^(?:(?:перемотай|отмотай|промотай|перемотка|перейди)\s+)?(?:(вперед|назад)\s+)?(?:на\s+|к\s+|до\s+)?(.+?)(?:\s+(вперед|назад))?$/);
 if(!m)return null;const explicit=/^(?:перемотай|отмотай|промотай|перемотка|перейди)\s/.test(s),direction=m[1]||m[3];if(!explicit&&!direction)return null;
 let t=m[2].replace(/^отметк[еу]\s+/,'');const seconds=timeValue(t);if(seconds===null)return null;
 const absolute=/отметк[еу]|\d+:\d+/.test(s);return absolute?{kind:'seek',position:seconds*1000}:{kind:'seek',offset:(direction==='назад'||/^отмотай/.test(s)?-1:1)*seconds*1000};
}
function classify(text,ownsMusic){
 const s=normalize(text);if(!s||s.length>512)return null;
 if(ownsMusic){
  if(/^(?:мне не нравится|не нравится|дизлайк|поставь дизлайк|поставь не нравится|эта песня мне не нравится)$/.test(s))return{kind:'rating',value:false};
  if(/^(?:мне нравится|нравится|лайк|поставь лайк|поставь нравится|эта песня мне нравится)$/.test(s))return{kind:'rating',value:true};
  if(/^(?:убери лайк|сними лайк|убери дизлайк|сними дизлайк|убери оценку|сними оценку)$/.test(s))return{kind:'rating',value:null};
  if(/^(?:что играет|что сейчас играет|что за песня|что за трек|что это за песня|кто поет|кто исполняет|назови песню|назови трек|назови исполнителя)$/.test(s))return{kind:'announce',explicit:true};
  if(/^(?:включи видео|включи клип|включи видеорежим|переключи на видео|переключись на видео|покажи видео)$/.test(s))return{kind:'mode',mode:'video',explicit:true};
  if(/^(?:включи аудио|включи аудиорежим|переключи на аудио|переключись на аудио|только аудио|включи только звук)$/.test(s))return{kind:'mode',mode:'audio',explicit:true};
 }
 if(/^(?:не|никогда|отмена)(?:\s|$)/.test(s))return null;
 if(/^(?:(?:включи|запусти|поставь)\s+)?(?:мою волну|моя волна|мой супермикс|мой микс|персональную музыку|музыку для меня)$/.test(s))return{kind:'personal',explicit:true};
 if(/^(?:включи|продолжи|возобнови|продолжай)\s+музыку(?:\s+(?:на|в|через)\s+(?:ютуб|youtube)(?:\s+music|\s+мьюзик)?)?$/.test(s))return {kind:'resume'};
 if(ownsMusic){
  if(/^(?:продолжи|продолжить|продолжай|возобнови|играй|играй дальше|сними с паузы|продолжи воспроизведение)$/.test(s))return{kind:'resume'};
  const seek=seekIntent(s);if(seek)return seek;
  if(/^(?:пауза|стоп|хватит|достаточно|замолчи|помолчи|остановить|(?:останови|выключи|отключи|приостанови)(?:\s+музыку|\s+воспроизведение)?|поставь(?:\s+музыку)?\s+на\s+паузу)$/.test(s))return {kind:'pause'};
  if(/^(?:дальше|далее|пропусти|другую песню|другой трек|пропусти трек|следующий|следующая|следующий\s+трек|следующая\s+песня|переключи\s+трек)$/.test(s))return {kind:'next'};
  if(/^(?:предыдущий|предыдущая|назад|предыдущий\s+трек|предыдущая\s+песня)$/.test(s))return {kind:'previous'};
 }
 let m=s.match(/^(?:включи|поставь|запусти|сыграй|найди\s+и\s+включи)\s+(?:пожалуйста\s+)?(.+)$/);if(!m)return null;
 let q=m[1].replace(/\s+пожалуйста$/,'').replace(/\s+(?:на|в|через)\s+(?:ютуб|youtube)(?:\s+music|\s+мьюзик)?$/,'');let type='auto',explicit=false,channel=null;
 for(const [prefix,t] of [['альбом','album'],['плейлист','playlist'],['песню','song'],['трек','song'],['композицию','song'],['группу','artist'],['исполнителя','artist'],['исполнительницу','artist'],['музыку группы','artist'],['музыку исполнителя','artist']]){
  if(q.startsWith(prefix+' ')){q=q.slice(prefix.length+1);type=t;explicit=true;break;}
 }
 if(!explicit&&q.split(' ').some(w=>home.some(p=>p==='тв'?w===p:w.startsWith(p))))return null;
 if(!explicit&&!q.split(' ').some(w=>home.some(p=>p==='тв'?w===p:w.startsWith(p)))){
  for(const[mood,rx]of [['Energize',/энергичн|бодрящ|бодрую|пободрее/],['Sad',/грустн|печальн/],['Chill',/спокойн|расслабля|релакс/],['Sleep',/для сна|для засыпания|уснуть/],['Workout',/для трениров|для спорт|тренировочн/],['Focus',/для работы|для учебы|для концентрации|сосредоточ/],['Party',/для вечерин|танцевальн/],['Feel good',/весел|позитивн/],['Romance',/романтич/]])if(rx.test(q))return{kind:'flow',mood,explicit:true};
 }
 const by=q.match(/^(.+?)\s+(?:группы|исполнителя|исполнительницы)\s+(.+)$/);
 if(by){q=by[1]+' '+by[2];if(type==='auto')type='song';explicit=true;}
 q=q.replace(/^(?:группы|исполнителя)\s+/,'');
 const cm=q.match(/^(.+?)\s+(?:с канала|на канале|от канала|от автора|от)\s+(.+)$/);if(cm){q=cm[1];channel=cm[2];explicit=true;}

 
 return q.length>=2&&q.length<=400?{kind:'search',query:q,mediaType:type,explicit,...(channel?{channel}: {})}:null;
}
function finalRequest(s){if(![1,3].includes(s.state)||!s.final||!s.started||typeof s.text!=='string'||s.text.length<1||s.text.length>512||s.text!==s.requestText||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(s.id))return null;return{id:s.id,text:s.text};}
class Dedupe{constructor(){this.seen=new Map();}accept(id,now){for(const[k,t]of this.seen)if(now-t>300000)this.seen.delete(k);if(this.seen.has(id))return false;this.seen.set(id,now);while(this.seen.size>64)this.seen.delete(this.seen.keys().next().value);return true;}}
root.MusicCore={normalize,classify,finalRequest,Dedupe,timeValue,seekIntent};if(typeof module!=='undefined')module.exports=root.MusicCore;
})(globalThis);
