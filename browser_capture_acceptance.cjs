// Saved 10/14 evidence -> offline page -> desktop/touch sorting and status.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium,webkit,devices}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=__dirname,output=path.join(root,'reports/2026-10-14/browser');fs.mkdirSync(output,{recursive:true});
async function main(){
 const checks=[];
 for(const [name,type,options,mobile] of [
  ['desktop-windows-profile',chromium,{viewport:{width:1440,height:1080},userAgent:'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36'},false],
  ['iphone-chromium',chromium,{...devices['iPhone 13']},true],
  ['iphone-webkit',webkit,{...devices['iPhone 13']},true]]){
  const browser=await type.launch(type===chromium&&process.env.CHROMIUM_EXECUTABLE_PATH?{executablePath:process.env.CHROMIUM_EXECUTABLE_PATH,args:['--no-sandbox','--disable-dev-shm-usage','--no-zygote']}:{});
  try{
   const context=await browser.newContext({...options,timezoneId:'Asia/Taipei'}),page=await context.newPage(),errors=[],network=[];
   page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!r.url().startsWith('file:'))network.push(r.url());});
   await page.goto('file://'+path.join(root,'reports/2026-10-14/oct14-isolated-preview.html'));
   await page.waitForFunction(()=>window.TailDashboardView?.rows.length===6);
   assert.equal(await page.locator('#universe').innerText(),'1,970');assert.equal(await page.locator('#calculable').innerText(),'1,946');
   assert.equal(await page.locator('#unknown').innerText(),'24');assert.match(await page.locator('#capture-detail').innerText(),/缺 50 檔/);
   assert.match(await page.locator('#official-detail').innerText(),/已驗證 0 檔/);assert.match(await page.locator('#next-check').innerText(),/14:50/);
   assert.equal(await page.locator('.candidate-card').count(),6);assert.equal(await page.locator('#desktop-list tr').count(),6);
   for(const key of ['closing_auction_volume','intraday_total_volume','closing_volume_ratio_pct']){
    if(mobile)await page.locator('#mobile-sort-field').selectOption(key);else await page.locator('[data-sort-key="'+key+'"]').click();
    for(const direction of ['desc','asc']){
     if(direction==='asc'){if(mobile)await page.locator('#mobile-sort-direction').tap();else await page.locator('[data-sort-key="'+key+'"]').press('Enter');}
     assert.equal(await page.locator('th[aria-sort="'+(direction==='desc'?'descending':'ascending')+'"]').count(),1);
     assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth),true);
    }
   }
   // Re-render actual failed origin with its research list retained for diagnosis;
   // official match must not change the capture outcome or validation flags.
   await page.evaluate(()=>{
    const v=window.TailDashboardView,live={...v.live,capture_outcome:'CAPTURE_FAILED',status:'failed'};
    const official={trade_date:v.today,status:'SAME_DATE_COMPARISON_ONLY',source_capture_run_id:live.run_id};
    const model=window.TailDashboard.model(new Date(),{calendar:{year:2026,closed_dates:[]},data:v.data,live,official});
    window.TailDashboard.render(document,model);window.captureTestView=model;
   });
   assert.match(await page.locator('#headline').innerText(),/擷取未完成/);assert.match(await page.locator('#official-detail').innerText(),/比對已完成/);
   assert.equal(await page.evaluate(()=>window.captureTestView.verified),0);assert.equal(await page.locator('.candidate-card').count(),6);
   // Verify independent running, pending and official source-error states.
   for(const [state,officialStatus] of [['running','PENDING'],['partial','PENDING_SOURCE_ERROR'],['partial','RECHECKING'],['partial','PENDING_RECHECK_ERROR']]){
    await page.evaluate(({state,officialStatus})=>{
     const v=window.TailDashboardView,live={...v.live,status:state,capture_outcome:state==='running'?null:'CAPTURE_PARTIAL',phase:'close_reference_B'};
     const view=window.TailDashboard.model(new Date(),{calendar:{year:2026,closed_dates:[]},live,official:{trade_date:v.today,status:officialStatus}});
     window.TailDashboard.render(document,view);
    },{state,officialStatus});
    assert.match(await page.locator('#capture-detail').innerText(),state==='running'?/正在擷取/:/部分擷取完成/);
    assert.equal(await page.locator('.candidate-card').count(),0);
   }
   await page.evaluate(()=>window.TailDashboard.render(document,window.TailDashboardView));
   await page.emulateMedia({colorScheme:'light'});assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).backgroundColor),'rgb(13, 20, 35)');
   await page.emulateMedia({colorScheme:'dark'});assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).backgroundColor),'rgb(13, 20, 35)');
   await page.screenshot({path:path.join(output,name+'.png'),fullPage:true});
   assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
   checks.push({profile:name,status:'PASS',browser_version:browser.version(),host_os:process.platform,device_emulation:mobile,
    full_sort_orders:6,no_external_network:true,no_page_errors:true,historical_failed_state_preserved:true,formal_signals:0});
   await context.close();
  }finally{await browser.close();}
 }
 fs.writeFileSync(path.join(output,'capture-acceptance.json'),JSON.stringify({checks,limitations:'Linux engines with Windows UA and iPhone emulation; not physical Windows or iPhone hardware.'},null,2));
 console.log(JSON.stringify(checks,null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
