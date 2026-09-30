"""Gallery images drawn by the game's own renderer (the YouTube build), in three sizes and three
text variants, plus the og.png for the web page. Output goes to art/."""
import os, sys, time, json, functools, threading, zipfile
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, 'art'); os.makedirs(ART, exist_ok=True)
MOCK = open(os.path.join(ROOT, 'tests', 'mock-sdk.js')).read()
SDK = 'https://www.youtube.com/game_api/v1'

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = ThreadingHTTPServer(('127.0.0.1', 8621), functools.partial(Quiet, directory=os.path.join(ROOT, 'dist', 'youtube')))
threading.Thread(target=srv.serve_forever, daemon=True).start()

SIZES = {'16x9': (1920, 1080), '1x1': (1280, 1280), '9x16': (1080, 1920), 'og': (1200, 630)}
TITLES = {'en': ('Moonpull', 'Move the moon. Lift the sea.'), 'ar': ('مدّ القمر', 'حرّك القمر، وارفع البحر.')}

SCENE = r"""([kind, level]) => {
  const s = __moon.save; s.tut = 5; s.up = { pull: 3, flip: 1 };
  __moon.startLevel(level);
  __moon.timeScale = 0;
  const w = __moon.world, lv = w.lv;
  document.getElementById('ui').style.display = 'none';
  const wide = kind === '16x9' || kind === 'og';
  View.setZoom(wide ? 1.3 : kind === '1x1' ? 1.2 : 1.3);
  const X = 3000;
  lv.rocks = [{ x: X + (wide ? 520 : 330), w: 120, top: 150, seed: 7 }]; lv.thorns = []; lv.arches = []; lv.whirls = []; lv.gusts = []; lv.whales = [];
  lv.jellies = [{ x: X - (wide ? 420 : 250), ph: 0 }];
  lv.buoys = [{ x: X - (wide ? 760 : 420), lit: true }];
  lv.motes = [];
  for (let k = 0; k < 7; k++) { const t = k / 6; lv.motes.push({ x: X + (wide ? 60 : 50) + k * (wide ? 50 : 34), y: (wide ? 300 : 200) + Math.sin(t * Math.PI) * 70 - t * 90, got: false, gold: k === 3 }); }
  for (let k = 0; k < 4; k++) lv.motes.push({ x: X - 200 - k * 55, y: 60, got: false });
  w.moon.x = w.moon.tx = X - (wide ? 190 : kind === '9x16' ? 105 : 150); w.moon.y = w.moon.ty = Core.MOON_MIN + 40;
  w.t = 3;
  for (let i = 0; i < 500; i++) w.stepWater(1 / 120);
  const o = w.o; o.x = X; o.y = w.surf(X) + (wide ? 120 : 55); o.vx = wide ? 470 : 0; o.vy = 420; o.air = true; o.airT = 0.2; o.rot = 0;
  View.cam.lock = true;
  const S = View.S, H = innerHeight, W = innerWidth;
  const wantY = wide ? 0.5 * H : 0.62 * H, wantX = wide ? 0.33 * W : 0.52 * W;
  View.cam.x = o.x - (wantX - W / 2) / S;
  View.cam.y = o.y - (View.horizon - wantY) / S;
  window.__otterBox = () => { const x = View.sx(o.x), y = View.sy(o.y), S = View.S; return { l: x - 80 * S, r: x + 70 * S, t: y - 110 * S, b: y + 60 * S }; };
}"""

def overlay(page, lang, kind):
    title, tag = TITLES[lang]
    wide = kind in ('16x9', 'og')
    page.evaluate("""([title, tag, lang, wide, kind]) => {
      let d = document.getElementById('promoText'); if (d) d.remove();
      if (!title) return;
      d = document.createElement('div'); d.id = 'promoText'; d.dir = lang === 'ar' ? 'rtl' : 'ltr';
      const H = innerHeight, W = innerWidth;
      const size = kind === 'og' ? 104 : wide ? 150 : kind === '1x1' ? 130 : 150;
      Object.assign(d.style, { position: 'fixed', zIndex: 9, textAlign: 'center', fontFamily: 'Moonfont', color: '#fff6dc', pointerEvents: 'none',
        top: wide ? '11%' : kind === '1x1' ? '5%' : '9%', left: wide ? '52%' : '6%', right: wide ? '3%' : '6%' });
      d.innerHTML = `<div style="font-weight:700;font-size:${size}px;line-height:1.05;text-shadow:0 0 .35em rgba(255,220,150,.6),0 .05em 0 #b57a3a,0 .12em .4em rgba(0,0,0,.55)">${title}</div>` +
        `<div style="margin-top:.35em;font-size:${Math.round(size * 0.3)}px;color:#8fe3d6;text-shadow:0 2px 10px rgba(0,0,0,.7)">${tag}</div>`;
      document.body.appendChild(d);
    }""", [title, tag, lang, wide, kind])

def boxes_clear(page):
    r = page.evaluate("""() => { const o = __otterBox(); const d = document.getElementById('promoText'); if (!d) return { ok: true, o }; const b = d.getBoundingClientRect();
      const hit = !(b.right < o.l || b.left > o.r || b.bottom < o.t || b.top > o.b); return { ok: !hit, o, t: { l: b.left, r: b.right, t: b.top, b: b.bottom }, W: innerWidth, H: innerHeight }; }""")
    return r

def clean(path):
    im = Image.open(path).convert('RGB')
    im.save(path, 'PNG', optimize=True)  # re-encoded: no text chunks or other metadata

report = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for kind, (w, h) in SIZES.items():
        ctx = b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=1)
        page = ctx.new_page()
        page.route(SDK, lambda r: r.fulfill(status=200, content_type='text/javascript', body=MOCK))
        page.goto('http://127.0.0.1:8621/')
        page.wait_for_function("document.body.classList.contains('ready')")
        page.evaluate(SCENE, [kind, 9])
        time.sleep(1.6)
        variants = [('en', 'en'), ('ar', 'ar'), ('none', None)] if kind != 'og' else [('en', 'en')]
        for name, lang in variants:
            if lang: overlay(page, lang, kind)
            else: page.evaluate("() => { const d = document.getElementById('promoText'); if (d) d.remove(); }")
            time.sleep(0.25)
            chk = boxes_clear(page)
            out = os.path.join(ART, 'og.png' if kind == 'og' else f'moonpull-{kind}-{name}.png')
            page.screenshot(path=out); clean(out)
            report.append((os.path.basename(out), chk['ok'], chk))
            print(os.path.basename(out), 'title clear of Nuri' if chk['ok'] else 'OVERLAP', flush=True)
        ctx.close()
    b.close()
srv.shutdown()
with zipfile.ZipFile(os.path.join(ROOT, 'dist', 'moonpull-gallery.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
    for f in sorted(os.listdir(ART)):
        if f.startswith('moonpull-') and f.endswith('.png'): z.write(os.path.join(ART, f), f)
    z.write(os.path.join(ART, 'description.txt'), 'description.txt') if os.path.exists(os.path.join(ART, 'description.txt')) else None
sys.exit(0 if all(r[1] for r in report) else 1)
