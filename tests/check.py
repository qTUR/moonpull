"""Browser checks for all three builds.

Runs the YouTube build with a stand-in SDK, plays from the first-time tutorial to the
last sea, and checks saving, pausing, sound, ads and their rules, console errors and
network requests. Then takes screenshots at phone and desktop sizes in both languages.
"""
import json, os, re, sys, threading, time, functools
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, 'dist')
SHOTS = os.path.join(DIST, 'shots')
os.makedirs(SHOTS, exist_ok=True)
SDK = 'https://www.youtube.com/game_api/v1'
MOCK = open(os.path.join(ROOT, 'tests', 'mock-sdk.js')).read()
SIM = open(os.path.join(ROOT, 'tools', 'sim.cjs')).read()
PILOT_SRC = SIM[SIM.index('function pilotFactory'):SIM.index('function playLevel')]

results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print(('PASS ' if ok else 'FAIL ') + name + (' · ' + str(detail) if detail else ''), flush=True)

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

def serve(folder, port):
    h = functools.partial(Quiet, directory=folder)
    srv = ThreadingHTTPServer(('127.0.0.1', port), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

def watch(page, base):
    errors, foreign = [], []
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: errors.append('pageerror: ' + str(e)))
    def on_req(r):
        u = r.url
        if u.startswith(base) or u.startswith('data:') or u.startswith('blob:'): return
        if u == SDK: return
        foreign.append(u)
    page.on('request', on_req)
    page.route(SDK, lambda route: route.fulfill(status=200, content_type='text/javascript', body=MOCK))
    return errors, foreign

def install_pilot(page, skill=0.7, speed=8):
    page.evaluate("""([src, skill, speed]) => {
      let s = 12345; const rnd = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
      const make = new Function('skill', 'rnd', src + '; return pilotFactory(skill, rnd);');
      let ctl = null, w = null;
      __moon.driver = (world, dt) => { if (world !== w) { w = world; ctl = make(skill, rnd); } ctl(world, dt); };
      __moon.timeScale = speed;
    }""", [PILOT_SRC, skill, speed])

def wait_for(page, js, timeout=60, step=0.1):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if page.evaluate(js): return True
        except Exception:
            pass
        time.sleep(step)
    return False

def buy_everything(page):
    page.evaluate("() => { if (__moon.mode === 'play') return; }")
    page.click('#shrineBtn')
    for _ in range(20):
        btns = page.query_selector_all('#shrineList .buy:not([disabled])')
        if not btns: break
        btns[0].click(); time.sleep(0.05)
    page.click('#shrine [data-back]')

def main_youtube(p):
    base = 'http://127.0.0.1:8611/'
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 1280, 'height': 720})
    page = ctx.new_page()
    errors, foreign = watch(page, base)
    page.goto(base)
    check('page loads and shows the title', wait_for(page, "document.body.classList.contains('ready') && __moon.screen === 'title'", 10))
    calls = page.evaluate('__yt.calls.map(c => c[0])')
    check('firstFrameReady then gameReady', 'firstFrameReady' in calls and 'gameReady' in calls and calls.index('firstFrameReady') < calls.index('gameReady'), calls[:4])
    check('game loads saved data through the SDK', 'loadData' in calls)
    check('no local storage save while the SDK is present', page.evaluate("localStorage.getItem('moonpull.save.v1') === null"))
    check('English by default from getLanguage(en-US)', page.evaluate("document.documentElement.dir === 'ltr' && document.getElementById('playBtn').textContent.trim() === 'Play'"))
    page.screenshot(path=os.path.join(SHOTS, 'yt-title.png'))

    # --- tutorial, played with the mouse ---
    page.click('#playBtn')
    check('first level starts with the tutorial', wait_for(page, "__moon.mode === 'play' && !document.getElementById('tut').hidden", 5))
    t0 = time.time(); step_times = []
    last = -1
    while time.time() - t0 < 90:
        st = page.evaluate("""() => { const w = __moon.world; if (!w) return null; return { tut: __moon.save.tut, ox: View.sx(w.o.x), oy: View.sy(w.o.y), mx: View.sx(w.moon.x), my: View.sy(w.moon.y), air: w.o.air, W: innerWidth, H: innerHeight, hor: View.horizon, S: View.S }; }""")
        if st is None: break
        if st['tut'] != last: step_times.append(round(time.time() - t0, 1)); last = st['tut']
        if st['tut'] >= 5: break
        tut = st['tut']; S = st['S']
        low_y = st['hor'] - 215 * S
        if tut == 0:
            page.mouse.move(st['mx'] + 120, st['my'] + 60, steps=6)
        elif tut in (1, 3, 4):
            page.mouse.move(max(10, st['ox'] - 150 * S), low_y, steps=3)
            if tut == 3 and int(time.time() * 2) % 5 == 0:
                page.mouse.move(st['ox'], low_y, steps=2); time.sleep(0.35); page.mouse.move(st['ox'] + 60, 30, steps=2); time.sleep(0.3)
        elif tut == 2:
            page.mouse.move(st['ox'], low_y, steps=3); time.sleep(0.4)
            page.mouse.move(st['ox'] + 60, 20, steps=2); time.sleep(0.5)
        time.sleep(0.08)
    check('tutorial completes with mouse input (5 steps)', page.evaluate('__moon.save.tut') >= 5, 'step times ' + str(step_times))
    ads_tut = page.evaluate("__yt.ads.filter(a => a[0] === 'interstitial').length")
    check('no interstitial during the tutorial', ads_tut == 0)
    page.screenshot(path=os.path.join(SHOTS, 'yt-play.png'))

    # finish level 1 with the virtual player
    install_pilot(page, 0.7, 6)
    check('level 1 reaches the lighthouse', wait_for(page, "__moon.screen === 'win'", 120))
    page.screenshot(path=os.path.join(SHOTS, 'yt-win.png'))

    # --- rewarded: double ---
    light0 = page.evaluate('__moon.save.light')
    page.click('#doubleBtn')
    wait_for(page, "document.getElementById('doubleBtn').hidden", 5)
    light1 = page.evaluate('__moon.save.light')
    check('rewarded ad doubles the reward when watched', light1 > light0 and page.evaluate("__yt.ads.some(a => a[1] === 'double')"), f'{light0} -> {light1}')

    # --- rewarded refused: nothing given ---
    page.click('#nextBtn')
    wait_for(page, "__moon.mode === 'play' && __moon.world", 5)
    page.evaluate("() => { __moon.driver = null; __moon.timeScale = 1; const w = __moon.world; w.o.hurtT = 0; w.flames = 1; w.hurt('thorn'); }")
    check('losing all flames shows the lose card', wait_for(page, "__moon.screen === 'lose'", 5))
    page.evaluate("__yt.reward = false")
    page.click('#secondBtn'); time.sleep(0.8)
    check('second chance gives nothing if the ad is not finished', page.evaluate("__moon.screen === 'lose' && __moon.world.dead"))
    page.evaluate("__yt.reward = true")
    page.click('#secondBtn')
    check('second chance revives when the ad is watched', wait_for(page, "__moon.screen === null && !__moon.world.dead && __moon.world.flames === __moon.world.maxFlames", 5))

    # --- pause / resume from the platform ---
    saves_before = page.evaluate("__yt.calls.filter(c => c[0] === 'saveData').length")
    t_before = page.evaluate("() => { __ytfire('pause'); return __moon.world.t; }")
    time.sleep(0.6)
    t_after = page.evaluate('__moon.world.t')
    snd = page.evaluate('Sound.state()')
    check('onPause stops the game', abs(t_after - t_before) < 0.05 and page.evaluate("__moon.screen === 'pause'"), f'dt={t_after - t_before:.3f}')
    check('onPause silences sound', snd['paused'] is True, snd)
    check('onPause saves', page.evaluate("__yt.calls.filter(c => c[0] === 'saveData').length") > saves_before)
    page.evaluate("__ytfire('resume')")
    page.click('#resumeBtn'); time.sleep(0.4)
    check('game runs again after resume', page.evaluate('__moon.world.t') > t_after and page.evaluate('!Sound.state().paused'))

    # --- sound settings ---
    page.evaluate("__ytfire('audio', false)"); time.sleep(0.3)
    check('onAudioEnabledChange(false) mutes', page.evaluate('Sound.state().sysOn === false'))
    page.evaluate("__ytfire('audio', true)")
    page.keyboard.press('Escape'); time.sleep(0.2)
    check('pause screen has language and sound buttons', page.is_visible('#langBtn') and page.is_visible('#muteBtn'))
    page.click('#muteBtn'); time.sleep(0.1)
    check('mute button mutes', page.evaluate('Sound.state().muted && __moon.save.mute'))
    page.click('#muteBtn')
    page.click('#resumeBtn')

    # --- save and load ---
    install_pilot(page, 0.7, 8)
    wait_for(page, "__moon.screen === 'win'", 120)
    snap = page.evaluate('JSON.stringify({best: __moon.save.best, light: __moon.save.light})')
    page.evaluate('__moon.persist()'); time.sleep(0.3)
    page.reload()
    wait_for(page, "document.body.classList.contains('ready')", 10)
    snap2 = page.evaluate('JSON.stringify({best: __moon.save.best, light: __moon.save.light})')
    check('progress survives a reload (saveData/loadData)', snap == snap2, snap2[:80])

    # --- full run to the last sea ---
    t_run = time.time(); level_log = []
    boot_real = page.evaluate('__yt.boot')
    while time.time() - t_run < 1500:
        done = page.evaluate("Object.keys(__moon.save.best).length")
        if page.evaluate("Object.keys(__moon.save.best).filter(k => __moon.save.best[k] > 0).length") >= page.evaluate('Core.STORY_LEVELS'):
            break
        if page.evaluate("__moon.mode") != 'play':
            if page.evaluate("__moon.screen") == 'title':
                buy_everything(page)
                # next level if open; otherwise replay the weakest level for pearls
                target = page.evaluate("""() => { const s = __moon.save; let i = 0; while (s.best[i] > 0) i++;
                   const info = Core.levelInfo(i); const need = Core.regionGate(info.region);
                   const total = Object.values(s.best).reduce((a, b) => a + b, 0);
                   if (info.local === 0 && info.region > 0 && total < need) { let w = 0, wp = 4; for (let k = 0; k < i; k++) if ((s.best[k] || 0) < wp) { wp = s.best[k] || 0; w = k; } return w; }
                   return i; }""")
                page.click('#chartBtn')
                btns = page.query_selector_all('#chartList .lv')
                btns[target].click()
                install_pilot(page, 0.75, 10)
            else:
                page.evaluate("() => { document.querySelectorAll('[data-back]').forEach(b => b.offsetParent && b.click()); }")
                time.sleep(0.2)
                if page.evaluate("__moon.screen") not in ('title',):
                    page.evaluate("() => { const b = document.querySelector('#chart [data-back]'); if (b && b.offsetParent) b.click(); }")
            continue
        scr = page.evaluate("__moon.screen")
        if scr == 'win':
            level_log.append(page.evaluate('__moon.save.played'))
            if page.is_visible('#nextBtn') and page.evaluate("Math.random() < 0.8"):
                page.click('#nextBtn'); install_pilot(page, 0.75, 10)
            else:
                page.click('#winMap'); time.sleep(0.2); page.click('#chart [data-back]')
        elif scr == 'lose':
            page.click('#retryBtn'); install_pilot(page, 0.75, 10)
        elif scr == 'pause':
            page.click('#resumeBtn')
        time.sleep(0.15)
    finished = page.evaluate("Object.keys(__moon.save.best).filter(k => __moon.save.best[k] > 0).length")
    total = page.evaluate('Core.STORY_LEVELS')
    check(f'played through every sea to the last one ({finished}/{total})', finished >= total, f'{round(time.time() - t_run)} s of real time')
    check('Eclipse Tide reached and New Moon gifted', page.evaluate('__moon.save.up.newmoon === 1'))
    check('Open Sea opens after the story', page.evaluate(f'__moon.save.best[{total - 1}] > 0'))
    # interstitial rules
    inter = page.evaluate("__yt.ads.filter(a => a[0] === 'interstitial').map(a => a[1] - __yt.boot)")
    gaps = [inter[i] - inter[i - 1] for i in range(1, len(inter))]
    check('interstitials only after big moments, at least 150 s apart, never in the first 3 s',
          all(g >= 150000 for g in gaps) and all(t > 3000 for t in inter), f'{len(inter)} shown, gaps {[round(g / 1000) for g in gaps]}')

    # --- endless tides and prestige ---
    if page.evaluate("__moon.mode") == 'play':
        page.keyboard.press('Escape'); page.click('#pauseMap'); page.click('#chart [data-back]')
    page.evaluate("() => { __moon.save.s.finish = 999; __moon.save.s.motes = 99999; __moon.save.s.launch = 999; __moon.save.s.buoys = 999; __moon.save.s.bounce = 999; __moon.save.s.spout = 99; __moon.save.s.nohit = 99; __moon.save.s.gold = 99; __moon.save.s.visitor = 9; __moon.save.s.perfect = 9; __moon.save.s.flips = 9; __moon.save.s.air = 9; __moon.save.s.max_flips = 9; __moon.save.s.max_air = 9; }")
    page.click('#missionsBtn')
    claimed = 0
    for _ in range(40):
        bt = page.query_selector('#missionList .mis.ready .buy')
        if not bt: break
        bt.click(); claimed += 1; time.sleep(0.03)
    n_fixed = page.evaluate('Core.MISSIONS.length')
    endless_shown = page.evaluate("document.querySelectorAll('#missionList .tag').length")
    check(f'more than 20 missions, then endless ones ({n_fixed} fixed)', n_fixed > 20 and claimed >= n_fixed and endless_shown > 0, f'claimed {claimed}')
    page.click('#missions [data-back]')
    page.click('#shrineBtn')
    shards0 = page.evaluate('__moon.save.shards')
    page.click('#ritualBtn'); page.click('#ritualBtn'); time.sleep(0.3)
    check('New Moon Ritual resets for permanent shards', page.evaluate('__moon.save.shards') > shards0 and page.evaluate('Object.keys(__moon.save.best).length === 0'), page.evaluate('__moon.save.shards'))
    page.click('#shrine [data-back]')

    # --- language switch to Arabic ---
    page.click('#langBtn'); time.sleep(0.2)
    check('Arabic switches to RTL and Arabic text', page.evaluate("document.documentElement.dir === 'rtl' && /[\\u0600-\\u06FF]/.test(document.getElementById('playBtn').textContent)"))
    check('Arabic digits in Arabic', page.evaluate("/^[٠-٩]+$/.test(document.getElementById('titleLight').textContent)"), page.evaluate("document.getElementById('titleLight').textContent"))

    check('no console errors (YouTube build)', not errors, errors[:5])
    check('no network requests except the SDK', not foreign, foreign[:5])
    b.close()

def lang_boot(p):
    base = 'http://127.0.0.1:8611/'
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    ctx.add_init_script("sessionStorage.setItem('mockcfg', JSON.stringify({lang: 'ar-SA'}))")
    page = ctx.new_page(); errors, foreign = watch(page, base)
    page.goto(base)
    wait_for(page, "document.body.classList.contains('ready')", 10)
    check('Arabic by default from getLanguage(ar-SA)', page.evaluate("document.documentElement.dir === 'rtl' && document.documentElement.lang === 'ar'"))
    # touch drag moves the moon
    page.tap('#playBtn')
    wait_for(page, "__moon.mode === 'play'", 5)
    cdp = ctx.new_cdp_session(page)
    m0 = page.evaluate('__moon.world.moon.x')
    pts = [(100, 500), (160, 470), (230, 440), (300, 420)]
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': pts[0][0], 'y': pts[0][1]}]})
    for x, y in pts[1:]:
        time.sleep(0.1); cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': y}]})
    time.sleep(0.5)
    m1 = page.evaluate('__moon.world.moon.x')
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    check('one-finger drag moves the moon on a phone', m1 - m0 > 60, f'{m0:.0f} -> {m1:.0f}')
    check('no console errors (Arabic phone)', not errors, errors[:3])
    check('no network requests except the SDK (Arabic phone)', not foreign, foreign[:3])
    b.close()

def screenshots(p):
    base = 'http://127.0.0.1:8611/'
    sizes = {'phone-portrait': (390, 844, True), 'phone-landscape': (844, 390, True), 'desktop': (1920, 1080, False)}
    b = p.chromium.launch()
    for lang in ('en', 'ar'):
        for name, (w, h, mob) in sizes.items():
            ctx = b.new_context(viewport={'width': w, 'height': h}, is_mobile=mob, has_touch=mob, device_scale_factor=2 if mob else 1)
            ctx.add_init_script("sessionStorage.setItem('mockcfg', JSON.stringify({lang: '%s'}))" % ('ar-SA' if lang == 'ar' else 'en-US'))
            page = ctx.new_page(); errors, foreign = watch(page, base)
            page.goto(base); wait_for(page, "document.body.classList.contains('ready')", 10)
            # skip the tutorial and give some progress so screens have content
            page.evaluate("""() => { const s = __moon.save; s.tut = 5; s.played = 5; s.light = 820; for (let i = 0; i < 11; i++) s.best[i] = 1 + (i % 3); s.up = { pull: 2, magnet: 1, flip: 1 }; }""")
            page.evaluate("() => { __moon.startLevel(0); __moon.startLevel(0); }")
            page.evaluate("() => { document.getElementById('corner').hidden = false; }")
            page.evaluate("() => { __moon.persist(); }")
            page.reload(); wait_for(page, "document.body.classList.contains('ready')", 10)
            time.sleep(0.6)
            page.screenshot(path=os.path.join(SHOTS, f'{lang}-{name}-title.png'))
            page.evaluate('__moon.startLevel(12)')
            install_pilot(page, 0.8, 1)
            time.sleep(4.5)
            page.screenshot(path=os.path.join(SHOTS, f'{lang}-{name}-play.png'))
            page.evaluate("() => { __moon.driver = null; }")
            page.keyboard.press('Escape'); time.sleep(0.2)
            page.screenshot(path=os.path.join(SHOTS, f'{lang}-{name}-pause.png'))
            page.click('#pauseMap'); time.sleep(0.2)
            page.screenshot(path=os.path.join(SHOTS, f'{lang}-{name}-chart.png'))
            page.click('#chart [data-back]'); page.click('#shrineBtn'); time.sleep(0.2)
            page.screenshot(path=os.path.join(SHOTS, f'{lang}-{name}-shrine.png'))
            page.click('#shrine [data-back]')
            page.evaluate('__moon.startLevel(1)'); install_pilot(page, 0.8, 10)
            wait_for(page, "__moon.screen === 'win'", 90); time.sleep(0.8)
            page.screenshot(path=os.path.join(SHOTS, f'{lang}-{name}-win.png'))
            overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
            check(f'{lang} {name}: no errors, no foreign requests, no sideways overflow', not errors and not foreign and not overflow, (errors or foreign)[:2])
            ctx.close()
    b.close()

def pages_and_artifact(p):
    b = p.chromium.launch()
    # Pages build
    base = 'http://127.0.0.1:8612/'
    page = b.new_page(viewport={'width': 1280, 'height': 720}); errors, foreign = watch(page, base)
    page.goto(base)
    ok = wait_for(page, "document.body.classList.contains('ready')", 10)
    og = page.evaluate("document.querySelector('meta[property=\"og:image\"]').content")
    desc = page.evaluate("!!document.querySelector('meta[name=\"description\"]')")
    check('Pages build loads with og:image and description', ok and og == 'https://qtur.github.io/moonpull/og.png' and desc, og)
    check('Pages build has .nojekyll and og.png', os.path.exists(os.path.join(DIST, 'pages', '.nojekyll')) and os.path.exists(os.path.join(DIST, 'pages', 'og.png')))
    fonts_ok = page.evaluate("document.fonts.check('700 20px Moonfont') && document.fonts.check('700 20px Moonfont', 'مد')")
    check('Pages build font loads (Latin and Arabic)', fonts_ok)
    check('no console errors (Pages build)', not errors, errors[:3])
    check('no network requests except the SDK (Pages build)', not foreign, foreign[:3])
    # Artifact build, no SDK: falls back to local storage
    base = 'http://127.0.0.1:8613/'
    page = b.new_page(viewport={'width': 1280, 'height': 720}); errors, foreign = watch(page, base)
    page.goto(base + 'index.html')
    ok = wait_for(page, "document.body.classList.contains('ready')", 10)
    page.click('#langBtn'); time.sleep(0.5)
    check('Artifact build runs without the SDK and saves to local storage', ok and page.evaluate("localStorage.getItem('moonpull.save.v1') !== null"))
    check('no console errors (Artifact build)', not errors, errors[:3])
    b.close()

if __name__ == '__main__':
    # the artifact build has no document shell of its own; wrap it for the local check
    art_dir = os.path.join(DIST, 'artifact-check'); os.makedirs(art_dir, exist_ok=True)
    body = open(os.path.join(DIST, 'artifact', 'moonpull.html')).read()
    open(os.path.join(art_dir, 'index.html'), 'w').write('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + body + '</body></html>')
    s1 = serve(os.path.join(DIST, 'youtube'), 8611); s2 = serve(os.path.join(DIST, 'pages'), 8612); s3 = serve(art_dir, 8613)
    parts = sys.argv[1:] or ['youtube', 'lang', 'pages', 'shots']
    with sync_playwright() as p:
        if 'youtube' in parts: main_youtube(p)
        if 'lang' in parts: lang_boot(p)
        if 'pages' in parts: pages_and_artifact(p)
        if 'shots' in parts: screenshots(p)
    bad = [r for r in results if not r[1]]
    print(f'\n{len(results) - len(bad)}/{len(results)} checks passed')
    json.dump([{'check': n, 'ok': o, 'detail': str(d)} for n, o, d in results], open(os.path.join(DIST, 'check-results.json'), 'w'), ensure_ascii=False, indent=1)
    sys.exit(1 if bad else 0)
