(function(root){
 'use strict';
 const RAW='https://raw.githubusercontent.com/gxaawill2-ui/tw-close-auction-mis-probe/main/';
 const priorities={HIGH:'高',MEDIUM:'中',LOW:'低',DATA_INSUFFICIENT:'資料不足'};
 const label={announcement_date:'公告',effective_date:'生效',closing_impact_date:'收盤觀察',implementation_window:'過渡期間'};
 const statuses={CONFIRMED_CLOSE_IMPLEMENTATION:'官方確認收盤實施',EXPECTED_CLOSE_WATCH_DATE:'預估觀察日',EXPECTED_MULTIDAY_TRANSITION:'預估多日換股期間',DATE_UNVERIFIED:'收盤日未確認'};
 const esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function taipei(now){return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(now);}
 function valid(data,now){
  if(!data||data.schema_version!==1||data.timezone!=='Asia/Taipei'||!Array.isArray(data.events))throw new Error('事件資料格式未確認');
  if(!Number.isFinite(Date.parse(data.generated_at))||Date.parse(data.generated_at)>now.getTime())throw new Error('事件資料時間不符');
  const ids=new Set();
  for(const e of data.events){
   if(!e.event_id||ids.has(e.event_id)||!e.index_name||!e.event_name||!/^https:\/\//.test(e.source_url)||!statuses[e.close_date_status]||!Array.isArray(e.affected_stocks)||!Array.isArray(e.related_etf_codes))throw new Error('事件證據不完整');
   ids.add(e.event_id);
   for(const key of Object.keys(label).filter(x=>x!=='implementation_window'))if(e[key]&&!/^20\d\d-\d\d-\d\d$/.test(e[key]))throw new Error('事件日期錯誤');
   if(!Number.isFinite(Date.parse(e.first_seen_at))||!Number.isFinite(Date.parse(e.information_available_as_of)))throw new Error('事件首次得知時間未確認');
  }
  return data;
 }
 function materialInfo(e,now){
  if(!Number.isFinite(Date.parse(e.information_available_as_of))||Date.parse(e.information_available_as_of)>now.getTime())return null;
  const stocks=(e.affected_stocks||[]).filter(s=>['ADDITION','DELETION','WEIGHT_CHANGE'].includes(s.change_type));
  if(e.constituent_details_status==='OFFICIAL_LIST'&&stocks.length)return '官方成分異動 '+stocks.length+' 檔';
  const c=e.constituent_counts;
  if(e.evidence_level==='OFFICIAL_ISSUER_DATE_ONLY'&&c&&Number.isInteger(c.additions)&&Number.isInteger(c.deletions)&&c.additions>=0&&c.deletions>=0&&c.additions+c.deletions>0)return '官方新增 '+c.additions+' 檔／刪除 '+c.deletions+' 檔（未公布逐檔名單）';
  const m=e.material_change_evidence;
  if(m?.status==='OFFICIAL_CONFIRMED'&&['ADDITION','DELETION','WEIGHT_CHANGE','NONROUTINE_CHANGE'].includes(m.change_type)&&m.summary&&m.source_url===e.source_url&&Date.parse(m.observed_at)<=now.getTime())return m.summary;
  return null;
 }
 function model(now,data,health,error='',fundData=null){
  let events=[];try{if(data)events=valid(data,now).events;}catch(e){error=e.message;}
  events=events.map(e=>({...e,material_summary:materialInfo(e,now),fund_events:e.related_etf_codes.map(code=>(fundData?.fund_events||[]).find(r=>r.event_id===e.event_id&&r.fund_code===code&&Date.parse(r.information_available_as_of)<=now.getTime())||{fund_code:code,importance_level:'DATA_INSUFFICIENT'})}));
  const day=taipei(now),limit=new Date(day+'T12:00:00Z');limit.setUTCDate(limit.getUTCDate()+30);
  const end=limit.toISOString().slice(0,10),entries=[];
  for(const event of events){
   if(!event.material_summary||Date.parse(event.first_seen_at)>now.getTime()||event.event_status==='CONFLICT'||event.close_date_status==='DATE_UNVERIFIED')continue;
   const dates=(event.implementation_window||{}).dates||[];
   if(event.closing_impact_date&&!dates.includes(event.closing_impact_date))entries.push({date:event.closing_impact_date,type:'closing_impact_date',event});
   for(const d of [...new Set(dates)])entries.push({date:d,type:'implementation_window',event});
  }
  entries.sort((a,b)=>a.date.localeCompare(b.date)||a.event.event_name.localeCompare(b.event.event_name));
  const today=entries.filter(x=>x.date===day);
  const sourceStale=!health||!Number.isFinite(Date.parse(health.last_successful_scan_at))||now.getTime()-Date.parse(health.last_successful_scan_at)>36*3600*1000;
  const incomplete=Boolean(error||sourceStale||data?.coverage_status!=='COMPLETE'||health?.sources?.some(s=>s.status!=='SUCCESS'));
  const headline=today.length?(today.some(x=>x.event.close_date_status==='CONFIRMED_CLOSE_IMPLEMENTATION')?'今日有官方確認的指數實質調整（基金交易時間未確認）':'今日有實質調整的預估收盤觀察日／過渡期間'):'今日未發現已確認實質調整的收盤觀察日';
  let upcoming=entries.filter(x=>x.date>day&&x.date<=end),range='未來 30 天 · 實質調整';
  if(!upcoming.length){const next=entries.find(x=>x.date>day);if(next){upcoming=entries.filter(x=>x.date===next.date);range='30 天以外 · 下一個實質調整日';}}
  const conflicts=events.filter(e=>e.event_status==='CONFLICT'&&Date.parse(e.information_available_as_of)<=now.getTime()).length;
  return {day,today,headline,upcoming,range,error,incomplete,sourceStale,
   note:(incomplete?'部分官方來源未能完整取得，調整事件可能有缺漏。':'已完成已設定官方來源掃描。')+(conflicts?' '+conflicts+' 筆來源日期衝突，暫不列入。':'')+' 最後資料確認：'+(data?.generated_at||'尚未取得')};
 }
 function fundLabels(rows){
  return rows.slice().sort((a,b)=>({HIGH:0,MEDIUM:1,LOW:2,DATA_INSUFFICIENT:3}[a.importance_level]??3)-({HIGH:0,MEDIUM:1,LOW:2,DATA_INSUFFICIENT:3}[b.importance_level]??3)||a.fund_code.localeCompare(b.fund_code)).map(r=>'<div class="fund-priority">'+esc(r.fund_code+(r.fund_name?' '+r.fund_name:''))+' · 重要程度：'+esc(priorities[r.importance_level]||'資料不足')+(r.importance_confidence==='PROVISIONAL'?'（暫定）':'')+'</div>').join('');
 }
 function htmlEntry(x){
  const e=x.event,expected=e.event_status==='EXPECTED'||['closing_impact_date','implementation_window'].includes(x.type)&&e.close_date_status!=='CONFIRMED_CLOSE_IMPLEMENTATION';
  const type=x.type==='announcement_date'&&e.announcement_timezone==='SOURCE_DATE_TIME_UNPUBLISHED'?'公告 · 來源日期（台北時間待確認）':label[x.type];
  return '<li class="event-row"><div class="event-date">'+esc(x.date)+'<small>'+esc(type)+'</small></div><div class="event-description"><strong>'+esc(e.event_name)+'</strong><div>'+esc(e.related_etf_codes.length?'ETF '+e.related_etf_codes.join('、'):e.index_name)+'</div>'+fundLabels(e.fund_events||[])+'<p class="event-note">'+esc(e.material_summary||'')+'；指數實施不等於基金實際下單。</p><span class="event-tag'+(expected?' expected':'')+'">'+esc(expected?(x.type==='implementation_window'?'預估多日換股期間 · 依官方規則／交易日推算':'預估 · 依官方規則／交易日推算'):x.type==='closing_impact_date'?statuses[e.close_date_status]:'官方日期 · 收盤實施另確認')+'</span><a href="'+esc(e.source_url)+'" target="_blank" rel="noopener noreferrer">官方來源</a></div></li>';
 }
 function grouped(rows){
  const groups=new Map();
  for(const x of rows){const e=x.event,key=x.date+':'+x.type+':'+e.source_organization+':'+e.source_url+':'+e.close_date_status;
   if(!groups.has(key))groups.set(key,[]);groups.get(key).push(x);}
  return [...groups.values()].map(items=>{
   if(items.length===1)return htmlEntry(items[0]);
   const x=items[0],e=x.event,etfs=[...new Set(items.flatMap(v=>v.event.related_etf_codes))];
   const entry={...x,event:{...e,event_name:e.source_organization+' 指數定審 · '+items.length+' 項',related_etf_codes:etfs,
     fund_events:items.flatMap(v=>v.event.fund_events||[]),material_summary:[...new Set(items.map(v=>v.event.index_name+'：'+v.event.material_summary))].join('；'),index_name:items.map(v=>v.event.index_name.replace(/^臺灣指數公司/,'')).join('；')}};
   return htmlEntry(entry);
  }).join('');
 }
 function render(doc,view){
  const set=(id,text)=>{doc.getElementById(id).textContent=text;};
  set('event-today-title',view.headline);set('event-note',view.error?'事件資料更新失敗；股票名單仍獨立更新。 '+view.note:view.note);
  set('event-range',view.range);set('event-empty',view.upcoming.length?'':'目前尚無已確認實質調整的收盤觀察日');
  for(const [id,rows] of [['event-today-list',view.today],['event-upcoming',view.upcoming]]){
   const element=doc.getElementById(id),html=grouped(rows);if(element.dataset.rendered!==html){element.innerHTML=html;element.dataset.rendered=html;}
  }
 }
 function relation(row,events,day,asOf){
  const cutoff=Date.parse(asOf),dayEvents=events.filter(e=>e.event_status!=='CONFLICT'&&Date.parse(e.information_available_as_of)<=cutoff&&
   (e.closing_impact_date===day||(e.implementation_window?.dates||[]).includes(day)));
  const matches=[];
  for(const e of dayEvents)for(const s of e.affected_stocks)if(s.code===row.code&&s.market===row.market&&s.market_status==='OFFICIAL_CONFIRMED')matches.push({event:e,stock:s});
  return {matches,label:matches.length?matches.map(x=>x.event.event_name+' · '+({ADDITION:'納入',DELETION:'刪除',WEIGHT_CHANGE:'權重調整'}[x.stock.change_type]||'官方異動')).join('；'):
    dayEvents.length?'當日有指數調整事件，個股關聯未確認':'個股事件關聯未確認'};
 }
 const api={valid,materialInfo,model,render,relation,taipei,fundLabels};
 if(typeof module!=='undefined'&&module.exports){module.exports=api;return;}
 root.IndexEvents=api;
 let lastGood=null,lastHealth=null,lastFunds=null,running=false;
 async function read(name){const c=new AbortController(),timer=setTimeout(()=>c.abort(),12000);try{
  const r=await fetch(RAW+'state/events/'+name+'?v='+Math.floor(Date.now()/300000),{cache:'no-store',signal:c.signal});
  if(!r.ok)throw new Error('HTTP '+r.status);return await r.json();
 }finally{clearTimeout(timer);}}
 function annotate(){
  const dashboard=root.TailDashboardView;if(!dashboard?.data||!lastGood)return;
  for(const row of dashboard.rows){
   const info=relation(row,lastGood.events,dashboard.today,new Date().toISOString());
   // Addendum only; never alters values, validation or sorting in stock rows.
   const targets=[document.querySelector('.candidate-card[data-code="'+row.code+'"]'),document.querySelector('#desktop-list tr[data-code="'+row.code+'"] td:first-child')];
   for(const target of targets){if(!target)continue;let node=target.querySelector('.stock-event-note');if(!node){node=document.createElement('p');node.className='stock-event-note';target.appendChild(node);}
    const text=info.label+'（事件資料截至 '+taipei(new Date(lastGood.generated_at))+'）';if(node.textContent!==text)node.textContent=text;
   }
  }
 }
 document.addEventListener('tail-dashboard-updated',annotate);
 async function refresh(){if(running)return;running=true;let error='';const now=new Date();
  try{const [data,health,funds]=await Promise.all([read('events-index.json'),read('source-health.json'),read('fund-events.json').catch(()=>null)]);valid(data,now);lastGood=data;lastHealth=health;lastFunds=funds;}catch(e){error=e.message;}
  finally{render(document,model(now,lastGood,lastHealth,error,lastFunds));annotate();running=false;setTimeout(refresh,300000);}}
 refresh();
})(typeof globalThis!=='undefined'?globalThis:this);
