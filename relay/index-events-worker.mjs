// Fixed-purpose relay. No private keys, tokens or caller secrets in source/logs.
const REPO='gxaawill2-ui/tw-close-auction-mis-probe';
const REPO_ID=1395186758;
const DISPATCH='https://api.github.com/repos/'+REPO+'/actions/workflows/index-events.yml/dispatches';
const encoder=new TextEncoder();
const reply=(status,result)=>new Response(JSON.stringify({result}),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
const b64=x=>btoa(String.fromCharCode(...new Uint8Array(x))).replace(/=/g,'').replace(/\+/g,'-').replace(/\//g,'_');
const encode=x=>b64(encoder.encode(JSON.stringify(x)));
async function boundedText(request,limit){
 const reader=request.body?.getReader();if(!reader)return '';
 const chunks=[];let length=0;
 try{for(;;){const {done,value}=await reader.read();if(done)break;length+=value.byteLength;if(length>limit){await reader.cancel();throw new Error('TOO_LARGE');}chunks.push(value);}}
 finally{reader.releaseLock();}
 const joined=new Uint8Array(length);let offset=0;for(const chunk of chunks){joined.set(chunk,offset);offset+=chunk.length;}
 return new TextDecoder().decode(joined);
}
export async function authenticated(request,secret){
 if(typeof secret!=='string'||! /^[A-Za-z0-9_-]{43,128}$/.test(secret))return false;
 const supplied=request.headers.get('Authorization')||'';
 if(supplied.length>160)return false;
 const a=new Uint8Array(await crypto.subtle.digest('SHA-256',encoder.encode(supplied)));
 const b=new Uint8Array(await crypto.subtle.digest('SHA-256',encoder.encode('Bearer '+secret)));
 let difference=0;for(let i=0;i<a.length;i++)difference|=a[i]^b[i];return difference===0;
}
// GitHub downloads PKCS#1; WebCrypto imports PKCS#8. Wrap only validated DER.
function derLength(n){if(n<128)return [n];const bytes=[];while(n){bytes.unshift(n&255);n>>=8;}return [128|bytes.length,...bytes];}
function der(tag,bytes){return new Uint8Array([tag,...derLength(bytes.length),...bytes]);}
export function privateDer(pem){
 const pkcs1=/^-----BEGIN RSA PRIVATE KEY-----[\s\S]+-----END RSA PRIVATE KEY-----\s*$/.test(pem);
 if(!pkcs1&&!/^-----BEGIN PRIVATE KEY-----[\s\S]+-----END PRIVATE KEY-----\s*$/.test(pem))throw new Error('KEY_FORMAT');
 const binary=atob(pem.replace(/-----[^-]+-----|\s/g,''));
 const raw=Uint8Array.from(binary,c=>c.charCodeAt(0));
 if(raw.length<1000||raw.length>4096||raw[0]!==48)throw new Error('KEY_FORMAT');
 return pkcs1?der(48,[2,1,0,48,13,6,9,42,134,72,134,247,13,1,1,1,5,0,...der(4,raw)]):raw;
}
export async function appJWT(env,now){
 if(!/^[A-Za-z0-9_.-]{1,80}$/.test(env.APP_CLIENT_ID||''))throw new Error('CONFIG');
 const key=await crypto.subtle.importKey('pkcs8',privateDer(env.APP_PRIVATE_KEY),{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['sign']);
 const seconds=Math.floor(now/1000),input=encode({alg:'RS256',typ:'JWT'})+'.'+encode({iat:seconds-60,exp:seconds+540,iss:env.APP_CLIENT_ID});
 return input+'.'+b64(await crypto.subtle.sign('RSASSA-PKCS1-v1_5',key,encoder.encode(input)));
}
async function github(url,token,body,fetcher=fetch){
 const control=new AbortController(),timer=setTimeout(()=>control.abort(),6500);
 try{return await fetcher(url,{method:'POST',redirect:'error',signal:control.signal,headers:{'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2026-03-10','Content-Type':'application/json','User-Agent':'tw-index-events-app-relay'},body:JSON.stringify(body)});}finally{clearTimeout(timer);}
}
export async function dispatch(env,slot,selfTest,now,fetcher=fetch){
 if(!/^[1-9]\d{0,15}$/.test(env.APP_INSTALLATION_ID||''))throw new Error('CONFIG');
 // No token persisted: each of two daily calls gets a fresh one-hour token.
 const jwt=await appJWT(env,now);
 const r=await github('https://api.github.com/app/installations/'+env.APP_INSTALLATION_ID+'/access_tokens',jwt,{repository_ids:[REPO_ID],permissions:{actions:'write',metadata:'read'}},fetcher);
 if(r.status!==201)throw new Error('TOKEN_HTTP_'+r.status);
 const data=JSON.parse(await boundedText(r,32768)),expires=Date.parse(data.expires_at);
 if(typeof data.token!=='string'||!Number.isFinite(expires)||expires<now+60000||expires>now+3660000||data.permissions?.actions!=='write'||Object.keys(data.permissions||{}).some(k=>!['actions','metadata'].includes(k))||!Array.isArray(data.repositories)||data.repositories.length!==1||data.repositories[0].id!==REPO_ID||data.repositories[0].full_name!==REPO)throw new Error('TOKEN_SCOPE');
 const sent=await github(DISPATCH,data.token,{ref:'main',inputs:{schedule_slot:slot,self_test:selfTest}},fetcher);
 if(sent.status===204)return {result:'DISPATCH_ACCEPTED',workflow_run_id:null};
 if(sent.status!==200)throw new Error('DISPATCH_HTTP_'+sent.status);
 const run=JSON.parse(await boundedText(sent,4096));
 if(!Number.isSafeInteger(run.workflow_run_id)||run.workflow_run_id<=0||run.run_url!=='https://api.github.com/repos/'+REPO+'/actions/runs/'+run.workflow_run_id||run.html_url!=='https://github.com/'+REPO+'/actions/runs/'+run.workflow_run_id)throw new Error('DISPATCH_RECEIPT_SCOPE');
 return {result:'DISPATCH_ACCEPTED',workflow_run_id:run.workflow_run_id};
}
export function slotIdentity(slot,now,selfTest=false){
 const local=new Date(now+8*3600000),day=local.toISOString().slice(0,10),minute=local.getUTCHours()*60+local.getUTCMinutes();
 const planned=slot==='08:20'?500:slot==='17:20'?1040:null;
 if(planned===null||(!selfTest&&(minute<planned+15||minute>planned+60)))return null;
 return day+'-'+slot.replace(':','')+(selfTest?'-self-test':'');
}
export default {async fetch(request,env){
 const url=new URL(request.url);
 if(url.pathname==='/health'&&request.method==='GET')return reply(200,'RELAY_ALIVE; AUTH_AND_INSTALLATION_NOT_PROVEN');
 if(url.pathname!=='/dispatch'||url.search)return reply(404,'NOT_FOUND');
 if(request.method!=='POST')return reply(405,'METHOD_NOT_ALLOWED');
 if(!await authenticated(request,env.CALLER_SECRET))return reply(401,'UNAUTHORIZED');
 if(Number(request.headers.get('Content-Length')||0)>256)return reply(413,'TOO_LARGE');
 let body;try{body=JSON.parse(await boundedText(request,256));}catch(e){return reply(e.message==='TOO_LARGE'?413:400,'INVALID_BODY');}
 if(!body||Object.keys(body).some(k=>!['schedule_slot','self_test'].includes(k))||!['08:20','17:20'].includes(body.schedule_slot)||typeof body.self_test!=='boolean')return reply(400,'INVALID_BODY');
 if(!slotIdentity(body.schedule_slot,Date.now(),body.self_test))return reply(409,'OUTSIDE_SLOT_WINDOW');
 // A single SQLite Durable Object supplies globally atomic replay/lease limits.
 return env.DISPATCH_GATE.get(env.DISPATCH_GATE.idFromName('fixed-repository')).fetch(new Request('https://gate/dispatch',{method:'POST',body:JSON.stringify(body)}));
}};
export class DispatchGate {
 constructor(state,env){this.state=state;this.env=env;}
 async fetch(request){
  const body=await request.json(),now=Date.now(),id=slotIdentity(body.schedule_slot,now,body.self_test);
  if(!id)return reply(409,'OUTSIDE_SLOT_WINDOW');
  const day=id.slice(0,10),storage=this.state.storage;
  const decision=await storage.transaction(async txn=>{
   const prior=await txn.get(id)||{attempts:0},budget=await txn.get('budget')||{day,count:0};
   if(prior.success)return 'DUPLICATE_ACCEPTED';
   if(prior.lease_until>now)return 'IN_PROGRESS';
   if(prior.attempts>=2)return 'ATTEMPT_LIMIT';
   if(budget.day===day&&budget.count>=6)return 'DAILY_LIMIT';
   await txn.put('budget',{day,count:(budget.day===day?budget.count:0)+1});
   await txn.put(id,{attempts:prior.attempts+1,lease_until:now+60000});
   return 'CLAIMED';
  });
  if(decision!=='CLAIMED')return reply(['DUPLICATE_ACCEPTED','IN_PROGRESS'].includes(decision)?200:429,decision);
  try{
   const accepted=await dispatch(this.env,body.schedule_slot,body.self_test,now);
   await storage.transaction(async txn=>{const v=await txn.get(id);await txn.put(id,{...v,success:true,lease_until:0,accepted_at:Date.now(),workflow_run_id:accepted.workflow_run_id});});
   // Keep only a bounded seven-day replay ledger. Never store auth data.
   const ledger=await storage.list({limit:40});for(const key of ledger.keys())if(/^20\d\d-\d\d-\d\d-/.test(key)&&key.slice(0,10)<new Date(now-7*86400000).toISOString().slice(0,10))await storage.delete(key);
   return reply(202,'DISPATCH_ACCEPTED; WORKFLOW_RECEIPT_PENDING');
  }catch{
   // Ambiguous network failures may already have dispatched: one bounded retry,
   // then the workflow's separate CAS receipt prevents another source scan.
   await storage.transaction(async txn=>{const v=await txn.get(id);await txn.put(id,{...v,lease_until:Date.now()+60000,failed_at:Date.now()});});
   return reply(503,'DISPATCH_UNVERIFIED');
  }
 }
}
