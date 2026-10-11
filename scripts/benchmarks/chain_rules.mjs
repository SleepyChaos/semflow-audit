import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';

export async function ruleChain(h,language,audit,input) {
  const {page,api,step,poll,settleStage,selectOption,upload,download}=h;
  await page.getByRole('button',{name:'查看RAG 规则',exact:true}).click();
  await step(language,'knowledge-import-and-real-bm25-retrieval',async()=>{
    await page.getByText('知识库管理与版本',{exact:true}).click();
    const marker=`chain_${language}_integer_eval_contract_20261009`;
    await page.getByLabel('资料标题',{exact:true}).fill(marker);
    await page.getByLabel('来源或文档引用',{exact:true}).fill('local:derived-chain-business-contract');
    await page.getByLabel('CodeQL语言库版本（规则生成按此过滤）',{exact:true}).fill(h.config.library_versions[language]);
    await page.getByLabel('资料许可证',{exact:true}).fill('self-authored-test-material');
    await page.getByLabel('资料正文（不会自动访问来源网址）',{exact:true}).fill(`${marker}: ${language} endpoint converts a signed integer string. Dynamic eval is outside this business contract. Review anchors enumerate eval-related syntax, including constants and shadowed calls; they are investigation locations, not proof of exploitable vulnerabilities. Use actual CodeQL library APIs and preserve target locations.`);
    const pending=page.waitForResponse(r=>r.url().endsWith('/knowledge/')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'导入知识',exact:true}).click();
    const response=await pending;
    assert.equal(response.status(),201,await response.text());
    const knowledge=await api('GET','/knowledge/');
    const own=knowledge.find(d=>d.title===marker&&!d.shared);
    assert.ok(own);
    assert.equal(own.provenance.trust,'user_supplied');
    const retrieved=await api('GET',`/knowledge/search?query=${encodeURIComponent(marker)}&language=${language}&mode=bm25&corpus=reference`);
    await writeFile(path.join(h.output,`${language}-retrieval-receipt.json`),JSON.stringify(retrieved,null,2)+'\n');
    assert.ok(JSON.stringify(retrieved).includes(marker),'BM25 did not return the new owned material');
    const capabilities=await api('GET','/knowledge/capabilities');
    if(capabilities.embedding_model) {
      const card=page.locator('article.candidate-card').filter({has:page.getByRole('heading',{name:marker,exact:true})});
      const indexing=page.waitForResponse(r=>r.url().endsWith(`/knowledge/${own.document_id}/index`)&&r.request().method()==='POST');
      await card.getByRole('button',{name:'建立向量索引',exact:true}).click();
      assert.equal((await indexing).status(),202);
      const indexed=await poll('/knowledge/',rows=>rows.some(d=>d.document_id===own.document_id&&(d.indexed_chunks===d.chunks||d.index_error)),180000);
      const document=indexed.find(d=>d.document_id===own.document_id);
      assert.equal(document.index_error,null);
      assert.equal(document.indexed_chunks,document.chunks);
      await writeFile(path.join(h.output,`${language}-embedding-receipt.json`),JSON.stringify(document,null,2)+'\n');
    } else {
      await api('POST',`/knowledge/${own.document_id}/index`,undefined,409);
    }
    await page.getByText('知识库管理与版本',{exact:true}).click();
    return {document_id:own.document_id, trust:own.provenance.trust,embedding_configured:Boolean(capabilities.embedding_model)};
  });
  const rule=await step(language,'real-rag-rule-generation-and-confirmation-interrupt',async()=>{
    await page.getByLabel('规则目标与覆盖缺口',{exact:true}).fill(`Generate a ${language} eval review anchor for this project. Enumerate built-in/global eval calls, aliases and local shadowed eval calls as investigation locations, including constant arguments. Purpose review_anchor does NOT claim vulnerabilities. Preserve actual call locations and use supported CodeQL APIs; no filename-only matching.`);
    await selectOption('独立规则测试集',`eval · ${language}-eval-review_anchor-v1`);
    await selectOption('规则生成策略','新查询');
    await page.getByLabel('相关源码路径（每行一个；选择已确认漏洞时可从关联证据自动读取）',{exact:true}).fill(language==='python'?'calc.py\napp.py':'calc.js\napp.js');
    const pending=page.waitForResponse(r=>r.url().endsWith(`/audits/${audit.id}/rule`)&&r.request().method()==='POST');
    await page.getByRole('button',{name:'检索知识并生成规则',exact:true}).click();
    const response=await pending;
    assert.equal(response.status(),201,await response.text());
    const stage=await settleStage((await response.json()).id);
    assert.equal(stage.status,'awaiting_confirmation',stage.error);
    assert.ok(stage.model_calls.length>0);
    const rules=await api('GET',`/rules/?language=${language}`);
    const rule=rules.find(r=>r.stage_id===stage.id);
    assert.ok(rule);
    assert.equal(rule.fixtures_approved,false);
    assert.ok(rule.retrieval.length>0);
    assert.equal(rule.purpose,'review_anchor');
    return rule;
  });
  await step(language,'unapproved-rule-publication-rejected',()=>api('POST',`/rules/${rule.id}/publish`,undefined,409));
  await step(language,'browser-fixture-approval-resumes-worker-and-holdout-validation',async()=>{
    const card=page.locator('article.candidate-card').filter({has:page.getByRole('heading',{name:rule.title,exact:true})}).first();
    const fixture=rule.fixtures;
    assert.ok(fixture.positive.expected.length>0);
    assert.equal(fixture.negative.expected.length,0);
    for(const item of fixture.positive.expected)assert.ok(fixture.positive.files[item.file].split('\n')[item.line-1]);
    await card.getByLabel('样本确认理由',{exact:true}).fill('Workflow test actor checked review-anchor semantics, positive/negative source and exact expected sink lines. Approval only authorizes real validation; it is not independent quality gold or an automatic publication decision.');
    const pending=page.waitForResponse(r=>r.url().endsWith(`/rules/${rule.id}/approve-fixtures`)&&r.request().method()==='POST');
    await card.getByRole('button',{name:'批准样本并运行真实验收',exact:true}).click();
    assert.equal((await pending).status(),200);
    const stage=await settleStage(rule.stage_id);
    assert.equal(stage.status,'completed',stage.error);
    const checked=await api('GET',`/rules/${rule.id}`);
    await writeFile(path.join(h.output,`${language}-rule-receipt.json`),JSON.stringify(checked,null,2)+'\n');
    assert.equal(checked.validation.status,'passed',JSON.stringify(checked.validation));
    assert.equal(checked.validation.independent_holdout.status,'passed',JSON.stringify(checked.validation.independent_holdout));
    assert.equal(checked.status,'validated',JSON.stringify(checked.validation));
    assert.ok(checked.validation.project_replay,'No real project replay receipt');
    return {rule_id:rule.id,generated:checked.validation.status,independent:checked.validation.independent_holdout.status,project:checked.validation.project_replay.status};
  });
  await step(language,'publish-test-owner-rule-and-download-query',async()=>{
    const card=page.locator('article.candidate-card').filter({has:page.getByRole('heading',{name:rule.title,exact:true})}).first();
    const pending=page.waitForResponse(r=>r.url().endsWith(`/rules/${rule.id}/publish`)&&r.request().method()==='POST');
    await card.getByRole('button',{name:'发布此版本',exact:true}).click();
    const response=await pending;
    assert.equal(response.status(),200,await response.text());
    await download(card.getByRole('button',{name:'下载查询',exact:true}),`${language}-published.ql`);
    return {id:rule.id,status:'published',owner_scope:'temporary-test-owner-only'};
  });
  await step(language,'published-rule-selected-in-new-real-upload-and-sarif',async()=>{
    const details=page.locator('details').filter({has:page.locator('summary').filter({hasText:'补充已发布规则（最多 4 个版本）'})}).first();
    if(!await details.evaluate(e=>e.open))await details.locator('summary').click();
    const checked=page.locator(`[id="upload-rule-${rule.id}"]`);
    if(!await checked.isChecked())await checked.click();
    const next=await upload(language,input.archive,`chain-${language}-supplement`,true);
    assert.ok(next.custom_rule_ids.includes(rule.id));
    assert.ok(next.findings.some(f=>f.origin==='baseline'));
    assert.ok(next.findings.some(f=>f.rule_version===rule.id),'No supplemental origin in actual SARIF result');
    await download(page.getByRole('button',{name:'下载 SARIF',exact:true}),`${language}-supplemented.sarif`);
    const sarif=JSON.parse(await readFile(path.join(h.output,`${language}-supplemented.sarif`),'utf8'));
    assert.ok(sarif.runs.length>0);
    await page.getByRole('button',{name:`chain-${language}-primary`,exact:true}).first().click();
    return {audit_id:next.id,published_rule_id:rule.id,baseline_and_supplemental:true};
  });
  return rule;
}
