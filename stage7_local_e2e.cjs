const {execFile}=require('node:child_process'),{promisify}=require('node:util'),crypto=require('node:crypto');
(async()=>{
 const bridgeToken=crypto.randomBytes(32).toString('hex'),{worker,url,token,key}=await require('./stage3_worker_runtime.cjs').startWorker({bridgeToken});
 try{
  const result=await promisify(execFile)('python3',['stage7_local_e2e.py'],{cwd:__dirname,env:{...process.env,LOCAL_WORKER_URL:url,LOCAL_TOKEN:token,LOCAL_KEY:key,LOCAL_BRIDGE_TOKEN:bridgeToken},timeout:45000});
  process.stdout.write(result.stdout);
 }finally{await worker.dispose();}
})().catch(e=>{process.stderr.write(e.stderr||e.message);process.exitCode=1});
