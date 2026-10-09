const test=require('node:test');
const assert=require('node:assert/strict');
const s=require('./docs/diagnostic.js');
const calendar={year:2026,closed_dates:['2026-10-09']};
const now=new Date('2026-10-05T06:08:00Z');
test('Taipei date uses +08 even when execution clock is UTC',()=>{
 assert.equal(s.taipei(new Date('2026-10-04T16:01:00Z')).date,'2026-10-05');
});
test('October 2 success cannot mask October 5 no run',()=>{
 const v=s.model(now,{calendar,live:{trade_date:'2026-10-02',status:'success_raw_capture'}});
 assert.equal(v.status,'NOT RUN');assert.equal(v.live,null);assert.equal(v.isTradingDay,true);
 assert.ok(v.references.every(r=>r.status==='NOT_SAMPLED'));
});
test('Dry-run success and declaration of cron source cannot certify external cron',()=>{
 const v=s.model(now,{calendar,dry:{status:'dry_run_success'},external:{configured:true,status:'VERIFIED'},execution:{declared_source:'cron-job.org'}});
 assert.equal(v.status,'NOT RUN');assert.equal(v.externalConfigured,false);
});
test('Persisted blocked missing day stays NOT RUN',()=>{
 const v=s.model(now,{calendar,live:{trade_date:'2026-10-05',status:'missing_incomplete',capture_blocked:true,reason:'scheduler did not trigger'}});
 assert.equal(v.status,'NOT RUN');assert.equal(v.reason,'scheduler did not trigger');
 assert.equal(v.dual.both_converged_count,undefined);
});
test('Official annual holidays avoid assuming every weekday trades',()=>{
 assert.equal(s.tradingDay('2026-10-09',calendar),false);
 assert.equal(s.tradingDay('2026-10-06',calendar),true);
 assert.equal(s.tradingDay('2027-01-04',calendar),null);
});
test('No stale annual year or previous today fallback',()=>{
 assert.equal(s.tradingDay('2027-01-04',calendar,{today:'2026-10-05',is_trading_day:true}),null);
});
test('Incomplete convergence is PARTIAL, PENDING official alone is not a failure',()=>{
 const live={trade_date:'2026-10-05',status:'success_raw_capture',universe_count:1970,convergence:{both_converged_count:1960},official_validation:'PENDING'};
 assert.equal(s.model(now,{calendar,live}).status,'PARTIAL');
 live.convergence.both_converged_count=1970;
 assert.equal(s.model(now,{calendar,live}).status,'SUCCESS');
});
test('Page independently detects unfinished execution after 13:40',()=>{
 assert.equal(s.model(now,{calendar,live:{trade_date:'2026-10-05',status:'running'}}).status,'FAILED');
 assert.equal(s.model(new Date('2026-10-05T05:00:00Z'),{calendar,live:{trade_date:'2026-10-05',status:'running'}}).status,'RUNNING');
});
test('Explicit capture outcome is separate from official PENDING and research counts',()=>{
 const live={trade_date:'2026-10-05',status:'partial',capture_outcome:'CAPTURE_PARTIAL',official_validation:'PENDING'};
 assert.equal(s.model(now,{calendar,live}).status,'PARTIAL');
 live.capture_outcome='CAPTURE_SUCCESS';assert.equal(s.model(now,{calendar,live}).status,'SUCCESS');
 live.capture_outcome='CAPTURE_FAILED';assert.equal(s.model(now,{calendar,live}).status,'FAILED');
});
test('diagnostic opens and refreshes automatically without manual controls',async()=>{
 const fs=require('node:fs'),vm=require('node:vm'),{parseHTML}=require('linkedom');
 const {document}=parseHTML(fs.readFileSync('docs/diagnostic.html','utf8'));
 assert.equal(document.querySelectorAll('button,input,select,form,[role="button"]').length,0);
 let requests=0,interval;
 const fixtures={
  'state/calendars/2026.json':calendar,
  'state/calendar_latest.json':{today:'2026-10-09',is_trading_day:false},
  'state/external_scheduler.json':{},
 };
 const RealDate=Date;
 class Clock extends RealDate{constructor(...args){super(...(args.length?args:['2026-10-09T13:35:00+08:00']));}static now(){return new RealDate('2026-10-09T13:35:00+08:00').getTime();}}
 const context={document,Date:Clock,Intl,AbortController,setTimeout,clearTimeout,
  setInterval:(callback,ms)=>{assert.equal(ms,60000);interval=callback;},
  fetch:async(url,options)=>{
   requests++;assert.equal(options.cache,'no-store');
   const path=new URL(url).pathname.split('/main/')[1];
   return {status:path in fixtures?200:404,ok:path in fixtures,json:async()=>fixtures[path]};
  }};
 vm.runInNewContext(fs.readFileSync('docs/diagnostic.js','utf8'),context);
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(requests,7);assert.equal(document.getElementById('headline').textContent,'NON TRADING');
 await interval();assert.equal(requests,14);
 assert.equal(document.getElementById('headline').textContent,'NON TRADING');
 assert.equal(document.getElementById('network').textContent,'');
});
