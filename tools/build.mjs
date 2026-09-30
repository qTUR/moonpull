// Builds the three versions of the game from src/game.html.
import { readFileSync, writeFileSync, mkdirSync, rmSync, copyFileSync, existsSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { minify } from 'terser';

const ROOT = new URL('..', import.meta.url).pathname;
const SITE = 'https://qtur.github.io/moonpull/';
const src = readFileSync(ROOT + 'src/game.html', 'utf8');
const FONTS = [['el-messiri-regular.woff2', 400], ['el-messiri-bold.woff2', 700]];

const DESC_EN = 'Drag the moon to lift the sea and send Nuri the lantern otter surfing, flipping and flying toward the lighthouse.';
const DESC_AR = 'اسحب القمر عشان يرتفع البحر، وخلّ نوري قضاعة الفانوس تتزحلق وتتشقلب وتطير لين توصل المنارة.';

function fontFace(mode) {
  return FONTS.map(([f, w]) => {
    const url = mode === 'inline' ? `data:font/woff2;base64,${readFileSync(ROOT + 'fonts/' + f).toString('base64')}` : `fonts/${f}`;
    return `@font-face{font-family:Moonfont;src:url(${url}) format("woff2");font-weight:${w};font-style:normal;font-display:block}`;
  }).join('');
}
const squashCss = css => css.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\s+/g, ' ').replace(/\s*([{}:;,>])\s*/g, '$1').replace(/;}/g, '}').trim();

async function page(mode) {
  let html = src;
  // script
  const m = html.match(/<script>([\s\S]*?)<\/script>\s*<\/body>/);
  const js = (await minify(m[1], { compress: { passes: 2 }, mangle: true, format: { comments: false } })).code;
  html = html.replace(m[0], `<script>${js}</script></body>`);
  // style
  html = html.replace(/<style>([\s\S]*?)<\/style>/, (_, css) => `<style>${fontFace(mode === 'artifact' ? 'inline' : 'file')}${squashCss(css.replace('/*@FONTFACE*/', ''))}</style>`);
  const sdk = mode === 'artifact' ? '' : '<script src="https://www.youtube.com/game_api/v1"></script>';
  html = html.replace('<!--@SDK-->', sdk);
  let meta = '';
  if (mode === 'pages') {
    meta = [
      `<meta name="description" content="${DESC_EN}">`,
      `<meta property="og:type" content="website">`,
      `<meta property="og:title" content="Moonpull · مدّ القمر">`,
      `<meta property="og:description" content="${DESC_EN}">`,
      `<meta property="og:url" content="${SITE}">`,
      `<meta property="og:image" content="${SITE}og.png">`,
      `<meta property="og:image:width" content="1200">`,
      `<meta property="og:image:height" content="630">`,
      `<meta name="twitter:card" content="summary_large_image">`,
      `<meta name="twitter:image" content="${SITE}og.png">`,
      `<meta name="theme-color" content="#070b1f">`,
    ].join('');
  }
  html = html.replace('<!--@META-->', meta);
  // collapse whitespace between tags in markup
  html = html.replace(/>\s+</g, '><');
  if (mode === 'artifact') {
    // The artifact host supplies the document shell; keep head bits and body content only.
    const title = html.match(/<title>[\s\S]*?<\/title>/)[0];
    const style = html.match(/<style>[\s\S]*?<\/style>/)[0];
    const body = html.match(/<body>([\s\S]*)<\/body>/)[1];
    html = title + style + body;
  }
  return html;
}

const out = ROOT + 'dist/';
rmSync(out, { recursive: true, force: true });
for (const d of ['artifact', 'youtube/fonts', 'pages/fonts']) mkdirSync(out + d, { recursive: true });
writeFileSync(out + 'artifact/moonpull.html', await page('artifact'));
writeFileSync(out + 'youtube/index.html', await page('youtube'));
writeFileSync(out + 'pages/index.html', await page('pages'));
writeFileSync(out + 'pages/.nojekyll', '');
for (const [f] of FONTS) { copyFileSync(ROOT + 'fonts/' + f, out + 'youtube/fonts/' + f); copyFileSync(ROOT + 'fonts/' + f, out + 'pages/fonts/' + f); }
copyFileSync(ROOT + 'fonts/OFL.txt', out + 'pages/fonts/OFL.txt');
if (existsSync(ROOT + 'art/og.png')) copyFileSync(ROOT + 'art/og.png', out + 'pages/og.png');
execSync('zip -X -q -9 -r ../moonpull-youtube.zip index.html fonts', { cwd: out + 'youtube' });
const size = f => (readFileSync(f).length / 1024).toFixed(1) + ' KB';
console.log('artifact', size(out + 'artifact/moonpull.html'));
console.log('youtube ', size(out + 'youtube/index.html'), '+ zip', size(out + 'moonpull-youtube.zip'));
console.log('pages   ', size(out + 'pages/index.html'));
export { DESC_EN, DESC_AR };
