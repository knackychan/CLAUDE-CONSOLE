"""Check the standalone operator proposal with installed Playwright and Edge."""
from pathlib import Path
import json
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent
URL = (ROOT / 'index.html').as_uri()
SHOTS = ROOT / 'screenshots'
SHOTS.mkdir(exist_ok=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='msedge', headless=True)
    page = browser.new_page(viewport={'width': 1510, 'height': 1040}, reduced_motion='reduce')
    errors, network, checks = [], [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda req: network.append(req.url) if req.url.startswith(('http:', 'https:')) else None)
    page.clock.install()

    def load(route='', theme='dark'):
        page.goto(URL + ('?theme=light' if theme == 'light' else '') + ('#' + route if route else ''))
        page.evaluate('document.fonts.ready')

    def click(selector):
        if selector == '#global-toggle' and not page.locator(selector).is_visible():
            selector = '#rail-global'
        page.locator(selector).first.click()
        page.wait_for_function('''() => {
            const [id, view] = location.hash.slice(1).split('/');
            return !id || id === 'grid' ? boardOpen : id === 'global' ? globalOpen :
                !boardOpen && !globalOpen && selected === id && tab === (view || 'now');
        }''')

    def no_overflow():
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        for node in page.locator('.main:visible,.detail-scroll:visible,.queue:visible,.composer:visible,.grid-scroll:visible,.tile-stream:visible,.global-panel:visible,.project-rail:visible,.usage-header:visible,.usage-breakdown:visible,.task-telemetry:visible').all():
            assert node.evaluate('(e)=>e.scrollWidth <= e.clientWidth + 1'), node.get_attribute('class')

    def luminance(color):
        values = [int(color.lstrip('#')[i:i+2], 16) / 255 for i in (0, 2, 4)]
        values = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
        return sum(v * weight for v, weight in zip(values, (.2126, .7152, .0722)))

    load()
    expect(page.locator('#usage-amount')).to_have_text('$7.41')
    assert page.locator('[data-telemetry]').count() == 6
    expect(page.locator('[data-telemetry=thumbnails]')).to_contain_text('Ctx 72K')
    expect(page.locator('[data-telemetry=thumbnails]')).to_contain_text('Task ~$1.42')
    expect(page.locator('[data-telemetry=search]')).to_contain_text('Unknown')
    assert page.locator('[data-telemetry=search] .meter-cells').count() == 0
    expect(page.locator('[data-telemetry=audio] .task-context')).to_have_attribute('data-pressure', 'high')
    page.locator('#usage-summary').focus()
    page.keyboard.press('Enter')
    expect(page.locator('#usage-breakdown')).to_be_visible()
    expect(page.locator('[data-usage-model=Sonnet]')).to_contain_text('980K')
    expect(page.locator('[data-usage-model=Sonnet]')).to_contain_text('~$4.83')
    expect(page.locator('[data-usage-model=Codex]')).to_contain_text('Unknown')
    assert page.evaluate("usageTotal([{tokens:0,cents:0}]).unknown") == 0
    assert page.evaluate("usd(0)") == '$0.00'
    no_overflow()
    page.screenshot(path=str(SHOTS / 'usage-breakdown-dark.png'), full_page=True)
    click('[data-project="Catalog Atlas"]')
    expect(page.locator('#usage-amount')).to_have_text('$7.41')
    expect(page.locator('#usage-breakdown')).to_be_visible()
    click('#usage-summary')
    load('thumbnails/chat/1')
    expect(page.locator('.task-telemetry-note')).to_contain_text('not recorded')
    assert page.locator('.task-telemetry .meter-cells').count() == 0
    load('thumbnails/chat/4')
    expect(page.locator('.task-telemetry-note')).to_contain_text('not started')
    load('audio/now/4')
    expect(page.locator('.task-model')).to_have_text('Sonnet')
    click('[data-action=approve]')
    expect(page.locator('.task-model')).to_have_text('Opus')
    expect(page.locator('.task-telemetry-note')).to_contain_text('awaiting retry reading')
    expect(page.locator('.task-cost')).to_have_text('Task ~$3.17')
    expect(page.locator('#usage-amount')).to_have_text('$7.41')
    checks.append('Usage totals reconcile by model and task; global spend survives project filtering; unknown cost/context and retry readings stay explicit; breakdown opens from the keyboard.')

    load()
    expect(page.locator('[data-project=all]')).to_have_attribute('aria-current', 'true')
    assert page.locator('[data-project]').count() == 7
    click('[data-project="Catalog Atlas"]')
    assert page.locator('[data-tile]').count() == 1
    assert page.locator('[data-tile=thumbnails]').is_visible()
    assert '3 need you' in page.locator('#all-decisions').inner_text()
    assert 'Running 1' in page.locator('[data-grid-filter=running]').inner_text()
    click('[data-grid-filter=needs]')
    assert page.locator('[data-tile]').count() == 0
    assert page.locator('.grid-empty').is_visible()
    click('[data-grid-filter=all]')
    click('#rail-global')
    assert page.locator('.live-grid').is_visible()
    assert page.locator('#global-panel').is_visible()
    assert page.locator('#global-panel [data-open]').count() == 3
    assert 'all projects' in page.locator('#global-panel .global-head').inner_text()
    page.locator('#global-draft').fill('Keep all projects moving.')
    before = page.locator('[data-grid-stream=thumbnails]').inner_text()
    click('[data-playback]')
    page.locator('#global-draft').focus()
    page.clock.run_for(9000)
    assert page.locator('[data-grid-stream=thumbnails]').inner_text() != before
    expect(page.locator('#global-draft')).to_be_focused()
    assert page.locator('#global-draft').input_value() == 'Keep all projects moving.'
    click('[data-project="Fieldnotes CRM"]')
    assert page.locator('[data-tile=import]').is_visible()
    assert page.locator('#global-draft').input_value() == 'Keep all projects moving.'
    click('#global-form button')
    assert page.locator('#global-panel .chat-event.user').count() == 1
    assert page.locator('[data-tile=import] .tile-meta').inner_text().startswith('Needs your reply')
    page.keyboard.press('Escape')
    expect(page.locator('#global-panel')).not_to_be_visible()
    expect(page.locator('#rail-global')).to_be_focused()
    click('#all-decisions')
    assert page.locator('[data-tile]').count() == 3
    expect(page.locator('[data-project=all]')).to_have_attribute('aria-current', 'true')
    checks.append('Project filters and scoped counts work; all-project decisions stay reachable; global chat streams alongside the grid without mixing drafts.')

    load()
    assert page.locator('[data-tile]').count() == 6
    assert page.locator('[data-grid-stream]').count() == 3
    assert not page.locator('.queue').is_visible()
    assert page.locator('[data-playback]').get_attribute('aria-pressed') == 'false'
    grid_order = page.locator('[data-tile]').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.tile)')
    thumb = page.locator('[data-grid-stream=thumbnails]')
    search = page.locator('[data-grid-stream=search]')
    quiet_output = page.locator('[data-grid-stream=captions] [data-field=output]').inner_text()
    thumb_before, search_before = thumb.inner_text(), search.inner_text()
    click('[data-playback]')
    page.clock.run_for(9000)
    assert thumb.inner_text() != thumb_before
    assert search.inner_text() != search_before
    assert page.locator('[data-grid-stream=captions] [data-field=output]').inner_text() == quiet_output
    assert '3m 21s' in page.locator('[data-freshness=captions]').inner_text()
    thumb.evaluate('(e)=>e.scrollTop=0')
    page.clock.run_for(100)
    expect(page.locator('[data-follow=thumbnails]')).to_have_attribute('aria-pressed', 'false')
    page.clock.run_for(4000)
    assert thumb.evaluate('(e)=>e.scrollTop') == 0
    assert search.evaluate('(e)=>e.scrollHeight-e.clientHeight-e.scrollTop') < 2
    click('[data-playback]')
    paused_text = search.inner_text()
    page.clock.run_for(2000)
    assert search.inner_text() == paused_text
    click('[data-tile=thumbnails] [data-open]')
    page.locator('#guidance-draft').fill('Keep watching the other tasks.')
    click('#grid-toggle')
    assert thumb.evaluate('(e)=>e.scrollTop') == 0
    assert page.locator('[data-tile]').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.tile)') == grid_order
    click('[data-follow=thumbnails]')
    assert thumb.evaluate('(e)=>e.scrollHeight-e.clientHeight-e.scrollTop') < 2
    click('#global-toggle')
    assert page.locator('[data-return]').inner_text().strip() == 'Close chat'
    assert page.locator('.live-grid').is_visible()
    click('[data-return]')
    assert page.locator('.live-grid').is_visible()
    click('[data-grid-filter=running]')
    assert page.locator('[data-tile]').count() == 3
    click('[data-grid-filter=needs]')
    assert page.locator('[data-tile]').count() == 3
    assert page.locator('[data-grid-stream]').count() == 0
    checks.append('Three simultaneous chat panes; independent follow/scroll, pause, filters and return-to-grid state work.')

    load('import/now/3')
    assert page.locator('.queue-section.needs .task-row').count() == 3
    assert page.locator('[name=notes]:checked').count() == 0
    assert page.locator('#answer-form [type=submit]').is_disabled()
    click('[name=notes][value=append]')
    assert 'keep all existing notes' in page.locator('#answer-draft').input_value()
    page.locator('#answer-draft').fill('Keep existing notes. Append only the imported text.')
    assert page.locator('[name=notes]:checked').count() == 0
    click('#global-toggle')
    page.locator('#global-draft').fill('Global priorities, separate from task answers.')
    click('[data-return]')
    assert page.locator('#answer-draft').input_value().startswith('Keep existing notes.')
    click('[data-open=audio]')
    page.go_back()
    assert page.locator('#answer-draft').input_value().startswith('Keep existing notes.')
    click('#answer-form [type=submit]')
    assert page.locator('.queue-section.needs .task-row').count() == 2
    assert page.locator('.receipt strong').inner_text().strip().startswith('Answer sent')
    click('[data-tab=chat]')
    assert 'Keep existing notes. Append only the imported text.' in page.locator('#transcript').inner_text()
    page.locator('#guidance-draft').fill('Task guidance remains on this step.')
    click('#global-toggle')
    assert page.locator('#global-draft').input_value() == 'Global priorities, separate from task answers.'
    click('#global-form button')
    click('[data-return]')
    assert page.locator('#guidance-draft').input_value() == 'Task guidance remains on this step.'
    assert 'Global priorities' not in page.locator('#transcript').inner_text()
    checks.append('Task answers, step guidance and global drafts stay separate; browser Back retains drafts.')

    page.locator('#step-select').select_option('1')
    assert page.locator('#guidance-form').count() == 0
    page.locator('#step-select').select_option('5')
    assert 'has not started' in page.locator('.detail-scroll').inner_text()
    assert page.locator('main textarea').count() == 0
    checks.append('Completed and future steps are read-only.')

    click('[data-open=audio]')
    click('[data-action=dismiss]')
    assert page.locator('.queue-section').filter(has=page.get_by_role('heading', name='Paused', exact=False)).count() == 1
    click('[data-action=revisit]')
    click('[data-action=approve]')
    assert 'Retry approved' in page.locator('.receipt').inner_text()
    click('[data-open=archive]')
    assert 'manifest.json' in page.locator('main').inner_text()
    click('[data-action=accept]')
    assert page.locator('.queue-section.needs').count() == 0
    click('[data-filter=needs]')
    assert 'No decisions waiting' in page.locator('#queue-list').inner_text()
    click('[data-clear]')
    click('#global-toggle')
    assert 'No decisions waiting.' in page.locator('#global-panel').inner_text()
    click('[data-return]')
    checks.append('Answer, dismiss/revisit, approve and accept update the queue and global summary.')

    page.locator('#search').fill('Harbor')
    assert page.locator('.task-row').count() == 1
    page.locator('#search').fill('unmatched task')
    assert 'No tasks match' in page.locator('#queue-list').inner_text()
    click('[data-clear]')
    click('[data-open=observed]')
    assert page.locator('main textarea').count() == 0
    assert 'VS Code' in page.locator('main').inner_text()
    click('#reset')
    assert page.locator('.queue-section.needs .task-row').count() == 3
    checks.append('Search, empty-state recovery, observed read-only chat and Reset sample work.')

    load('import/now/3')
    page.locator('#answer-draft').fill('<img src=x onerror=alert(1)> & original notes')
    click('#answer-form [type=submit]')
    click('[data-tab=chat]')
    assert page.locator('#transcript img').count() == 0
    assert '<img src=x onerror=alert(1)>' in page.locator('#transcript').inner_text()
    checks.append('User-authored text is escaped in conversations.')

    load('thumbnails/chat/3')
    page.locator('#guidance-draft').fill('Do not change the image dimensions.')
    click('#playback')
    page.locator('#guidance-draft').focus()
    page.clock.run_for(9000)
    assert page.locator('#guidance-draft').input_value() == 'Do not change the image dimensions.'
    assert page.locator('#guidance-draft').evaluate('(e)=>document.activeElement===e')
    assert page.locator('[data-event=test]').count() == 1
    page.locator('[data-event=read] summary').focus()
    page.keyboard.press('Enter')
    page.clock.run_for(1000)
    assert page.locator('[data-event=read] summary').evaluate('(e)=>document.activeElement===e')
    assert page.locator('[data-event=read] details').get_attribute('open') is not None
    click('#playback')
    checks.append('Explicit stream playback preserves drafts, keyboard focus and expanded evidence.')

    for theme in ('dark', 'light'):
        load('', theme)
        tokens = page.evaluate("Object.fromEntries(['ink','mut','you','ok','page','win','raise'].map(k=>[k,getComputedStyle(document.documentElement).getPropertyValue('--'+k).trim()]))")
        for foreground in ('ink', 'mut', 'you', 'ok'):
            for background in ('page', 'win', 'raise'):
                dark, light = sorted([luminance(tokens[foreground]), luminance(tokens[background])])
                assert (light + .05) / (dark + .05) >= 4.5, (theme, foreground, background)
        for width in (320, 375, 414, 768, 900, 1280, 1510, 1920):
            page.set_viewport_size({'width': width, 'height': 900})
            load('', theme)
            no_overflow()
            click('#usage-summary')
            no_overflow()
            assert page.locator('[data-usage-model=Codex]').is_visible()
            if width in (375, 1510):
                page.screenshot(path=str(SHOTS / f'usage-{width}-{theme}.png'), full_page=True)
            click('#usage-summary')
            if width < 768:
                assert page.locator('.live-grid').is_visible()
                page.locator('#project-select').select_option('Fieldnotes CRM')
                assert page.locator('[data-tile]').count() == 1
                click('#rail-global')
                expect(page.locator('#global-panel')).to_be_visible()
                assert not page.locator('.main').is_visible()
                page.keyboard.press('Escape')
                expect(page.locator('#global-panel')).not_to_be_visible()
                assert page.locator('[data-tile=import]').is_visible()
                page.locator('#project-select').select_option('all')
                if width == 375:
                    page.screenshot(path=str(SHOTS / f'grid-mobile-{theme}.png'), full_page=True)
                click('[data-tile=import] [data-open]')
                assert not page.locator('.queue').is_visible()
                assert page.locator('#answer-form').is_visible()
                if width == 375:
                    page.screenshot(path=str(SHOTS / f'mobile-decision-{theme}.png'), full_page=True)
                click('[data-queue]')
                assert page.locator('.queue').is_visible()
                click('#global-toggle')
                assert page.locator('#global-draft').is_visible()
                page.keyboard.press('Escape')
            for route in ('grid', 'import/now/3', 'audio/now/4', 'thumbnails/chat/3', 'archive/plan/4', 'global'):
                page.evaluate('(hash)=>location.hash=hash', route)
                page.wait_for_function('(hash)=>location.hash.slice(1)===hash', arg=route)
                page.wait_for_timeout(30)
                no_overflow()
            if width == 1510:
                load('', theme)
                page.screenshot(path=str(SHOTS / f'desktop-{theme}.png'), full_page=True)
                assert page.locator('[data-tile]').evaluate_all('''nodes => nodes.every(n => {
                    const card = n.getBoundingClientRect(), area = n.closest('.grid-scroll').getBoundingClientRect();
                    return card.top >= area.top && card.bottom <= area.bottom;
                })'''), 'All six cards should fit at desktop width and 900 px height.'
                click('[data-project="Catalog Atlas"]')
                page.screenshot(path=str(SHOTS / f'project-filter-{theme}.png'), full_page=True)
                click('[data-project=all]')
                click('#rail-global')
                no_overflow()
                page.screenshot(path=str(SHOTS / f'grid-global-{theme}.png'), full_page=True)
        checks.append(f'{theme.title()} theme: primary/secondary/status text contrast >= 4.5:1; layouts fit 320–1920 px.')

    page.set_viewport_size({'width': 375, 'height': 900})
    load()
    mobile_stream = page.locator('[data-grid-stream=thumbnails]')
    mobile_stream.evaluate('(e)=>e.scrollTop=30')
    expect(page.locator('[data-follow=thumbnails]')).to_have_attribute('aria-pressed', 'false')
    old_position = mobile_stream.evaluate('(e)=>e.scrollTop')
    assert old_position > 0
    click('#rail-global')
    page.locator('#global-draft').fill('Global draft on a phone.')
    click('[data-return]')
    assert mobile_stream.evaluate('(e)=>e.scrollTop') == old_position
    click('#rail-global')
    assert page.locator('#global-draft').input_value() == 'Global draft on a phone.'
    checks.append('The mobile chat panel preserves the hidden grid reading position and its global draft.')

    page.set_viewport_size({'width': 1510, 'height': 1040})
    page.emulate_media(reduced_motion='no-preference')
    load()
    assert page.locator('[data-playback]').get_attribute('aria-pressed') == 'true'
    page.clock.run_for(25000)
    assert page.locator('[data-playback]').inner_text() == 'Replay streams'
    click('[data-playback]')
    assert page.locator('[data-playback]').get_attribute('aria-pressed') == 'true'
    page.emulate_media(reduced_motion='reduce')
    checks.append('Streams play together by default; reduced motion starts paused; the finite sample can be replayed.')
    for name, route in [('retry', 'audio/now/4'), ('step-chat', 'thumbnails/chat/3'), ('global', 'global')]:
        load(route)
        page.screenshot(path=str(SHOTS / (name + '.png')), full_page=True)
    page.set_viewport_size({'width': 755, 'height': 520})
    load('import/now/3')
    page.evaluate('''() => {
      const sizes = [...document.querySelectorAll('body *')].map(e => [e, parseFloat(getComputedStyle(e).fontSize)]);
      for (const [e, size] of sizes) e.style.fontSize = size * 1.3 + 'px';
    }''')
    no_overflow()
    assert not errors, errors
    assert not network, network
    checks.append('No JavaScript errors or HTTP requests; reduced viewport and 130% text fit without horizontal overflow.')
    report = {'checks': checks, 'javascript_errors': errors, 'network_requests': network}
    (ROOT / 'check-results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    browser.close()
