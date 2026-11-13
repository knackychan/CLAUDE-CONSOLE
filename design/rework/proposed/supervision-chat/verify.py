"""File-only mock QA. Uses installed Edge and Playwright; no Console service."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).parent
URL=(ROOT/'index.html').as_uri()
SHOTS=ROOT/'screenshots'
SHOTS.mkdir(exist_ok=True)
errors,network,checks=[],[],[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1510,'height':1080},reduced_motion='reduce')
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:network.append(r.url) if r.url.startswith(('http:','https:')) else None)
    page.clock.install()
    def load(q=''):
        page.goto(URL+q)
        page.evaluate('document.fonts.ready')
    def shot(name):
        page.screenshot(path=str(SHOTS/(name+'.png')),full_page=True)
    def tab(view):
        page.locator('[data-task-view="'+view+'"]').click()
    def play(ms):
        page.locator('#playback').click()
        page.clock.run_for(ms)
        page.locator('#playback').click()
    def no_overflow():
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert page.locator('main').evaluate('(e)=>e.scrollWidth<=e.clientWidth')
        for node in page.locator('.overview-panel,.chat-transcript,.task-compose').all():
            assert node.evaluate('(e)=>e.scrollWidth<=e.clientWidth'), node.get_attribute('class')

    load('?stream=paused')
    assert page.locator('[data-card]').count()==6
    assert page.locator('.task-grid').evaluate('(e)=>getComputedStyle(e).gridTemplateColumns.split(" ").length')==2
    page.locator('#global-draft').fill('GLOBAL DRAFT STAYS GLOBAL')
    page.locator('[data-card="thumbnails"] .task-title').click()
    assert page.locator('[data-task-view="overview"]').get_attribute('aria-pressed')=='true'
    assert page.locator('.overview-panel').count()==1
    assert page.locator('.chat-layout,.task-thread,.step-peek').count()==0
    assert page.locator('#task-composer textarea').count()==0
    assert page.locator('[data-overview-step]').count()==5
    page.locator('[data-overview-step="3"] button').click()
    assert page.locator('[data-task-view="chat"]').get_attribute('aria-pressed')=='true'
    assert page.locator('.overview-panel,.step-detail,.task-thread').count()==0
    assert '03 · Implement cache' in page.locator('#step-chat-heading').inner_text()
    assert page.locator('#task-form').get_attribute('data-recipient')=='task-thumbnails-step-3-guidance'
    assert page.locator('[data-event="brief"]').inner_text().startswith('You')
    assert page.locator('.chat-transcript .tool-call').count()==1
    page.locator('#task-draft').fill('THUMBNAILS STEP 3 DRAFT')
    tab('overview')
    assert page.locator('#task-composer textarea').count()==0
    tab('chat')
    assert page.locator('#task-draft').input_value()=='THUMBNAILS STEP 3 DRAFT'
    page.locator('#step-select').select_option('1')
    assert page.locator('#task-composer textarea').count()==0
    assert 'Completed step · read-only' in page.locator('#task-composer').inner_text()
    page.locator('#step-select').select_option('4')
    assert 'has not started' in page.locator('#step-transcript').inner_text()
    assert page.locator('#task-composer textarea').count()==0
    page.locator('#step-select').select_option('3')
    assert page.locator('#task-draft').input_value()=='THUMBNAILS STEP 3 DRAFT'
    assert page.locator('#global-draft').input_value()=='GLOBAL DRAFT STAYS GLOBAL'
    checks.append('PASS: explicit task overview and step chat; no stacked duplicate conversations; per-step recipient; current/historical/planned states; separate drafts across tabs and steps')

    page.emulate_media(reduced_motion='no-preference')
    page.locator('#playback').click()
    page.clock.run_for(4000)
    assert 'bounded eviction' in page.locator('[data-event="implementation"] [data-field="text"]').inner_text()
    assert page.locator('[data-event="implementation"] .spinning').evaluate('(e)=>getComputedStyle(e).animationName')=='chat-spin'
    read=page.locator('[data-event="read"] summary')
    read.click()
    read.focus()
    page.clock.run_for(5000)
    assert read.evaluate('(e)=>e===document.activeElement')
    assert page.locator('[data-event="read"] details').get_attribute('open') is not None
    assert page.locator('[data-event="test"] .spinning').count()==1
    assert page.locator('[data-event="implementation"] .spinning').count()==0
    assert 'npm test -- thumbnailCache' in page.locator('[data-event="test"] code').inner_text()
    assert page.locator('#task-draft').input_value()=='THUMBNAILS STEP 3 DRAFT'
    assert page.locator('#global-draft').input_value()=='GLOBAL DRAFT STAYS GLOBAL'
    page.locator('#step-transcript').evaluate('(e)=>e.scrollTop=0')
    page.clock.run_for(8000)
    assert page.locator('#step-transcript').evaluate('(e)=>e.scrollTop')==0
    ids=page.locator('.chat-inner > [data-event]').evaluate_all('(es)=>es.map(e=>e.dataset.event)')
    assert ids.index('read')<ids.index('implementation')<ids.index('edit')<ids.index('test-intro')<ids.index('test')<ids.index('diff-intro')<ids.index('diff')
    page.locator('#playback').click()
    before=page.locator('.chat-inner').inner_text()
    page.clock.run_for(4000)
    assert page.locator('.chat-inner').inner_text()==before
    assert page.locator('.chat-inner .spinning').evaluate('(e)=>getComputedStyle(e).animationPlayState')=='paused'
    page.emulate_media(reduced_motion='reduce')
    assert page.locator('.chat-inner .spinning').evaluate('(e)=>getComputedStyle(e).animationName')=='none'
    checks.append('PASS: chronological streamed messages and inline command/results; active spinner transfer; pause/reduced motion; tool expansion, keyboard focus, reader scroll and drafts survive updates')

    page.locator('#task-form button[type="submit"]').click()
    assert 'THUMBNAILS STEP 3 DRAFT' in page.locator('#step-transcript').inner_text()
    assert 'Guidance queued' in page.locator('#step-transcript').inner_text()
    page.get_by_role('button',name='Back to dashboard',exact=True).click()
    assert page.locator('[data-card="thumbnails"] .task-title').evaluate('(e)=>e===document.activeElement')
    page.locator('#main-scroll').evaluate('(e)=>e.scrollTop=430')
    scroll=page.locator('#main-scroll').evaluate('(e)=>e.scrollTop')
    page.locator('[data-card="thumbnails"] .task-title').click()
    page.get_by_role('button',name='Back to dashboard',exact=True).click()
    assert abs(page.locator('#main-scroll').evaluate('(e)=>e.scrollTop')-scroll)<2
    page.locator('[data-card="import"] [data-question]').click()
    assert page.locator('#question-form').get_attribute('data-recipient')=='task-import-question-step3'
    page.locator('#question-draft').fill('QUESTION DRAFT: append and retain notes')
    tab('overview')
    assert page.locator('#question-form').count()==0
    tab('chat')
    assert page.locator('#question-draft').input_value().startswith('QUESTION DRAFT:')
    page.locator('#question-form button').click()
    assert 'QUESTION DRAFT: append and retain notes' in page.locator('#step-transcript').inner_text()
    assert page.locator('#global-draft').input_value()=='GLOBAL DRAFT STAYS GLOBAL'
    assert page.locator('#top-count').inner_text()=='2 for you'
    checks.append('PASS: local step guidance and question answer append to the same thread; fixed recipients; question draft survives overview; global draft unchanged; back focus and dashboard position restored')

    load('?task=thumbnails&tab=chat&stream=paused')
    play(9000)
    page.locator('#task-draft').fill('SENT AT TICK 9')
    page.locator('#task-form button[type="submit"]').click()
    play(8000)
    event_ids=lambda:page.locator('.chat-inner > [data-event]').evaluate_all('(es)=>es.map(e=>e.dataset.event)')
    ids=event_ids()
    assert ids.index('test')<ids.index('message-0')<ids.index('diff-intro')<ids.index('diff')
    tab('overview')
    tab('chat')
    assert event_ids()==ids
    page.locator('#task-draft').fill('SENT AT TICK 17')
    page.locator('#task-form button[type="submit"]').click()
    play(4000)
    ids=event_ids()
    assert ids.index('message-0')<ids.index('diff-intro')<ids.index('message-1')<ids.index('final')
    tab('overview')
    tab('chat')
    assert event_ids()==ids
    load('?task=import&stream=paused')
    assert 'Ask me how to merge notes' in page.locator('[data-event="brief"]').inner_text()
    assert 'Awaiting your answer' not in page.locator('[data-event="brief"]').inner_text()
    play(9000)
    page.locator('#question-draft').fill('ANSWER SENT AT TICK 9')
    page.locator('#question-form button[type="submit"]').click()
    ids=event_ids()
    assert ids.index('message-0')<ids.index('answer-receipt')
    page.locator('#task-draft').fill('GUIDANCE SENT AT THE SAME TICK')
    page.locator('#task-form button[type="submit"]').click()
    ids=event_ids()
    assert ids.index('message-0')<ids.index('answer-receipt')<ids.index('message-1')
    tab('overview')
    tab('chat')
    assert event_ids()==ids
    shot('answered-question-dark')
    checks.append('PASS: user briefs contain user instructions; guidance sent between fixture events keeps its chronological position after later output, tab changes and a second send')
    checks.append('PASS: nonzero-tick question answer precedes its receipt, which precedes same-tick follow-up guidance after tab reconstruction')

    load('?task=audio&stream=paused')
    assert page.locator('[data-action="approve"]').count()==1
    tab('chat')
    assert page.locator('[data-action="approve"]').count()==0
    assert 'Exited 1' in page.locator('#step-transcript').inner_text()
    assert page.locator('#task-composer textarea').count()==0
    tab('overview')
    page.locator('[data-action="approve"]').click()
    assert 'retry approved' in page.locator('#feedback').inner_text()
    assert 'Running independently' in page.locator('.task-shell-head').inner_text()
    load('?task=audio&stream=paused')
    page.locator('[data-action="dismiss"]').click()
    assert 'Paused' in page.locator('.task-shell-head').inner_text()
    load('?task=archive&stream=paused')
    page.get_by_role('button',name='Review result',exact=True).click()
    assert page.locator('#sample-result').evaluate('(e)=>e===document.activeElement')
    page.locator('[data-action="accept"]').click()
    assert 'Accepted' in page.locator('.task-shell-head').inner_text()
    tab('chat')
    assert page.locator('#task-composer textarea').count()==0
    load('?task=observed&stream=paused')
    assert 'Reply in the original VS Code chat' in page.locator('main').inner_text()
    assert page.locator('#task-composer textarea').count()==0
    assert page.locator('#global-draft').is_visible()
    checks.append('PASS: supervisor recommendation stays in overview; failed/finished step chats read-only; simulated approve/dismiss/accept and result destination; observed external chat read-only')

    for theme in ('dark','light'):
        for width in (1510,900,400,340):
            page.set_viewport_size({'width':width,'height':1080 if width==1510 else 1000})
            load('?theme='+theme+'&stream=paused')
            no_overflow()
            if width in (1510,400):shot(f'dashboard-{width}-{theme}')
            page.locator('[data-card="thumbnails"] .task-title').click()
            no_overflow()
            shot(f'overview-{width}-{theme}')
            tab('chat')
            play(9000)
            no_overflow()
            shot(f'chat-{width}-{theme}')
            assert page.locator('#task-form label').inner_text().startswith('To: T-031 · step 03')
            if width<=400:
                page.locator('#task-draft').fill('NARROW STEP DRAFT')
                page.locator('#nav-supervision').click()
                page.locator('#global-draft').fill('NARROW GLOBAL DRAFT')
                page.locator('#nav-tasks').click()
                assert page.locator('#task-draft').input_value()=='NARROW STEP DRAFT'
            tiny=page.locator('.window').evaluate('''e=>[...e.querySelectorAll('button')].filter(b=>b.getClientRects().length).filter(b=>b.getBoundingClientRect().height<24||b.getBoundingClientRect().width<24).map(b=>b.textContent)''')
            assert not tiny,(theme,width,tiny)
            checks.append(f'PASS: {width}px {theme} overview/chat/dashboard; no horizontal overflow; >=24px button targets; narrow view separation')
    page.set_viewport_size({'width':1510,'height':1080})
    for name,query in [('question-chat','?task=import'),('supervisor-overview','?task=audio'),('finished-overview','?task=archive'),('observed','?task=observed')]:
        load(query+'&stream=paused')
        shot(name+'-dark')
    load('?task=thumbnails&tab=chat&stream=paused')
    play(4000)
    shot('streaming-chat-dark')
    load('?stream=paused')
    play(9000)
    page.locator('#show-running').click()
    shot('running-previews-dark')
    page.locator('[data-card="captions"] [data-chat]').click()
    assert 'No output for 3m' in page.locator('.step-chat-meta').inner_text()
    assert 'Process running' in page.locator('#step-transcript').inner_text()
    shot('quiet-chat-dark')
    load('?task=thumbnails&tab=chat&stream=paused')
    play(9000)
    page.evaluate('''const sizes=[...document.querySelectorAll('.window *')].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]);sizes.forEach(([e,n])=>e.style.fontSize=n*1.3+'px')''')
    no_overflow()
    shot('chat-text130-dark')
    checks.append('PASS: quiet process exposes elapsed time and output age; shared dashboard preview/current-step chat; 130% computed-text desktop smoke check')
    for width in (400,340):
        page.set_viewport_size({'width':width,'height':760})
        load('?task=thumbnails&tab=chat&stream=paused')
        play(9000)
        no_overflow()
        assert page.locator('#step-transcript').bounding_box()['height']>=100
        assert page.locator('#task-form button[type="submit"]').is_visible()
        shot(f'chat-{width}x760-dark')
    checks.append('PASS: 400/340 x 760px window retains >=100px transcript and visible scoped composer')
    assert not errors,errors
    assert not network,network
    checks.append('PASS: no JavaScript page errors or HTTP(S) requests')
    browser.close()
(ROOT/'check-results.json').write_text(json.dumps({'checks':checks,'page_errors':errors,'network_requests':network},indent=2),encoding='utf-8')
print('\n'.join(checks))
