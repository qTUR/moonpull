// Pacing simulation: virtual players of different skill play the real level physics
// and the real economy, level after level, until the story is done.
const Core = require('./core-load.cjs');
const DT = 1 / 120;

function pilotFactory(skill, rnd) {
  // A virtual player: surfs with the moon behind, times launches toward high moonlight and over rocks,
  // dodges thorns, and uses the New Moon under arches. Skill sets how often it tries and how precise it is.
  let state = 'push', t = 0, noiseX = 0, noiseY = 0, nextNoise = 0, bestX = 0, stuckT = 0, retreat = 0;
  const plan = (obj, p) => (obj.plan != null ? obj.plan : (obj.plan = rnd() < p));
  return function control(w, dt) {
    const o = w.o, lv = w.lv;
    t += dt; nextNoise -= dt;
    if (nextNoise <= 0) { nextNoise = 0.2 + rnd() * 0.3; noiseX = (rnd() - 0.5) * 170 * (1 - skill); noiseY = (rnd() - 0.5) * 110 * (1 - skill); }
    // A person who is stuck backs off to get a run-up.
    if (o.x > bestX + 40) { bestX = o.x; stuckT = 0; } else stuckT += dt;
    if (stuckT > 5 && retreat <= 0) { retreat = 1 + rnd(); stuckT = 0; bestX = o.x; for (const r of lv.rocks) r.plan = null; }
    if (retreat > 0) { retreat -= dt; w.setMoon(o.x + 170, Core.MOON_MIN + 20); state = 'push'; return; }
    const vx = Math.max(120, o.vx);
    const surf = w.surf(o.x);
    const rock = lv.rocks.find(r => r.x - r.w / 2 > o.x - 30 && r.x - r.w / 2 < o.x + 360 && r.top > surf + 20);
    const thornNear = lv.thorns.find(th => th.x > o.x - 60 && th.x < o.x + 480);
    const avoidAir = thornNear && plan(thornNear, 0.3 + skill * 0.7);
    const arch = lv.arches.find(a => o.x > a.x - a.w / 2 - 280 && o.x < a.x + a.w / 2 + 40);
    if (w.st.newmoon) {
      const want = arch && plan(arch, 0.35 + skill * 0.6) ? -1 : 1;
      if (want !== w.moon.phase && rnd() < dt * (2 + skill * 10)) w.togglePhase();
    }
    const newMoon = w.moon.phase < 0;
    // next moonlight worth chasing
    const m = lv.motes.find(mm => !mm.got && mm.x > o.x - 10 && mm.x < o.x + 460);
    const chaseHigh = m && m.y - surf > 70 && plan(m, 0.1 + skill * 0.85);
    const low = Core.MOON_MIN + 10 + (1 - skill) * 30;
    const high = Core.MOON_MIN + Core.MOON_SPAN + 60;
    const lead = vx * (0.5 + 0.1 * rnd()) + 30 + (1 - skill) * (rnd() - 0.5) * 160;
    let wantLaunchAt = null;
    if (!avoidAir && !arch) {
      if (rock && plan(rock, 0.7 + skill * 0.3)) wantLaunchAt = rock.x - rock.w / 2 - vx * 0.45;
      else if (chaseHigh) wantLaunchAt = m.x - lead;
      else { const j = lv.jellies.find(jj => jj.x > o.x + 40 && jj.x < o.x + 400); if (j && plan(j, skill * 0.7)) wantLaunchAt = j.x - vx * 0.7; }
    }
    let tx, ty;
    if (state === 'push') {
      tx = newMoon ? o.x + 150 : o.x - 150; ty = low + 25;
      if (m && !chaseHigh && !newMoon) ty = m.y > o.y + 10 ? low : low + 70; // ride the swell to the height of low moonlight
      if (avoidAir) ty = low + 150;
      if (wantLaunchAt != null && !o.air && o.x > wantLaunchAt - vx * 0.4 && t > 0.25) { state = 'charge'; t = 0; }
    } else if (state === 'charge') {
      tx = o.x - 10; ty = low;
      if (t > 0.3 + (1 - skill) * 0.2 * rnd()) { state = 'flick'; t = 0; }
    } else {
      tx = o.x + 60; ty = high;
      if (t > 0.4) { state = 'push'; t = 0; }
    }
    if (o.air && w.st.tether && state === 'push') {
      const target = lv.motes.find(mm => !mm.got && mm.x > o.x && mm.x < o.x + 300);
      if (target && plan(target, skill)) { tx = target.x; ty = Math.max(target.y + 90, low + 40); }
      else { tx = o.x + 140; ty = Math.max(o.y + 80, low + 40); }
    }
    w.setMoon(tx + noiseX, ty + noiseY);
  };
}

function playLevel(index, save, skill, rnd, opts = {}) {
  const lv = Core.makeLevel(index, 0);
  const st = Core.stats(save.up, save.shards);
  const w = new Core.World(lv, st, { salt: save.played });
  const ctl = pilotFactory(skill, rnd);
  let t = 0; let revived = false; const kinds = {};
  while (t < 600) {
    ctl(w, DT * 2);
    w.step(DT); w.step(DT); t += DT * 2;
    for (const e of w.events) if (e.type === 'hurt') kinds[e.kind] = (kinds[e.kind] || 0) + 1;
    w.events.length = 0;
    if (w.done) break;
    if (w.dead) {
      if (!revived && opts.ads && rnd() < 0.35) { revived = true; w.revive(); continue; }
      break;
    }
  }
  const r = w.result();
  return { win: w.done, t, ...r, lightRaw: w.light, kinds, x: w.o.x | 0, len: lv.len };
}

const PRIORITY = ['flip', 'pull', 'magnet', 'tether', 'flame', 'pull', 'magnet', 'puffin', 'bell'];

function campaign(skill, seed, log) {
  let s = seed; const rnd = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
  const save = { light: 0, up: {}, best: {}, shards: 0, played: 0 };
  const total = () => Object.values(save.best).reduce((a, b) => a + b, 0);
  const regionStart = r => Core.REGIONS.slice(0, r).reduce((a, x) => a + x.levels, 0);
  const humanFactor = 1.9 - skill * 0.8; // hesitation, looking around, retrying mentally
  const OVERHEAD = 20; // menus, result screens
  let clock = 0; const regionTime = new Array(7).fill(0); const regionPlays = new Array(7).fill(0);
  let walls = 0, fails = 0, farm = 0, missionsLight = 0;
  let idx = 0; let stuck = 0;
  const upgrade = () => {
    for (let pass = 0; pass < 6; pass++) {
      let bought = false;
      for (const id of PRIORITY) {
        const u = Core.upgradeById[id]; const have = save.up[id] || 0;
        if (have >= u.max) continue;
        if (u.needLevel && !(save.best[u.needLevel - 1] > 0)) continue;
        const c = Core.upgradeCost(id, have);
        if (save.light >= c) { save.light -= c; save.up[id] = have + 1; bought = true; break; }
      }
      if (!bought) break;
    }
  };
  while (idx < Core.STORY_LEVELS && clock < 3600 * 12) {
    const info = Core.levelInfo(idx);
    // Region gate: farm pearls on the weakest earlier level
    if (info.local === 0 && info.region > 0 && total() < Core.regionGate(info.region)) {
      let worst = -1, wp = 4;
      for (let k = 0; k < idx; k++) if ((save.best[k] || 0) < wp) { wp = save.best[k] || 0; worst = k; }
      if (worst < 0 || wp >= 3) { walls++; break; }
      const r = playLevel(worst, save, skill, rnd, { ads: true });
      const dtime = r.t * humanFactor + OVERHEAD; clock += dtime; regionTime[info.region - 1] += dtime; farm++;
      save.played++;
      if (r.win) { save.best[worst] = Math.max(save.best[worst] || 0, r.pearls); save.light += Math.round(r.lightRaw) + 15 + 3 * worst; }
      else save.light += Math.round(r.lightRaw * 0.5);
      stuck++; if (stuck > 25) { walls++; break; }
      upgrade();
      continue;
    }
    const r = playLevel(idx, save, skill, rnd, { ads: true });
    const dtime = r.t * humanFactor * (save.best[idx] ? 1 : 1.3) + OVERHEAD; clock += dtime; regionTime[info.region] += dtime; regionPlays[info.region]++;
    save.played++;
    if (r.win) {
      save.best[idx] = Math.max(save.best[idx] || 0, r.pearls);
      const bonus = 15 + 3 * idx; let gain = Math.round(r.lightRaw) + bonus;
      if (rnd() < 0.3) gain *= 2; // sometimes watches the ×2 ad
      save.light += gain;
      // mission rewards trickle in, about one per level early on
      const mr = idx < Core.MISSIONS.length ? Core.MISSIONS[idx].reward : 150; save.light += mr; missionsLight += mr;
      if (info.region === 4 && info.local === Core.REGIONS[4].levels - 1) save.up.newmoon = 1;
      idx++; stuck = 0;
    } else { fails++; save.light += Math.round(r.lightRaw * 0.5); stuck++; if (stuck > 12) { walls++; break; } }
    upgrade();
    if (log) log(idx, r, clock, save);
  }
  return { wallAt: idx, skill, clock, regionTime, regionPlays, walls, fails, farm, done: idx, pearls: total(), up: save.up, light: save.light, missionsLight };
}

if (require.main === module) {
  const fmt = s => (s / 60).toFixed(0) + 'm';
  const names = Core.REGIONS.map(r => r.key);
  for (const [label, skill] of [['weak', 0.4], ['average', 0.62], ['strong', 0.85]]) {
    const runs = []; const firstLevels = [];
    for (let k = 0; k < 2; k++) runs.push(campaign(skill, 1234 + k * 99, (idx, r, clock) => { if (k === 0 && idx <= 3 && r.win) firstLevels.push(Math.round(clock)); }));
    const avg = f => runs.reduce((a, r) => a + f(r), 0) / runs.length;
    console.log(`\n${label} (skill ${skill}): total ${fmt(avg(r => r.clock))}, finished ${avg(r => r.done).toFixed(1)}/${Core.STORY_LEVELS}, pearls ${avg(r => r.pearls).toFixed(0)}, fails ${avg(r => r.fails).toFixed(0)}, farm replays ${avg(r => r.farm).toFixed(0)}, walls ${avg(r => r.walls)} at ${runs.map(r => r.walls ? r.wallAt : '-').join(',')}`);
    console.log('  per region: ' + names.map((n, i) => `${n} ${fmt(avg(r => r.regionTime[i]))}`).join(' · '));
    console.log('  clock after levels 1-3: ' + firstLevels.map(x => x + 's').join(', ') + ' · upgrades at end: ' + JSON.stringify(runs[0].up));
  }
}
module.exports = { campaign, playLevel, pilot: pilotFactory };
