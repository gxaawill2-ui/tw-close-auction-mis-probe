// Browser rendering tests only. No MIS requests, no credentials, no live dispatch.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {chromium,webkit,devices}=require('playwright');
const ROOT=__dirname,calendar=JSON.parse(fs.readFileSync('state/calendars/2026.json','utf8'));
const data=JSON.parse(fs.readFileSync('state/candidates/2026-10-08.json','utf8'));
const eventsData=JSON.parse(fs.readFileSync('state/events/events-index.json','utf8'));
const fundsData=JSON.parse(fs.readFileSync('state/events/fund-events.json','utf8'));
const PUBLIC='https://gxaawill2-ui.github.io/tw-close-auction-mis-probe/';
const OUT=path.join(ROOT,'browser-results');fs.mkdirSync(OUT,{recursive:true});
const server=http.createServer((request,response)=>{
 const name=new URL(request.url,'http://localhost').pathname;
 const file=path.join(ROOT,'docs',name==='/'?'index.html':name);
 if(!file.startsWith(path.join(ROOT,'docs')+path.sep)){response.writeHead(403).end();return;}
 try{response.setHeader('Content-Type',file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html');response.end(fs.readFileSync(file));}
 catch{response.writeHead(404).end();}
});
const copy=x=>JSON.parse(JSON.stringify(x));
const sortKeys=['closing_auction_volume','intraday_total_volume','closing_volume_ratio_pct'];
async function verifySort(page,mobile,rows){
 const before=await page.evaluate(()=>JSON.stringify(window.TailDashboardView.data));
 const fields=mobile?page.locator('#mobile-sort-field'):null;
 for(const key of sortKeys){
  if(mobile)await fields.selectOption(key);else await page.locator('[data-sort-key="'+key+'"]').click();
  for(const direction of ['desc','asc']){
   if(direction==='asc'){
    const button=mobile?page.locator('#mobile-sort-direction'):page.locator('[data-sort-key="'+key+'"]');
    if(mobile)await button.tap();else{await button.focus();await button.press('Enter');}
   }
   const expected=rows.map((r,index)=>({r,index,v:r.volume_status==='MIS_EVIDENCE_CONFIRMED'&&r[key]!=null?Number(r[key]):null})).sort((a,b)=>{
    if(a.v===null||b.v===null)return a.v===b.v?a.index-b.index:a.v===null?1:-1;
    return (direction==='desc'?b.v-a.v:a.v-b.v)||a.index-b.index;
   }).map(x=>x.r.code);
   for(const selector of ['#desktop-list tr','.candidate-card'])assert.deepEqual(await page.locator(selector).evaluateAll(nodes=>nodes.map(x=>x.dataset.code)),expected);
   assert.equal(await page.locator('th[aria-sort="'+(direction==='desc'?'descending':'ascending')+'"]').count(),1);
   assert.equal(await page.locator('th[aria-sort="none"]').count(),2);
   assert.deepEqual(await page.locator('th[aria-sort="none"] .sort-arrow').allTextContents(),['⇅','⇅']);
   assert.equal(await page.locator('th[aria-sort="'+(direction==='desc'?'descending':'ascending')+'"] .sort-arrow').evaluate(el=>getComputedStyle(el).color),'rgb(138, 168, 255)');
   for(const color of await page.locator('th[aria-sort="none"] .sort-arrow').evaluateAll(nodes=>nodes.map(el=>getComputedStyle(el).color)))assert.equal(color,'rgb(135, 152, 173)');
   assert.equal(await page.locator('[data-sort-key="'+key+'"] .sort-arrow').innerText(),direction==='desc'?'↓':'↑');
   assert.match(await page.locator('#sort-summary').textContent(),direction==='desc'?/↓/:/↑/);
   assert.equal(await page.locator('#mobile-sort-field').inputValue(),key);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth),true);
   assert.equal(await page.evaluate(()=>JSON.stringify(window.TailDashboardView.data)),before);
  }
 }
 if(mobile){const button=page.locator('#mobile-sort-direction');await button.focus();await button.press('Enter');await button.press('Enter');assert.match(await button.innerText(),/↑/);}
}
async function verifyHeaderHitArea(page){
 const geometry=await page.locator('th[aria-sort]').evaluateAll(nodes=>nodes.map(el=>({width:el.getBoundingClientRect().width,height:el.getBoundingClientRect().height,font:getComputedStyle(el).fontSize})));
 for(const key of sortKeys){
  const header=page.locator('th').filter({has:page.locator('[data-sort-key="'+key+'"]')});
  const normal=await header.evaluate(el=>getComputedStyle(el).backgroundColor);
  await page.mouse.move(0,0);await header.hover();
  await page.waitForFunction(key=>getComputedStyle(document.querySelector('[data-sort-key="'+key+'"]').closest('th')).backgroundColor==='rgb(43, 58, 83)',key);
  const rect=await header.evaluate(el=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};});
  // Click cell padding, outside the original text/button rectangle.
  await page.mouse.click(rect.x+2,rect.y+2);
  assert.equal(await header.getAttribute('aria-sort'),'descending');
  await page.mouse.click(rect.x+rect.width-2,rect.y+rect.height-2);
  assert.equal(await header.getAttribute('aria-sort'),'ascending');
  await page.locator('[data-sort-key="'+key+'"]').focus();await page.keyboard.press('Space');
  assert.equal(await header.getAttribute('aria-sort'),'descending');
  assert.deepEqual(await page.locator('th[aria-sort]').evaluateAll(nodes=>nodes.map(el=>({width:el.getBoundingClientRect().width,height:el.getBoundingClientRect().height,font:getComputedStyle(el).fontSize}))),geometry);
  assert.equal(geometry.every(x=>x.font==='11px'),true);
 }
}
async function fixtureContext(browser,options,date='2026-10-08T18:30:00+08:00',payload=data,eventFailure=false){
 const context=await browser.newContext({...options,timezoneId:'Asia/Taipei'});
 const eventFixture=copy(eventsData);eventFixture.generated_at=date;
 // Synthetic UI clock only. Production first-seen timestamps are untouched.
 for(const e of eventFixture.events){e.first_seen_at=e.information_available_as_of='2026-10-07T00:00:00+08:00'; if(e.closing_impact_date){e.constituent_counts={additions:1,deletions:1};e.evidence_level='OFFICIAL_ISSUER_DATE_ONLY';}}
 await context.addInitScript(fixed=>{
  const RealDate=Date;class Clock extends RealDate{constructor(...args){super(...(args.length?args:[fixed]));}static now(){return new RealDate(fixed).getTime();}}
  window.Date=Clock;
 },date);
 await context.route('https://raw.githubusercontent.com/**',route=>{
  const url=route.request().url();
  if(url.includes('/state/events/')){
   if(eventFailure)return route.fulfill({status:503,body:'Source temporarily unavailable'});
   if(url.includes('events-index.json'))return route.fulfill({json:eventFixture});
   if(url.includes('fund-events.json'))return route.fulfill({json:fundsData});
   if(url.includes('source-health.json'))return route.fulfill({json:{last_successful_scan_at:date,coverage_status:'PARTIAL',sources:[{status:'SUCCESS'}]}});
  }
  if(url.includes('/state/calendars/'))return route.fulfill({json:calendar});
  if(url.includes('/state/candidates/')&&payload!==null)return route.fulfill({json:payload});
  return route.fulfill({status:404,body:'Not found'});
 });
 // Every fixture request is offline or to our local test server. Forbid an
 // accidental market endpoint even if a future UI edit tried to add one.
 await context.route('**/*',route=>{
  const url=route.request().url();
  if(url.startsWith('http://127.0.0.1:')||url.startsWith('https://raw.githubusercontent.com/'))return route.fallback();
  throw new Error('Forbidden test network request: '+url);
 });
 return context;
}
async function main(){
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port+'/',checks=[];
 for(const [name,type,options,mobile] of [
  ['chromium-desktop',chromium,{viewport:{width:1440,height:1100}},false],
  ['chromium-mobile',chromium,{...devices['iPhone 13'],viewport:{width:390,height:844}},true],
  ['webkit-iphone',webkit,{...devices['iPhone 13'],viewport:{width:390,height:844}},true]
 ]){
  const browser=await type.launch();
  try{
   const context=await fixtureContext(browser,options),page=await context.newPage(),errors=[];
   page.on('pageerror',error=>errors.push(error.message));await page.goto(base);
   await page.waitForFunction(()=>document.querySelector('#candidate-count').textContent==='7');
   assert.equal(await page.locator('button').count(),4);assert.equal(await page.locator('select').count(),1);assert.equal(await page.locator('input,form,[role="button"]').count(),0);
   assert.equal(await page.locator('.candidate-card').count(),7);
   assert.equal(await page.locator('#desktop-list tr').count(),7);
   assert.equal(await page.locator('#desktop-wrap').isVisible(),!mobile);
   assert.equal(await page.locator('.candidate-card').first().isVisible(),mobile);
   assert.equal(await page.locator('#mobile-list .delayed').count(),3);
   assert.equal(await page.locator('.candidate-card .tail.up').count(),4);
   assert.equal(await page.locator('.candidate-card .tail.down').count(),3);
   await page.waitForFunction(()=>document.querySelectorAll('#event-upcoming .event-row').length>0);
   assert.match(await page.locator('#event-today-title').innerText(),/未發現已確認實質調整/);
   assert.ok(await page.locator('#event-upcoming a').count()>0);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth),true);
   if(mobile){
    assert.match(await page.locator('.candidate-card[data-code="3259"]').innerText(),/13:33:00/);
    assert.match(await page.locator('.candidate-card[data-code="3684"]').innerText(),/1,255/);
    assert.match(await page.locator('.candidate-card[data-code="5543"]').innerText(),/75/);
   }
   await page.screenshot({path:path.join(OUT,'dashboard-'+name+'.png'),fullPage:true});
   await page.emulateMedia({colorScheme:'light'});
   const fixedDark=await page.evaluate(()=>({
     background:getComputedStyle(document.documentElement).backgroundColor,
     panel:getComputedStyle(document.querySelector('.overview')).backgroundColor,
     text:getComputedStyle(document.documentElement).color,
     controls:getComputedStyle(document.documentElement).colorScheme,
     rise:getComputedStyle(document.querySelector('.tail.up')).color,
     fall:getComputedStyle(document.querySelector('.tail.down')).color
   }));
   assert.equal(fixedDark.background,'rgb(13, 20, 35)');
   assert.equal(fixedDark.panel,'rgb(22, 33, 50)');
   assert.equal(fixedDark.controls,'dark');
   assert.notEqual(fixedDark.rise,fixedDark.fall);
   await page.emulateMedia({colorScheme:'dark'});
   const darkPreference=await page.evaluate(()=>({
     background:getComputedStyle(document.documentElement).backgroundColor,
     panel:getComputedStyle(document.querySelector('.overview')).backgroundColor,
     text:getComputedStyle(document.documentElement).color,
     controls:getComputedStyle(document.documentElement).colorScheme,
     rise:getComputedStyle(document.querySelector('.tail.up')).color,
     fall:getComputedStyle(document.querySelector('.tail.down')).color
   }));
   assert.deepEqual(darkPreference,fixedDark);
   assert.equal(await page.locator('button').count(),4);assert.equal(await page.locator('select').count(),1);assert.equal(await page.locator('input,form,[role="button"]').count(),0);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth),true);
   if(mobile)assert.equal(await page.locator('.candidate-card').first().evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(22, 33, 50)');
   await page.screenshot({path:path.join(OUT,'dashboard-'+name+'-dark-only.png'),fullPage:true});
   checks.push({name:name+'/dark-only',result:'PASS',independent_of_system_theme:true,authorized_sort_controls:true});
   await page.emulateMedia({colorScheme:'light'});
   assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).backgroundColor),'rgb(13, 20, 35)');
   assert.deepEqual(errors,[]);checks.push({name,result:'PASS',width:options.viewport.width,seven_candidates:true,authorized_sort_controls:true,no_horizontal_overflow:true});
   assert.equal(await page.locator('.market-closing').isVisible(),false);
   assert.equal(await page.locator('.market-closing').evaluate(el=>el.getBoundingClientRect().height),0);
   const tails=await page.locator('.candidate-card .tail').allTextContents();assert.ok(tails.every(x=>/^[+-]\d+\.\d{2}%$/.test(x)));
   await page.waitForFunction(()=>document.querySelectorAll('.stock-event-note').length===14);
   assert.match(await page.locator('.stock-event-note').first().textContent(),/ETF／指數換股關聯：資料不足，尚無法確認/);
   const rows=await page.evaluate(()=>window.TailDashboardView.rows);
   assert.deepEqual(await page.locator('.sort-arrow').allTextContents(),['⇅','⇅','⇅']);
   await verifySort(page,mobile,rows);
   if(!mobile)await verifyHeaderHitArea(page);
   assert.equal(await page.locator('.candidate-card').count(),7);assert.equal(await page.locator('.stock-event-note').count(),14);
   checks.push({name:name+'/four-ui-updates',result:'PASS',six_sort_orders:true,keyboard:true,raw_payload_unchanged:true,hidden_section_zero_height:true});
   await context.close();
   // Valid ratios differ below display precision; ties and unverified values
   // exercise the same user controls, without changing any saved candidate JSON.
   const mixed=copy(data);
   mixed.candidate_list.forEach((r,i)=>{
    if(i===6){r.volume_status='UNVERIFIED';r.closing_auction_volume=r.intraday_total_volume=r.closing_volume_ratio_pct=null;}
    else{r.volume_status='MIS_EVIDENCE_CONFIRMED';r.closing_auction_volume=[2,10,2,2.0001,9,1][i];r.intraday_total_volume=[100,1000,100,100,90,100][i];r.closing_volume_ratio_pct=r.closing_auction_volume/r.intraday_total_volume*100;}
   });
   const sortContext=await fixtureContext(browser,options,'2026-10-08T18:30:00+08:00',mixed),sortPage=await sortContext.newPage();
   await sortPage.goto(base);await sortPage.waitForFunction(()=>document.querySelectorAll('.candidate-card').length===7);
   await verifySort(sortPage,mobile,await sortPage.evaluate(()=>window.TailDashboardView.rows));
   checks.push({name:name+'/stable-raw-missing-sort',result:'PASS',six_sort_orders:true,stable_ties:true,unverified_last:true,unrounded_ratio:true});await sortContext.close();
   const confirmedContext=await fixtureContext(browser,options);
   await confirmedContext.route('**/state/events/events-index.json?*',route=>{
    const confirmed=copy(eventsData);confirmed.generated_at='2026-10-08T18:30:00+08:00';
    const event=copy(confirmed.events[0]);event.event_id='confirmed-ui-test';event.event_name='官方測試調整';event.first_seen_at=event.information_available_as_of='2026-10-07T00:00:00+08:00';event.closing_impact_date='2026-10-08';event.event_status='CONFIRMED';event.close_date_status='CONFIRMED_CLOSE_IMPLEMENTATION';event.affected_stocks=[{code:data.candidate_list[0].code,market:data.candidate_list[0].market,market_status:'OFFICIAL_CONFIRMED',change_type:'ADDITION'}];confirmed.events=[event];
    return route.fulfill({json:confirmed});
   });
   const confirmedPage=await confirmedContext.newPage();await confirmedPage.goto(base);
   await confirmedPage.waitForFunction(()=>[...document.querySelectorAll('.stock-event-note')].some(x=>x.textContent.includes('官方測試調整 · 納入')));
   assert.equal(await confirmedPage.locator('.stock-event-note').filter({hasText:'官方測試調整 · 納入'}).count(),2);
   checks.push({name:name+'/confirmed-stock-event',result:'PASS',confirmed_label_preserved:true});await confirmedContext.close();
   for(const [eventCase,fixedDate,failure,title] of [
    ['events-source-failure','2026-10-08T18:30:00+08:00',true,'今日未發現已確認實質調整'],
    ['events-expected-close','2026-11-30T13:35:00+08:00',false,'今日有實質調整的預估收盤觀察日'],
    ['events-effective-not-close','2026-12-01T13:35:00+08:00',false,'今日未發現已確認實質調整']
   ]){
    const ctx=await fixtureContext(browser,options,fixedDate,failure?data:null,failure),p=await ctx.newPage();
    await p.goto(base);await p.locator('#event-today-title').filter({hasText:title}).waitFor();
    if(failure){await p.waitForFunction(()=>document.querySelectorAll('.candidate-card').length===7);assert.match(await p.locator('#event-note').innerText(),/股票名單仍獨立更新/);}
    assert.equal(await p.locator('button').count(),4);assert.equal(await p.locator('select').count(),1);
    assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth),true);
    checks.push({name:name+'/'+eventCase,result:'PASS'});await ctx.close();
   }
   for(const [caseName,caseDate,expected] of [
    ['market-holiday','2026-10-11T18:00:00+08:00','休市'],
    ['market-missing','2026-10-08T18:00:00+08:00','尚未確認'],
    ['market-preclose','2026-10-08T13:25:00+08:00','尚未確認']
   ]){
    const ctx=await fixtureContext(browser,options,caseDate,null),p=await ctx.newPage();await p.goto(base);
    await p.waitForFunction(expected=>document.querySelector('#market-closing-state').textContent.includes(expected),expected);assert.equal(await p.locator('.market-closing').isVisible(),false);
    assert.equal(await p.locator('button').count(),4);assert.equal(await p.locator('select').count(),1);
    assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth),true);
    await p.emulateMedia({colorScheme:'light'});assert.equal(await p.evaluate(()=>getComputedStyle(document.documentElement).colorScheme),'dark');
    checks.push({name:name+'/'+caseName,result:'PASS'});await ctx.close();
   }
   const diagnosticContext=await fixtureContext(browser,options,'2026-10-09T13:35:00+08:00',null);
   const diagnostic=await diagnosticContext.newPage(),diagnosticErrors=[];
   diagnostic.on('pageerror',error=>diagnosticErrors.push(error.message));
   await diagnostic.goto(base+'diagnostic.html');
   await diagnostic.locator('#headline').filter({hasText:'NON TRADING'}).waitFor();
   await diagnostic.emulateMedia({colorScheme:'light'});
   assert.equal(await diagnostic.evaluate(()=>getComputedStyle(document.body).backgroundColor),'rgb(13, 20, 35)');
   await diagnostic.emulateMedia({colorScheme:'dark'});
   assert.equal(await diagnostic.evaluate(()=>getComputedStyle(document.body).backgroundColor),'rgb(13, 20, 35)');
   assert.equal(await diagnostic.locator('button,input,select,form,[role="button"]').count(),0);
   assert.deepEqual(diagnosticErrors,[]);
   checks.push({name:name+'/diagnostic',result:'PASS',automatic_initial_load:true,authorized_sort_controls:true});
   await diagnosticContext.close();
   for(const [scenario,date,payload,expected] of [
    ['no-data','2026-10-08T08:00:00+08:00',null,'今日尚未產生尾盤研究資料'],
    ['holiday','2026-10-09T13:35:00+08:00',null,'今日休市'],
    ['zero','2026-10-08T18:30:00+08:00',{...copy(data),candidate_count:0,candidate_list:[]},'今日無符合 ±3% 的股票'],
    ['wrong-date','2026-10-08T18:30:00+08:00',{...copy(data),trade_date:'2026-10-07'},'資料更新失敗／尚無當日結果'],
    ['unverified-volume','2026-10-08T18:30:00+08:00',{...copy(data),candidate_list:data.candidate_list.map(r=>({...r,volume_status:'UNVERIFIED',closing_auction_volume:null,intraday_total_volume:null,closing_volume_ratio_pct:null}))},'今日 7 檔符合尾盤 ±3%']
   ]){
    const ctx=await fixtureContext(browser,options,date,payload),p=await ctx.newPage();await p.goto(base);
    await p.locator('#headline').filter({hasText:expected}).waitFor();
    if(scenario==='unverified-volume'){assert.equal(await p.locator('.candidate-card').count(),7);assert.match(await p.locator('.candidate-card').first().textContent(),/未驗證/);}
    else assert.equal(await p.locator('.candidate-card').count(),0);
    checks.push({name:name+'/'+scenario,result:'PASS'});await ctx.close();
   }
   const fundContext=await fixtureContext(browser,options,'2026-12-17T18:30:00+08:00',null),fundPage=await fundContext.newPage();
   await fundPage.goto(base);await fundPage.locator('#event-upcoming .fund-priority').first().waitFor();
   assert.match(await fundPage.locator('#event-upcoming').textContent(),/重要程度：高/);
   assert.match(await fundPage.locator('#event-upcoming').textContent(),/重要程度：中/);
   assert.match(await fundPage.locator('#event-upcoming').textContent(),/預估/);
   assert.equal(await fundPage.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth),true);
   checks.push({name:name+'/per-fund-priority',result:'PASS',date_confidence_independent:true});
   await fundPage.goto(base+'fund-events.html');await fundPage.locator('#funds article').first().waitFor();
   assert.equal(await fundPage.locator('#funds article').count(),fundsData.fund_events.length);
   assert.equal(await fundPage.locator('button,input,select,form,[role="button"]').count(),0);
   await fundPage.emulateMedia({colorScheme:'light'});assert.equal(await fundPage.evaluate(()=>getComputedStyle(document.body).backgroundColor),'rgb(11, 16, 26)');
   assert.equal(await fundPage.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth),true);
   await fundPage.screenshot({path:path.join(OUT,'funds-'+name+'.png'),fullPage:false});
   checks.push({name:name+'/fund-readonly-page',result:'PASS',all_priorities_visible:true});await fundContext.close();
   if(process.env.SKIP_PUBLIC==='true')continue;
   // Public smoke uses the real Taipei day, normal anonymous HTTP and no routes.
   // Future runs do not expect yesterday's October 8 candidates as today's list.
   const publicContext=await browser.newContext({...options,timezoneId:'Asia/Taipei'}),publicPage=await publicContext.newPage();
   await publicPage.goto(PUBLIC);await publicPage.waitForFunction(()=>!document.querySelector('#today').textContent.includes('讀取'));
   if(process.env.REQUIRE_PUBLIC_UI==='true'||process.env.REQUIRE_PUBLIC_EVENTS==='true'){
    for(let attempt=0;attempt<24;attempt++){
     if(await publicPage.locator('script[src="status.js?v=dashboard2&sort=1"]').count())break;
     await publicPage.waitForTimeout(5000);await publicPage.reload();
    }
    assert.equal(await publicPage.locator('script[src="status.js?v=dashboard2&sort=1"]').count(),1);
    assert.equal(await publicPage.locator('.market-closing').isVisible(),false);
    await publicPage.waitForFunction(()=>window.TailDashboardView&&window.TailDashboardView.state);
    const liveRows=await publicPage.evaluate(()=>window.TailDashboardView.rows);
    if(liveRows.length){await verifySort(publicPage,mobile,liveRows);if(!mobile)await verifyHeaderHitArea(publicPage);assert.ok((await publicPage.locator('.candidate-card .tail').allTextContents()).every(x=>/^[+-]\d+\.\d{2}%$/.test(x)));}
    checks.push({name:'public/'+name+'/four-ui-updates',result:'PASS',live_candidate_count:liveRows.length,hidden_section:true,six_sort_orders:liveRows.length>0});
   }
   await publicPage.emulateMedia({colorScheme:'light'});
   assert.equal(await publicPage.evaluate(()=>getComputedStyle(document.documentElement).backgroundColor),'rgb(13, 20, 35)');
   await publicPage.emulateMedia({colorScheme:'dark'});
   assert.equal(await publicPage.evaluate(()=>getComputedStyle(document.documentElement).backgroundColor),'rgb(13, 20, 35)');
   assert.equal(await publicPage.title(),'台股尾盤 ±3% 自動選股看板');
   assert.equal(await publicPage.locator('input,form,[role="button"]').count(),0);
   if(process.env.REQUIRE_PUBLIC_EVENTS==='true'){
    await publicPage.waitForFunction(()=>document.querySelector('#event-empty').textContent.includes('尚無已確認')||document.querySelectorAll('#event-upcoming .event-row').length>0);
    assert.ok(await publicPage.locator('#event-today-title').count());
    assert.ok(await publicPage.locator('#event-upcoming').count()>0);
    assert.notEqual(await publicPage.locator('#event-today-title').innerText(),'事件資料確認中');
    assert.equal(await publicPage.locator('#market-closing-state').count(),1);
    const marketState=await publicPage.locator('#market-closing-state').innerText();assert.ok(['有','沒有','尚未確認','休市'].includes(marketState));
    for(const path of ['state/events/events-index.json','state/events/fund-events.json','state/market-closing-volume/2026-10-08.json']){
     const response=await publicContext.request.get('https://raw.githubusercontent.com/gxaawill2-ui/tw-close-auction-mis-probe/main/'+path+'?acceptance='+Date.now());assert.equal(response.status(),200);assert.ok(await response.json());
    }
   }
   assert.equal(await publicPage.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth),true);
   const date=await publicPage.locator('#today').textContent();
   if(date.includes('2026-10-08'))assert.equal(await publicPage.locator('#candidate-count').textContent(),'7');
   if(date.includes('2026-10-09')){
    await publicPage.locator('#headline').filter({hasText:'今日休市'}).waitFor();
    assert.equal(await publicPage.locator('.candidate-card').count(),0);
   }
   await publicPage.screenshot({path:path.join(OUT,'public-'+name+'.png'),fullPage:true});
   checks.push({name:'public/'+name,result:'PASS',date,authorized_sort_controls:true,no_horizontal_overflow:true,url:publicPage.url()});
   await publicContext.close();
  }finally{await browser.close();}
 }
 fs.writeFileSync(path.join(OUT,'acceptance.json'),JSON.stringify({verified_at:new Date().toISOString(),commit_sha:process.env.GITHUB_SHA,checks},null,2));
 console.log(JSON.stringify({result:'PASS',checks:checks.length},null,2));
}
main().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>server.close());
