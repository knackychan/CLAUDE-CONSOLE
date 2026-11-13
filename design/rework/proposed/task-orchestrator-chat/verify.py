"""File-only plan 62 QA. Uses installed Playwright/Edge, never a Console service."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import traceback
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
REF = ROOT.parent / 'supervision-operator' / 'index.html'
URL = (ROOT / 'index.html').as_uri()
SHOTS = ROOT / 'screenshots'
SHOTS.mkdir(exist_ok=True)
checks, errors, console, network, screenshots, scenarios, viewports = [], [], [], [], [], [], set()
header_measurements = []

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='msedge', headless=True)
    page = browser.new_page(viewport={'width':1510, 'height':1080}, reduced_motion='reduce')
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: console.append(m.text) if m.type == 'error' else None)
    def request(r):
        if r.url.startswith(('http:', 'https:', 'ws:', 'wss:')):
            network.append(r.url)
    page.on('request', request)
    page.route('http://**/*', lambda route: route.abort())
    page.route('https://**/*', lambda route: route.abort())
    page.clock.install()

    def size(w=1510, h=1080):
        page.set_viewport_size({'width':w, 'height':h})
        viewports.add(f'{w}x{h}')
    def load(query=''):
        page.goto(URL + ('?' + query if query else ''))
        page.evaluate('document.fonts.ready')
    def task(key='thumbnails', panel='overview', extra=''):
        load(f'view=task&task={key}&panel={panel}&stream=paused&{extra}')
    def click(selector):
        page.locator(selector).click()
    def controls():
        if page.locator('#review-controls').get_attribute('open') is None:
            click('#review-controls > summary')
    def step(n=1):
        controls()
        for _ in range(n):
            click('#advance')
        click('#review-controls > summary')
    def panel(name):
        click(f'button[data-panel="{name}"]')
    def shot(name):
        path = SHOTS / (name + '.png')
        page.screenshot(path=str(path))
        screenshots.append(str(path.relative_to(ROOT)).replace('\\', '/'))
    def body():
        return page.locator('main').inner_text()
    def overflow():
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'body overflow'
        assert page.locator('#window').evaluate('(e)=>e.scrollWidth<=e.clientWidth'), 'frame overflow'
        assert page.locator('#window').bounding_box()['y'] + page.locator('#window').bounding_box()['height'] <= page.viewport_size['height'] + 1
        for e in page.locator('.thread,.overview,.context,.step-transcript,.composer,.scroll,.tile-footer,.tile-telemetry,.tile-details-panel').all():
            if e.is_visible():
                assert e.evaluate('(e)=>e.scrollWidth<=e.clientWidth+1'), 'panel overflow: ' + str(e.get_attribute('class'))
        for e in page.locator('#window button, #window select, #window textarea').all():
            if not e.is_visible():
                continue
            bounds = e.bounding_box()
            assert bounds['width'] >= 24 and bounds['height'] >= 24, ('target size', e.inner_text())
    def run(check, description, test):
        size()
        first = len(screenshots)
        try:
            test()
            checks.append({'id':check,'status':'pass','procedure':description,'evidence':screenshots[first:] or ['verify.py: '+test.__name__]})
            print(check + ' PASS: ' + description, flush=True)
        except Exception as e:
            shot('failure-' + check)
            checks.append({'id':check,'status':'fail','procedure':description,'error':str(e),'trace':traceback.format_exc(),'evidence':screenshots[first:]})
            print(check + ' FAIL: ' + str(e), flush=True)

    def m01():
        load()
        assert page.locator('[data-card]').count() == 6
        assert page.locator('textarea,.orchestrator').count() == 0
        assert page.locator('#top-count').inner_text() == '3 for you'
        assert page.locator('[data-active]').inner_text() == '3'
        assert page.locator('.task-grid').first.evaluate('(e)=>getComputedStyle(e).gridTemplateColumns.split(" ").length') == 3
        assert page.locator('.project-rail').is_visible()
        assert page.locator('[data-preview-task]').count()==3
        assert page.locator('[data-task-telemetry]').count()==6
        for key,context,cost in [('thumbnails','6.4k est.','$0.49'),('captions','3.1k est.','$0.30'),('search','Unavailable','$0.38'),('import','4.8k est.','$0.42'),('audio','5.2k est.','$0.96'),('archive','2.7k est.','$0.42')]:
            telemetry=page.locator(f'[data-task-telemetry="{key}"]')
            assert telemetry.is_visible()
            assert telemetry.locator('.task-context b').inner_text()==context
            assert telemetry.locator('.task-spend b').inner_text()==cost
        assert page.locator('[data-task-telemetry="archive"] .task-context').inner_text().startswith('Orch ctx')
        gauge=page.locator('[data-task-telemetry="thumbnails"] .context-cells')
        assert gauge.locator('i').count()==15
        assert gauge.get_attribute('role')=='meter'
        assert gauge.get_attribute('aria-valuenow')=='6400'
        assert gauge.get_attribute('aria-valuemax')=='300000'
        assert float(gauge.locator('i').first.evaluate('(e)=>e.style.getPropertyValue("--fill")').strip('%'))==32
        unknown=page.locator('[data-task-telemetry="search"] .context-cells')
        assert unknown.get_attribute('role')=='img' and unknown.get_attribute('aria-valuenow') is None
        assert 'unavailable' in unknown.get_attribute('class')
        assert '$3.18' in page.locator('#usage-strip').inner_text()
        assert [page.locator(f'[data-strip-model="{model}"]').inner_text().splitlines()[1] for model in ['Astra','Opus','Sonnet']]==['78,000','108,000','214,000']
        footer=page.locator('.product-footer').bounding_box()['y']
        assert all(e.bounding_box()['y']+e.bounding_box()['height']<=footer for e in page.locator('[data-card]').all())
        tile=page.locator('[data-card="search"]')
        header=tile.locator('.tile-head').bounding_box()['height']
        chat=tile.locator('.tile-stream').bounding_box()['height']
        assert header<=90 and chat>=210
        header_measurements.append({'viewport':'1510x1080','header_before_px':123.1875,'header_after_px':header,'chat_before_px':172.84375,'chat_after_px':chat})
        details=tile.locator('.tile-details')
        assert details.get_attribute('open') is None
        details.locator('summary').click()
        assert 'Astra / Codex' in details.inner_text()
        assert '2 of 4' in details.inner_text() and '$0.38' in details.inner_text()
        assert tile.locator('.tile-head').bounding_box()['height']==header
        assert tile.locator('.tile-stream').bounding_box()['height']==chat
        shot('header-details-desktop-dark')
        page.keyboard.press('Escape')
        assert details.get_attribute('open') is None
        assert details.locator('summary').evaluate('(e)=>e===document.activeElement')
        details.locator('summary').click()
        click('.grid-head h2')
        assert details.get_attribute('open') is None
        click('[data-project-scope="Catalog Atlas"]')
        assert page.locator('[data-card]').count()==1
        assert page.locator('[data-card="thumbnails"]').is_visible()
        click('[data-project-scope="all"]')
        click('[data-grid-filter="running"]')
        assert page.locator('[data-card]').count()==3
        click('.grid-head [data-decisions]')
        assert page.locator('[data-card]').count()==3 and page.locator('[data-preview-task]').count()==0
        assert page.locator('textarea').count()==0
        task()
        assert page.locator('.orchestrator').bounding_box()['width'] == 330
        assert page.locator('#task-form').get_attribute('data-recipient') == 'T-031-orchestrator'
    run('M01','Operator usage strip, project rail, six live tiles, working filters, no global composer',m01)

    def m02():
        task()
        assert page.locator('[data-owner]').inner_text() == 'Astra / Codex · high'
        initial = page.locator('#orchestrator-thread').inner_text()
        for tab in ('step','context','overview'):
            panel(tab)
            assert page.locator('[data-owner]').inner_text() == 'Astra / Codex · high'
        click('[data-back]')
        click('[data-card="import"] .task-title')
        assert page.locator('[data-owner]').inner_text() == 'Opus / Claude Code · high'
        assert page.locator('#orchestrator-thread').inner_text() != initial
        assert page.locator('#task-form').get_attribute('data-recipient') == 'T-017-orchestrator'
    run('M02','Task identities and conversations differ; fixed ownership across views',m02)

    def m03():
        task()
        page.locator('#task-draft').fill('THUMBNAILS ONLY')
        panel('step')
        for n in ('1','4','3'):
            page.locator('#step-select').select_option(n)
            assert page.locator('#task-draft').input_value() == 'THUMBNAILS ONLY'
            assert page.locator('#task-form').get_attribute('data-recipient') == 'T-031-orchestrator'
        click('[data-back]')
        click('[data-card="import"] .task-title')
        page.locator('#task-draft').fill('IMPORT ONLY')
        for key,text in [('thumbnails','THUMBNAILS ONLY'),('import','IMPORT ONLY')]*2:
            click('[data-back]'); click(f'[data-card="{key}"] .task-title')
            assert page.locator('#task-draft').input_value() == text
        click('[data-back]')
        assert page.locator('textarea').count() == 0
    run('M03','Per-task drafts and recipients survive task/tab/step navigation',m03)

    def m04():
        for scenario in ('cli-unavailable','rate-limited','renewal'):
            task(extra='scenario='+scenario)
            assert page.locator('[data-owner]').inner_text() == 'Astra / Codex · high'
            before = page.evaluate('currentTask().session')
            step(2)
            assert page.locator('[data-owner]').inner_text() == 'Astra / Codex · high'
            if scenario=='renewal':
                assert page.evaluate('currentTask().session') != before
                assert 'New session, same orchestrator' in body()
            else:
                assert page.evaluate('currentTask().status') == 'held'
                assert 'disconnected' in body() if scenario=='cli-unavailable' else 'Reset time is unavailable' in body()
        task(extra='scenario=cli-unavailable')
        page.locator('#task-draft').fill('Keep this task draft')
        controls();page.locator('#connections').select_option('default');click('#review-controls > summary')
        assert page.locator('#task-draft').input_value()=='Keep this task draft'
        assert page.evaluate('currentTask().owner')=='astra'
        assert page.evaluate('currentTask().status')=='deciding'
    run('M04','Disconnected/limited owners wait; renewal retains model, CLI and effort',m04)

    def m05():
        load('view=new')
        assert page.locator('#owner-route option').count() == 3
        click('#new-task-form details summary')
        assert 'OpenCode · Disconnected' in page.locator('.availability').inner_text()
        page.locator('#goal').fill('A local sample goal')
        page.locator('#owner-route').select_option('astra')
        controls(); page.locator('#connections').select_option('codex-off'); click('#review-controls > summary')
        click('#start-task')
        assert 'explicit pick and draft are retained' in page.locator('#start-error').inner_text()
        assert page.locator('#goal').input_value() == 'A local sample goal'
        assert page.evaluate('state.tasks.length') == 6
        load('view=new')
        page.locator('#goal').fill('Recheck preview at Start')
        assert 'Astra' in page.locator('#assignment-preview').inner_text()
        page.evaluate("state.activity='astra-active'")
        click('#start-task')
        assert 'Opus' in page.locator('[data-owner]').inner_text()
        assert 'provisional preview changed' in page.locator('#feedback').inner_text()
        load('scenario=no-eligible-cli')
        page.locator('#goal').fill('Keep this draft')
        assert page.locator('#start-task').is_disabled()
        assert 'No eligible orchestrator' in body()
    run('M05','Eligible routes, explicit pick refusal, no-route draft, Start revalidation',m05)

    def m06():
        for activity,expected in [('idle','Astra'),('astra-active','Opus')]:
            load('view=new')
            page.locator('#goal').fill('Assign against '+activity)
            controls();page.locator('#activity').select_option(activity);click('#review-controls > summary')
            click('#start-task')
            assert expected in page.locator('[data-owner]').inner_text()
            assert page.evaluate("state.tasks.find(t=>t.id==='thumbnails').owner") == 'astra'
    run('M06','Global usage balances equal load; idle preference wins differing activity',m06)

    def m07():
        load('view=settings')
        page.locator('#effort').select_option('medium')
        click('#settings-form button')
        assert 'Existing tasks keep their effort' in page.locator('#settings-feedback').inner_text()
        assert page.evaluate('state.tasks.every(t=>t.effort==="high")')
        click('[data-view="new"]')
        page.locator('#goal').fill('Use the new default')
        click('#start-task')
        assert page.locator('[data-owner]').inner_text().endswith('medium')
        assert page.evaluate("resolvedEffort('astra','max')") == 'high'
        assert page.evaluate("resolvedEffort('opus','max')") == 'max'
    run('M07','New global effort affects future assignments and fixture adapter mappings only',m07)

    def m08():
        load('view=usage')
        expected={'Astra':(78000,63),'Opus':(108000,148),'Sonnet':(214000,107)}
        for model,(tokens,cents) in expected.items():
            row=page.locator(f'[data-model="{model}"]')
            assert int(row.get_attribute('data-tokens'))==tokens
            assert int(row.get_attribute('data-cents'))==cents
            row.locator('summary').click()
            assert all(label in row.inner_text() for label in ['Orchestration','Workers','Other sessions'])
        assert page.locator('[data-global-tokens]').get_attribute('data-global-tokens')=='400000'
        assert page.locator('[data-global-cents]').get_attribute('data-global-cents')=='318'
        assert page.evaluate('total(state.ledger.filter(r=>r.task!==null))')=={'tokens':381000,'cents':297,'unknown':0}
        for key,tokens,cents in [('import',54000,42),('audio',100000,96),('thumbnails',84000,49),('captions',39000,30),('search',48000,38),('archive',56000,42)]:
            page.evaluate('(id)=>{selected=id;view="task";panel="overview";render()}',key)
            subset=page.locator('[data-task-tokens]')
            assert int(subset.get_attribute('data-task-tokens'))==tokens
            assert int(subset.get_attribute('data-task-cents'))==cents
        before=page.evaluate('total()')
        page.evaluate('addUsage({...state.ledger[0]})')
        assert page.evaluate('total()')==before
    run('M08','Exact global/model/task/role ledger reconciliation and duplicate identity',m08)

    def m09():
        task(extra='scenario=renewal')
        step(3)
        assert page.evaluate('total()')=={'tokens':403000,'cents':321,'unknown':0}
        assert page.evaluate("total(state.ledger.filter(r=>r.model==='Astra'))")=={'tokens':81000,'cents':66,'unknown':0}
        assert page.evaluate("total(state.ledger.filter(r=>r.task==='T-031'))")=={'tokens':87000,'cents':52,'unknown':0}
        assert 'Orchestration 24,000 / $0.21' in body()
        assert 'Workers 63,000 / $0.31' in body()
        page.locator('.usage-subset').scroll_into_view_if_needed()
        shot('renewal-usage-confirmation-dark')
        load('view=tasks&scenario=renewal')
        telemetry=page.locator('[data-task-telemetry="thumbnails"]')
        assert telemetry.locator('.task-spend b').inner_text()=='$0.49'
        step(2)
        assert telemetry.locator('.task-spend b').inner_text()=='$0.52'
        assert telemetry.locator('.task-context b').inner_text()=='4.1k est.'
        gauge=telemetry.locator('.context-cells')
        assert gauge.get_attribute('aria-valuenow')=='4100'
        assert float(gauge.locator('i').first.evaluate('(e)=>e.style.getPropertyValue("--fill")').strip('%'))==20.5
        assert page.evaluate('state.tasks.find(t=>t.id==="thumbnails").steps[2].contextTokens')==72000
        assert '$3.21' in page.locator('#usage-strip').inner_text()
        load('scenario=unknown-usage')
        assert '400,000 processed tokens / $3.18 known subtotal' in body()
        assert '1 session with unavailable usage' in body()
        assert 'Unknown is not zero' in body()
        click('[data-view="tasks"]')
        assert page.locator('[data-task-telemetry="thumbnails"] .task-spend b').inner_text()=='$0.49 + unavailable'
        assert page.locator('[data-task-telemetry="thumbnails"] .task-context b').inner_text()=='Unavailable'
        click('[data-card="thumbnails"] .task-title');step()
        assert '1 session with unavailable usage' in body()
    run('M09','Renewal settles once with exact increments; unknown remains explicit',m09)

    def m10():
        task('audio')
        click('[data-action="approve"]')
        assert page.evaluate('currentTask().steps.length')==6
        assert page.evaluate('currentTask().steps[4].status')=='Running'
        assert page.evaluate('currentTask().steps[5].status')=='Planned'
        click('[data-back]')
        assert page.locator('[data-task-telemetry="audio"] .task-context b').inner_text()=='5.2k est.'
        click('[data-card="audio"] .task-title')
        page.evaluate('act("approve")')
        assert page.evaluate('currentTask().steps.length')==6
        assert 'Opus / Claude Code' in page.locator('[data-owner]').inner_text()
        step(3)
        assert page.evaluate('currentTask().steps[5].status')=='Planned'
        assert page.locator('[data-step="5"] button').inner_text()=='View result'
        step()
        assert page.evaluate('currentTask().steps[5].status')=='Running'
        assert page.locator('[data-step="6"] button').inner_text()=='Open step chat'
        page.locator('[data-step="6"] button').scroll_into_view_if_needed()
        shot('repair-step-actions-confirmation-dark')
        task('audio')
        click('[data-action="reject"]')
        assert page.evaluate('currentTask().workerRunning') is False
        assert page.evaluate('currentTask().steps.length')==4
        assert 'Proposal rejected' in body()
    run('M10','Repair approval starts one within-cap worker; later verify starts separately; reject holds',m10)

    def m11():
        task('archive')
        assert 'Ready for your acceptance' in body()
        assert page.evaluate('currentTask().status')=='ready'
        click('[data-action="accept"]')
        assert page.evaluate('currentTask().status')=='accepted'
        assert page.locator('#task-draft').count()==0
        task('archive',extra='scenario=stale-verification')
        assert page.locator('[data-action="accept"]').count()==0
        assert body().count('Needs recheck')>=2
        page.evaluate('act("accept")')
        assert page.evaluate('currentTask().status')!='accepted'
    run('M11','Current evidence awaits explicit acceptance; stale evidence cannot be accepted',m11)

    def m12():
        task(panel='context')
        assert all(s in body() for s in ['Included','Partially included','Available on demand','Not automatically included','Last decision context'])
        click('.context-details summary')
        assert all(s in body() for s in ['3.6 / 8 KiB','18.4 / 32 KiB','6 / 16 KiB','3 / 6','Estimated last decision context: 6.4k tokens'])
        before=page.evaluate('total()')
        click('[data-artifact="checkpoint"]')
        assert 'revision: 7' in page.locator('#dialog-body').inner_text()
        page.keyboard.press('Escape')
        assert page.evaluate('total()')==before
        for i,title in enumerate(['Original goal and acceptance criteria','Saved decisions','Accepted first-step handoff','Selected task facts','Older troubleshooting']):
            click(f'[data-artifact="source-{i}"]')
            assert title in page.locator('#dialog-title').inner_text()
            assert 'T-031' in page.locator('#dialog-title').inner_text()
            assert 'source-'+str(i) not in page.locator('#dialog-title').inner_text()
            assert len(page.locator('#dialog-body pre').inner_text())>60
            if i==0:
                assert 'prompt.md' in page.locator('#dialog-body').inner_text()
                assert 'Implement a bounded thumbnail cache' in page.locator('#dialog-body').inner_text()
                shot('source-inspection-confirmation-dark')
            page.keyboard.press('Escape')
        task(panel='context',extra='scenario=unknown-usage')
        click('.context-details summary')
        assert 'Last decision context: Unavailable' in body()
    run('M12','Scoped source manifest, inspection-only artifacts, KiB and separate token telemetry',m12)

    def m13():
        for scenario,text in [('checkpoint-error','previous valid checkpoint'),('context-overflow','No requirements were cut'),('uncertain','will not be replayed automatically')]:
            task(extra='scenario='+scenario)
            before=page.evaluate('({checkpoint:currentTask().checkpoint,steps:currentTask().steps.length})')
            step(3)
            assert text in body()
            assert page.evaluate('currentTask().status')=='held'
            assert page.evaluate('({checkpoint:currentTask().checkpoint,steps:currentTask().steps.length})')==before
            assert page.evaluate('currentTask().workerRunning') is False
    run('M13','Checkpoint failure, required overflow and uncertain effects preserve holds/evidence',m13)

    def m14():
        task('import')
        click('[data-suggest="Append the imported notes and keep all existing notes."]')
        assert page.evaluate('state.pending.length')==0
        assert page.locator('#task-draft').input_value().startswith('Append')
        click('#task-form button[type="submit"]')
        assert 'Queued' in body()
        assert 'Received by orchestrator' not in body()
        step()
        assert 'Received by orchestrator' in body()
        assert 'Delivered to step 03' not in body()
        page.locator('#task-draft').fill('Same-tick follow-up')
        page.keyboard.press('Control+Enter')
        step()
        assert 'Delivered to step 03' in body()
        assert page.locator('.composer .question,.composer [data-suggest]').count()==0
        assert page.locator('#task-form button[type=submit]').inner_text()=='Send'
        events=page.evaluate('currentTask().events.map(e=>({seq:e.seq,text:e.text,question:e.question}))')
        texts=[e['text'] for e in events]
        assert texts.index('Received by orchestrator')<texts.index('Same-tick follow-up')<texts.index('Delivered to step 03')
        assert next(e for e in events if e['text']=='Received by orchestrator')['question']=='notes-step-3'
        assert next(e for e in events if e['text']=='Delivered to step 03')['question']=='notes-step-3'
        assert [e['seq'] for e in events]==sorted(e['seq'] for e in events)
    run('M14','Question identity, queued submission, separate ordered receipt and worker delivery',m14)

    def m15():
        task(panel='step')
        assert page.locator('.step-transcript textarea').count()==0
        assert page.locator('textarea').count()==1
        page.locator('#task-draft').fill('Do not retarget')
        click('.readonly-footer [data-message]')
        assert page.locator('#task-draft').evaluate('(e)=>e===document.activeElement')
        assert page.locator('#task-draft').input_value()=='Do not retarget'
        assert page.evaluate('state.pending.length')==0
        size(340,760);task(panel='step')
        assert page.locator('#task-draft').is_hidden()
        click('.readonly-footer [data-message]')
        assert page.locator('#task-draft').is_visible()
        assert page.locator('#task-draft').evaluate('(e)=>e===document.activeElement')
    run('M15','Read-only worker inspection links to the sole unchanged orchestrator composer',m15)

    def m16():
        load()
        live=page.locator('[data-preview-task="thumbnails"]')
        tool=live.locator('.tool-call summary')
        tool.click();tool.focus()
        live.evaluate('(e)=>e.scrollTop=0')
        page.evaluate('window.liveTool=document.activeElement;advance();advance();advance()')
        assert page.evaluate('window.liveTool===document.activeElement')
        assert live.locator('.tool-call').first.get_attribute('open') is not None
        assert live.evaluate('(e)=>e.scrollTop')==0
        click('[data-follow="thumbnails"]')
        assert live.evaluate('(e)=>e.scrollHeight-e.scrollTop-e.clientHeight<2')
        size(900,760)
        task(panel='step')
        page.locator('#task-draft').fill('PRESERVE THIS DRAFT')
        tool=page.locator('.step-transcript .tool-call summary')
        tool.click();tool.focus()
        page.locator('#step-transcript').evaluate('(e)=>e.scrollTop=0')
        page.evaluate('window.retainedTool=document.activeElement')
        page.evaluate('window.retainedScroll=document.getElementById("step-transcript").scrollTop')
        page.evaluate('advance();advance();advance();advance();advance();advance()')
        assert page.evaluate('window.retainedTool===document.activeElement')
        assert page.locator('.step-transcript .tool-call').first.get_attribute('open') is not None
        assert page.locator('#task-draft').input_value()=='PRESERVE THIS DRAFT'
        assert page.locator('#step-transcript').evaluate('(e)=>e.scrollTop')==page.evaluate('window.retainedScroll')
        assert page.locator('#new-activity').is_visible()
        click('#new-activity')
        assert page.locator('#step-transcript').evaluate('(e)=>e.scrollHeight-e.scrollTop-e.clientHeight<2')
        controls();click('#playback');page.clock.run_for(1000);click('#playback');click('#review-controls > summary')
        tick=page.evaluate('state.tick');page.clock.run_for(3000);assert page.evaluate('state.tick')==tick
        panel('overview');panel('step')
        assert page.locator('.step-transcript .tool-call').first.get_attribute('open') is not None
    run('M16','Stream patches retain DOM focus, open tools, drafts and scroll; explicit follow/playback',m16)

    def m17():
        task(extra='scenario=paused')
        assert page.evaluate('currentTask().workerRunning') is True
        assert 'existing step 03 worker is still running' in body()
        step(2)
        assert page.evaluate('state.pending[0].phase')==0
        click('[data-action="resume"]');step(2)
        assert page.evaluate('state.pending[0].phase')==2
        click('[data-action="stop"]');click('[data-confirm-stop]')
        assert page.evaluate('currentTask().status')=='stopped'
        assert page.evaluate('currentTask().workerRunning') is False
        step(2);assert page.evaluate('currentTask().status')=='stopped'
        task(extra='scenario=budget-hold');step(2);assert '6 of 6' in body()
        task(extra='scenario=capacity');assert page.evaluate('currentTask().workerRunning') is False
        step(2);assert page.evaluate('currentTask().workerRunning') is True
        for filter_name in ('running','needs','empty-running'):
            load('view=tasks&scenario=capacity')
            if filter_name=='empty-running':click('[data-project-scope="Catalog Atlas"]')
            click(f'[data-grid-filter="{"running" if filter_name=="empty-running" else filter_name}"]')
            assert page.locator('[data-active]').inner_text()==('0' if filter_name=='empty-running' else '2')
            step(2)
            assert page.locator('[data-active]').inner_text()==('1' if filter_name=='empty-running' else '3')
            assert '3 running' in page.locator('[data-project-scope="all"]').inner_text()
            if filter_name!='needs':assert page.locator('[data-card="thumbnails"]').is_visible()
        task('archive',extra='scenario=accepted')
        assert page.locator('#task-draft').count()==0
        click('.composer-closed [data-action="reopen"]')
        assert page.locator('#task-draft').is_visible()
        assert page.locator('[data-owner]').inner_text()=='Opus / Claude Code · high'
        task(extra='scenario=delivery-uncertain')
        before=page.evaluate('currentTask().events.length')
        step(3)
        assert page.evaluate('currentTask().events.length')==before
        assert 'Delivery unconfirmed' in body()
        assert 'Received by orchestrator' not in body()
        task()
        page.locator('#task-draft').fill('Wait for this owner to reconnect')
        page.keyboard.press('Control+Enter')
        controls();page.locator('#connections').select_option('codex-off');click('#review-controls > summary')
        step(2);assert page.evaluate('state.pending[0].phase')==0
        controls();page.locator('#connections').select_option('default');click('#review-controls > summary')
        step();assert page.evaluate('state.pending[0].phase')==1
    run('M17','Pause keeps queue/running worker; Stop ends activity; capacity/caps/reopen are explicit',m17)

    def m18():
        names=list(page.evaluate('Object.keys(scenarioNames)'))
        for theme in ('dark','light'):
            for w,h in ((1510,1080),(340,760)):
                size(w,h)
                for scenario in names:
                    load(f'scenario={scenario}&theme={theme}&stream=paused')
                    overflow()
                    scenarios.append({'scenario':scenario,'theme':theme,'viewport':f'{w}x{h}','status':'pass'})
                    assert page.locator('.disclosure').is_visible()
                if w==1510:
                    for name,query in [('tasks','view=tasks'),('overview','view=task&task=thumbnails&panel=overview'),('step','view=task&task=thumbnails&panel=step'),('context','view=task&task=thumbnails&panel=context')]:
                        load(f'{query}&theme={theme}');overflow();shot(f'{name}-{w}-{theme}')
                else:
                    for name in ('orchestrator','step'):
                        task(panel=name,extra='theme='+theme);overflow();shot(f'{name}-{w}-{theme}')
                for name in ('new','settings','usage'):
                    load(f'view={name}&theme={theme}');overflow();shot(f'{name}-{w}-{theme}')
                load(f'view=tasks&scenario=unknown-usage&theme={theme}')
                overflow()
        for theme in ('dark','light'):
            size(900,900);task(extra='theme='+theme);overflow();shot('overview-900-'+theme)
            assert page.locator('.orchestrator').is_visible()
            assert page.locator('.overview').is_visible()
            size(400,760)
            for name in ('orchestrator','step'):
                task(panel=name,extra='theme='+theme);overflow();shot(f'{name}-400-{theme}')
        size()
        for scenario in ('question','proposal','ready','cli-unavailable','renewal','checkpoint-error'):
            load('scenario='+scenario)
            if scenario=='renewal':step()
            shot(scenario+'-desktop-dark')
        size(340,760)
        for scenario in ('question','checkpoint-error'):
            load('scenario='+scenario);overflow();shot(scenario+'-340-dark')
        task(panel='step')
        assert page.locator('#step-transcript').bounding_box()['height']>=100
        panel('orchestrator')
        submit=page.locator('#task-form button[type=submit]').bounding_box()
        assert submit['y']+submit['height']<=760
    run('M18','All 24 scenarios in both themes at desktop/340; full required capture and short-height matrix',m18)

    def m19():
        for theme in ('dark','light'):
            size(340,760);load('theme='+theme)
            details=page.locator('[data-card="thumbnails"] .tile-details')
            header=page.locator('[data-card="thumbnails"] .tile-head').bounding_box()['height']
            details.locator('summary').focus();page.keyboard.press('Enter')
            assert details.get_attribute('open') is not None
            assert page.locator('[data-card="thumbnails"] .tile-head').bounding_box()['height']==header
            assert page.locator('.tile-details-panel').first.bounding_box()['x']>=0
            assert page.locator('.tile-details-panel').first.bounding_box()['x']+page.locator('.tile-details-panel').first.bounding_box()['width']<=340
            overflow();shot('header-details-340-'+theme)
            page.keyboard.press('Tab')
            assert details.locator('.tile-details-panel').evaluate('(e)=>e===document.activeElement')
            page.keyboard.press('Escape')
            assert details.get_attribute('open') is None
        size()
        task(panel='context')
        click('[data-artifact="checkpoint"]')
        assert page.locator('#close-dialog').evaluate('(e)=>e===document.activeElement')
        page.keyboard.press('Tab')
        assert page.locator('#close-dialog').evaluate('(e)=>e===document.activeElement')
        page.keyboard.press('Escape')
        assert page.locator('[data-artifact="checkpoint"]').evaluate('(e)=>e===document.activeElement')
        page.locator('button[data-panel="context"]').focus()
        page.keyboard.press('ArrowLeft')
        assert page.locator('button[data-panel="step"]').get_attribute('aria-selected')=='true'
        assert page.locator('button[data-panel="step"]').evaluate('(e)=>e===document.activeElement')
        page.locator('#task-draft').fill('Draft survives Escape')
        page.keyboard.press('Escape')
        assert page.locator('#task-draft').input_value()=='Draft survives Escape'
        page.locator('#task-draft').focus();page.keyboard.press('Enter')
        assert '\n' in page.locator('#task-draft').input_value()
        page.locator('#task-draft').fill('   ');page.keyboard.press('Control+Enter')
        assert page.evaluate('state.pending.length')==0
        page.emulate_media(reduced_motion='reduce')
        assert page.evaluate('matchMedia("(prefers-reduced-motion: reduce)").matches')
        assert not page.evaluate('document.getAnimations().some(a=>a.playState==="running")')
        for w,h in ((1510,1080),(340,760)):
            size(w,h)
            for name in ('orchestrator','overview','step','context'):
                task(panel=name)
                page.evaluate('''const sizes=[...document.querySelectorAll('#window *')].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]);for(const [e,n] of sizes)e.style.fontSize=n*1.3+'px' ''')
                overflow();shot(f'text130-{name}-{w}-dark')
        size();task()
        for _ in range(12):page.keyboard.press('Tab')
        assert page.evaluate('document.activeElement.tagName')!='BODY'
    run('M19','Tab keys, focus trap/return, Escape/newline semantics, reduced motion and 130% text',m19)

    def m20():
        task()
        text='<img src="https://invalid.example/x" onerror="window.injected=true"> & <script>bad()</script>'
        page.locator('#task-draft').fill(text);page.keyboard.press('Control+Enter')
        assert page.locator('#orchestrator-thread img, #orchestrator-thread script').count()==0
        assert page.locator('#orchestrator-thread').inner_text().find(text)>=0
        assert page.evaluate('window.injected') is None
        load('view=new');page.locator('#goal').fill(text);click('#start-task')
        assert page.locator('#task-title').inner_text()==text
        assert page.locator('main img, main script').count()==0
        assert not errors,errors
        assert not console,console
        assert not network,network
        source=(ROOT/'app.js').read_text(encoding='utf-8')
        assert 'fetch(' not in source and 'XMLHttpRequest' not in source and 'WebSocket(' not in source
    run('M20','File-only browser, no HTTP/API/process actions or browser errors; escaped supplied text',m20)

    def m21():
        task();page.locator('#task-draft').fill('temporary')
        controls();click('#reset');click('#review-controls > summary')
        assert page.locator('[data-card]').count()==6
        assert page.evaluate('total()')=={'tokens':400000,'cents':318,'unknown':0}
        assert page.evaluate('state.tasks.every(t=>t.draft==="")')
        assert page.evaluate('state.effort')=='high'
        for query in ['view=tasks&theme=dark&stream=paused','view=task&task=thumbnails&panel=overview','view=task&task=thumbnails&panel=step&step=3&theme=light','view=task&task=thumbnails&panel=context&scenario=renewal']:
            load(query);assert page.evaluate('playing') is False
        load('view=task&task=thumbnails&panel=wrong&step=999&theme=wrong&stream=wrong')
        assert page.evaluate('panel')=='overview' and page.evaluate('viewedStep')==3
        load('view=bogus&task=missing&scenario=bogus')
        assert page.evaluate('view')=='tasks'
        assert page.locator('[data-card]').count()==6
        load();page.locator('.scroll').evaluate('(e)=>e.scrollTop=20')
        before=page.locator('.scroll').evaluate('(e)=>e.scrollTop')
        assert before>0
        click('[data-card="thumbnails"] .task-title');click('[data-back]')
        assert abs(page.locator('.scroll').evaluate('(e)=>e.scrollTop')-before)<2
        assert page.locator('[data-card="thumbnails"] .task-title').evaluate('(e)=>e===document.activeElement')
    run('M21','Reset fixtures/defaults/drafts, deterministic validated deep links and Tasks scroll/focus',m21)

    def m22():
        load('view=observed')
        assert page.locator('textarea,[data-owner]').count()==0
        assert 'no assigned orchestrator' in body()
        assert '10,000 processed tokens / $0.14' in body()
        assert page.evaluate("state.ledger.filter(r=>r.id==='u14').length")==1
        assert page.evaluate('total()')=={'tokens':400000,'cents':318,'unknown':0}
        shot('observed-desktop-dark')
    run('M22','Observed session remains read-only and its known usage contributes once',m22)
    browser.close()

result = {
    'executed_at_utc':datetime.now(timezone.utc).isoformat(),
    'scope':'Local mockup only; M-checks are not runtime B-check evidence.',
    'browser':'Installed Microsoft Edge / Playwright, headless file://',
    'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    'reference_sha256':hashlib.sha256(REF.read_bytes()).hexdigest(),
    'visual_base':'supervision-operator/index.html, latest user instruction',
    'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('index.html','app.js','style.css','reference-tokens.css','verify.py')},
    'header_measurements':header_measurements,
    'checks':checks,'page_errors':errors,'console_errors':console,'network_requests':network,
    'viewports':sorted(viewports),'scenario_coverage':scenarios,'screenshots':screenshots,
    'summary':{status:sum(c['status']==status for c in checks) for status in ('pass','fail','not-run')},
    'limitations':['No real CLI, provider, Console API, runtime persistence or native-window checks.','Visual approval remains with the user.']
}
(ROOT/'check-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result['summary']))
raise SystemExit(1 if result['summary']['fail'] else 0)
