/* PC 看板前端（D3）—— 无框架、无 CDN，断网也能跑。
   数据只从 /api/state 来，每 1 s 拉一次。 */
(function () {
  'use strict';

  var state = null;
  var tab = 'nodes';
  var sub = 'env';
  var NODE_COLORS = { nodeA: '#4c9aff', nodeB: '#b07cff', nodeX: '#8fa3bf' };

  function $(id) { return document.getElementById(id); }
  function txt(v, d) { return (v === null || v === undefined || v === '') ? (d || '—') : v; }

  function ago(s) {
    if (s === null || s === undefined) return '—';
    if (s < 1) return '<1 s';
    if (s < 60) return s.toFixed(1) + ' s 前';
    return Math.floor(s / 60) + ' min ' + Math.round(s % 60) + ' s 前';
  }

  /* ---------------- 页签 ---------------- */
  function setTab(name) {
    tab = name;
    ['nodes', 'curves', 'events'].forEach(function (t) {
      $('tab-' + t).classList.toggle('hide', t !== name);
    });
    Array.prototype.forEach.call(document.querySelectorAll('#tabs button'), function (b) {
      b.classList.toggle('on', b.getAttribute('data-tab') === name);
    });
    var hint = { nodes: '两个节点 · 状态机取 6 s / 30 s', curves: '窗口 5 min', events: '按 ts 排序' };
    $('hint').textContent = hint[name] || '';
    render();
  }

  function setSub(name) {
    sub = name;
    $('sub-env').classList.toggle('hide', name !== 'env');
    $('sub-link').classList.toggle('hide', name !== 'link');
    Array.prototype.forEach.call(document.querySelectorAll('.subtabs button'), function (b) {
      b.classList.toggle('on', b.getAttribute('data-sub') === name);
    });
    render();
  }

  /* ---------------- 总览 ---------------- */
  function renderOverview() {
    if (!state) return;
    $('ov-online').textContent = state.online + '/' + state.total;
    var al = $('ov-alarm');
    al.textContent = state.alarms;
    al.style.color = state.alarms ? '#ef5350' : '#35c46b';
    $('ov-events').textContent = state.events_today;
    $('ov-timeout').textContent = state.warn_s.toFixed(0) + ' s / ' + state.offline_s.toFixed(0) + ' s';
    $('clock').textContent = state.now_text;
  }

  /* ---------------- 节点卡 ---------------- */
  var LV_STYLE = {
    hazard: 'background:rgba(239,83,80,.18);color:#ff8a87;border:1px solid rgba(239,83,80,.45)',
    caution: 'background:rgba(240,180,41,.15);color:#ffce5c;border:1px solid rgba(240,180,41,.4)',
    deny: 'background:rgba(176,124,255,.15);color:#c9a6ff;border:1px solid rgba(176,124,255,.4)'
  };

  function renderRecent() {
    var ul = $('recent');
    if (!ul) return;
    ul.innerHTML = '';
    if (!state.events.length) {
      ul.innerHTML = '<li style="color:#8fa3bf">还没有事件</li>';
      return;
    }
    state.events.slice(0, 5).forEach(function (e) {
      var badge = (e.level && e.level !== 'NA')
        ? '<span class="lv" style="' + (LV_STYLE[e.level] || '') + '">' + e.level_zh + '</span>'
        : '<span class="lv" style="background:#1c2740;color:#8fa3bf;border:1px solid #2b3b58">解除</span>';
      var li = document.createElement('li');
      li.innerHTML = '<span class="t">' + e.t + '</span>' +
        '<span class="nm">' + e.node + '</span>' +
        '<span class="ev">' + e.src_zh + ' · ' + e.event_zh + '</span>' + badge;
      ul.appendChild(li);
    });
  }

  function renderNodes() {
    if (!state) return;
    var box = $('nodecards');
    box.innerHTML = '';
    if (!state.nodes.length) {
      box.innerHTML = '<div class="empty">还没有任何帧。启动 mock：<code>python app.py --mock</code></div>';
      renderRecent();
      return;
    }
    state.nodes.forEach(function (n) {
      var st = n.status === 'ok' ? '在线' : (n.status === 'warn' ? '链路异常' : (n.frames_rx ? '离线' : '未上线'));
      var lvCls = n.lv >= 2 ? 'hazard' : (n.lv === 1 ? 'caution' : 'norm');
      var lvTxt = n.lv >= 2 ? '危险' : (n.lv === 1 ? '注意' : '正常');
      var pat = n.pattern ? n.pattern + ' ms' : '—';
      var integ = n.integrity === null ? '—' : n.integrity.toFixed(1) + '%';
      var cnt = (n.count === null || n.count === undefined) ? '—' : n.count;
      var skew = (n.skew_s === null || n.skew_s === undefined) ? '—'
        : (n.skew_s > 0 ? '+' : '') + n.skew_s.toFixed(2) + ' s';
      var drop = (n.dropped || 0) + ' 帧 / 失败 ' + (n.post_failed || 0);
      var el = document.createElement('div');
      el.className = 'card ' + n.status;
      el.innerHTML =
        '<div class="chead"><span class="name">' + n.name + '</span>' +
        '<span class="ip">' + n.ip + '</span>' +
        '<span class="pill ' + n.status + '">' + st + '</span></div>' +
        '<div class="lvl"><span class="lvlbig ' + lvCls + '">' + lvTxt + '</span>' +
        '<span class="pat">' + pat + '</span></div>' +
        '<dl>' +
        '<div><dt>最后心跳</dt><dd>' + ago(n.age_s) + '</dd></div>' +
        '<div><dt>报警来源</dt><dd>' + txt(n.src_zh) + '</dd></div>' +
        '<div><dt>门磁</dt><dd>' + n.door_zh + (n.door_ago !== null ? '（' + ago(n.door_ago) + '）' : '') + '</dd></div>' +
        '<div><dt>本组人次</dt><dd>' + cnt + '</dd></div>' +
        '<div><dt>帧完整性</dt><dd>' + integ + '</dd></div>' +
        '<div><dt>复位 / 重启</dt><dd>rst=' + n.rst + ' · ' + n.reboots + ' 次</dd></div>' +
        '<div><dt>时钟偏差 / 丢帧</dt><dd>' + skew + ' · ' + drop + '</dd></div>' +
        '</dl>';
      box.appendChild(el);
    });
    renderRecent();
  }

  /* ---------------- 曲线 ---------------- */
  function pts(tsArr, valArr) {
    var out = [];
    for (var i = 0; i < tsArr.length; i++) out.push([tsArr[i], valArr[i]]);
    return out;
  }

  function chart(cv, series, opt) {
    if (!cv) return;
    var dpr = window.devicePixelRatio || 1;
    var W = cv.clientWidth || 600, H = cv.clientHeight || 170;
    cv.width = Math.max(1, Math.round(W * dpr));
    cv.height = Math.max(1, Math.round(H * dpr));
    var g = cv.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H);

    var pad = { l: 44, r: 66, t: 14, b: 20 };
    var iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
    var now = (state && state.server_ts) || Date.now() / 1000;
    var t0 = now - 300, t1 = now;

    var lo = Infinity, hi = -Infinity;
    series.forEach(function (s) {
      s.pts.forEach(function (p) {
        if (p[1] !== null && isFinite(p[1])) { lo = Math.min(lo, p[1]); hi = Math.max(hi, p[1]); }
      });
    });
    (opt.thresholds || []).forEach(function (th) { lo = Math.min(lo, th.v); hi = Math.max(hi, th.v); });
    if (!isFinite(lo)) { lo = 0; hi = 1; }
    if (hi - lo < 1e-9) { hi = lo + 1; }
    var padv = (hi - lo) * 0.14;
    lo -= padv; hi += padv;
    if (opt.min !== undefined && lo < opt.min) lo = opt.min;

    function X(t) { return pad.l + (t - t0) / (t1 - t0) * iw; }
    function Y(v) { return pad.t + (1 - (v - lo) / (hi - lo)) * ih; }

    // 网格 + y 标尺
    g.font = '11px Consolas, monospace';
    g.textBaseline = 'middle';
    var rows = 4;
    for (var r = 0; r <= rows; r++) {
      var v = lo + (hi - lo) * r / rows;
      var y = Y(v);
      g.strokeStyle = 'rgba(255,255,255,.06)';
      g.beginPath(); g.moveTo(pad.l, y); g.lineTo(pad.l + iw, y); g.stroke();
      g.fillStyle = '#6f86a8';
      g.textAlign = 'right';
      g.fillText(v.toFixed(Math.abs(hi) > 100 ? 0 : 1), pad.l - 6, y);
    }
    // x 标尺（每 60 s）
    g.textAlign = 'center';
    for (var m = 0; m <= 5; m++) {
      var tt = t0 + m * 60, x = X(tt);
      g.strokeStyle = 'rgba(255,255,255,.05)';
      g.beginPath(); g.moveTo(x, pad.t); g.lineTo(x, pad.t + ih); g.stroke();
      var d = new Date(tt * 1000);
      var lab = ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
      g.fillStyle = '#6f86a8';
      g.fillText(lab, x, pad.t + ih + 11);
    }
    // 轴名/单位（右上角，贴近刻度区但不压数字）
    g.textAlign = 'right';
    g.fillStyle = '#8fa3bf';
    g.font = '11px "Microsoft YaHei UI", sans-serif';
    g.fillText(opt.unit || '', W - 6, 9);

    // 阈值线
    (opt.thresholds || []).forEach(function (th) {
      var y = Y(th.v);
      g.strokeStyle = th.color || 'rgba(239,83,80,.55)';
      g.setLineDash([4, 4]);
      g.beginPath(); g.moveTo(pad.l, y); g.lineTo(pad.l + iw, y); g.stroke();
      g.setLineDash([]);
      g.fillStyle = th.color || '#ef8a87';
      g.font = '10.5px Consolas, monospace';
      g.textAlign = 'left';
      g.fillText(th.label, pad.l + iw + 6, y);
    });

    // 线
    series.forEach(function (s) {
      g.strokeStyle = s.color;
      g.lineWidth = 1.8;
      g.beginPath();
      var on = false;
      s.pts.forEach(function (p) {
        if (p[1] === null || !isFinite(p[1])) { on = false; return; }
        var x = X(p[0]), y = Y(p[1]);
        if (!on) { g.moveTo(x, y); on = true; } else { g.lineTo(x, y); }
      });
      g.stroke();
      // 最新点
      for (var i = s.pts.length - 1; i >= 0; i--) {
        if (s.pts[i][1] !== null && isFinite(s.pts[i][1])) {
          g.fillStyle = s.color;
          g.beginPath(); g.arc(X(s.pts[i][0]), Y(s.pts[i][1]), 2.6, 0, 6.2832); g.fill();
          break;
        }
      }
    });

    // 图例
    var lx = pad.l + 8, ly = pad.t + 10;
    series.forEach(function (s) {
      g.fillStyle = s.color;
      g.fillRect(lx, ly - 4, 14, 2.5);
      g.fillStyle = '#cfe0f7';
      g.font = '11px Consolas, monospace';
      g.textAlign = 'left';
      g.fillText(s.name, lx + 19, ly);
      lx += 19 + g.measureText(s.name).width + 18;
    });
  }

  function renderCurves() {
    if (!state) return;
    var names = Object.keys(state.curves).sort();
    if (sub === 'env') {
      var sets = [
        { id: 'c-t', key: 't', unit: '℃', th: [{ v: 45, label: '45 ℃ L2' }] },
        { id: 'c-smoke', key: 'smoke', unit: '0–255', min: 0, th: [{ v: 120, label: 'L1 120' }, { v: 200, label: 'L2 200' }] },
        { id: 'c-flame', key: 'flame', unit: '0–255', min: 0, th: [{ v: 150, label: 'L1 150' }, { v: 250, label: 'L2 250' }] }
      ];
      sets.forEach(function (s) {
        var series = names.map(function (n) {
          return { name: n, color: NODE_COLORS[n] || '#8fa3bf', pts: pts(state.curves[n].ts, state.curves[n][s.key]) };
        });
        chart($(s.id), series, { unit: s.unit, min: s.min, thresholds: s.th });
      });
    } else {
      var sets2 = [
        { id: 'c-lat', key: 'lat', unit: 'ms', th: [] },
        { id: 'c-bw', key: 'bw', unit: 'B/s', th: [] },
        { id: 'c-cpu', key: 'cpu', unit: '%', th: [] }
      ];
      sets2.forEach(function (s) {
        var series = names.map(function (n) {
          var L = state.links[n] || { ts: [], lat: [], bw: [], cpu: [] };
          return { name: n, color: NODE_COLORS[n] || '#8fa3bf', pts: pts(L.ts, L[s.key]) };
        });
        chart($(s.id), series, { unit: s.unit, min: 0, thresholds: s.th });
      });
    }
  }

  /* ---------------- 事件时间线 ---------------- */
  function renderEvents() {
    if (!state) return;
    var body = $('evbody');
    body.innerHTML = '';
    if (!state.events.length) {
      body.innerHTML = '<tr><td colspan="7" class="empty">还没有事件</td></tr>';
      return;
    }
    state.events.slice(0, 60).forEach(function (e) {
      var tr = document.createElement('tr');
      tr.className = e.event === 'clear' ? 'clear' : (e.level || '');
      var cls = e.level === 'hazard' ? 'hazard' : (e.level === 'caution' ? 'caution' : (e.level === 'deny' ? 'deny' : 'na'));
      var badge = e.level === 'NA' || !e.level ? '<span class="badge na">—</span>'
        : '<span class="badge ' + cls + '">' + e.level_zh + ' · ' + e.level + '</span>';
      tr.innerHTML =
        '<td class="ts">' + e.t + '</td>' +
        '<td>' + e.node + '</td>' +
        '<td>' + e.src_zh + ' <span style="color:#6f86a8">(' + e.src + ')</span></td>' +
        '<td>' + e.event_zh + '</td>' +
        '<td>' + badge + '</td>' +
        '<td class="pat">' + txt(e.pattern) + '</td>' +
        '<td style="color:#8fa3bf">' + txt(e.note, '') + '</td>';
      body.appendChild(tr);
    });
  }

  function render() {
    renderOverview();
    if (tab === 'nodes') renderNodes();
    else if (tab === 'curves') renderCurves();
    else renderEvents();
  }

  /* ---------------- 拉数据 ---------------- */
  function tick() {
    fetch('/api/state', { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(function (s) {
        state = s;
        $('srvdot').classList.add('on');
        $('ov-src').textContent = 'POST /ingest · ' + (s.mock ? 'mock_feed 假数据' : '真实节点（无 mock）');
        render();
      })
      .catch(function () {
        $('srvdot').classList.remove('on');
      });
  }

  var q = new URLSearchParams(location.search);
  window.addEventListener('DOMContentLoaded', function () {
    if (q.get('mock') === '1') window.__MOCK__ = true;
    Array.prototype.forEach.call(document.querySelectorAll('#tabs button'), function (b) {
      b.addEventListener('click', function () { setTab(b.getAttribute('data-tab')); });
    });
    Array.prototype.forEach.call(document.querySelectorAll('.subtabs button'), function (b) {
      b.addEventListener('click', function () { setSub(b.getAttribute('data-sub')); });
    });
    setTab(q.get('tab') || 'nodes');
    setSub(q.get('sub') || 'env');
    tick();
    setInterval(tick, 1000);
    window.addEventListener('resize', function () { render(); });
  });
})();
