import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';

export async function reviewRepair(h, language, audit) {
  const {page,api,step,settleStage,selectOption,download}=h;
  const module=language==='python'?'calc.py':'calc.js';
  await page.getByRole('button',{name:'查看AI 复审',exact:true}).click();
  const review=await step(language,'real-model-review-through-worker',async()=>{
    const pending=page.waitForResponse(r=>r.url().endsWith(`/audits/${audit.id}/review`)&&r.request().method()==='POST');
    await page.getByRole('button',{name:'启动统一复核',exact:true}).click();
    const response=await pending;
    assert.equal(response.status(),201);
    const created=await response.json();
    const completed=await settleStage(created.id);
    assert.equal(completed.status,'completed',completed.error);
    assert.ok(completed.model_calls.length>0);
    return {id:completed.id,status:completed.status,usage:completed.usage,model_assessments:completed.result?.assessment_counts};
  });
  const candidates=await api('GET',`/audits/${audit.id}/candidates`);
  const candidate=candidates.find(c=>c.stage_id===review.id && c.static_finding_id && c.location.file===module)
    ?? candidates.find(c=>c.stage_id===review.id && c.location.file===module);
  assert.ok(candidate,'Review produced no target-module candidate');
  await step(language,'unconfirmed-repair-rejected',()=>api('POST',`/audits/${audit.id}/repair`,{candidate_ids:[candidate.id]},409));
  await step(language,'source-evidence-and-confirmation-in-browser',async()=>{
    await page.getByText('人工补充源码证据',{exact:true}).click();
    await page.getByLabel('快照文件路径',{exact:true}).fill(module);
    await page.getByLabel('目标行',{exact:true}).fill('1');
    const pending=page.waitForResponse(r=>r.url().includes(`/audits/${audit.id}/evidence`)&&r.request().method()==='POST');
    await page.getByRole('button',{name:'读取并保存证据',exact:true}).click();
    const response=await pending;
    assert.equal(response.status(),201);
    const evidence=await response.json();
    assert.equal(evidence.kind,'code');
    assert.ok(evidence.content.includes('eval('));
    const stored=(await api('GET',`/audits/${audit.id}/evidence`)).find(e=>e.id===evidence.id);
    assert.equal(stored.snapshot_hash,audit.snapshot_hash);
    const cards=page.locator('article.candidate-card').filter({has:page.getByRole('heading',{name:candidate.title,exact:true})});
    const card=cards.first();
    await card.getByText('选择判断依据（源码或查询证据必选）',{exact:true}).click();
    const checkbox=card.locator(`[id="candidate-${candidate.id}-${evidence.id}"]`);
    if(!await checkbox.isChecked())await checkbox.click();
    await card.getByLabel('判断理由（至少 10 个字符）',{exact:true}).fill(`Workflow test actor verified ${module}: HTTP value reaches eval despite integer-only contract; existing arithmetic regression reproduces unsupported execution. This is derived-fixture evidence, not independent human gold.`);
    const deciding=page.waitForResponse(r=>r.url().endsWith(`/candidates/${candidate.id}/decisions`)&&r.request().method()==='POST');
    await card.getByRole('button',{name:'记录人工判断',exact:true}).click();
    const decided=await deciding;
    assert.equal(decided.status(),201,await decided.text());
    assert.equal((await decided.json()).status,'confirmed');
    return {candidate_id:candidate.id, evidence_id:evidence.id, model_assessment:candidate.model_assessment, actor_kind:'automated-workflow-test-not-independent-human'};
  });
  const repaired=await step(language,'real-model-repair-project-tests-and-codeql-rescan',async()=>{
    await page.getByRole('button',{name:'查看修复与报告',exact:true}).click();
    const checkbox=page.locator(`[id="repair-${audit.id}-${candidate.id}"]`);
    await checkbox.click();
    await page.getByLabel('允许修改的关联文件（每行一个；源码证据文件自动加入）',{exact:true}).fill(module);
    await selectOption('补丁验证配置',language==='python'?'隔离 pytest':'隔离 Node.js 测试');
    const pending=page.waitForResponse(r=>r.url().endsWith(`/audits/${audit.id}/repair`)&&r.request().method()==='POST');
    await page.getByRole('button',{name:'生成并验证修复 Diff',exact:true}).click();
    const response=await pending;
    assert.equal(response.status(),201);
    const stage=await settleStage((await response.json()).id);
    assert.equal(stage.status,'completed',stage.error);
    const repairs=await api('GET',`/audits/${audit.id}/repairs`);
    const repair=repairs.find(r=>r.stage_id===stage.id);
    assert.ok(repair);
    assert.equal(repair.status,'checks_passed',JSON.stringify(repair.validation));
    assert.ok(repair.changes.length>0);
    assert.ok(repair.changes.every(c=>c.file===module));
    await writeFile(path.join(h.output,`${language}-repair-receipt.json`),JSON.stringify(repair,null,2)+'\n');
    return repair;
  });
  await step(language,'accept-patch-and-download-diff',async()=>{
    const card=page.locator('article.candidate-card').filter({has:page.getByRole('heading',{name:`修复尝试 ${repaired.id.slice(0,8)}`,exact:true})});
    await card.getByLabel('补丁审阅理由',{exact:true}).fill('Workflow test actor reviewed the integer contract, project regression output, isolated diff and real CodeQL target rescan; original source remains immutable.');
    const pending=page.waitForResponse(r=>r.url().endsWith(`/repairs/${repaired.id}/accept`)&&r.request().method()==='POST');
    await card.getByRole('button',{name:'接受此补丁',exact:true}).click();
    const response=await pending;
    assert.equal(response.status(),200,await response.text());
    const diff=await download(card.getByRole('button',{name:'下载 Diff',exact:true}),`${language}-accepted.diff`);
    assert.ok((await readFile(diff,'utf8')).includes(module));
    return {repair_id:repaired.id,status:'accepted', original_snapshot_unchanged:true};
  });
  return {candidate,repair:repaired};
}
