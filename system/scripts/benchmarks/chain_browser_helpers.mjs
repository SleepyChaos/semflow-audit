import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import path from 'node:path';

export function helpers(page, output, config) {
  const record = {steps: [], audit_ids: [], stage_ids: [], downloads: []};
  async function api(method, route, body, expected=200) {
    const token = await page.evaluate(() => localStorage.getItem('access_token'));
    const response = await page.request.fetch(`${config.api_url}/api/v1${route}`, {
      method, headers: {Authorization: `Bearer ${token}`}, ...(body === undefined ? {} : {data: body}),
    });
    const value = await response.json().catch(() => null);
    assert.equal(response.status(), expected, `${method} ${route}: ${JSON.stringify(value)}`);
    return value;
  }
  async function persist() {
    await writeFile(path.join(output, 'progress.json'), JSON.stringify(record,null,2)+'\n');
  }
  async function step(language, name, fn) {
    const began=Date.now();
    try {
      const value=await fn();
      record.steps.push({language, name, status:'passed', seconds:(Date.now()-began)/1000, ...(value===undefined?{}:{result:value})});
      await persist();
      console.log(JSON.stringify({language, name, status:'passed'}));
      return value;
    } catch(error) {
      record.steps.push({language, name, status:'failed', seconds:(Date.now()-began)/1000, error:String(error.message).slice(0,1200)});
      await page.screenshot({path:path.join(output,`${language}-${name.replaceAll(/[^a-z0-9]/gi,'-')}-failure.png`),fullPage:true}).catch(()=>{});
      await persist();
      console.log(JSON.stringify({language, name, status:'failed'}));
      throw error;
    }
  }
  async function poll(route, ready, timeout=900000) {
    const began=Date.now();
    while(Date.now()-began<timeout) {
      const value=await api('GET',route);
      if(ready(value)) return value;
      await new Promise(resolve=>setTimeout(resolve,1500));
    }
    throw new Error(`Polling timeout: ${route}`);
  }
  async function settleStage(identifier) {
    record.stage_ids.push(identifier);
    const stage=await poll(`/stages/${identifier}`,s=>!['queued','running'].includes(s.status));
    await writeFile(path.join(output,`${identifier}-${stage.status}-stage-receipt.json`),JSON.stringify(stage,null,2)+'\n');
    await page.getByRole('button',{name:'刷新',exact:true}).click();
    return stage;
  }
  async function selectOption(label,name) {
    await page.getByRole('combobox',{name:label,exact:true}).click();
    await page.getByRole('option',{name,exact:true}).first().click();
  }
  async function upload(language, archive, name, reuse=false) {
    await page.getByLabel('项目名称（可选）',{exact:true}).fill(name);
    await page.getByRole('radio',{name: language==='python'?'Python':'JavaScript / TypeScript',exact:true}).click();
    await page.getByLabel('选择代码包',{exact:true}).setInputFiles(archive);
    const response=page.waitForResponse(r=>r.url().includes('/api/v1/audits/')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'开始审计',exact:true}).click();
    const createdResponse=await response;
    const created=await createdResponse.json();
    assert.equal(createdResponse.status(),201,JSON.stringify(created));
    record.audit_ids.push(created.id);
    const audit=await poll(`/audits/${created.id}`,r=>!['queued','running'].includes(r.status));
    await writeFile(path.join(output,`${created.id}-audit-receipt.json`),JSON.stringify(audit,null,2)+'\n');
    assert.equal(audit.status,'completed',audit.error);
    if(audit.coverage.dual_engine?.scout_stage_id) await settleStage(audit.coverage.dual_engine.scout_stage_id);
    await page.getByRole('button',{name,exact:true}).first().click();
    if(!reuse) assert.ok(audit.findings.some(f=>/code-injection|code-inj|eval/.test(f.rule)), 'No real baseline eval finding');
    return audit;
  }
  async function download(button, filename) {
    const pending=page.waitForEvent('download');
    await button.click();
    const item=await pending;
    const destination=path.join(output,filename);
    await item.saveAs(destination);
    record.downloads.push({name:filename,suggested_filename:item.suggestedFilename()});
    return destination;
  }
  return {page,output,config,record,api,step,poll,settleStage,selectOption,upload,download,persist};
}
