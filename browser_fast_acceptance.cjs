const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium,webkit,devices}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const output=path.join(__dirname,'reports/2026-10-14-fast/browser');fs.mkdirSync(output,{recursive:true});
async function main(){
 const checks=[];
 for(const [name,type,profile,mobile] of [
  ['desktop-windows-profile',chromium,{viewport:{width:1440,height:1080},userAgent:'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'},false],
  ['iphone-chromium',chromium,devices['iPhone 13'],true],['iphone-webkit',webkit,devices['iPhone 13'],true]]){
  const browser=await type.launch(type===chromium?{executablePath:process.env.CHROMIUM_EXECUTABLE_PATH,args:['--no-sandbox','--disable-dev-shm-usage','--no-zygote']}:{});
  try{
   const page=await browser.newPage({...profile,timezoneId:'Asia/Taipei'}),errors=[],network=[];
   page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!r.url().startsWith('file:'))network.push(r.url());});
   await page.goto('file://'+path.join(__dirname,'reports/2026-10-14-fast/replay/mis-fast-selection-preview.html'));
   assert.equal(await page.locator('#fast-count').innerText(),'6');assert.equal(await page.locator('#fast-verified').innerText(),'0');
   assert.equal(await page.locator('#fast-universe').innerText(),'1,970');assert.match(await page.locator('#fast-note').innerText(),/不能當作正式交易訊號/);
   assert.equal(await page.locator('#fast-first').innerText(),'13:32:35');assert.match(await page.locator('#fast-audit').innerText(),/14:50.*15:20.*17:50/);
   for(const key of ['closing_auction_volume','intraday_total_volume','closing_volume_ratio_pct']){
    if(mobile)await page.locator('#fast-sort').selectOption(key);else await page.locator('[data-fast-sort="'+key+'"]').click();
    for(const direction of ['desc','asc']){
     if(direction==='asc'){if(mobile)await page.locator('#fast-direction').tap();else await page.locator('[data-fast-sort="'+key+'"]').press('Enter');}
     const actual=await page.evaluate(()=>FastController.getState());assert.equal(actual.direction,direction);
     const values=actual.rows.map(r=>r[key]).filter(v=>v!=null).map(Number);
     assert.deepEqual(values,values.slice().sort((a,b)=>direction==='asc'?a-b:b-a));
     assert.equal(await page.locator('th[aria-sort="'+(direction==='desc'?'descending':'ascending')+'"]').count(),1);
    }
   }
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth),true);
   assert.equal(await page.locator(mobile?'#fast-cards article':'#fast-rows tr').count(),6);
   assert.match(await page.locator(mobile?'#fast-cards':'#fast-rows').innerText(),/初次出現.*收盤取得.*更新.*保存/s);
   await page.evaluate(()=>FastController.render({...FastPayload,rows:[],research_count:0}));
   assert.match(await page.locator('#fast-empty').innerText(),/目前沒有/);
   await page.evaluate(()=>FastController.render(FastPayload));
   await page.evaluate(()=>FastController.render({...FastPayload,rows:FastPayload.rows.map(r=>({...r,validated:true,verification_status:'VERIFIED'}))}));
   assert.equal(await page.locator('#fast-verified').innerText(),'0');
   await page.evaluate(()=>FastController.render(FastPayload));
   for(const scheme of ['light','dark']){await page.emulateMedia({colorScheme:scheme});assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).backgroundColor),'rgb(13, 20, 35)');}
   await page.screenshot({path:path.join(output,name+'.png'),fullPage:true});
   assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
   checks.push({profile:name,status:'PASS',engine_version:browser.version(),six_sort_orders:true,
    per_stock_times:true,late_audit_separate:true,fabricated_flag_rejected:true,empty_state:true,
    dark_in_light_and_dark:true,no_overflow:true,no_external_requests:true,page_errors:errors});
  }finally{await browser.close();}
 }
 // Read-only local HTTP flow: an already-generated JSON appears in the page,
 // then the next ready batch is observed by its regular poll.
 const http=require('node:http'),payload=JSON.parse(fs.readFileSync(path.join(__dirname,'reports/2026-10-14-fast/replay/fast-results.json')));
 let current={...payload,rows:payload.rows.slice(0,1)};
 const server=http.createServer((req,res)=>{
  if(req.url==='/fast-results.json'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify(current));}
  else if(req.url==='/'){res.setHeader('Content-Type','text/html; charset=utf-8');res.end(fs.readFileSync(path.join(__dirname,'reports/2026-10-14-fast/replay/mis-fast-selection-preview.html')));}
  else{res.statusCode=404;res.end();}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE_PATH,args:['--no-sandbox','--disable-dev-shm-usage','--no-zygote']});
 try{
  const page=await browser.newPage();await page.goto('http://127.0.0.1:'+server.address().port+'/');
  await page.waitForFunction(()=>document.getElementById('fast-count').textContent==='1');
  current=payload;await page.waitForFunction(()=>document.getElementById('fast-count').textContent==='6');
  assert.equal(await page.locator('#fast-verified').innerText(),'0');
  checks.push({profile:'local-http-incremental-poll',status:'PASS',first_batch_count:1,updated_count:6,formal_signals:0,production_requests:0});
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
 fs.writeFileSync(path.join(output,'acceptance.json'),JSON.stringify({checks,physical_windows_or_iphone:false,formal_signals:0},null,2));
 console.log(JSON.stringify(checks,null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
