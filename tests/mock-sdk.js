// Stand-in for the Playables SDK, served at the SDK address during checks.
(function () {
  var cfg = {};
  try { cfg = JSON.parse(sessionStorage.getItem('mockcfg') || '{}'); } catch (e) {}
  var log = window.__yt = { calls: [], ads: [], reward: cfg.reward !== false, lang: cfg.lang || 'en-US', audio: cfg.audio !== false, boot: performance.now() };
  var cbs = { pause: [], resume: [], audio: [] };
  window.ytgame = {
    IN_PLAYABLES_ENV: true,
    game: {
      firstFrameReady: function () { log.calls.push(['firstFrameReady', performance.now()]); },
      gameReady: function () { log.calls.push(['gameReady', performance.now()]); },
      saveData: function (d) { log.calls.push(['saveData', d.length]); localStorage.setItem('mock.yt.save', d); return Promise.resolve(); },
      loadData: function () { log.calls.push(['loadData']); return Promise.resolve(localStorage.getItem('mock.yt.save') || ''); }
    },
    system: {
      isAudioEnabled: function () { return log.audio; },
      onAudioEnabledChange: function (cb) { cbs.audio.push(cb); return function () {}; },
      onPause: function (cb) { cbs.pause.push(cb); return function () {}; },
      onResume: function (cb) { cbs.resume.push(cb); return function () {}; },
      getLanguage: function () { return Promise.resolve(log.lang); }
    },
    ads: {
      requestRewardedAd: function (id) { log.ads.push(['rewarded', id, performance.now()]); return new Promise(function (r) { setTimeout(function () { r(log.reward); }, 250); }); },
      requestInterstitialAd: function () { log.ads.push(['interstitial', performance.now()]); return new Promise(function (r) { setTimeout(r, 250); }); }
    }
  };
  window.__ytfire = function (k, v) { cbs[k].forEach(function (f) { f(v); }); };
})();
