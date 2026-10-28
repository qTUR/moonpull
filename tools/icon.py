"""App icon, store icon and feature graphic, drawn by the game's own renderer."""
import os, time, functools, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'art', 'store'); os.makedirs(OUT, exist_ok=True)
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = ThreadingHTTPServer(('127.0.0.1', 8641), functools.partial(Quiet, directory=os.path.join(ROOT, 'dist', 'play')))
threading.Thread(target=srv.serve_forever, daemon=True).start()

SCENE = r"""([zoom, fx, fy, moonDx, moonDy]) => {
  const s = __moon.save; s.tut = 5; s.up = { pull: 3 };
  __moon.startLevel(9); __moon.timeScale = 0;
  document.getElementById('ui').style.display = 'none';
  const w = __moon.world, lv = w.lv, X = 3000;
  lv.rocks = []; lv.thorns = []; lv.arches = []; lv.whirls = []; lv.gusts = []; lv.whales = []; lv.jellies = []; lv.buoys = []; lv.motes = [];
  View.setZoom(zoom);
  w.moon.x = w.moon.tx = X + moonDx; w.moon.y = w.moon.ty = Core.MOON_MIN + moonDy; w.t = 3;
  for (let i = 0; i < 500; i++) w.stepWater(1 / 120);
  const o = w.o; o.x = X; o.y = w.surf(X) + 20; o.vx = 0; o.vy = 0; o.air = false;
  View.cam.lock = true; const S = View.S;
  View.cam.x = o.x - (fx * innerWidth - innerWidth / 2) / S;
  View.cam.y = o.y - (View.horizon - fy * innerHeight) / S;
}"""
def shot(w, h, args, path, extra=None):
    ctx = b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2)
    pg = ctx.new_page(); pg.goto('http://127.0.0.1:8641/')
    pg.wait_for_function("document.body.classList.contains('ready')")
    pg.evaluate(SCENE, args)
    if extra: pg.evaluate(extra)
    time.sleep(1.4); pg.screenshot(path=path); ctx.close()

with sync_playwright() as p:
    b = p.chromium.launch()
    # square close-up: Nuri's face, lantern and a slice of moon
    shot(256, 256, [3.0, 0.45, 0.8, -45, -120], OUT + '/_icon.png')
    # feature graphic 1024x500 with the title
    title = """() => { const d = document.createElement('div'); d.dir = 'ltr'; Object.assign(d.style, { position: 'fixed', zIndex: 9, top: '24%', right: '5%', width: '50%', textAlign: 'center', fontFamily: 'Moonfont', color: '#fff6dc' });
      d.innerHTML = '<div style="font-weight:700;font-size:92px;line-height:1;text-shadow:0 0 .35em rgba(255,220,150,.6),0 .05em 0 #b57a3a,0 .12em .4em rgba(0,0,0,.55)">Moonpull</div><div style="font-weight:700;font-size:54px;margin-top:.15em;color:#ffe9b8;text-shadow:0 0 .3em rgba(255,220,150,.5)">مدّ القمر</div>';
      document.body.appendChild(d); }"""
    shot(1024, 500, [1.8, 0.3, 0.8, -150, 30], OUT + '/_feature.png', title)
    b.close()
srv.shutdown()
ic = Image.open(OUT + '/_icon.png').convert('RGB').resize((512, 512), Image.LANCZOS)
ic.save(OUT + '/icon-512.png', optimize=True)
fg = Image.open(OUT + '/_feature.png').convert('RGB').resize((1024, 500), Image.LANCZOS)
fg.save(OUT + '/feature-1024x500.png', optimize=True)
# adaptive launcher foreground: the icon centred in the 72/108 safe zone
res = os.path.join(ROOT, 'android', 'app', 'src', 'main', 'res')
fgi = Image.new('RGBA', (432, 432), (0, 0, 0, 0))
fgi.paste(ic.resize((300, 300), Image.LANCZOS), (66, 66))
fgi.save(os.path.join(res, 'drawable-nodpi', 'ic_fg.png'), optimize=True)
for d, px in {'mdpi': 48, 'hdpi': 72, 'xhdpi': 96, 'xxhdpi': 144, 'xxxhdpi': 192}.items():
    os.makedirs(os.path.join(res, 'mipmap-' + d), exist_ok=True)
    ic.resize((px, px), Image.LANCZOS).save(os.path.join(res, 'mipmap-' + d, 'ic_launcher.png'), optimize=True)
for f in ('_icon.png', '_feature.png'): os.remove(OUT + '/' + f)
print('ok')
