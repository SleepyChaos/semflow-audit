import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {helpers} from './chain_browser_helpers.mjs';
import {reviewRepair} from './chain_review_repair.mjs';
import {ruleChain} from './chain_rules.mjs';

const root=path.resolve(import.meta.dirname,'../../..');
const require=createRequire(new URL('../../frontend/package.json',import.meta.url));
const {chromium}=require('@playwright/test');
const output=path.resolve(process.argv[2]);
const config=JSON.parse(await readFile(path.join(output,'config.json'),'utf8'));
const actors=JSON.parse(await readFile(path.join(output,'credentials.private.json'),'utf8'));
const inputs=JSON.parse(await readFile(path.join(output,'inputs.json'),'utf8'));
const began=Date.now();
const browser=await chromium.launch({headless:true,channel:'chrome'});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
page.setDefaultTimeout(25000);
const h=helpers(page,output,config);
const errors=[];
page.on('pageerror',error=>errors.push({kind:'pageerror',message:String(error).slice(0,700)}));
page.on('console',msg=>{if(msg.type()==='error')errors.push({kind:'console',message:msg.text().slice(0,700)});});
async function verifyFreeze() {
  for(const [file,hash] of Object.entries({...config.production_hashes,...config.runner_hashes}))
    assert.equal(createHash('sha256').update(await readFile(path.join(root,file))).digest('hex'),hash,`Changed ${file}`);
  for(const input of inputs.records)
    assert.equal(createHash('sha256').update(await readFile(input.archive)).digest('hex'),input.sha256);
}
try {
  await verifyFreeze();
  await h.step('shared','real-login-and-workbench',async()=>{
    await page.goto(config.url);
    await page.getByTestId('email-input').fill(actors[0].email);
    await page.getByTestId('password-input').fill(actors[0].password);
    await page.getByRole('button',{name:'登录',exact:true}).click();
    await page.getByRole('heading',{name:'审计工作台',exact:true}).waitFor();
    assert.equal(await page.locator('vite-error-overlay').count(),0);
    return {browser:browser.version(),url:page.url(),viewport:{width:1440,height:1000}};
  });
  for(const input of inputs.records) {
    const language=input.language;
    try {
      const audit=await h.step(language,config.resume_audits?'resume-existing-v2-real-upload':'browser-real-upload-codeql-scout-worker-join',async()=>{
        if(!config.resume_audits)return h.upload(language,input.archive,`chain-${language}-primary`);
        const prior=await h.api('GET',`/audits/${config.resume_audits[language]}`);
        assert.equal(prior.status,'completed');h.record.audit_ids.push(prior.id);
        await h.settleStage(prior.coverage.dual_engine.scout_stage_id);
        await page.getByRole('button',{name:prior.project_name,exact:true}).first().click();
        return {...prior,reused_from_attempt:'20261009-v2'};
      });
      await h.step(language,'snapshot-source-and-sarif-download',async()=>{
        await h.download(page.getByRole('button',{name:'下载 SARIF',exact:true}),`${language}-baseline.sarif`);
        const module=language==='python'?'calc.py':'calc.js';
        const source=await h.api('GET',`/audits/${audit.id}/source?file=${module}&line=1`);
        assert.ok(source.lines.join('\n').includes('eval('));
        return {snapshot:audit.snapshot_hash,baseline_alerts:audit.findings.length,dual_engine:audit.coverage.dual_engine};
      });
      await reviewRepair(h,language,audit);
      const rule=await ruleChain(h,language,audit,input);
      await h.step(language,'owned-data-isolation-for-other-real-account',async()=>{
        const tokenResponse=await page.request.post(`${config.api_url}/api/v1/login/access-token`,{form:{username:actors[1].email,password:actors[1].password}});
        assert.equal(tokenResponse.status(),200);
        const token=(await tokenResponse.json()).access_token;
        const checks=[];
        for(const route of [`/audits/${audit.id}`,`/audits/${audit.id}/source?file=calc.py&line=1`,`/audits/${audit.id}/report`,`/rules/${rule.id}`]) {
          const response=await page.request.get(`${config.api_url}/api/v1${route}`,{headers:{Authorization:`Bearer ${token}`}});
          assert.equal(response.status(),404,route);
          checks.push({route,status:response.status()});
        }
        return checks;
      });
      await h.step(language,'browser-json-markdown-report-download-and-history',async()=>{
        await page.getByRole('button',{name:'查看修复与报告',exact:true}).click();
        const jsonFile=await h.download(page.getByRole('button',{name:'导出 JSON 报告',exact:true}),`${language}-final-report.json`);
        const mdFile=await h.download(page.getByRole('button',{name:'导出 Markdown 报告',exact:true}),`${language}-final-report.md`);
        const report=JSON.parse(await readFile(jsonFile,'utf8'));
        assert.ok(report.repairs.some(r=>r.status==='accepted'));
        assert.ok(report.rules.some(r=>r.status==='published'));
        assert.ok(report.summary.candidate_states.confirmed>=1);
        assert.ok((await readFile(mdFile,'utf8')).length>300);
        const stages=await h.api('GET',`/audits/${audit.id}/stages`);
        assert.ok(stages.some(s=>s.kind==='rule'&&s.status==='completed'));
        assert.ok(stages.some(s=>s.kind==='repair'&&s.status==='completed'));
        await writeFile(path.join(output,`${language}-history-receipt.json`),JSON.stringify(stages,null,2)+'\n');
        await page.locator('section.detail-panel').screenshot({path:path.join(output,`${language}-final-panel.png`)});
        return {repair:'accepted',rule:'published',report:'JSON + Markdown',stage_history:stages.map(s=>({id:s.id,kind:s.kind,status:s.status,prompt_version:s.prompt_version}))};
      });
      await h.step(language,'test-rule-retirement-preserves-existing-scan',async()=>{
        await page.getByRole('button',{name:'查看RAG 规则',exact:true}).click();
        const card=page.locator('article.candidate-card').filter({has:page.getByRole('heading',{name:rule.title,exact:true})}).first();
        const pending=page.waitForResponse(r=>r.url().endsWith(`/rules/${rule.id}/retire`)&&r.request().method()==='POST');
        await card.getByRole('button',{name:'停用此版本',exact:true}).click();
        assert.equal((await pending).status(),200);
        const current=await h.api('GET',`/rules/${rule.id}`);
        assert.equal(current.status,'retired');
        const original=await h.api('GET',`/audits/${audit.id}`);
        assert.equal(original.snapshot_hash,audit.snapshot_hash);
        return {rule:'retired',original_snapshot_unchanged:true};
      });
    } catch(error) {
      h.record.steps.push({language,name:'remaining-dependent-steps',status:'not_evaluated',reason:String(error.message).slice(0,800)});
      await h.persist();
    }
  }
  await h.step('shared','console-health-and-no-framework-overlay',async()=>{
    assert.deepEqual(errors,[]);
    assert.equal(await page.locator('vite-error-overlay').count(),0);
  });
  await h.step('shared','real-logout-protects-workbench',async()=>{
    await page.getByRole('button',{name:'退出登录',exact:true}).click();
    await page.waitForURL('**/login');
    await page.goto(config.url);
    await page.waitForURL('**/login');
  });
  await verifyFreeze();
} catch(error) {
  h.record.steps.push({language:'shared',name:'infrastructure-or-integrity',status:'failed',reason:String(error.message).slice(0,800)});
} finally {
  await h.persist();
  const report={...h.record,seconds:(Date.now()-began)/1000,browser:browser.version(),console:errors,passed:h.record.steps.filter(s=>s.status==='passed').length,failed:h.record.steps.filter(s=>s.status==='failed').length,not_evaluated:h.record.steps.filter(s=>s.status==='not_evaluated').length,scope:config.scope,approval_actor:config.confirmation_origin};
  await writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
  await browser.close();
}
process.exitCode=h.record.steps.some(s=>s.status!=='passed')?1:0;
