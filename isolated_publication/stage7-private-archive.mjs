// Existing isolated credentials and binding only. Immutable server-side copies;
// expiry is anchored to the source namespace, never refreshed by reads/retries.
const enc=new TextEncoder(),day=86400000;
const digest=async value=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',enc.encode(value))),n=>n.toString(16).padStart(2,'0')).join('');
export async function maybeArchive(request,env,h){
 const u=new URL(request.url),m=/^\/private-archive\/(\d{4}-\d{2}-\d{2})\/(index|[a-f0-9]{64})$/.exec(u.pathname);
 if(!m)return null;
 const reply=h.privateResponse;
 if(u.search||!['GET','POST'].includes(request.method))return reply(404,{error:'NOT_FOUND'});
 if(!env.PUBLISH_TOKEN||!env.DECISION_KEY)return reply(503,{error:'NOT_CONFIGURED'});
 if(request.headers.get('Authorization')!=='Bearer '+env.PUBLISH_TOKEN)return reply(401,{error:'UNAUTHORIZED'});
 const target=env.SELECTION.get(env.SELECTION.idFromName('isolated-private-archive-'+m[1]));
 if(request.method==='GET')return target.fetch(new Request('https://actor/archive/'+m[1]+'/'+m[2]));
 let packet;try{packet=JSON.parse(await h.limitedText(request,4096));}catch{return reply(413,{error:'INVALID_OR_LARGE_BODY'});}
 if(!packet||typeof packet.body!=='object'||!packet.body||typeof packet.signature!=='string'||packet.signature!==await h.sign(packet.body,env.DECISION_KEY))return reply(403,{error:'INVALID_SIGNATURE'});
 const b=packet.body;
 if(b?.scope!=='PRIVATE_FUGLE_ARCHIVE_COPY'||b.trade_date!==m[1]||b.id!==m[2]||m[2]==='index'||Object.keys(b).sort().join(',')!=='id,scope,trade_date')return reply(422,{error:'ARCHIVE_REFERENCE_REQUIRED'});
 const source=env.SELECTION.get(env.SELECTION.idFromName('isolated-private-evidence-'+m[1]));
 const indexResponse=await source.fetch(new Request('https://actor/private/'+m[1]+'/index'));
 if(indexResponse.status!==200)return reply(409,{error:'SOURCE_UNAVAILABLE'});
 const index=await indexResponse.json(),firstId=index.entries?.[0]?.id;
 if(!/^[a-f0-9]{64}$/.test(firstId||'')||!index.entries.some(e=>e.id===b.id))return reply(409,{error:'SOURCE_INDEX_MISMATCH'});
 const [firstResponse,savedResponse]=await Promise.all([source.fetch(new Request('https://actor/private/'+m[1]+'/'+firstId)),source.fetch(new Request('https://actor/private/'+m[1]+'/'+b.id))]);
 if(firstResponse.status!==200||savedResponse.status!==200)return reply(409,{error:'SOURCE_UNAVAILABLE'});
 const first=await firstResponse.json(),saved=await savedResponse.json();
 const expires=Date.parse(first.private_written_at)+30*day;
 if(!Number.isFinite(expires)||expires<=Date.now()||expires>Date.now()+30*day)return reply(410,{error:'SOURCE_RETENTION_EXPIRED_OR_INVALID'});
 if(saved.scope!=='PRIVATE_FUGLE_EVIDENCE'||saved.trade_date!==m[1]||saved.id!==b.id||saved.event?.source!=='FUGLE'||typeof saved.event.raw!=='string'||await digest(h.canonical(saved.event))!==b.id||await digest(saved.event.raw)!==saved.event.sha256)return reply(409,{error:'SOURCE_DIGEST_MISMATCH'});
 return target.fetch(new Request('https://actor/archive/'+m[1]+'/'+b.id,{method:'POST',body:JSON.stringify({...saved,source_private_written_at:saved.private_written_at,archive_expires_at:new Date(expires).toISOString()})}));
}
export async function archiveStore(request,state,h){
 const id=new URL(request.url).pathname.split('/').at(-1),s=state.storage,reply=h.privateResponse;
 return state.blockConcurrencyWhile(async()=>{
  const expiry=await s.get('archive_expires_at');
  if(expiry&&Date.parse(expiry)<=Date.now())return reply(410,{error:'ARCHIVE_EXPIRED'});
  if(request.method==='GET'){
   const saved=await s.get(id==='index'?'index':'evidence:'+id);
   return reply(saved?200:404,saved||{error:'NOT_FOUND'});
  }
  if(request.method!=='POST')return reply(405,{error:'METHOD_NOT_ALLOWED'});
  const body=await request.json(),until=Date.parse(body.archive_expires_at);
  if(!Number.isFinite(until)||until<=Date.now()||until>Date.now()+30*day||expiry&&expiry!==body.archive_expires_at)return reply(409,{error:'FIXED_ARCHIVE_EXPIRY_REQUIRED'});
  const prior=await s.get('evidence:'+id);
  if(prior)return reply(200,{id,sha256:prior.event.sha256,private_written_at:prior.private_written_at,archive_expires_at:prior.archive_expires_at,duplicate:true});
  const index=await s.get('index')||{entries:[],bytes:0,archive_expires_at:body.archive_expires_at,scope:'PRIVATE_FUGLE_ARCHIVE'};
  const bytes=enc.encode(h.canonical(body)).length;
  if(index.entries.length>=600||index.bytes+bytes>10000000)return reply(507,{error:'PRIVATE_ARCHIVE_BUDGET'});
  const saved={...body,private_written_at:new Date().toISOString()};
  // Alarm first: a crash may leave an empty expiring actor, never immortal data.
  await s.setAlarm(until);
  await s.transaction(async t=>{
   await t.put('archive_expires_at',body.archive_expires_at);
   await t.put('evidence:'+id,saved);
   index.entries.push({id,sha256:body.event.sha256});index.bytes+=bytes;await t.put('index',index);
  });
  return reply(200,{id,sha256:body.event.sha256,private_written_at:saved.private_written_at,archive_expires_at:saved.archive_expires_at,duplicate:false});
 });
}
