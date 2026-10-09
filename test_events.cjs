const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {parseHTML}=require('linkedom'),ui=require('./docs/events.js');
const now=new Date('2026-10-09T12:00:00+08:00'),seen='2026-10-09T10:00:00+08:00';
const copy=x=>JSON.parse(JSON.stringify(x));
const event={event_id:'e1',index_name:'MSCI Taiwan',event_name:'MSCI 定審',source_url:'https://www.msci.com/official.pdf',
 close_date_status:'EXPECTED_CLOSE_WATCH_DATE',event_status:'SCHEDULE_ONLY',announcement_date:'2026-11-11',effective_date:'2026-12-01',closing_impact_date:'2026-11-30',
 first_seen_at:seen,information_available_as_of:seen,affected_stocks:[],related_etf_codes:[]};
const data={schema_version:1,timezone:'Asia/Taipei',generated_at:seen,coverage_status:'PARTIAL',events:[event]};
const health={last_successful_scan_at:seen,sources:[{status:'SUCCESS'}]};
const dom=()=>parseHTML(fs.readFileSync('docs/index.html','utf8')).document;
test('unknown or partial source coverage never means no events',()=>{
 assert.equal(ui.model(now,null,null).headline,'事件資料尚未完整確認');
 assert.equal(ui.model(now,data,health).headline,'事件資料尚未完整確認');
 const complete={...data,coverage_status:'COMPLETE'};
 assert.equal(ui.model(now,complete,health).headline,'今日無已確認的重大指數調整事件');
});
test('stale, timeout, malformed and future snapshots fail closed',()=>{
 const stale={...health,last_successful_scan_at:'2026-10-01T08:20:00+08:00'};
 assert.equal(ui.model(now,{...data,coverage_status:'COMPLETE'},stale).incomplete,true);
 assert.equal(ui.model(now,data,health,'timeout').incomplete,true);
 const future={...data,generated_at:'2026-12-01T00:00:00Z'};
 assert.match(ui.model(now,future,health).error,/時間/);
 assert.match(ui.model(now,{...data,events:[event,event]},health).error,/證據/);
});
test('announcement, implementation and effective dates distinct',()=>{
 for(const [day,type] of [['2026-11-11','announcement_date'],['2026-11-30','closing_impact_date'],['2026-12-01','effective_date']]){
  const v=ui.model(new Date(day+'T12:00:00+08:00'),data,health);
  assert.equal(v.today[0].type,type);
  if(type==='closing_impact_date')assert.match(v.headline,/預估/);
  else assert.match(v.headline,/收盤集中交易未確認/);
 }
});
test('known explicit close is distinguishable from expected observation',()=>{
 const d=copy(data);d.events[0].closing_impact_date='2026-10-09';d.events[0].close_date_status='CONFIRMED_CLOSE_IMPLEMENTATION';
 assert.match(ui.model(now,d,health).headline,/官方確認/);
 const doc=dom();ui.render(doc,ui.model(now,d,health));
 assert.match(doc.getElementById('event-today-list').textContent,/官方確認收盤實施/);
});
test('thirty-day calendar sorted, with explicit out-of-range fallback',()=>{
 const v=ui.model(now,data,health);assert.match(v.range,/30 天以外/);assert.equal(v.upcoming[0].date,'2026-11-11');
 const d=copy(data);d.events.push({...event,event_id:'e2',announcement_date:'2026-10-20',closing_impact_date:null,effective_date:'2026-10-21'});
 const w=ui.model(now,d,health);assert.equal(w.range,'未來 30 天');assert.equal(w.upcoming[0].date,'2026-10-20');
});
test('multi-day ETF window retained rather than all at one close',()=>{
 const d=copy(data);d.events[0].implementation_window={dates:['2026-10-09','2026-10-12','2026-10-13']};
 assert.equal(ui.model(now,d,health).today[0].type,'implementation_window');
 assert.match(ui.model(now,d,health).headline,/過渡期間/);
});
test('only official exact code AND market matches permit a stock label',()=>{
 const e={...event,closing_impact_date:'2026-11-30',affected_stocks:[{code:'2330',market:'TWSE',market_status:'OFFICIAL_CONFIRMED',change_type:'ADDITION'}]};
 assert.equal(ui.relation({code:'2330',market:'TWSE'},[e],'2026-11-30','2026-11-30T13:35:00+08:00').matches.length,1);
 assert.equal(ui.relation({code:'2330',market:'TPEx'},[e],'2026-11-30','2026-11-30T13:35:00+08:00').matches.length,0);
 assert.match(ui.relation({code:'3073',market:'TPEx'},[e],'2026-11-30','2026-11-30T13:35:00+08:00').label,/個股關聯未確認/);
});
test('later first-seen information never claims a pre-close relationship',()=>{
 const e={...event,information_available_as_of:'2026-11-30T17:00:00+08:00'};
 assert.equal(ui.relation({code:'2330',market:'TWSE'},[e],'2026-11-30','2026-11-30T13:35:00+08:00').matches.length,0);
});
test('DOM keeps dark-only, no controls, escaped links and updates without flicker',()=>{
 const doc=dom(),v=ui.model(now,data,health);ui.render(doc,v);const first=doc.querySelector('.event-row');ui.render(doc,v);
 assert.equal(doc.querySelector('.event-row'),first);
 assert.equal(doc.querySelectorAll('button,input,select,form,[role="button"]').length,0);
 assert.equal(doc.querySelector('meta[name="color-scheme"]').getAttribute('content'),'dark');
 assert.equal(doc.querySelector('.event-description a').getAttribute('rel'),'noopener noreferrer');
 assert.ok(doc.querySelector('#event-today-title'));assert.ok(doc.querySelector('#event-upcoming'));
});
test('source errors leave the event-independent stock UI intact',()=>{
 const stock=require('./docs/status.js'),doc=dom();
 const cal=JSON.parse(fs.readFileSync('state/calendars/2026.json')),payload=JSON.parse(fs.readFileSync('state/candidates/2026-10-08.json'));
 stock.render(doc,stock.model(new Date('2026-10-08T18:00:00+08:00'),{calendar:cal,data:payload}));
 ui.render(doc,ui.model(now,null,null,'HTTP 503'));
 assert.equal(doc.querySelectorAll('.candidate-card').length,7);
 assert.match(doc.getElementById('event-note').textContent,/股票名單仍獨立更新/);
});
test('conflicting dates cannot appear as confirmed calendar or stock relationships',()=>{
 const conflict={...event,event_status:'CONFLICT',closing_impact_date:'2026-10-09',affected_stocks:[{code:'2330',market:'TWSE',market_status:'OFFICIAL_CONFIRMED',change_type:'ADDITION'}]};
 const v=ui.model(now,{...data,events:[conflict]},health);
 assert.equal(v.today.length,0);assert.equal(v.upcoming.length,0);assert.match(v.note,/來源日期衝突/);
 assert.equal(ui.relation({code:'2330',market:'TWSE'},[conflict],'2026-10-09',now.toISOString()).matches.length,0);
});
test('expected multiday status supported without upgrading to official close',()=>{
 const multi={...event,closing_impact_date:null,close_date_status:'EXPECTED_MULTIDAY_TRANSITION',implementation_window:{dates:['2026-10-09','2026-10-12']}};
 const v=ui.model(now,{...data,events:[multi]},health),doc=dom();ui.render(doc,v);
 assert.match(v.headline,/預估/);assert.match(doc.getElementById('event-today-list').textContent,/預估/);
 assert.doesNotMatch(doc.getElementById('event-today-list').textContent,/官方確認收盤實施/);
});
