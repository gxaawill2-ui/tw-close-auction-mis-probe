// Entirely separate from the existing relay/Pages. No cron and no GitHub calls.
import {maybeMISBridge} from './stage5-mis-bridge.mjs';
const encoder=new TextEncoder();
export function canonical(value){
 if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
 if(value&&typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';
 return JSON.stringify(value);
}
const hex=bytes=>Array.from(new Uint8Array(bytes),x=>x.toString(16).padStart(2,'0')).join('');
export async function sign(body,key){
 const secret=await crypto.subtle.importKey('raw',encoder.encode(key),{name:'HMAC',hash:'SHA-256'},false,['sign']);
 return hex(await crypto.subtle.sign('HMAC',secret,encoder.encode(canonical(body))));
}
function equal(a,b){if(typeof a!=='string'||typeof b!=='string'||a.length!==b.length)return false;let diff=0;for(let i=0;i<a.length;i++)diff|=a.charCodeAt(i)^b.charCodeAt(i);return diff===0;}
export function matchesReadETag(value,etag){
 // If-None-Match uses weak comparison (RFC 9110 13.1.2). Cloudflare
 // compression can change a strong response tag into W/"...".
 if(typeof value!=='string')return false;
 let rest=value.trim(),matched=false;
 if(rest==='*')return true;
 while(rest){
  const token=/^(?:W\/)?"[\x21\x23-\x7e\x80-\xff]*"/.exec(rest);
  if(!token)return false;
  if(token[0].replace(/^W\//,'')===etag.replace(/^W\//,''))matched=true;
  rest=rest.slice(token[0].length).trim();
  if(!rest)return matched;
  if(rest[0]!==',')return false;
  rest=rest.slice(1).trim();
 }
 return false;
}
export function meetsTailThreshold(before,close){
 // Match Python Decimal at the inclusive +/-3% boundary, without binary rounding.
 const fraction=value=>{
  if(!['string','number'].includes(typeof value))return null;
  const raw=String(value);if(raw.length>100)return null;
  const m=/^([+]?)(\d+)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/.exec(raw);
  if(!m||Math.abs(Number(m[4]||0))>100)return null;
  let n=BigInt(m[2]+(m[3]||'')),scale=(m[3]||'').length-Number(m[4]||0);
  if(n<=0n)return null;
  return scale>=0?{n,d:10n**BigInt(scale)}:{n:n*10n**BigInt(-scale),d:1n};
 };
 const p=fraction(before),c=fraction(close);if(!p||!c)return false;
 const base=p.n*c.d,difference=c.n*p.d-base;
 return (difference<0n?-difference:difference)*100n>=base*3n;
}
export function validate(body,env,now=Date.now()){
 const restricted=new Set(['raw','raw_path','pages','quote_before','quote_after','pre_tick','close_tick','lastTrade','lastTrial','FUGLE_API_KEY']);
 function hasRaw(value){return value&&typeof value==='object'&&Object.entries(value).some(([k,v])=>(restricted.has(k)&&v!=null)||hasRaw(v));}
 if(hasRaw(body))return 'RESTRICTED_SOURCE_EVIDENCE_NOT_PUBLIC';
 if(body?.schema_version!=='STAGE3_SELECTION_V1'||!/^\d{4}-\d{2}-\d{2}$/.test(body.trade_date||'')||
  !Number.isSafeInteger(body.version)||body.version<1||!['LIVE','SYNTHETIC','OFFLINE_REPLAY'].includes(body.mode)||
  !Array.isArray(body.rows)||body.rows.length>200||body.is_synthetic!==(body.mode==='SYNTHETIC'))return 'INVALID_SCHEMA';
 const generated=Date.parse(body.generated_at);
 if(!Number.isFinite(generated))return 'INVALID_GENERATION_TIME';
 if(body.mode==='LIVE'){
  if(env.PUBLIC_POLICY_REQUIRED==='true'&&body.public_data_policy!=='MIS_DERIVED_RESEARCH_NO_FUGLE_RAW')return 'PUBLIC_DATA_POLICY_REQUIRED';
  const today=new Date(now+8*3600000).toISOString().slice(0,10);
  const opening=Date.parse(body.trade_date+'T13:30:00+08:00'),deadline=Date.parse(body.trade_date+'T14:30:00+08:00');
  if(body.trade_date!==today||Math.abs(now-generated)>30000||now<opening||now>=deadline)return 'LIVE_OUTSIDE_CURRENT_PUBLICATION_WINDOW';
 }
 let count=0;const seen=new Set();
 for(const row of body.rows){
  if(!/^\d{4}$/.test(row.code||'')||!['tse','otc'].includes(row.ex)||!['RESEARCH_ONLY','VERIFIED','UNKNOWN'].includes(row.verification_status))return 'INVALID_ROW';
  const identity=row.ex+':'+row.code;if(seen.has(identity))return 'DUPLICATE_SECURITY';seen.add(identity);
  if(row.validated){
   if(body.mode!=='LIVE'||env.ALLOW_LIVE_VERIFIED!=='true')return 'LIVE_VALIDATION_NOT_RELEASED';
   if(row.verification_status!=='VERIFIED'||row.simulated_only||row.simulation_passed||
    !['pre_actual_trade_before_1325','pre_last_trade_independently_proven','close_independent_finality','tail_threshold','required_volume_evidence'].every(k=>row.checks?.[k]===true)||
    row.independent_evidence?.source_contract_live_released!==true||row.independent_evidence?.validated!==true)return 'UNPROVEN_VERIFIED_FLAG';
   const before=Number(row.P_before),close=Number(row.P_close),volume=Number(row.closing_auction_volume),total=Number(row.intraday_total_volume);
   if(!Number.isFinite(before)||!Number.isFinite(close)||before<=0||close<=0||!meetsTailThreshold(row.P_before,row.P_close)||!(volume>0&&total>=volume))return 'INVALID_VERIFIED_VALUES';
   count++;
  }else if(row.verification_status==='VERIFIED')return 'UNPROVEN_VERIFIED_FLAG';
 }
 if(count!==body.verified_count)return 'VERIFIED_COUNT_MISMATCH';
 if(body.research_count!==body.rows.filter(r=>r.verification_status==='RESEARCH_ONLY').length||body.unknown_candidate_count!==body.rows.filter(r=>r.verification_status==='UNKNOWN').length)return 'CANDIDATE_COUNT_MISMATCH';
 if(!Number.isSafeInteger(body.universe_count)||!Number.isSafeInteger(body.screening_calculable_count)||body.screening_calculable_count<0||body.screening_calculable_count>body.universe_count||body.screening_unresolved_count!==body.universe_count-body.screening_calculable_count)return 'SCREENING_COUNT_MISMATCH';
 return null;
}
function response(status,data,extra={}){
 return new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json; charset=utf-8',
  'Cache-Control':'no-store, max-age=0','Pragma':'no-cache','X-Content-Type-Options':'nosniff',
  'Access-Control-Allow-Origin':'*','Access-Control-Expose-Headers':'ETag, X-Published-At',...extra}});
}
export default {async fetch(request,env){
 const url=new URL(request.url);
 const mis=await maybeMISBridge(request,env,{sign,canonical,privateResponse,limitedText});if(mis)return mis;
 if(url.pathname==='/health')return response(200,{scope:'ISOLATED_STAGE3',read_validator_revision:'weak-etag-v2',handoff_revision:env.HANDOFF_REVISION||null,private_evidence_available:true,live_validation_released:env.ALLOW_LIVE_VERIFIED==='true'});
 const privatePath=/^\/private-evidence\/(\d{4}-\d{2}-\d{2})\/(index|[a-f0-9]{64})$/.exec(url.pathname);
 if(privatePath){
  if(url.search||!['GET','POST'].includes(request.method))return privateResponse(404,{error:'NOT_FOUND'});
  if(!env.PUBLISH_TOKEN||!env.DECISION_KEY)return privateResponse(503,{error:'NOT_CONFIGURED'});
  if(!equal(request.headers.get('Authorization')||'','Bearer '+env.PUBLISH_TOKEN))return privateResponse(401,{error:'UNAUTHORIZED'});
  if(request.method==='POST'){
   let packet;try{packet=JSON.parse(await limitedText(request,98304));}catch{return privateResponse(413,{error:'INVALID_OR_LARGE_BODY'});}
   if(!equal(packet.signature,await sign(packet.body,env.DECISION_KEY)))return privateResponse(403,{error:'INVALID_SIGNATURE'});
   const body=packet.body,today=new Date(Date.now()+8*3600000).toISOString().slice(0,10);
   if(privatePath[1]!==today||privatePath[2]==='index'||body?.trade_date!==today||body?.id!==privatePath[2]||body?.scope!=='PRIVATE_FUGLE_EVIDENCE')return privateResponse(422,{error:'PRIVATE_SCHEMA_OR_DATE'});
   const digest=hex(await crypto.subtle.digest('SHA-256',encoder.encode(canonical(body.event))));
   if(digest!==body.id||typeof body.event?.raw!=='string'||body.event.source!=='FUGLE')return privateResponse(422,{error:'EVIDENCE_DIGEST_MISMATCH'});
   const rawHash=hex(await crypto.subtle.digest('SHA-256',encoder.encode(body.event.raw)));
   if(rawHash!==body.event.sha256)return privateResponse(422,{error:'RAW_DIGEST_MISMATCH'});
   return env.SELECTION.get(env.SELECTION.idFromName('isolated-private-evidence-'+today)).fetch(new Request('https://actor/private/'+today+'/'+body.id,{method:'POST',body:JSON.stringify(body)}));
  }
  return env.SELECTION.get(env.SELECTION.idFromName('isolated-private-evidence-'+privatePath[1])).fetch(new Request('https://actor/private/'+privatePath[1]+'/'+privatePath[2]));
 }
 if(url.pathname==='/data'&&request.method==='OPTIONS')return new Response(null,{status:204,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Methods':'GET','Access-Control-Allow-Headers':'If-None-Match'}});
 if(url.pathname==='/data'&&request.method==='GET'){
  const date=url.searchParams.get('date');if(!/^\d{4}-\d{2}-\d{2}$/.test(date||''))return response(400,{error:'INVALID_DATE'});
  return env.SELECTION.get(env.SELECTION.idFromName('isolated-market-selection')).fetch(new Request('https://actor/data?date='+date,{headers:{'If-None-Match':request.headers.get('If-None-Match')||''}}));
 }
 if(url.pathname!=='/publish'||url.search||request.method!=='POST')return response(404,{error:'NOT_FOUND'});
 if(!env.PUBLISH_TOKEN||!env.DECISION_KEY)return response(503,{error:'ISOLATED_WRITE_NOT_CONFIGURED'});
 if(!equal(request.headers.get('Authorization')||'','Bearer '+env.PUBLISH_TOKEN))return response(401,{error:'UNAUTHORIZED'});
 if(Number(request.headers.get('Content-Length')||0)>131072)return response(413,{error:'BODY_TOO_LARGE'});
 let envelope;try{
  const reader=request.body.getReader();let length=0,chunks=[];
  while(true){const {value,done}=await reader.read();if(done)break;length+=value.byteLength;if(length>131072){await reader.cancel();return response(413,{error:'BODY_TOO_LARGE'});}chunks.push(value);}
  const bytes=new Uint8Array(length);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}
  envelope=JSON.parse(new TextDecoder().decode(bytes));
 }catch{return response(400,{error:'INVALID_JSON'});}
 if(!equal(envelope.signature,await sign(envelope.body,env.DECISION_KEY)))return response(403,{error:'DECISION_SIGNATURE_MISMATCH'});
 const error=validate(envelope.body,env);if(error)return response(422,{error});
 return env.SELECTION.get(env.SELECTION.idFromName('isolated-market-selection')).fetch(new Request('https://actor/publish',{method:'POST',body:JSON.stringify(envelope.body)}));
}};
function privateResponse(status,data){const r=response(status,data);r.headers.delete('Access-Control-Allow-Origin');r.headers.delete('Access-Control-Expose-Headers');r.headers.set('X-Robots-Tag','noindex, nofollow');return r;}
async function limitedText(request,limit){const reader=request.body.getReader(),parts=[];let length=0;while(true){const {value,done}=await reader.read();if(done)break;length+=value.byteLength;if(length>limit){await reader.cancel();throw Error('LIMIT');}parts.push(value);}const bytes=new Uint8Array(length);let offset=0;for(const p of parts){bytes.set(p,offset);offset+=p.length;}return new TextDecoder().decode(bytes);}
export class SelectionStore{
 constructor(state,env){this.state=state;this.env=env;}
 async fetch(request){
  const url=new URL(request.url),storage=this.state.storage;
  if(url.pathname.startsWith('/private/')){
   const id=url.pathname.split('/').at(-1);
   if(request.method==='GET'){
    const saved=await storage.get(id==='index'?'index':'evidence:'+id);
    return privateResponse(saved?200:404,saved||{error:'NOT_FOUND'});
   }
   const body=await request.json(),bytes=encoder.encode(canonical(body)).length;
   return this.state.blockConcurrencyWhile(async()=>{
    const prior=await storage.get('evidence:'+id);
    if(prior){if(!prior.private_written_at){prior.private_written_at=new Date().toISOString();await storage.put('evidence:'+id,prior);}return privateResponse(200,{id,sha256:prior.event.sha256,private_written_at:prior.private_written_at,duplicate:true});}
    const index=await storage.get('index')||{entries:[],bytes:0};
    if(index.entries.length>=600||index.bytes+bytes>10000000)return privateResponse(507,{error:'PRIVATE_EVIDENCE_BUDGET'});
    const saved={...body,private_written_at:null};
    await storage.transaction(async txn=>{await txn.put('evidence:'+id,saved);index.entries.push({id,sha256:body.event.sha256});index.bytes+=bytes;await txn.put('index',index);});
    saved.private_written_at=new Date().toISOString();await storage.put('evidence:'+id,saved);
    if(!await storage.getAlarm())await storage.setAlarm(Date.now()+7*86400000);
    return privateResponse(200,{id,sha256:body.event.sha256,private_written_at:saved.private_written_at,duplicate:false});
   });
  }
  if(request.method==='GET'){
   const saved=await storage.get('date:'+url.searchParams.get('date'));
   if(!saved)return response(404,{error:'NO_PUBLISHED_DATA'});
   const headers={ETag:'"'+saved.sha256+'"','X-Published-At':saved.public_written_at,'X-Read-Validator-Revision':'weak-etag-v2'};
   if(matchesReadETag(request.headers.get('If-None-Match'),headers.ETag))return new Response(null,{status:304,headers:{...headers,'Cache-Control':'no-store','Access-Control-Allow-Origin':'*'}});
   return response(200,saved,headers);
  }
  const body=await request.json();
  const sha256=hex(await crypto.subtle.digest('SHA-256',encoder.encode(canonical(body))));
  const saved={...body,sha256,public_written_at:null,server_write_started_at:new Date().toISOString(),publication_scope:'ISOLATED_WORKER'};
  const outcome=await this.state.blockConcurrencyWhile(async()=>{
   const result=await storage.transaction(async txn=>{
   const key='date:'+body.trade_date,prior=await txn.get(key);
   if(prior&&prior.version===body.version&&prior.sha256===sha256)return {duplicate:true,saved:prior};
   if(prior&&prior.version>=body.version)return {conflict:true};
   await txn.put(key,saved);
   const dates=await txn.get('dates')||[];if(!dates.includes(body.trade_date))dates.push(body.trade_date);
   dates.sort();while(dates.length>10)await txn.delete('date:'+dates.shift());await txn.put('dates',dates);
   return {saved};
   });
   if(result.saved&&(!result.duplicate||!result.saved.public_written_at)){
    // Record after the payload transaction committed, never before writing.
    result.saved.public_written_at=new Date().toISOString();
    await storage.put('date:'+body.trade_date,result.saved);
   }
   return result;
  });
  if(outcome.conflict)return response(409,{error:'STALE_VERSION_OR_CONFLICT'});
  return response(200,{version:outcome.saved.version,sha256:outcome.saved.sha256,
   public_written_at:outcome.saved.public_written_at,duplicate:outcome.duplicate||false});
 }
 async alarm(){await this.state.storage.deleteAll();}
}
