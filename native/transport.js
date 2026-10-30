// Station-local authenticated IPC. No desktop connection is involved.
let localSocket=null, localWrites=Promise.resolve(), localOnline=false;
function emit(message){
 if(!localSocket)return;
 const line=JSON.stringify(message)+'\n';
 localWrites=localWrites.then(()=>localSocket.output.writeAll(Array.from(unescape(encodeURIComponent(line)),c=>c.charCodeAt(0)))).catch(()=>{localOnline=false;if(typeof bridgeMode!=='undefined')bridgeMode='observe';});
}
async function localConnect(){
 try{
  localSocket=await Socket.connect({host:'127.0.0.1',port:27044});
  await localSocket.setNoDelay(true);
  emit({event:'hello',token:LOCAL_TOKEN,role:LOCAL_ROLE,pid:Process.id});
  let pending=[];
  while(true){
   const chunk=new Uint8Array(await localSocket.input.read(8192));if(!chunk.length)throw Error('IPC closed');
   for(const byte of chunk){if(byte!==10){pending.push(byte);if(pending.length>65536)throw Error('IPC frame too large');continue;}
    const message=JSON.parse(decodeURIComponent(escape(String.fromCharCode.apply(null,pending))));pending=[];
    if(message.authenticated){localOnline=true;if(typeof bridgeMode!=='undefined')bridgeMode=message.route?'route':'observe';emit({event:'online',role:LOCAL_ROLE});continue;}
    if(!localOnline)throw Error('Unauthenticated IPC');
    if(typeof message.method!=='string'||!Object.prototype.hasOwnProperty.call(rpc.exports,message.method))continue;
    Promise.resolve().then(()=>rpc.exports[message.method].apply(null,message.args||[])).then(result=>emit({event:'result',call:message.call,result}),error=>emit({event:'result',call:message.call,error:String(error)}));
   }
  }
 }catch(error){localOnline=false;if(typeof bridgeMode!=='undefined')bridgeMode='observe';if(localSocket){try{await localSocket.close();}catch(_){}}localSocket=null;setTimeout(localConnect,1500);}
}
setTimeout(localConnect,100);
