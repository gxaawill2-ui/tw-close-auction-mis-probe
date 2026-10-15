'use strict';
// Real browser engines against LOCAL synthetic transport, never a market feed.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const {chromium,webkit,devices}=require(require.resolve('playwright',{paths:[process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES]}));
async function main(){
 const {worker,token,key,url}=await require('./stage3_worker_runtime.cjs').startWorker();
 const {canonical}=await import('./isolated_publication/worker.mjs');
 const html=fs.readFileSync('isolated_publication/stage4-site/index.html');
 const output='reports/2026-10-15-stage4/cloud-preparation/browser';fs.mkdirSync(output,{recursive:true});
 let version=Date.now()*10;const checks=[];
 async function publish(rows){
  const body={schema_version:'STAGE3_SELECTION_V1',trade_date:'2099-01-01',version:++version,mode:'SYNTHETIC',is_synthetic:true,rows,verified_count:0,research_count:0,unknown_candidate_count:rows.length,universe_count:0,screening_calculable_count:0,screening_unresolved_count:0,generated_at:new Date().toISOString()};
  const signature=crypto.createHmac('sha256',key).update(canonical(body)).digest('hex');
  const r=await fetch(url+'/publish',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({body,signature})});assert.equal(r.status,200);return r.json();
 }
 const row={code:'0000',ex:'tse',name:'合成傳輸測試，非真實股票',verification_status:'UNKNOWN',validated:false};
 const server=http.createServer(async(req,res)=>{
  if(req.url.startsWith('/data?')){try{const upstream=await fetch(url+req.url,{cache:'no-store'});const headers=Object.fromEntries(upstream.headers);delete headers['content-encoding'];delete headers['content-length'];delete headers['transfer-encoding'];res.writeHead(upstream.status,headers);res.end(Buffer.from(await upstream.arrayBuffer()));}catch{res.writeHead(503);res.end();}}
  else{res.setHeader('Content-Type','text/html; charset=utf-8');res.end(html);}
 });
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try{
  for(const [name,engine,profile] of [['desktop',chromium,{viewport:{width:1440,height:1080}}],['iphone-chromium',chromium,devices['iPhone 13']],['iphone-webkit',webkit,devices['iPhone 13']]]){
   let browser;try{browser=await engine.launch(engine===chromium?{executablePath:process.env.CHROMIUM_EXECUTABLE_PATH||'/workspace/scratch/52ff117b908b/fast-browser-runtime/bin/chromium',args:['--no-sandbox','--disable-dev-shm-usage','--no-zygote']}:{});}
   catch(error){checks.push({profile:name,status:'BLOCKED',reason:error.message,physical_device:false,public_internet:false});continue;}
   try{
    const page=await browser.newPage({...profile,timezoneId:'Asia/Taipei'}),errors=[],transport=[];page.on('pageerror',e=>errors.push(e.message));page.on('requestfailed',r=>transport.push({url:r.url(),failure:r.failure()}));page.on('console',m=>{if(m.type()==='error')transport.push({console:m.text()});});
    await publish([]);await page.goto('http://127.0.0.1:'+server.address().port+'/');
    try{await page.waitForFunction(()=>document.querySelector('#stage3-network').textContent.includes('已讀取'),{},{timeout:10000});}
    catch(error){fs.writeFileSync(path.join(output,name+'-failure.json'),JSON.stringify({errors,transport,network:await page.locator('#stage3-network').innerText(),body:await page.locator('body').innerText(),read:await fetch(url+'/data?date=2099-01-01').then(r=>r.json())},null,2));throw error;}
    assert.match(await page.locator('#stage3-mode').innerText(),/合成測試/);assert.equal(await page.locator('#stage3-verified').innerText(),'0');
    const receipt=await publish([row]);await page.waitForFunction(()=>document.querySelector('#stage3-unknown').textContent==='1');
    const reads=await page.evaluate(()=>Stage3Controller.reads);assert.ok(reads.some(x=>x.version===receipt.version&&x.sha256===receipt.sha256));
    await page.reload();await page.waitForFunction(()=>document.querySelector('#stage3-unknown').textContent==='1');
    await page.screenshot({path:path.join(output,name+'-with-synthetic-row.png'),fullPage:true});
    await publish([]);await page.waitForFunction(()=>document.querySelector('#stage3-unknown').textContent==='0');
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.deepEqual(errors,[]);
    await page.screenshot({path:path.join(output,name+'.png'),fullPage:true});
    checks.push({profile:name,status:'PASS',refresh:'EMPTY_TO_UNKNOWN_TO_EMPTY',reload:true,synthetic_banner:true,formal_verified:0,no_overflow:true,physical_device:false,public_internet:false,read_receipts:reads});
   }finally{await browser.close();}
  }
 }finally{await worker.dispose();await new Promise(r=>server.close(r));}
 fs.writeFileSync(path.join(output,'acceptance.json'),JSON.stringify({scope:'REAL_BROWSER_ENGINES_LOCAL_SYNTHETIC_ONLY',checks},null,2)+'\n');console.log(JSON.stringify(checks.map(({profile,status})=>({profile,status}))));if(checks.some(x=>x.status!=='PASS'))process.exitCode=1;
}
main().catch(e=>{console.error(e);process.exitCode=1;});
