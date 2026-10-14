const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),http=require('node:http'),crypto=require('node:crypto');
const {startWorker}=require('./stage3_worker_runtime.cjs');
const {chromium,webkit,devices}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const output=path.join(__dirname,'reports/2026-10-14-stage3/browser');fs.mkdirSync(output,{recursive:true});
async function main(){
 const {worker,token,key,url}=await startWorker(),{canonical}=await import('./isolated_publication/worker.mjs');
 const base=JSON.parse(fs.readFileSync(path.join(__dirname,'reports/2026-10-14-stage3/replay/stage3-results.json')));
 let version=0;const updates=[],checks=[];
 async function publish(rows){
  const body={...base,version:++version,rows,research_count:rows.filter(r=>r.verification_status==='RESEARCH_ONLY').length,unknown_candidate_count:rows.filter(r=>r.verification_status==='UNKNOWN').length};
  const signature=crypto.createHmac('sha256',key).update(canonical(body)).digest('hex');
  const started=new Date().toISOString();
  const r=await fetch(url+'/publish',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({body,signature})});
  assert.equal(r.status,200);const result=await r.json();updates.push({...result,client_request_started_at:started,client_ack_at:new Date().toISOString()});return result;
 }
 const server=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html; charset=utf-8');res.end(fs.readFileSync(path.join(__dirname,'reports/2026-10-14-stage3/replay/stage3-preview.html')));});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{
  for(const [name,type,profile,mobile] of [
   ['desktop-windows-profile',chromium,{viewport:{width:1440,height:1080},userAgent:'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'},false],
   ['iphone-chromium',chromium,devices['iPhone 13'],true],['iphone-webkit',webkit,devices['iPhone 13'],true]]){
   const browser=await type.launch(type===chromium?{executablePath:process.env.CHROMIUM_EXECUTABLE_PATH,args:['--no-sandbox','--disable-dev-shm-usage','--no-zygote']}:{});
   try{
    const page=await browser.newPage({...profile,timezoneId:'Asia/Taipei'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
    await publish(base.rows.slice(0,1));
    const endpoint=url+'/data?date='+base.trade_date;
    await page.goto('http://127.0.0.1:'+server.address().port+'/?endpoint='+encodeURIComponent(endpoint));
    await page.waitForFunction(()=>document.getElementById('stage3-research').textContent==='1');
    const receipt=await publish(base.rows);
    await page.waitForFunction(()=>document.getElementById('stage3-research').textContent==='6');
    assert.equal(await page.locator('#stage3-verified').innerText(),'0');
    assert.match(await page.locator('#stage3-screening').innerText(),/24.*可能漏選/);
    assert.match(await page.locator('#stage3-audit').innerText(),/14:50.*15:20.*17:50/);
    assert.notEqual(await page.locator('#stage3-write').innerText(),'未取得');assert.notEqual(await page.locator('#stage3-read').innerText(),'未取得');
    const reads=await page.evaluate(()=>Stage3Controller.reads);const observed=reads.find(r=>r.version===receipt.version);
    assert.ok(observed);assert.equal(observed.sha256,receipt.sha256);
    const readLag=Date.parse(observed.browser_observed_at)-Date.parse(receipt.public_written_at);assert.ok(readLag>=0&&readLag<6000);
    for(const sort of ['closing_auction_volume','intraday_total_volume','closing_volume_ratio_pct']){
     if(mobile)await page.locator('#stage3-sort').selectOption(sort);else await page.locator('[data-stage3-sort="'+sort+'"]').click();
     for(const direction of ['desc','asc']){
      if(direction==='asc'){if(mobile)await page.locator('#stage3-direction').tap();else await page.locator('[data-stage3-sort="'+sort+'"]').press('Enter');}
      const state=await page.evaluate(()=>Stage3Controller.getState());const values=state.rows.map(r=>r[sort]).filter(v=>v!=null).map(Number);
      assert.deepEqual(values,values.slice().sort((a,b)=>direction==='asc'?a-b:b-a));
     }
    }
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth),true);
    await page.evaluate(()=>Stage3Controller.render({...Stage3Payload,rows:[{...Stage3Payload.rows[0],verification_status:'UNKNOWN'}]}));
    assert.equal(await page.locator('#stage3-unknown').innerText(),'1');
    await page.evaluate(()=>Stage3Controller.render({...Stage3Payload,rows:Stage3Payload.rows.map(r=>({...r,validated:true,verification_status:'VERIFIED'}))}));
    assert.equal(await page.locator('#stage3-verified').innerText(),'0');
    // Failed read keeps the original state and update times visible.
    await page.evaluate(async()=>Stage3Controller.poll('http://127.0.0.1:1/data'));
    assert.match(await page.locator('#stage3-network').innerText(),/失敗.*上一版/);
    await page.evaluate(()=>Stage3Controller.render({...Stage3Payload,rows:[]}));assert.match(await page.locator('#stage3-empty').innerText(),/等待/);
    await page.evaluate(()=>Stage3Controller.render(Stage3Payload));
    for(const colorScheme of ['dark','light']){await page.emulateMedia({colorScheme});assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).backgroundColor),'rgb(13, 20, 35)');}
    await page.screenshot({path:path.join(output,name+'.png'),fullPage:true});assert.deepEqual(errors,[]);
    checks.push({profile:name,status:'PASS',engine_version:browser.version(),six_sort_orders:true,actual_local_worker_sqlite_refresh:'1_TO_6',public_internet:false,
      anonymous_read_receipts:reads,worker_write_to_browser_ms:readLag,independent_states:true,invalid_verified_rejected:true,dark_mode:true,no_overflow:true});
   }finally{await browser.close();}
  }
 }finally{await worker.dispose();await new Promise(resolve=>server.close(resolve));}
 fs.writeFileSync(path.join(output,'acceptance.json'),JSON.stringify({checks,updates,scope:'LOOPBACK_WORKER_ENGINE_NOT_CLOUDFLARE_DEPLOYMENT',physical_device:false,formal_signals:0},null,2));
 console.log(JSON.stringify(checks.map(x=>({profile:x.profile,status:x.status,worker_write_to_browser_ms:x.worker_write_to_browser_ms}))));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
