import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/api/client.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source.replaceAll('import.meta.env', '({BASE_URL:"/",VITE_API_BASE:""})'), {
  compilerOptions: { target: ts.ScriptTarget.ES2023, module: ts.ModuleKind.ESNext },
}).outputText
const { ApplyGuardApiClient, setActiveScenario } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)

test('recorded demos never read private drafts or depend on a backend', async (t) => {
  t.mock.method(globalThis, 'fetch', async (url) => {
    assert.match(url, /^\/prerecorded\/(unsupported_block|timeout_fallback)\.json$/)
    return new Response(await readFile(new URL(`../public${url}`, import.meta.url), 'utf8'))
  })
  globalThis.window = { location: { origin: 'http://localhost' } }
  t.after(() => { delete globalThis.window })
  const client = new ApplyGuardApiClient()
  client.getResumeDraft = async () => { throw new Error('Demo must not request a private draft') }
  for (const scenario of ['prerecorded_block', 'prerecorded_fallback']) {
    setActiveScenario(scenario)
    const result = await client.runWorkflow('')
    assert.ok(result.data?._prerecorded)
    assert.ok(result.data.parsed_jd.source_text)
  }
  setActiveScenario('error')
  assert.equal((await client.runWorkflow('')).error.code, 'DEMO_BACKEND_UNAVAILABLE')
  setActiveScenario('live')
})

test('health checks reject HTML, wrong services and unavailable backends', async (t) => {
  globalThis.window = { location: { origin: 'http://localhost' } }
  t.after(() => { delete globalThis.window })
  let payload = { status: 'ok', service: 'applyguard-foundation', version: '1.0.0' }
  t.mock.method(globalThis, 'fetch', async (_url, options) => {
    assert.ok(options.signal instanceof AbortSignal)
    assert.equal(options.cache, 'no-store')
    if (payload === null) throw new TypeError('Failed to fetch')
    return new Response(typeof payload === 'string' ? payload : JSON.stringify(payload))
  })
  const client = new ApplyGuardApiClient()
  assert.equal((await client.getHealth()).data.status, 'ok')
  for (const invalid of ['<html>Vite fallback</html>', {status:'ok',service:'other-app'}]) {
    payload = invalid
    assert.equal((await client.getHealth()).error.code, 'INVALID_HEALTH')
  }
  payload = null
  assert.equal((await client.getHealth()).error.code, 'NETWORK_ERROR')
})

test('explicit verification requires a fresh backend receipt for the submitted text', async t => {
  globalThis.window = {location: {origin: 'http://localhost'}}
  t.after(() => { delete globalThis.window })
  const claims = [{claim_id: 'one', text: 'Designed a test.'}]
  const workflow = {parsed_jd: {source_text:'Test engineer'}, grounding: {run_id:'previous'}, local_only:false}
  const valid = {resume_claims: claims, claim_verification: [{claim_id:'one'}], grounding: {mode:'sag_atomic',
    operation:'verify', fresh_atomic:true, run_id:'new', results:{one:{original_text:claims[0].text}}}}
  let payload = valid
  let status = 200
  t.mock.method(globalThis, 'fetch', async (_url, options) => {
    assert.equal(JSON.parse(options.body).fresh_atomic, true)
    if (payload instanceof Error) throw payload
    return new Response(typeof payload === 'string' ? payload : JSON.stringify(payload), {status})
  })
  const client = new ApplyGuardApiClient()
  const submit = () => client.reverifyWorkflow(workflow, claims, null, 'sag_atomic')
  assert.equal((await submit()).data.grounding.run_id, 'new')
  for (payload of ['', '<html>Wrong service</html>', {}, {...valid,grounding:{...valid.grounding,run_id:'previous'}},
    {...valid,grounding:{...valid.grounding,operation:'polish'}}, {...valid,grounding:{...valid.grounding,results:{}}}]) {
    assert.equal((await submit()).error.code, 'INVALID_VERIFICATION')
  }
  payload = new TypeError('Failed to fetch')
  assert.equal((await submit()).error.code, 'NETWORK_ERROR')
  status = 503
  payload = '<html>Unavailable</html>'
  assert.match((await submit()).error.message, /503/)
})
