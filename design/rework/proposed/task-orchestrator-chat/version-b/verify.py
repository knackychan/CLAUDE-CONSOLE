"""Local Version B browser checks. No Console service, provider or network access."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import traceback
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
URL = (ROOT / 'index.html').as_uri()
SHOTS = ROOT / 'screenshots'
SHOTS.mkdir(exist_ok=True)
results, errors, network, screenshots = [], [], [], []

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='msedge', headless=True)
    page = browser.new_page(viewport={'width': 1510, 'height': 1080}, reduced_motion='reduce')
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
    page.on('request', lambda request: network.append(request.url) if request.url.startswith(('http:', 'https:', 'ws:', 'wss:')) else None)
    page.route('http://**/*', lambda route: route.abort())
    page.route('https://**/*', lambda route: route.abort())
    page.clock.install()

    def load(query=''):
        page.goto(URL + ('?' + query if query else ''))
        page.evaluate('document.fonts.ready')

    def click(selector):
        page.locator(selector).click()

    def check(name, test):
        page.set_viewport_size({'width': 1510, 'height': 1080})
        try:
            test()
            results.append({'check': name, 'status': 'pass'})
            print('PASS ' + name, flush=True)
        except Exception as error:
            path = SHOTS / ('failure-' + str(len(results)) + '.png')
            page.screenshot(path=str(path))
            results.append({'check': name, 'status': 'fail', 'error': str(error), 'trace': traceback.format_exc()})
            print('FAIL ' + name + ': ' + str(error), flush=True)

    def assert_true(value, message='assertion failed'):
        assert value, message

    def snapshot(name):
        page.locator('h1:focus').evaluate_all('(items)=>items.forEach(e=>e.blur())')
        path = SHOTS / (name + '.png')
        page.screenshot(path=str(path))
        screenshots.append(str(path.relative_to(ROOT)))

    def overflow():
        issues = page.evaluate('''() => {
          const issues=[],frame=document.getElementById('window'),visible=e=>!!e.getClientRects().length;
          if(document.documentElement.scrollWidth>innerWidth)issues.push('page overflow');
          if(frame.scrollWidth>frame.clientWidth)issues.push('window overflow');
          if(frame.getBoundingClientRect().bottom>innerHeight+1)issues.push('window beyond viewport');
          for(const e of document.querySelectorAll('.b-task-workspace,.task-layout,.orchestrator,.task-content,.composer,.b-action-dock,.overview,.context,.step-header,.b-file-tabs'))
            if(visible(e)&&e.scrollWidth>e.clientWidth+1)issues.push('panel overflow: '+e.className);
          if([...document.querySelectorAll('#task-draft')].filter(visible).length>1)issues.push('multiple composers');
          for(const e of document.querySelectorAll('#window button,#window select,#window textarea')){
            if(!visible(e))continue;
            const box=e.getBoundingClientRect();
            if(box.width<24||box.height<24)issues.push('small target: '+(e.getAttribute('aria-label')||e.textContent));
          }
          return issues;
        }''')
        assert not issues, '; '.join(issues)

    def layout():
        load()
        assert page.locator('.b-project-dock').is_visible()
        assert page.locator('.b-needs [data-open]').count() == 3
        assert page.locator('#task-draft').count() == 1
        assert page.locator('#task-title').inner_text() == 'Cache product thumbnails'
        assert page.locator('.b-actionbar').is_visible()
        assert page.evaluate('total().tokens') == 400000
        assert page.evaluate('total().cents') == 318
        overflow()
        snapshot('workspace-desktop-dark')
    check('B01 · Project dock, pinned Needs you, single composer and shared accounting', layout)

    def draft_scope():
        load()
        page.locator('#task-draft').fill('Keep dimensions unchanged.')
        click('.b-needs [data-open="import"]')
        assert page.locator('#task-draft').input_value() == ''
        click('.b-projects [data-open="thumbnails"]')
        assert page.locator('#task-draft').input_value() == 'Keep dimensions unchanged.'
        click('[data-step-open="3"]')
        assert page.locator('#task-form').get_attribute('data-recipient') == 'T-031-orchestrator'
        click('[data-b-file-tab="received"]')
        assert page.locator('#task-form').get_attribute('data-recipient') == 'T-031-orchestrator'
    check('B02 · Draft isolation and worker inspection never retargets messages', draft_scope)

    def question():
        load('scenario=question')
        click('[data-b-action="answer-append"]')
        assert page.evaluate('state.pending[0].phase') == 0
        assert page.evaluate('currentTask().status') == 'question'
        page.evaluate('advance()')
        assert page.evaluate('state.pending[0].phase') == 1
        page.evaluate('advance()')
        assert page.evaluate('state.pending[0].phase') == 2
        assert page.evaluate('currentTask().status') == 'running'
        assert page.locator('.b-decision').count() == 0
    check('B03 · Answer, orchestrator receipt and worker delivery remain separate', question)

    def proposal():
        load('scenario=proposal')
        owner = page.evaluate('currentTask().owner')
        click('.b-decision [data-action="approve"]')
        assert page.evaluate('currentTask().steps.length') == 6
        assert page.evaluate('currentTask().status') == 'running'
        assert page.evaluate('currentTask().owner') == owner
        page.evaluate('advance();advance();advance()')
        assert page.evaluate('currentTask().status') == 'deciding'
        page.evaluate('advance()')
        assert page.evaluate('currentTask().steps[5].status') == 'Running'
        load('scenario=proposal')
        click('.b-decision [data-action="reject"]')
        assert page.evaluate('currentTask().status') == 'held'
    check('B04 · Proposal approval, rejection and fresh verification gates', proposal)

    def plan():
        load('scenario=planned')
        assert page.evaluate('currentTask().owner') is None
        assert page.locator('#task-draft').count() == 0
        click('[data-b-action="edit-plan"]')
        page.locator('#b-plan').fill('Inspect the cache\nVerify cache behavior')
        click('#b-plan-form [type="submit"]')
        assert page.evaluate('currentTask().steps.length') == 2
        click('[data-b-action="edit-prompt"]')
        page.locator('#b-prompt').fill('Preserve dimension-aware caching.')
        click('#b-prompt-form [type="submit"]')
        assert page.evaluate('currentTask().goal') == 'Preserve dimension-aware caching.'
        click('[data-b-action="start"]')
        owner = page.evaluate('currentTask().owner')
        assert owner in ['astra', 'opus']
        assert page.evaluate('currentTask().workerRunning') is False
        page.evaluate('advance()')
        assert page.evaluate('currentTask().workerRunning') is True
        assert page.evaluate('currentTask().owner') == owner
        load('scenario=plan-approval')
        assert page.evaluate('currentTask().workerRunning') is False
        click('[data-b-action="confirm-plan"]')
        assert page.evaluate('currentTask().workerRunning') is True
    check('B05 · Proposed plan editing, first assignment and explicit plan confirmation', plan)

    def holds():
        load('scenario=model-approval')
        owner = page.evaluate('currentTask().owner')
        click('[data-b-action="worker-fable"]')
        assert 'unavailable' in page.locator('#dialog-title').inner_text()
        assert page.evaluate('currentTask().workerRunning') is False
        click('#close-dialog')
        click('[data-b-action="worker-opus"]')
        assert page.evaluate('currentTask().steps[3].route') == 'opus'
        assert page.evaluate('currentTask().owner') == owner
        load('scenario=failed-twice')
        assert page.locator('.b-decision button[disabled]').count() == 1
        assert page.evaluate('currentTask().workerRunning') is False
        assert 'cancellation' not in page.locator('.overview .criteria').inner_text().lower()
        click('[data-b-action="see-failure"]')
        assert page.evaluate('viewedStep') == 4
        assert 'retained entries exceed' in page.locator('#step-transcript').inner_text() or page.locator('#step-transcript .tool-call').count() == 1
    check('B06 · Scarce-model hold, worker-only alternative and bounded failure recovery', holds)

    def acceptance():
        load('scenario=ready')
        assert page.evaluate('currentTask().status') == 'ready'
        click('.b-decision [data-action="accept"]')
        assert page.evaluate('currentTask().status') == 'accepted'
        assert page.locator('#task-draft').count() == 0
        click('.b-decision [data-action="reopen"]')
        assert page.evaluate('currentTask().status') == 'held'
        load('scenario=stale-verification')
        assert page.locator('[data-action="accept"]').count() == 0
    check('B07 · Ready, accepted, explicit reopening and stale-evidence refusal', acceptance)

    def pause_stop():
        load()
        click('.b-actionbar [data-action="pause"]')
        assert page.evaluate('currentTask().status') == 'paused'
        assert page.evaluate('currentTask().workerRunning') is True
        click('.b-decision [data-action="resume"]')
        click('.b-actionbar [data-action="stop"]')
        click('[data-confirm-stop]')
        assert page.evaluate('currentTask().status') == 'stopped'
        assert page.evaluate('currentTask().workerRunning') is False
    check('B08 · Pause keeps the worker; Stop ends it and retains history', pause_stop)

    def artifacts():
        load('view=task&task=thumbnails&panel=step&step=3')
        click('[data-b-file-tab="received"]')
        assert 'Received assignment' in page.locator('.b-step-artifact').inner_text()
        click('[data-b-file-tab="handoff"]')
        assert 'No saved handoff' in page.locator('.b-step-artifact').inner_text()
        click('[data-b-prev]')
        click('[data-b-file-tab="handoff"]')
        assert 'Saved step handoff' in page.locator('.b-step-artifact').inner_text()
        click('[data-b-file-tab="files"]')
        click('[data-b-file] >> nth=0')
        assert page.locator('#inspector').is_visible()
        click('#close-dialog')
        click('[data-b-file-tab="chat"]')
        page.evaluate('advance()')
        assert page.locator('#step-transcript').is_visible()
    check('B09 · Chat, Received, Handoff, Files and previous/next step inspection', artifacts)

    def autonomy():
        load('scenario=question')
        click('[data-b-action="rules"]')
        assert 'Pending questions' in page.locator('#dialog-body').inner_text()
        click('#close-dialog')
        click('[data-b-mode="Auto"]')
        assert page.evaluate('currentTask().mode') == 'Auto'
        assert page.evaluate('currentTask().status') == 'question'
        assert page.evaluate('currentTask().answerQueued || false') is False
        owner = page.evaluate('currentTask().owner')
        click('[data-view="settings"] >> nth=0')
        page.locator('#effort').select_option('low')
        click('#settings-form [type="submit"]')
        assert page.evaluate('state.tasks.find(t=>t.id==="import").effort') == 'high'
        assert page.evaluate('state.tasks.find(t=>t.id==="import").owner') == owner
    check('B10 · Autonomy does not approve pending decisions; effort defaults are prospective', autonomy)

    def observed():
        load('view=observed')
        assert page.locator('textarea').count() == 0
        assert 'Read-only' in page.locator('main').inner_text()
        click('[data-b-action="fork-verify"]')
        assert page.evaluate('view') == 'new'
        assert 'Verify' in page.locator('#goal').input_value()
        before = page.evaluate('state.tasks.length')
        click('#new-task-form [type="submit"]')
        assert page.evaluate('state.tasks.length') == before + 1
        assert page.evaluate('currentTask().owner') in ['astra', 'opus']
    check('B11 · Observed session is read-only; a fork starts as a separate task draft', observed)

    def utilities():
        load()
        for key in ['folder','terminal','handoff']:
            click('.b-utility [data-b-action="'+key+'"]')
            assert page.locator('#dialog-body').inner_text().strip()
            click('#close-dialog')
        click('.b-utility [data-b-action="delete"]')
        assert 'unavailable' in page.locator('#dialog-title').inner_text()
        load('scenario=planned')
        click('.b-utility [data-b-action="delete"]')
        click('[data-b-action="confirm-delete"]')
        assert page.evaluate('state.tasks.some(t=>t.id==="thumbnails")') is False
        assert page.evaluate('view') == 'tasks'
    check('B12 · Utility previews, protected deletion and retained usage ledger', utilities)

    def renewal():
        load('scenario=renewal&panel=context&view=task&task=thumbnails')
        owner = page.evaluate('currentTask().owner')
        page.evaluate('advance()')
        assert page.evaluate('currentTask().owner') == owner
        assert page.evaluate('total().tokens') == 403000
        assert page.evaluate('total().cents') == 321
        page.evaluate('advance()')
        assert page.evaluate('total().tokens') == 403000
        load('scenario=unknown-usage')
        assert 'unavailable' in page.locator('#usage-strip').inner_text()
    check('B13 · Context renewal retains owner and counts once; unknown usage stays unknown', renewal)

    def stream_integrity():
        load()
        click('#orchestrator-thread .tool-call summary')
        page.locator('#task-draft').fill('Preserve this draft')
        page.evaluate('advance();advance();advance()')
        assert page.locator('#task-draft').input_value() == 'Preserve this draft'
        assert page.locator('#task-draft').evaluate('(e)=>e===document.activeElement')
        assert page.locator('#orchestrator-thread .tool-call').get_attribute('open') is not None
        page.locator('.b-projects [data-open="thumbnails"]').focus()
        page.evaluate('advance()')
        assert page.locator('.b-projects [data-open="thumbnails"]').evaluate('(e)=>e===document.activeElement')
        click('[data-step-open="3"]')
        click('[data-b-file-tab="files"]')
        page.evaluate('advance()')
        assert page.locator('.b-step-artifact').is_visible()
    check('B14 · Stream updates preserve draft, focus, expanded tools and artifact view', stream_integrity)

    def keyboard():
        load()
        page.locator('#tab-overview').focus()
        page.keyboard.press('ArrowRight')
        assert page.evaluate('panel') == 'step'
        page.keyboard.press('Escape')
        assert page.evaluate('panel') == 'overview'
        button = page.locator('.b-utility [data-b-action="folder"]')
        button.focus()
        page.keyboard.press('Enter')
        assert page.locator('#inspector').is_visible()
        page.keyboard.press('Escape')
        assert button.evaluate('(e)=>e===document.activeElement')
        assert page.evaluate('matchMedia("(prefers-reduced-motion: reduce)").matches')
    check('B15 · Keyboard tabs, step escape, dialog focus return and reduced motion', keyboard)

    def drawer():
        page.set_viewport_size({'width':900,'height':960})
        load()
        assert not page.locator('.b-project-dock').is_visible()
        click('.b-breadcrumb [data-b-action="toggle-dock"]')
        assert page.locator('.b-project-dock').is_visible()
        click('.b-needs [data-open="import"]')
        assert not page.locator('.b-project-dock').is_visible()
        assert page.evaluate('selected') == 'import'
        click('.b-breadcrumb [data-b-action="toggle-dock"]')
        page.keyboard.press('Escape')
        assert not page.locator('.b-project-dock').is_visible()
        overflow()
    check('B19 · Project drawer opens, switches tasks and closes with Escape', drawer)

    def matrix():
        scenarios = page.evaluate('Object.keys(scenarioNames)')
        for scenario in scenarios:
            load('scenario='+scenario)
            overflow()
            if page.evaluate('view') == 'task':
                page.evaluate('advance()')
                overflow()
        for width in [320,340,375,400,414,768,900,1510]:
            for theme in ['dark','light']:
                page.set_viewport_size({'width':width,'height':812 if width<768 else 960})
                for scenario in ['worker-running','question','proposal','planned','plan-approval','model-approval','failed-twice','ready','observed','long-content']:
                    load('scenario='+scenario+'&theme='+theme)
                    overflow()
                for view in ['tasks','new','settings','usage']:
                    load('view='+view+'&theme='+theme)
                    overflow()
                if width in [340,375,900,1510]:
                    load('scenario=question&theme='+theme)
                    snapshot(f'question-{width}-{theme}')
                    load('view=task&task=thumbnails&panel=step&theme='+theme)
                    snapshot(f'step-{width}-{theme}')
        page.set_viewport_size({'width':340,'height':760})
        load('scenario=question')
        overflow()
        assert page.locator('#task-draft').bounding_box()['height'] >= 40
        assert page.locator('.composer button[type=submit]').is_visible()
        assert page.locator('#orchestrator-thread').bounding_box()['height'] >= 140, 'conversation is contained but not readable'
    check('B16 · All scenarios; both themes at 320/340/375/400/414/768/900/1510; short window', matrix)

    def state_captures():
        for scenario in ['planned','plan-approval','model-approval','failed-twice','proposal','ready','observed']:
            load('scenario='+scenario)
            snapshot(scenario+'-desktop-dark')
        load('theme=light')
        snapshot('workspace-desktop-light')
        load('view=tasks')
        snapshot('tasks-desktop-dark')
        load('view=task&task=thumbnails&panel=context')
        snapshot('context-desktop-dark')
    check('B17 · State and page evidence captures', state_captures)
    check('B18 · No browser errors or network requests', lambda: assert_true(not errors and not network, repr({'errors':errors,'network':network})))
    browser.close()

report = {'timestamp_utc':datetime.now(timezone.utc).isoformat(),'entry':'index.html','checks':results,'browser_errors':errors,'network_requests':network,'screenshots':screenshots,'source_sha256':{str(path.relative_to(ROOT.parent)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [ROOT.parent/'app.js',ROOT.parent/'style.css',ROOT/'version-b.js',ROOT/'version-b.css']}}
(ROOT/'check-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
passed=sum(result['status']=='pass' for result in results)
print(f'{passed}/{len(results)} checks passed; {len(errors)} browser errors; {len(network)} network requests',flush=True)
raise SystemExit(0 if passed==len(results) else 1)
