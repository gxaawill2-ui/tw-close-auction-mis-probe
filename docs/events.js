(function(root){
 'use strict';
 const RAW='https://raw.githubusercontent.com/gxaawill2-ui/tw-close-auction-mis-probe/main/';
 const label={announcement_date:'公告',effective_date:'生效',closing_impact_date:'收盤觀察',implementation_window:'過渡期間'};
 const statuses={CONFIRMED_CLOSE_IMPLEMENTATION:'官方確認收盤實施',EXPECTED_CLOSE_WATCH_DATE:'預估觀察日',DATE_UNVERIFIED:'收盤日未確認'};
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
 function model(now,data,health,error=''){
  let events=[];try{if(data)events=valid(data,now).events;}catch(e){error=e.message;}
  const day=taipei(now),limit=new Date(day+'T12:00:00Z');limit.setUTCDate(limit.getUTCDate()+30);
  const end=limit.toISOString().slice(0,10),entries=[];
  for(const event of events){
   if(Date.parse(event.first_seen_at)>now.getTime())continue;
   for(const key of ['announcement_date','closing_impact_date','effective_date'])if(event[key])entries.push({date:event[key],type:key,event});
   for(const d of (event.implementation_window||{}).dates||[])entries.push({date:d,type:'implementation_window',event});
  }
  entries.sort((a,b)=>a.date.localeCompare(b.date)||a.event.event_name.localeCompare(b.event.event_name)||a.type.localeCompare(b.type));
  const today=entries.filter(x=>x.date===day),close=today.filter(x=>['closing_impact_date','implementation_window'].includes(x.type));
  const sourceStale=!health||!health.last_successful_scan_at||now.getTime()-Date.parse(health.last_successful_scan_at)>36*3600*1000;
  const incomplete=error||sourceStale||data?.coverage_status!=='COMPLETE'||health?.sources?.some(s=>s.status!=='SUCCESS');
  let headline;
  if(close.length)headline=close.some(x=>x.event.close_date_status==='CONFIRMED_CLOSE_IMPLEMENTATION')?'今日有官方確認的指數收盤實施':'今日有預估觀察日／換股過渡期間';
  else if(today.length)headline='今日有指數'+[...new Set(today.map(x=>label[x.type]))].join('／')+'；收盤集中交易未確認';
  else headline=incomplete?'事件資料尚未完整確認':'今日無已確認的重大指數調整事件';
  let upcoming=entries.filter(x=>x.date>day&&x.date<=end),range='未來 30 天';
  if(!upcoming.length){const next=entries.find(x=>x.date>day);if(next){upcoming=entries.filter(x=>x.date===next.date);range='30 天以外 · 下一個已知日期';}}
  return {day,today,headline,upcoming,range,error,incomplete,sourceStale,
   note:incomplete?'部分來源受限、未更新或僅追蹤日程；未列出不代表沒有事件。':'已完成已設定官方來源掃描。'};
 }
 function htmlEntry(x){
  const e=x.event,expected=e.event_status==='EXPECTED'||['closing_impact_date','implementation_window'].includes(x.type)&&e.close_date_status!=='CONFIRMED_CLOSE_IMPLEMENTATION';
  const type=x.type==='announcement_date'&&e.announcement_timezone==='SOURCE_DATE_TIME_UNPUBLISHED'?'公告 · 來源日期（台北時間待確認）':label[x.type];
  return '<li class="event-row"><div class="event-date">'+esc(x.date)+'<small>'+esc(type)+'</small></div><div class="event-description"><strong>'+esc(e.event_name)+'</strong><div>'+esc(e.related_etf_codes.length?'ETF '+e.related_etf_codes.join('、'):e.index_name)+'</div><span class="event-tag'+(expected?' expected':'')+'">'+esc(expected?'預估 · 依官方規則／交易日推算':x.type==='closing_impact_date'?statuses[e.close_date_status]:'官方日期 · 收盤實施另確認')+'</span><a href="'+esc(e.source_url)+'" target="_blank" rel="noopener noreferrer">官方來源</a></div></li>';
 }
 function render(doc,view){
  const set=(id,text)=>{doc.getElementById(id).textContent=text;};
  set('event-today-title',view.headline);set('event-note',view.error?'事件資料更新失敗；股票名單仍獨立更新。 '+view.note:view.note);
  set('event-range',view.range);set('event-empty',view.upcoming.length?'':'已取得範圍內尚無近期日期；其餘期程未公布／未確認。');
  for(const [id,rows] of [['event-today-list',view.today],['event-upcoming',view.upcoming]]){
   const element=doc.getElementById(id),html=rows.map(htmlEntry).join('');if(element.dataset.rendered!==html){element.innerHTML=html;element.dataset.rendered=html;}
  }
 }
 function relation(row,events,day,asOf){
  const cutoff=Date.parse(asOf),dayEvents=events.filter(e=>Date.parse(e.information_available_as_of)<=cutoff&&
   (e.closing_impact_date===day||(e.implementation_window?.dates||[]).includes(day)));
  const matches=[];
  for(const e of dayEvents)for(const s of e.affected_stocks)if(s.code===row.code&&s.market===row.market&&s.market_status==='OFFICIAL_CONFIRMED')matches.push({event:e,stock:s});
  return {matches,label:matches.length?matches.map(x=>x.event.event_name+' · '+({ADDITION:'納入',DELETION:'刪除',WEIGHT_CHANGE:'權重調整'}[x.stock.change_type]||'官方異動')).join('；'):
    dayEvents.length?'當日有指數調整事件，個股關聯未確認':'個股事件關聯未確認'};
 }
 const api={valid,model,render,relation,taipei};
 if(typeof module!=='undefined'&&module.exports){module.exports=api;return;}
 root.IndexEvents=api;
 let lastGood=null,lastHealth=null,running=false;
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
  try{const [data,health]=await Promise.all([read('events-index.json'),read('source-health.json')]);valid(data,now);lastGood=data;lastHealth=health;}catch(e){error=e.message;}
  finally{render(document,model(now,lastGood,lastHealth,error));annotate();running=false;setTimeout(refresh,300000);}}
 refresh();
})(typeof globalThis!=='undefined'?globalThis:this);
