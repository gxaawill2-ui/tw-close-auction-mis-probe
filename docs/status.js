(function(root){
  'use strict';
  const REPO='gxaawill2-ui/tw-close-auction-mis-probe';
  const RAW='https://raw.githubusercontent.com/'+REPO+'/main/';
  const references={pre_reference_A:'13:27:00',pre_reference_B:'13:28:15',close_reference_A:'13:32:30',close_reference_B:'13:33:20'};
  function taipei(now){
    const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(now);
    const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));
    return {date:p.year+'-'+p.month+'-'+p.day,clock:p.hour+':'+p.minute+':'+p.second,year:Number(p.year)};
  }
  function sameDay(row,date,key='trade_date'){return row&&row[key]===date?row:null;}
  function tradingDay(date,calendar,latest){
    if(calendar&&calendar.year===Number(date.slice(0,4))&&Array.isArray(calendar.closed_dates)){
      const day=new Date(date+'T12:00:00+08:00').getUTCDay();
      return day!==0&&day!==6&&!calendar.closed_dates.includes(date);
    }
    return latest&&latest.today===date&&typeof latest.is_trading_day==='boolean'?latest.is_trading_day:null;
  }
  function model(now,input){
    const t=taipei(now),live=sameDay(input.live,t.date),official=sameDay(input.official,t.date);
    const trade=tradingDay(t.date,input.calendar,input.calendarLatest);
    let status='NOT RUN',reason=live&&(live.reason||live.error)||'今天尚無正式 capture；不顯示昨日成功。';
    if(!live&&trade===false){status='NON TRADING';reason='官方年度日曆：今日休市。';}
    else if(live){
      if(live.status==='running'){status=t.clock>='13:40:00'?'FAILED':'RUNNING';reason=status==='FAILED'?'13:40 後仍未完成，請查 Actions；不沿用舊成功。':'runner 已啟動，正在執行／等待指定時間。';}
      else if(live.status==='success_raw_capture'){
        const both=(live.convergence||{}).both_converged_count;
        status=typeof both==='number'&&both<live.universe_count?'PARTIAL':'SUCCESS';
        reason='原始 capture 已保存；收斂候選仍為研究，不代表 validated。';
      }else if(live.status==='partial'){status='PARTIAL';reason=reason||'部分完成，請查缺漏與收斂報告。';}
      else if(live.status==='missing_incomplete'||live.status==='failed_missing'){status='NOT RUN';}
      else if(typeof live.status==='string'&&live.status.startsWith('failed')){status='FAILED';}
    }
    const dual=(live||{}).convergence||{};
    const review=official&&official.convergence&&official.convergence.status==='RESEARCH_ONLY'?official:live;
    const ext=input.external||{};
    const phaseStates=Object.entries(references).map(([name,time])=>{
      const metrics=live&&live.snapshots&&live.snapshots[name];
      const progress=live&&live.reference_progress&&live.reference_progress[name];
      let state='NOT_SAMPLED';
      if(metrics){state=metrics.status==='NOT_SAMPLED'?'NOT_SAMPLED':(metrics.symbol_set_equal?'CAPTURED':'PARTIAL')+' · '+(metrics.success_count??'—')+'/'+(metrics.stock_universe_count??'—');}
      else if(progress){state=progress.status.toUpperCase()+' · '+(progress.returned_count??'—');}
      else if(live&&live.status==='running'&&t.clock<time){state='SCHEDULED';}
      else if(live&&live.status==='running'&&t.clock<'13:40:00'){state='PENDING_CAPTURE';}
      return {name,time,status:state};
    });
    return {today:t.date,clock:t.clock,isTradingDay:trade,status,reason,live,official,dual,references:phaseStates,
      externalConfigured:ext.configured===true&&ext.status==='VERIFIED'&&Boolean(ext.verified_test_run_id),
      external:ext,execution:input.execution||{},dry:input.dry||{},research:review||{}};
  }
  const api={taipei,model,tradingDay,references};
  if(typeof module!=='undefined'&&module.exports){module.exports=api;return;}
  root.MISStatus=api;
  const text=(id,value)=>{document.getElementById(id).textContent=value;};
  function renderList(id,rows){
    const list=document.getElementById(id);list.replaceChildren();
    for(const [label,value] of rows){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value??'—';list.append(dt,dd);}
  }
  function render(view,errors){
    text('today',view.today+' '+view.clock+' · Asia/Taipei');
    text('headline',view.status);document.querySelector('.headline').dataset.status=view.status;
    text('reason',view.reason);
    text('network',errors.length?'讀取失敗：'+errors.join('、')+'。缺資料保持未知，不補零。':'');
    const v=view.live||{},e=view.execution,x=view.external,d=view.dual;
    renderList('details',[
      ['今天是否交易日',view.isTradingDay===null?'UNKNOWN（官方日曆未取得）':view.isTradingDay?'是':'否'],
      ['外部排程',view.externalConfigured?'VERIFIED · cron-job.org':x.status||'PENDING_USER_SETUP'],
      ['外部 Test run id',x.verified_test_run_id??'尚未驗收'],['三次外部觸發','13:00 / 13:10 / 13:18（週一至五）'],
      ['最近 workflow run id',e.run_id],['最近 event / mode',(e.event||'—')+' / '+(e.mode||'—')],
      ['今日正式 run id',v.run_id],['正式 runner startedAt',v.runner_started_at],['phase',v.phase||'not_run'],
      ['tradable universe',v.universe_count],['finishedAt',v.finished_at],
      ['官方核對',view.official&&view.official.status||v.official_validation||'PENDING'],
      ['官方 MATCH / MISMATCH / UNAVAILABLE',view.official?[view.official.matches??'—',view.official.mismatches??'—',view.official.unavailable??'—'].join(' / '):'— / — / —']]);
    const rows=document.getElementById('references');rows.replaceChildren();
    for(const r of view.references){const tr=document.createElement('tr');for(const value of [r.name,r.time,r.status]){const td=document.createElement('td');td.textContent=value;tr.append(td);}rows.append(tr);}
    renderList('counts',[
      ['P_before converged',d.p_before_converged_count],['P_close converged',d.p_close_converged_count],
      ['both converged',d.both_converged_count],['stale responses',d.stale_response_count??d.stale_batch_count],
      ['server regressions',d.server_regression_response_count],['targeted retries',d.targeted_retry_count],
      ['unknown',d.unknown_count],['research ±3% 候選數',view.research.candidate_status==='RESEARCH_ONLY'||view.research.convergence&&view.research.convergence.status==='RESEARCH_ONLY'?view.research.candidate_count:'NOT_GENERATED'],
      ['正式 validated','false（研究版）'],['收盤量','UNVERIFIED']]);
    const dry=view.dry;
    text('dry-run',(dry.status||'尚未執行')+' · run '+(dry.run_id||'—')+' · '+(dry.finished_at||'—')+' · MIS '+(dry.returned_count??'—'));
    text('updated','本次頁面讀取：'+new Date().toISOString()+'。state 最新更新：'+(v.updated_at||v.recorded_at||'—'));
  }
  let running=false;
  async function refresh(){
    if(running)return;running=true;
    const now=new Date(),t=taipei(now),errors=[];
    async function read(path,optional=false){
      const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),12000);
      try{const r=await fetch(RAW+path+'?status_refresh='+Math.floor(Date.now()/60000),{cache:'no-store',signal:controller.signal});
        if(r.status===404&&optional)return null;
        if(!r.ok)throw new Error('HTTP '+r.status);
        return await r.json();
      }catch(e){errors.push(path+' '+e.message);return null;}finally{clearTimeout(timeout);}
    }
    try{
      const [live,official,calendar,calendarLatest,external,execution,dry]=await Promise.all([
        read('state/live/'+t.date+'.json',true),read('state/validation/'+t.date+'.json',true),
        read('state/calendars/'+t.year+'.json'),read('state/calendar_latest.json',true),
        read('state/external_scheduler.json'),read('state/execution_latest.json',true),read('state/dry_run_latest.json',true)]);
      render(model(now,{live,official,calendar,calendarLatest,external,execution,dry}),errors);
    }finally{running=false;}
  }
  document.getElementById('refresh').addEventListener('click',refresh);
  refresh();setInterval(refresh,60000);
})(typeof globalThis!=='undefined'?globalThis:this);
