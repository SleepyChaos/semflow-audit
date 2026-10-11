// Real Chromium interaction with dedicated synthetic terminal-state fixtures.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
const require = createRequire(new URL('../../frontend/package.json', import.meta.url));
const {chromium} = require('@playwright/test');
const output = path.resolve(process.argv[2]);
const root = path.resolve(import.meta.dirname, '../..');
const fixture = JSON.parse(await readFile(path.join(output, 'credentials.private.json'), 'utf8'));
const config = JSON.parse(await readFile(path.join(output, 'config.json'), 'utf8'));
async function verifyFreeze() {
  for (const [file, hash] of Object.entries(config.frontend_hashes)) {
    assert.equal(createHash('sha256').update(await readFile(path.join(root, file))).digest('hex'), hash);
  }
  assert.equal(createHash('sha256').update(await readFile(import.meta.filename)).digest('hex'), config.browser_script_sha256);
}
await verifyFreeze();
const checks = [];
const errors = [];
const responses = [];
const started = Date.now();
let browser;
let page;
async function check(name, fn) {
  try { await fn(); checks.push({name, status: 'passed'}); }
  catch (error) { checks.push({name, status: 'failed', error: String(error.message).slice(0, 700)}); }
}
try {
  browser = await chromium.launch({headless: true, ...(process.argv[3] ? {channel: process.argv[3]} : {})});
  page = await browser.newPage({viewport: config.viewports[0]});
  page.setDefaultTimeout(12000);
  page.on('pageerror', error => errors.push({kind: 'pageerror', message: String(error).slice(0, 600)}));
  page.on('console', msg => {if (['error', 'warning'].includes(msg.type())) errors.push({kind: msg.type(), message: msg.text().slice(0, 600)});});
  page.on('response', response => {if (response.url().includes('/api/') && response.status() >= 400) responses.push({url: response.url().split('?')[0], status: response.status()});});
  await check('protected route redirects to login', async () => {
    await page.goto(config.url);
    await page.waitForURL('**/login');
    await page.getByRole('heading', {name: '登录审计工作台', exact: true}).waitFor();
    assert.match(await page.title(), /登录/);
  });
  await check('login through real API renders workbench', async () => {
    await page.getByTestId('email-input').fill(fixture.email);
    await page.getByTestId('password-input').fill(fixture.password);
    await page.getByRole('button', {name: '登录', exact: true}).click();
    await page.getByRole('heading', {name: '审计工作台', exact: true}).waitFor();
    assert.equal(new URL(page.url()).pathname, '/');
    assert.ok((await page.locator('body').innerText()).length > 100);
    assert.equal(await page.locator('vite-error-overlay').count(), 0);
    await page.screenshot({path: path.join(output, 'desktop-workbench.png')});
  });
  await check('failed scan displays failure instead of zero findings success', async () => {
    await page.getByRole('button', {name: 'supplemental-gui-failed', exact: true}).click();
    await page.getByText('CodeQL 分支未完成', {exact: true}).waitFor();
    await page.getByText('Synthetic scanner failure: no successful empty result', {exact: true}).waitFor();
    assert.equal(await page.getByText('本次规则集未报告告警，不代表代码不存在漏洞。', {exact: true}).count(), 0);
    await page.screenshot({path: path.join(output, 'desktop-failure.png')});
  });
  await check('completed empty scan preserves uncertainty message', async () => {
    await page.getByRole('button', {name: 'supplemental-gui-completed', exact: true}).click();
    await page.getByText('本次规则集未报告告警，不代表代码不存在漏洞。', {exact: true}).waitFor();
  });
  await check('stage navigation and human confirmation gate', async () => {
    await page.getByRole('button', {name: '查看AI 复审', exact: true}).click();
    await page.getByRole('tab', {name: 'AI 复审', exact: true, selected: true}).waitFor();
    await page.getByRole('button', {name: '查看修复与报告', exact: true}).click();
    await page.getByText('暂无人工确认的缺陷。', {exact: true}).waitFor();
    await page.getByRole('button', {name: '查看RAG 规则', exact: true}).click();
    await page.getByRole('tab', {name: 'RAG 规则', exact: true, selected: true}).waitFor();
  });
  await check('wrong file extension rejected without upload', async () => {
    await page.getByLabel('选择代码包', {exact: true}).setInputFiles({name: 'bad.txt', mimeType: 'text/plain', buffer: Buffer.from('not a project')});
    await page.getByText('请选择不超过 20 MB 的 ZIP 代码包', {exact: true}).waitFor();
    assert.equal(await page.getByRole('button', {name: '开始审计', exact: true}).isDisabled(), true);
  });
  await check('language selection updates visible control state', async () => {
    await page.getByRole('radio', {name: 'JavaScript / TypeScript', exact: true}).click();
    assert.equal(await page.getByRole('radio', {name: 'JavaScript / TypeScript', exact: true}).isChecked(), true);
    await page.getByRole('button', {name: '刷新', exact: true}).click();
    await page.getByRole('button', {name: 'supplemental-gui-completed', exact: true}).waitFor();
  });
  await check('mobile workbench screenshot and viewport overflow', async () => {
    await page.setViewportSize(config.viewports[1]);
    await page.getByRole('heading', {name: '审计工作台', exact: true}).waitFor();
    await page.screenshot({path: path.join(output, 'mobile-workbench.png'), fullPage: true});
    const metrics = await page.evaluate(() => ({scroll: document.documentElement.scrollWidth, viewport: window.innerWidth}));
    assert.ok(metrics.scroll <= metrics.viewport + 1, JSON.stringify(metrics));
  });
  await check('mobile logout control remains visible', async () => {
    assert.equal(await page.getByRole('button', {name: '退出登录', exact: true}).isVisible(), true);
  });
  await check('desktop logout revokes local session and protects workbench', async () => {
    await page.setViewportSize(config.viewports[0]);
    await page.getByRole('button', {name: '退出登录', exact: true}).click();
    await page.waitForURL('**/login');
    await page.goto(config.url);
    await page.waitForURL('**/login');
  });
  await check('console health and API responses', async () => {
    assert.deepEqual(responses, []);
    assert.deepEqual(errors.filter(e => e.kind !== 'warning'), []);
  });
} catch (error) {
  checks.push({name: 'browser infrastructure', status: 'failed', error: String(error.message).slice(0, 700)});
} finally {
  if (page) await writeFile(path.join(output, 'last-dom.txt'), await page.locator('body').innerText().catch(() => 'unavailable'));
  if (browser) await browser.close();
  await verifyFreeze();
  await writeFile(path.join(output, 'report.json'), JSON.stringify({scope: config.scope, browser_path: config.browser_path, browser_channel: process.argv[3] ?? "bundled-chromium", browser_version: browser?.version(), seconds: (Date.now()-started)/1000, checks, console: errors, error_responses: responses, passed: checks.filter(c => c.status==='passed').length, failed: checks.filter(c => c.status==='failed').length, worker_started: false, model_calls: 0}, null, 2)+'\n');
}
process.exitCode = checks.some(c => c.status==='failed') ? 1 : 0;
