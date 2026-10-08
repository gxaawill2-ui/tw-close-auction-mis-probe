(function(root){
  'use strict';
  const RAW='https://raw.githubusercontent.com/gxaawill2-ui/tw-close-auction-mis-probe/main/';
  const TYPES=['AB_converged','AC_converged','BC_converged','A_1330_fresh_candidate'];
  function taipei(now){
    const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(now);
    const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));
    return {date:p.year+'-'+p.month+'-'+p.day,clock:p.hour+':'+p.minute+':'+p.second,year:Number(p.year)};
  }
  function tradingDay(date,calendar){
    if(!calendar||calendar.year!==Number(date.slice(0,4))||!Array.isArray(calendar.closed_dates))return null;
    const day=new Date(date+'T12:00:00+08:00').getUTCDay();
    return day!==0&&day!==6&&!calendar.closed_dates.includes(date);
  }
  function validate(data,date,now){
    if(!data||data.trade_date!==date)throw new Error('結果日期不符');
    if(data.status!=='RESEARCH_ONLY'||data.validated!==false||!['COMPLETE','PARTIAL'].includes(data.completion_status))throw new Error('研究結果尚未完成');
    const generated=new Date(data.generated_at);
    if(!Number.isFinite(generated.getTime())||taipei(generated).date!==date||generated>now)throw new Error('產生時間不符');
    const c=data.coverage||{},values=[c.tradable_universe,c.research_calculable,c.unknown];
    if(values.some(x=>!Number.isInteger(x)||x<0)||values[0]<=0||values[1]+values[2]!==values[0])throw new Error('涵蓋資料不完整');
    if(!Array.isArray(data.candidate_list)||data.candidate_count!==data.candidate_list.length||data.candidate_count>values[1])throw new Error('名單筆數不符');
    const keys=new Set();
    for(const row of data.candidate_list){
      const key=row.market+':'+row.code,pre=Number(row.P_before),close=Number(row.P_close),pct=Number(row.tail_return_pct);
      if(keys.has(key)||!/^\d{4}$/.test(row.code)||!row.name||row.validated!==false||!TYPES.includes(row.P_close_convergence_type)||!['HIGH_RESEARCH','MEDIUM_RESEARCH'].includes(row.confidence_level))throw new Error('候選資料不完整');
      keys.add(key);
      if(!Number.isFinite(pre)||!Number.isFinite(close)||pre<=0||close<=0||!Number.isFinite(pct)||Math.abs(pct)<3||Math.abs((close/pre-1)*100-pct)>1e-8)throw new Error('尾盤漲跌幅不符');
      if(!/^\d\d:\d\d:\d\d$/.test(row.P_before_trade_time)||row.P_before_trade_time<'09:00:00'||row.P_before_trade_time>='13:25:00'||!/^\d\d:\d\d:\d\d$/.test(row.P_close_trade_time))throw new Error('成交時間不符');
      if(row.volume_unit!=='張')throw new Error('成交量單位不符');
      const volume=[row.closing_auction_volume,row.intraday_total_volume,row.closing_volume_ratio_pct];
      if(row.volume_status==='MIS_EVIDENCE_CONFIRMED'){
        const [last,total,ratio]=volume.map(Number);
        if(volume.some(v=>v===null||v===undefined)||!volume.every(v=>Number.isFinite(Number(v)))||last<=0||last>total||Math.abs(last/total*100-ratio)>1e-8)throw new Error('成交量證據不符');
      }else if(volume.some(v=>v!==null))throw new Error('未驗證成交量必須留空');
    }
    return data;
  }
  function model(now,input){
    const t=taipei(now),trade=tradingDay(t.date,input.calendar),live=input.live&&input.live.trade_date===t.date?input.live:null;
    let data=null,error=input.error||'',state,headline,message;
    if(input.data){try{data=validate(input.data,t.date,now);}catch(e){error=e.message;}}
    if(trade===false){state='CLOSED';headline='今日休市';message='休市日不顯示其他日期的股票。';data=null;}
    else if(data){
      state=data.completion_status==='PARTIAL'||data.coverage.unknown>0?'PARTIAL':'READY';
      headline=data.candidate_count?'今日 '+data.candidate_count+' 檔符合尾盤 ±3%':'今日無符合 ±3% 的股票';
      message=state==='PARTIAL'?'已顯示可信研究候選；部分股票資料不足，保留 UNKNOWN。':'今日研究計算已完成。所有候選仍為 RESEARCH_ONLY。';
      if(data.candidate_count===0&&state==='READY')state='ZERO_CANDIDATES';
    }else if(error){state='UPDATE_FAILED';headline='資料更新失敗／尚無當日結果';message='稍後自動重試；不以昨日資料代替今日。';}
    else if(live&&live.status==='running'){state='CAPTURING';headline='今日尾盤資料擷取中';message='名單產生後自動顯示，無須重新整理。';}
    else if(live&&live.capture_outcome==='CAPTURE_FAILED'){state='CAPTURE_FAILED';headline='今日擷取未完成';message='必要資料不足，尚無可發布的當日結果。';}
    else if(live&&['CAPTURE_SUCCESS','CAPTURE_PARTIAL'].includes(live.capture_outcome)){state='PUBLISHING_DELAY';headline='研究結果發布中／尚無當日結果';message='擷取已完成，正在等待公開名單；這不代表今日沒有候選。';}
    else if(trade===null){state='UNKNOWN_CALENDAR';headline='尚無當日結果';message='交易日狀態暫未確認；取得資料後自動更新。';}
    else {state=t.clock<'09:00:00'?'BEFORE_OPEN':'WAITING';headline='今日尚未產生尾盤研究資料';message=t.clock<'09:00:00'?'尚未開盤；尾盤研究名單預計約 13:35 更新。':'尾盤研究名單預計約 13:35 更新。';}
    return {today:t.date,clock:t.clock,isTradingDay:trade,state,headline,message,data,error,
      rows:data?[...data.candidate_list].sort((a,b)=>Math.abs(Number(b.tail_return_pct))-Math.abs(Number(a.tail_return_pct))||a.code.localeCompare(b.code)):[]};
  }
  function polling(now){const t=taipei(now);return t.clock>='13:30:00'&&t.clock<'13:40:00'?20000:60000;}
  function number(value,decimals=2){return value===null||value===undefined?'—':new Intl.NumberFormat('zh-TW',{maximumFractionDigits:decimals}).format(Number(value));}
  function escape(value){return String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function priceLabel(row){return {MATCH:'收盤價一致',MISMATCH:'收盤價不符',UNAVAILABLE:'官方缺資料',PENDING:'待盤後核對'}[row.official_price_result]||'待盤後核對';}
  function confidence(row){return row.confidence_level==='HIGH_RESEARCH'?'高 · 研究':'中 · 研究';}
  function volume(row,key,unit){return row[key]===null?'— <small>未驗證</small>':number(row[key],3)+(unit?' <small>'+unit+'</small>':'');}
  function render(doc,view){
    const set=(id,text)=>{doc.getElementById(id).textContent=text;};
    set('today',view.today+' · 台北');set('market-state',view.isTradingDay===false?'休市':view.isTradingDay===true?'交易日':'交易日待確認');
    set('headline',view.headline);set('message',view.message);
    set('network',view.error?'資料更新失敗：'+view.error+'。將自動重試；已載入的當日資料保留原更新時間。':'');
    const data=view.data,c=data&&data.coverage;
    set('candidate-count',data?number(data.candidate_count,0):'—');
    for(const [id,key] of [['universe','tradable_universe'],['calculable','research_calculable'],['unknown','unknown']])set(id,c?number(c[key],0):'—');
    const stamp=x=>x?new Intl.DateTimeFormat('zh-TW',{timeZone:'Asia/Taipei',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(new Date(x)):'—';
    set('updated','最近資料更新：'+stamp(data&&(data.updated_at||data.published_at))+'（台北）');
    set('generated','研究名單產生時間：'+stamp(data&&data.generated_at)+'（台北）');
    const desktop=[],mobile=[];
    for(const row of view.rows){
      const positive=Number(row.tail_return_pct)>0,tail=(positive?'+':'')+number(row.tail_return_pct,3)+'%',color=positive?'up':'down';
      const name=escape(row.name),code=escape(row.code),market=row.ex==='tse'?'上市':'上櫃';
      const time=escape(row.P_close_trade_time),delayed=time>'13:30:00'?'<span class="delayed">延後收盤</span>':'';
      const type=escape(row.P_close_convergence_type.replace('_converged','').replace('A_1330_fresh_candidate','A 13:30'));
      const level=row.confidence_level==='MEDIUM_RESEARCH'?' medium':'',label=priceLabel(row),priceClass=row.official_price_result==='MATCH'?' match':row.official_price_result==='MISMATCH'?' mismatch':'';
      const last=volume(row,'closing_auction_volume','張'),total=volume(row,'intraday_total_volume','張'),ratio=volume(row,'closing_volume_ratio_pct','%');
      const volStatus=row.volume_status==='MIS_EVIDENCE_CONFIRMED'?'成交量：MIS 證據一致':'成交量：未驗證';
      desktop.push('<tr><td><span class="stock-name">'+name+'</span><span class="stock-code">'+code+'</span></td><td>'+market+'</td><td class="tail '+color+'">'+tail+'</td><td>'+number(row.P_before,4)+'</td><td>'+number(row.P_close,4)+'</td><td>'+time+delayed+'</td><td>'+last+'</td><td>'+total+'</td><td>'+ratio+'</td><td><span class="badge'+priceClass+'">'+label+'</span></td><td><span class="badge'+level+'">'+confidence(row)+' · '+type+'</span><span class="volume-note">'+volStatus+'</span></td></tr>');
      mobile.push('<article class="candidate-card" data-code="'+code+'"><div class="card-heading"><div><h3><span class="stock-code">'+code+'</span>'+name+'</h3><div class="market">'+market+'</div></div><div><div class="tail '+color+'">'+tail+'</div><span class="tail-label">尾盤漲跌幅</span></div></div><div class="card-metrics">'+[['13:25 前價',number(row.P_before,4)],['收盤價',number(row.P_close,4)],['最後成交時間',time+delayed],['最後一盤量',last],['全日盤中量',total],['收盤量占比',ratio]].map(([label,value])=>'<div class="metric"><span>'+label+'</span><strong>'+value+'</strong></div>').join('')+'</div><div class="card-footer"><div class="confidence"><span class="badge'+level+'">'+confidence(row)+' · '+type+'</span></div><span class="badge'+priceClass+'">'+label+'</span></div><div class="card-volume-status">'+volStatus+' · RESEARCH_ONLY</div></article>');
    }
    for(const [id,html] of [['desktop-list',desktop.join('')],['mobile-list',mobile.join('')]]){
      const element=doc.getElementById(id);if(element.dataset.rendered!==html){element.innerHTML=html;element.dataset.rendered=html;}
    }
    doc.getElementById('desktop-wrap').hidden=!view.rows.length;doc.getElementById('empty').hidden=Boolean(view.rows.length);
    set('empty',view.headline);
  }
  const api={taipei,tradingDay,validate,model,polling,number,render,RAW};
  if(typeof module!=='undefined'&&module.exports){module.exports=api;return;}
  root.TailDashboard=api;
  let calendar=null,calendarYear=null,lastGood=null,running=false;
  async function read(path,now,optional=false){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
    try{const response=await fetch(RAW+path+'?v='+Math.floor(now.getTime()/polling(now)),{cache:'no-store',signal:controller.signal});
      if(response.status===404&&optional)return null;if(!response.ok)throw new Error('HTTP '+response.status);return await response.json();
    }finally{clearTimeout(timer);}
  }
  async function refresh(){
    if(running)return;running=true;const now=new Date(),t=taipei(now);if(lastGood&&lastGood.trade_date!==t.date)lastGood=null;
    let data=null,live=null,error='';
    try{
      if(calendarYear!==t.year||!calendar){calendar=await read('state/calendars/'+t.year+'.json',now);calendarYear=t.year;}
      if(tradingDay(t.date,calendar)!==false){
        data=await read('state/candidates/'+t.date+'.json',now,true);
        if(data){validate(data,t.date,now);lastGood=data;}else live=await read('state/live/'+t.date+'.json',now,true);
      }
    }catch(e){error=e.message;data=lastGood;}
    finally{render(document,model(now,{calendar,data,live,error}));running=false;setTimeout(refresh,polling(new Date()));}
  }
  refresh();
})(typeof globalThis!=='undefined'?globalThis:this);
