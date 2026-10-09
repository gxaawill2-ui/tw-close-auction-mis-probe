const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {parseHTML}=require('linkedom'),ui=require('./docs/status.js');
const today=new Date('2026-10-08T18:30:00+08:00');
const payload=JSON.parse(fs.readFileSync('state/candidates/2026-10-08.json','utf8'));
const calendar=JSON.parse(fs.readFileSync('state/calendars/2026.json','utf8'));
const copy=x=>JSON.parse(JSON.stringify(x));
const model=(data=payload,extras={})=>ui.model(today,{calendar,data,...extras});
const dom=()=>parseHTML(fs.readFileSync('docs/index.html','utf8')).document;

test('Taipei date and polling automatically follow actual day and close window',()=>{
 assert.equal(ui.taipei(new Date('2026-10-07T17:00:00Z')).date,'2026-10-08');
 assert.equal(ui.polling(new Date('2026-10-08T13:34:00+08:00')),20000);
 assert.equal(ui.polling(today),60000);
});
test('before open without data is not a zero-candidate success',()=>{
 const view=ui.model(new Date('2026-10-08T08:00:00+08:00'),{calendar});
 assert.equal(view.state,'BEFORE_OPEN');assert.equal(view.data,null);
});
test('running capture, pending publication and genuine capture failure stay distinct',()=>{
 assert.equal(model(null,{live:{trade_date:'2026-10-08',status:'running'}}).state,'CAPTURING');
 assert.equal(model(null,{live:{trade_date:'2026-10-08',capture_outcome:'CAPTURE_SUCCESS'}}).state,'PUBLISHING_DELAY');
 assert.equal(model(null,{live:{trade_date:'2026-10-08',capture_outcome:'CAPTURE_FAILED'}}).state,'CAPTURE_FAILED');
});
test('zero candidates requires a completed same-day publication',()=>{
 const zero=copy(payload);zero.candidate_list=[];zero.candidate_count=0;zero.coverage={tradable_universe:1968,research_calculable:1968,unknown:0};zero.completion_status='COMPLETE';
 const view=model(zero);assert.equal(view.state,'ZERO_CANDIDATES');assert.equal(view.headline,'今日無符合 ±3% 的股票');
 assert.notEqual(model(null).state,'ZERO_CANDIDATES');
});
test('partial seven-candidate coverage is explicit and absolute-return sorted',()=>{
 const view=model();assert.equal(view.state,'PARTIAL');assert.equal(view.data.coverage.unknown,25);
 assert.deepEqual(view.rows.map(r=>r.code),['3259','2024','3073','4706','3684','5543','5355']);
});
test('wrong date, yesterday and future generation cannot appear as today',()=>{
 const old=copy(payload);old.trade_date='2026-10-07';assert.equal(model(old).state,'UPDATE_FAILED');assert.equal(model(old).rows.length,0);
 const future=copy(payload);future.generated_at='2026-10-08T23:00:00+08:00';assert.equal(model(future).state,'UPDATE_FAILED');
});
test('official-calendar holiday hides any stale stock list',()=>{
 const view=ui.model(new Date('2026-10-09T13:35:00+08:00'),{calendar,data:payload});
 assert.equal(view.state,'CLOSED');assert.equal(view.headline,'今日休市');assert.equal(view.rows.length,0);
 assert.equal(ui.tradingDay('2026-10-12',calendar),true);
});
test('network failure retains only verified current-day loaded data with warning',()=>{
 const view=model(payload,{error:'HTTP 503'});assert.equal(view.rows.length,7);assert.equal(view.error,'HTTP 503');
 assert.equal(model(null,{error:'HTTP 503'}).state,'UPDATE_FAILED');
 const doc=dom();ui.render(doc,view);assert.match(doc.getElementById('network').textContent,/資料更新失敗/);
});
test('invalid candidate count, unknown close and below-threshold stock fail closed',()=>{
 for(const type of ['count','unknown','threshold']){
  const data=copy(payload);
  if(type==='count')data.candidate_count=8;
  if(type==='unknown')data.candidate_list[0].P_close_convergence_type='unresolved';
  if(type==='threshold')data.candidate_list[0].tail_return_pct='2';
  assert.equal(model(data).state,'UPDATE_FAILED');assert.equal(model(data).rows.length,0);
 }
});
test('volume conversion display retains precision and comma separators',()=>{
 assert.equal(ui.number('15280',3),'15,280');assert.equal(ui.number('1.501',3),'1.501');assert.equal(ui.number(null),'—');
});
test('volume disagreement rejects verified data; unverified null does not block prices',()=>{
 const bad=copy(payload);bad.candidate_list[0].closing_volume_ratio_pct='88';assert.equal(model(bad).state,'UPDATE_FAILED');
 const data=copy(payload),r=data.candidate_list[0];r.volume_status='UNVERIFIED';r.closing_auction_volume=r.intraday_total_volume=r.closing_volume_ratio_pct=null;
 const doc=dom();ui.render(doc,model(data));const card=doc.querySelector('[data-code="'+r.code+'"]');
 assert.match(card.textContent,/未驗證/);assert.match(card.textContent,/—/);assert.equal(doc.querySelectorAll('.candidate-card').length,7);
});
test('real homepage DOM displays all seven, three delayed and four normal closes',()=>{
 const doc=dom();ui.render(doc,model());
 assert.equal(doc.title,'台股尾盤 ±3% 自動選股看板');
 assert.equal(doc.querySelectorAll('.candidate-card').length,7);assert.equal(doc.querySelectorAll('#desktop-list tr').length,7);
 for(const code of ['3073','3259','3684'])assert.match(doc.querySelector('[data-code="'+code+'"]').textContent,/13:33:00延後收盤/);
 for(const code of ['4706','5355','5543','2024'])assert.match(doc.querySelector('[data-code="'+code+'"]').textContent,/13:30:00/);
 assert.equal(doc.querySelectorAll('.candidate-card .tail.up').length,4);assert.equal(doc.querySelectorAll('.candidate-card .tail.down').length,3);
 assert.match(doc.getElementById('unknown').textContent,/25/);assert.match(doc.querySelector('[data-code="3259"]').textContent,/BC/);
});
test('homepage has no buttons, forms, date selectors, login or manual control',()=>{
 const doc=dom();ui.render(doc,model());assert.equal(doc.querySelectorAll('button,input,select,form,[role="button"]').length,0);
 assert.equal(doc.querySelectorAll('a').length,1);assert.equal(doc.querySelector('a').getAttribute('href'),'diagnostic.html');
});
test('render unchanged list keeps DOM nodes and avoids refresh flicker',()=>{
 const doc=dom();ui.render(doc,model());const node=doc.querySelector('.candidate-card');ui.render(doc,model());assert.equal(doc.querySelector('.candidate-card'),node);
});
test('mobile card CSS avoids horizontal tables and supports Safari viewport',()=>{
 const css=fs.readFileSync('docs/status.css','utf8'),doc=dom();
 assert.match(css,/@media\(max-width:900px\)/);assert.match(css,/\.desktop-wrap\{display:none\}/);
 assert.match(css,/grid-template-columns:repeat\(3,minmax\(0,1fr\)\)/);
 assert.match(doc.querySelector('meta[name="viewport"]').getAttribute('content'),/width=device-width/);
});
test('postmarket price match is separate from MIS volume and research qualification',()=>{
 const doc=dom();ui.render(doc,model());
 assert.match(doc.querySelector('[data-code="3259"]').textContent,/收盤價一致/);
 assert.match(doc.querySelector('[data-code="3259"]').textContent,/成交量：MIS 證據一致/);
 assert.match(doc.querySelector('[data-code="3259"]').textContent,/RESEARCH_ONLY/);
});


test('permanent dark appearance on every device, regardless of preference',()=>{
 const css=fs.readFileSync('docs/status.css','utf8'),diagnostic=fs.readFileSync('docs/diagnostic.css','utf8'),doc=dom();
 const diagnosticHtml=fs.readFileSync('docs/diagnostic.html','utf8');
 assert.doesNotMatch(css,/prefers-color-scheme/);
 assert.match(css,/color-scheme:dark/);
 assert.match(css,/background:\s*#0d1423/);
 assert.match(css,/\.overview, \.desktop-wrap, \.candidate-card, \.empty/);
 assert.match(css,/--red:\s*#ff788a/);
 assert.match(css,/--green:\s*#53dcb7/);
 assert.equal(doc.querySelector('meta[name="color-scheme"]').getAttribute('content'),'dark');
 assert.equal(doc.querySelectorAll('meta[name="theme-color"]').length,1);
 assert.equal(doc.querySelector('meta[name="theme-color"]').getAttribute('content'),'#0d1423');
 assert.equal(doc.querySelectorAll('button,input,select,form,[role="button"]').length,0);
 assert.match(diagnostic,/:root\{[^}]*color-scheme:dark/);
 assert.match(diagnostic,/background:#0d1423;color:#e8f0fc/);
 assert.doesNotMatch(diagnostic,/light-dark\(|prefers-color-scheme/);
 assert.match(diagnosticHtml,/<meta name="color-scheme" content="dark">/);
});
