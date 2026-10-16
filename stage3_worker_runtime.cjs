const path=require('node:path'),crypto=require('node:crypto');
async function startWorker({bridgeToken=null}={}){
 const modulePath=process.env.MINIFLARE_MODULE||path.resolve(__dirname,'../stage3-runtime/node_modules/miniflare');
 const {Miniflare}=require(modulePath);
 const token=crypto.randomBytes(32).toString('hex'),key=crypto.randomBytes(32).toString('hex');
 const worker=new Miniflare({scriptPath:path.join(__dirname,'isolated_publication/worker.mjs'),modules:true,
  compatibilityDate:'2026-07-30',host:'127.0.0.1',port:0,
  bindings:{PUBLISH_TOKEN:token,DECISION_KEY:key,ALLOW_LIVE_VERIFIED:'false',...(bridgeToken?{MIS_BRIDGE_TOKEN:bridgeToken}:{})},
  durableObjects:{SELECTION:{className:'SelectionStore',useSQLite:true}}});
 return {worker,token,key,url:String(await worker.ready).replace(/\/$/,'')};
}
module.exports={startWorker};
