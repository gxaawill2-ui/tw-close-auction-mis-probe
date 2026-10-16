// Dormant until separately approved, narrowly scoped MIS_BRIDGE_TOKEN exists.
// The formal collector never receives Fugle or general publisher credentials.
export async function maybeMISBridge(request,env,{sign,canonical,privateResponse,limitedText}){
 const url=new URL(request.url),match=/^\/private-mis-journal\/(\d{4}-\d{2}-\d{2})\/(index|[a-f0-9]{64})$/.exec(url.pathname);
 if(!match)return null;
 if(url.search||!['GET','POST'].includes(request.method))return privateResponse(404,{error:'NOT_FOUND'});
 const token=request.method==='GET'?env.PUBLISH_TOKEN:env.MIS_BRIDGE_TOKEN;
 if(!token)return privateResponse(503,{error:'PRIVATE_MIS_BRIDGE_NOT_CONFIGURED'});
 const actual=request.headers.get('Authorization')||'',expected='Bearer '+token;
 let diff=actual.length^expected.length;for(let i=0;i<Math.max(actual.length,expected.length);i++)diff|=(actual.charCodeAt(i)||0)^(expected.charCodeAt(i)||0);
 if(diff)return privateResponse(401,{error:'UNAUTHORIZED'});
 const target='https://actor/private/'+match[1]+'/'+match[2];
 const store=env.SELECTION.get(env.SELECTION.idFromName('isolated-private-mis-'+match[1]));
 if(request.method==='GET')return store.fetch(new Request(target));
 let packet;try{packet=JSON.parse(await limitedText(request,98304));}catch{return privateResponse(413,{error:'INVALID_OR_LARGE_BODY'});}
 if(typeof packet.signature!=='string'||packet.signature!==await sign(packet.body,token))return privateResponse(403,{error:'INVALID_MIS_BRIDGE_SIGNATURE'});
 const body=packet.body,event=body?.event,today=new Date(Date.now()+8*3600000).toISOString().slice(0,10),encoder=new TextEncoder();
 const digest=async text=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',encoder.encode(text))),b=>b.toString(16).padStart(2,'0')).join('');
 if(match[1]!==today||body.trade_date!==today||body.id!==match[2]||body.scope!=='PRIVATE_MIS_JOURNAL'||event?.source!=='MIS'||typeof event.raw!=='string'||await digest(canonical(event))!==body.id||await digest(event.raw)!==event.sha256)return privateResponse(422,{error:'MIS_BRIDGE_SCHEMA_HASH_OR_DATE'});
 let journal;try{journal=JSON.parse(event.raw);}catch{return privateResponse(422,{error:'INVALID_MIS_JOURNAL'});}
 const received=Date.parse(journal.record?.received_at),saved=Date.parse(journal.persisted_at);
 if(journal.origin!=='MIS_LOCAL_DURABLE_JOURNAL'||!Number.isFinite(received)||!Number.isFinite(saved)||received>saved||saved>Date.now()+1000||new Date(received+8*3600000).toISOString().slice(0,10)!==today)return privateResponse(422,{error:'INVALID_MIS_JOURNAL_PROVENANCE'});
 return store.fetch(new Request(target,{method:'POST',body:JSON.stringify(body)}));
}
