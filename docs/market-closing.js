(function(root){
 'use strict';
 const RAW='https://raw.githubusercontent.com/gxaawill2-ui/tw-close-auction-mis-probe/main/';
 const SCOPE='TWSE_ORDINARY_EQUITY_REGULAR_BOARD_LOT_1330_1333_V1';
 function model(now,data,calendar,error=''){
  const local=new Date(now.getTime()+8*3600000),day=local.toISOString().slice(0,10),clock=local.toISOString().slice(11,19);
  const knownCal=calendar?.year===Number(day.slice(0,4))&&calendar.status==='OFFICIAL_ANNUAL_CALENDAR';
  const closed=knownCal&&(local.getUTCDay()===0||local.getUTCDay()===6||calendar.closed_dates.includes(day));
  let status=closed?'休市':'尚未確認',usable=null;
  if(data&&data.trade_date===day&&data.schema_version===1&&data.market_scope===SCOPE&&Number.isFinite(Date.parse(data.generated_at))&&Date.parse(data.generated_at)<=now.getTime()&&clock>='13:33:00'&&knownCal&&!closed){
   if(data.source_quality==='VERIFIED_SAME_SCOPE'&&data.coverage_ratio===1&&!data.missing_stocks?.length&&data.official_reconciliation?.status==='MATCH_SAME_SCOPE'){
    const a=Number(data.closing_auction_turnover_twd),b=Number(data.daily_turnover_twd),p=Number(data.closing_turnover_share_pct);
    if(data.closing_auction_turnover_twd!==null&&data.daily_turnover_twd!==null&&data.closing_turnover_share_pct!==null&&Number.isFinite(a)&&Number.isFinite(b)&&b>0&&a>=0&&a<=b&&Number.isFinite(p)&&p>=0&&p<=100&&Math.abs(p-a/b*100)<.00001){
     usable=data;
     if(!error&&data.threshold_status==='CALIBRATED'&&data.status==='VERIFIED'&&data.historical_sample_count>=20&&typeof data.is_closing_volume_spike==='boolean')status=data.is_closing_volume_spike?'有':'沒有';
    }
   }
  }
  return {day,status,data:usable,note:closed?'依官方年度交易日曆；臨時停市仍待官方更新。':error?'量能來源暫未確認；不把缺資料視為沒有爆量。':'僅計上市普通股一般整股收盤撮合（含 13:33），排除 ETF、上櫃、零股、盤後及鉅額。門檻尚待同範圍歷史校準；候選規則 20% 且 1.5 倍，為 PROVISIONAL。'};
 }
 function render(doc,view){
  const set=(id,text)=>{const node=doc.getElementById(id);if(node)node.textContent=text;};
  const d=view.data,fmt=(n,unit)=>n===null||n===undefined?'—':new Intl.NumberFormat('zh-TW',{maximumFractionDigits:2}).format(Number(n))+unit;
  set('market-closing-state',view.status);
  set('market-closing-turnover',d?fmt(Number(d.closing_auction_turnover_twd)/1e8,' 億元'):'—');
  set('market-daily-turnover',d?fmt(Number(d.daily_turnover_twd)/1e8,' 億元'):'—');
  set('market-closing-share',fmt(d?.closing_turnover_share_pct,'%'));
  set('market-closing-median',fmt(d?.historical_median_share_pct,'%'));
  set('market-closing-multiple',fmt(d?.relative_multiple,' 倍'));
  set('market-closing-note',view.note+' 更新：'+(d?.generated_at||'尚無完整驗證資料'));
 }
 const api={model,render,SCOPE};if(typeof module!=='undefined'&&module.exports){module.exports=api;return;}
 root.MarketClosing=api;
 let saved=null,cal=null;
 async function read(path){const c=new AbortController(),timer=setTimeout(()=>c.abort(),10000);try{const r=await fetch(RAW+path+'?v='+Math.floor(Date.now()/300000),{cache:'no-store',signal:c.signal});if(!r.ok)throw new Error('HTTP');return await r.json();}finally{clearTimeout(timer);}}
 async function refresh(){const now=new Date(),day=new Date(now.getTime()+8*3600000).toISOString().slice(0,10);let error='';
  const results=await Promise.allSettled([read('state/calendars/'+day.slice(0,4)+'.json'),read('state/market-closing-volume/'+day+'.json')]);
  if(results[0].status==='fulfilled')cal=results[0].value;else error='calendar';
  if(results[1].status==='fulfilled')saved=results[1].value;else error='data';
  render(document,model(new Date(),saved,cal,error));setTimeout(refresh,300000);
 }
 refresh();
})(typeof globalThis!=='undefined'?globalThis:this);
