"""Phone screenshots for the store listing (1080x1920), English and Arabic, from the store build."""
import os, sys, time, functools, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'art', 'store'); os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, 'tests'))
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = ThreadingHTTPServer(('127.0.0.1', 8651), functools.partial(Quiet, directory=os.path.join(ROOT, 'dist', 'play')))
threading.Thread(target=srv.serve_forever, daemon=True).start()
SIM = open(os.path.join(ROOT, 'tools', 'sim.cjs')).read()
PILOT = SIM[SIM.index('function pilotFactory'):SIM.index('function playLevel')]
errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for lang in ('en', 'ar'):
        ctx = b.new_context(viewport={'width': 540, 'height': 960}, device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = ctx.new_page(); pg.on('pageerror', lambda e: errors.append(str(e)))
        pg.goto('http://127.0.0.1:8651/'); pg.wait_for_function("document.body.classList.contains('ready')")
        pg.evaluate("""(l) => { const s = __moon.save; s.lang = l; s.tut = 5; s.played = 9; s.light = 1240; for (let i = 0; i < 13; i++) s.best[i] = 1 + (i % 3); s.up = { pull: 3, magnet: 2, flip: 1, tether: 1 }; s.giftAt = Date.now(); __moon.persist(); }""", lang)
        pg.reload(); pg.wait_for_function("document.body.classList.contains('ready')"); time.sleep(0.8)
        n = 1
        def snap(name):
            global n
            f = os.path.join(OUT, f'phone-{lang}-{n}-{name}.png'); pg.screenshot(path=f)
            Image.open(f).convert('RGB').save(f, optimize=True); n += 1
        snap('title')
        for lv, wait in ((9, 5.0), (14, 6.0), (22, 6.5)):
            pg.evaluate(f'__moon.startLevel({lv})')
            pg.evaluate("""(src) => { let s = 77; const rnd = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
               const ctl = new Function('skill', 'rnd', src + '; return pilotFactory(skill, rnd);')(0.85, rnd); __moon.driver = (w, dt) => ctl(w, dt); __moon.timeScale = 1; }""", PILOT)
            time.sleep(wait); snap('play')
            pg.evaluate('__moon.driver = null'); pg.keyboard.press('Escape'); pg.click('#pauseMap'); pg.click('#chart [data-back]')
        pg.click('#shrineBtn'); time.sleep(0.4); snap('shrine'); pg.click('#shrine [data-back]')
        pg.click('#chartBtn'); time.sleep(0.4); snap('chart')
        ctx.close()
    b.close()
srv.shutdown()
print('errors', errors)
