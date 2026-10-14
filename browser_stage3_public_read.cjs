// One anonymous browser read of a separately committed sandbox file. No polling,
// no credentials and no claims about GitHub Pages or Cloudflare cloud latency.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
async function main(){
 const branch=process.env.STAGE3_BRANCH||'stage3/20261014-independent-ticks-publication';
 const endpoint='https://api.github.com/repos/gxaawill2-ui/tw-close-auction-mis-probe/contents/reports/2026-10-14-stage3/public-sandbox.json?ref='+encodeURIComponent(branch);
 const server=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html; charset=utf-8');res.end(fs.readFileSync(path.join(__dirname,'reports/2026-10-14-stage3/replay/stage3-preview.html')));});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE_PATH,args:['--no-sandbox','--disable-dev-shm-usage','--no-zygote']});
 const result={kind:'GITHUB_ANONYMOUS_ISOLATED_FILE_NOT_PAGES_OR_WORKER',branch,endpoint,
  started_at:new Date().toISOString(),read_without_credentials:true,production_site_mutated:false};
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1080},timezoneId:'Asia/Taipei'});
  const network=[];page.on('requestfailed',request=>{if(request.url().startsWith('https://api.github.com/'))network.push({url:request.url(),failure:request.failure()});});
  page.on('response',response=>{if(response.url().startsWith('https://api.github.com/'))network.push({url:response.url(),http_status:response.status(),content_type:response.headers()['content-type']});});
  await page.goto('http://127.0.0.1:'+server.address().port+'/');
  const began=performance.now();
  await page.evaluate(async endpoint=>Stage3Controller.poll(endpoint),endpoint);
  const reads=await page.evaluate(()=>Stage3Controller.reads);
  result.network=network;
  assert.equal(reads.length,1,'Anonymous public read must yield a version receipt');
  const nonce=await page.evaluate(()=>Stage3Controller.getState().body.nonce);
  assert.equal(nonce,'stage3-public-read-20261014-01');
  assert.equal(await page.locator('#stage3-verified').innerText(),'0');assert.equal(await page.locator('#stage3-research').innerText(),'6');
  Object.assign(result,{status:'PASS',request_to_browser_ms:performance.now()-began,read:reads[0],nonce,formal_signals:0});
 }catch(error){Object.assign(result,{status:'BLOCKED_OR_FAILED',error:error.message,formal_signals:0});}
 finally{result.completed_at=new Date().toISOString();await browser.close();await new Promise(resolve=>server.close(resolve));}
 fs.writeFileSync(path.join(__dirname,'reports/2026-10-14-stage3/public-read-acceptance.json'),JSON.stringify(result,null,2));
 console.log(JSON.stringify(result));if(result.status!=='PASS')process.exitCode=1;
}
main().catch(error=>{console.error(error);process.exitCode=1;});
