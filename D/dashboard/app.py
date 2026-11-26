#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四目边缘 · PC 看板（D 岗 · D3 mock 版）

三页面
  /          节点状态：心跳、在线判定、当前等级、门磁、环境值、数据完整性
  /curves    实时曲线：温度 / 湿度 / 烟雾 / 火焰，5 min 滚动
  /events    报警时间线：hazard / caution / deny，按 ts 排序（契约 3 §6）

接口
  POST /ingest    duo_bridge.py 推来的 JSON（宽容解析，见 README §四）
  GET  /api/state 页面 2 s 轮询
  GET  /health    健康检查

运行
  python app.py --data ../data --port 8000              # 正式（数据根 D/data）
  python app.py --data ../data/mock --port 8000         # mock 演示（不污染 raw/）

口径（契约 3 v1.1c）
  心跳 hb_interval_s = 2 s 常量；6 s 无新 @E 判"链路异常"；30 s 判"离线"
  报警只认 buzzer_level + pattern_ms，没有 freq_hz / tone
"""
import argparse
import csv
import json
import math
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HB_INTERVAL_S = 2.0          # 契约 3 §2：常量，不是读数
ABNORMAL_S = 6.0             # 3 帧无新 @E
OFFLINE_S = 30.0
WINDOW_S = 300.0             # 曲线 5 min
MAX_EVENTS = 400

NODE_IPS = {
    "milky-a": "192.168.5.9",
    "milky-b": "192.168.5.10",
    "milky-c": "192.168.5.11",
    "milky-d": "192.168.5.12",
}
LEVEL_NAME = {2: "hazard", 1: "caution", 0: "NA"}
PATTERN = {"hazard": "1000/500", "caution": "150/2850", "deny": "80x2/400", "NA": "NA"}
THRESHOLDS = {"smoke_l1": 120, "smoke_l2": 200, "flame_l1": 150, "flame_l2": 250,
              "temp_l2": 45.0, "hb_interval_s": 2.0}


def fnum(v, nd=1):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return round(x, nd)


class Store:
    def __init__(self, data_root, default_node="milky-a"):
        self.data = Path(data_root).resolve()
        self.default_node = default_node
        self.lock = threading.Lock()
        self.nodes = {}
        self.events = []
        self.rx = 0
        self.t0 = time.time()
        self.last_hb_log = {}
        self.raw_events = self.data / "raw" / "events"
        self.raw_env = self.data / "raw" / "env"
        self.raw_events.mkdir(parents=True, exist_ok=True)
        self.raw_env.mkdir(parents=True, exist_ok=True)

    # ---------- 节点 ----------
    def _node(self, nid):
        n = self.nodes.get(nid)
        if n is None:
            n = {
                "id": nid,
                "ip": NODE_IPS.get(nid, "NA"),
                "last_rx": None,
                "last_seen": None,
                "frames": 0,
                "first": None,
                "env": {"t": None, "h": None, "smoke": None, "flame": None,
                        "light": None, "sound": None, "rst": None},
                "door": None,
                "count": None,
                "level": 0,
                "src": "NONE",
                "series": [],
            }
            self.nodes[nid] = n
        return n

    def _write_env_raw(self, nid, ts, env):
        day = datetime.fromtimestamp(ts).strftime("%Y%m%d")
        path = self.raw_env / f"{day}.jsonl"
        row = {"ts": round(ts, 3), "node_id": nid}
        row.update(env)
        with path.open("a", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _write_event(self, ev):
        day = datetime.fromtimestamp(ev["ts"]).strftime("%Y%m%d")
        path = self.raw_events / f"{day}.csv"
        new = not path.exists()
        with path.open("a", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(["ts", "node_id", "src", "event", "buzzer_level", "pattern_ms", "note"])
            w.writerow([f'{ev["ts"]:.3f}', ev["node_id"], ev["src"], ev["event"],
                        ev["buzzer_level"], ev["pattern_ms"], ev["note"]])

    def add_event(self, nid, src, event, level, note=""):
        ev = {"ts": round(time.time(), 3), "node_id": nid, "src": src, "event": event,
              "buzzer_level": level, "pattern_ms": PATTERN.get(level, "NA"), "note": note}
        self.events.append(ev)
        self.events = self.events[-MAX_EVENTS:]
        self._write_event(ev)

    # ---------- 入站 ----------
    def ingest(self, obj, now=None):
        now = time.time() if now is None else now
        with self.lock:
            if isinstance(obj, list):
                for it in obj:
                    self._ingest_one(it, now)
                return
            if isinstance(obj, dict) and "batch" in obj:
                for it in obj["batch"]:
                    self._ingest_one(it, now)
                return
            self._ingest_one(obj, now)

    def _ingest_one(self, obj, now):
        if not isinstance(obj, dict):
            return
        typ = str(obj.get("type", "")).lower()
        nid = obj.get("node") or obj.get("node_id") or obj.get("id") or self.default_node
        nid = str(nid).strip() or self.default_node
        n = self._node(nid)
        n["last_seen"] = now

        if typ in ("env", "e", "@e"):
            env = {
                "t": fnum(obj.get("t")), "h": fnum(obj.get("h")),
                "smoke": fnum(obj.get("smoke", obj.get("smk")), 0),
                "flame": fnum(obj.get("flame", obj.get("flm")), 0),
                "light": fnum(obj.get("light"), 0), "sound": fnum(obj.get("sound"), 0),
                "rst": fnum(obj.get("rst"), 0),
            }
            for k, v in env.items():
                if v is not None:
                    n["env"][k] = v
            n["frames"] += 1
            n["last_rx"] = now
            if n["first"] is None:
                n["first"] = now
            self.rx += 1
            n["series"].append([now] + [env[k] if env[k] is not None else float("nan")
                                        for k in ("t", "h", "smoke", "flame")])
            n["series"] = [p for p in n["series"] if now - p[0] <= WINDOW_S + 30]
            self._write_env_raw(nid, now, {k: v for k, v in env.items() if v is not None})
            # 心跳事件：每节点 60 s 记一条，避免刷屏
            if now - self.last_hb_log.get(nid, 0) >= 60:
                self.last_hb_log[nid] = now
                self.add_event(nid, "HEARTBEAT", "heartbeat", "NA", "#hb")
            return

        if typ in ("a", "@a", "alarm"):
            args = obj.get("args") or [obj.get("lv"), obj.get("src", "NONE")]
            try:
                lv = int(args[0])
            except (TypeError, ValueError, IndexError):
                return
            lv = min(max(lv, 0), 2)
            src = str(args[1]).upper() if len(args) > 1 and args[1] else "NONE"
            if lv != n["level"] or src != n["src"]:
                n["level"], n["src"] = lv, src
                self.add_event(nid, src, "alarm" if lv > 0 else "clear",
                               LEVEL_NAME[lv], "#level-change")
            return

        if typ in ("d", "@d", "door"):
            args = obj.get("args") or [obj.get("val")]
            try:
                n["door"] = int(args[0])
            except (TypeError, ValueError, IndexError):
                pass
            return

        if typ in ("c", "@c", "count"):
            args = obj.get("args") or [obj.get("n")]
            try:
                n["count"] = int(args[0])
            except (TypeError, ValueError, IndexError):
                pass
            return

        if typ in ("r", "@r", "card"):
            uid = str(obj.get("uid", "NA"))
            ok = bool(obj.get("ok", False))
            if not ok:
                self.add_event(nid, "CARD", "deny", "deny", f"uid={uid}")
            return

        if typ == "heartbeat":
            return

    # ---------- 视图 ----------
    def state(self):
        now = time.time()
        with self.lock:
            nodes = []
            total_exp = 0.0
            total_rx = 0
            for nid, n in self.nodes.items():
                age = None if n["last_rx"] is None else round(now - n["last_rx"], 1)
                if age is None:
                    online = "silent"
                elif age > OFFLINE_S:
                    online = "offline"
                elif age > ABNORMAL_S:
                    online = "abnormal"
                else:
                    online = "online"
                exp = 0.0 if n["first"] is None else max((now - n["first"]) / HB_INTERVAL_S, 1.0)
                loss = None if n["first"] is None else round(max(0.0, 1 - n["frames"] / exp) * 100, 2)
                total_exp += exp
                total_rx += n["frames"]
                nodes.append({
                    "id": nid, "ip": n["ip"], "online": online, "age": age,
                    "frames": n["frames"], "expected": round(exp, 1),
                    "loss_pct": loss, "level": n["level"],
                    "level_name": LEVEL_NAME[n["level"]], "src": n["src"],
                    "door": n["door"], "count": n["count"], "env": n["env"],
                    "ip_from_contract5": nid in NODE_IPS,
                })
            order = {"milky-a": 0, "milky-b": 1, "milky-c": 2, "milky-d": 3}
            nodes.sort(key=lambda x: (order.get(x["id"], 9), x["id"]))
            series = {nid: [[round(p[0], 3), p[1], p[2], p[3], p[4]] for p in n["series"]]
                      for nid, n in self.nodes.items()}
            loss_all = None if total_exp <= 0 else round(max(0.0, 1 - total_rx / total_exp) * 100, 2)
            counts = {"hazard": 0, "caution": 0, "deny": 0, "NA": 0}
            for ev in self.events:
                counts[ev["buzzer_level"]] = counts.get(ev["buzzer_level"], 0) + 1
            return {
                "now": round(now, 3),
                "started": round(self.t0, 3),
                "hb_interval_s": HB_INTERVAL_S,
                "abnormal_s": ABNORMAL_S,
                "offline_s": OFFLINE_S,
                "window_s": WINDOW_S,
                "thresholds": THRESHOLDS,
                "nodes": nodes,
                "series": series,
                "events": list(reversed(self.events))[:80],
                "counts": counts,
                "integrity": {
                    "rx": total_rx, "expected": round(total_exp, 1),
                    "loss_pct": loss_all,
                    "window_s": round(now - self.t0, 1),
                },
                "data_root": str(self.data),
            }


# ------------------------------------------------------------------ HTML
CSS = """
:root{
  --bg:#0e1421; --panel:#161e2e; --panel2:#1b2537; --line:#26344e;
  --txt:#e8eefb; --muted:#8fa2c2; --accent:#4ea1ff; --green:#37d39a;
  --amber:#f5b544; --red:#ff6b6b; --purple:#b98bff;
}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 600px at 20% -10%,#18243a 0,#0e1421 55%) fixed;
  color:var(--txt);font:14px/1.5 "Segoe UI","Microsoft YaHei",system-ui,sans-serif}
.wrap{max-width:1240px;margin:0 auto;padding:22px 26px 34px}
header{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:18px}
.brand{display:flex;flex-direction:column;gap:2px}
.brand h1{margin:0;font-size:19px;letter-spacing:.4px}
.brand span{color:var(--muted);font-size:12px}
.live{margin-left:auto;display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 0 4px rgba(55,211,154,.12)}
.dot.warn{background:var(--amber);box-shadow:0 0 0 4px rgba(245,181,68,.12)}
nav{display:flex;gap:6px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:5px}
nav a{color:var(--muted);text-decoration:none;padding:7px 14px;border-radius:8px;font-size:13px}
nav a.on{background:linear-gradient(180deg,#2a3d5e,#22304a);color:#fff;box-shadow:inset 0 0 0 1px #3a557e}
.pills{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.pill{font-size:11px;padding:3px 9px;border-radius:999px;border:1px solid var(--line);color:var(--muted)}
.pill.ok{color:var(--green);border-color:rgba(55,211,154,.35);background:rgba(55,211,154,.08)}
.pill.warn{color:var(--amber);border-color:rgba(245,181,68,.35);background:rgba(245,181,68,.08)}
.pill.bad{color:var(--red);border-color:rgba(255,107,107,.35);background:rgba(255,107,107,.08)}
.pill.gray{color:#9aa7bd;border-color:#33405a;background:#1a2334}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:6px 0 18px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:13px 16px}
.kpi b{display:block;font-size:24px;font-weight:600;letter-spacing:.3px}
.kpi span{color:var(--muted);font-size:12px}
.kpi small{color:#6d7d99;font-size:11px}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:15px 17px;position:relative;overflow:hidden}
.card:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:#2b3c58}
.card.on:before{background:var(--green)}
.card.ab:before{background:var(--amber)}
.card.off:before{background:#4a5670}
.nhead{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.nid{font-size:16px;font-weight:600}
.ip{color:var(--muted);font-size:12px}
.nhead .pills{margin-left:auto}
.lvl{margin:12px 0 4px;display:flex;align-items:center;gap:10px}
.lvl b{font-size:15px}
.bar{flex:1;height:8px;border-radius:6px;background:#0c1220;display:flex;gap:3px;padding:0}
.bar i{flex:1;border-radius:5px;background:#233049}
.bar i.a{background:var(--green)} .bar i.b{background:var(--amber)} .bar i.c{background:var(--red)}
.env{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:12px}
.med{background:var(--panel2);border:1px solid #223049;border-radius:10px;padding:8px 10px}
.med span{display:block;color:var(--muted);font-size:11px}
.med b{font-size:15px;font-weight:600}
.med b.na{color:#5f6d86;font-weight:400}
.foot{display:flex;gap:14px;color:var(--muted);font-size:11.5px;margin-top:12px;flex-wrap:wrap}
h2{font-size:13px;color:var(--muted);font-weight:600;letter-spacing:.6px;margin:22px 0 10px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid #202c42}
th{color:#93a5c4;font-weight:500;font-size:12px}
td.num{font-variant-numeric:tabular-nums}
tbody tr:hover{background:#182136}
.badge{font-size:11px;padding:2px 8px;border-radius:6px;display:inline-block}
.b-hazard{background:rgba(255,107,107,.14);color:#ff8f8f;box-shadow:inset 0 0 0 1px rgba(255,107,107,.3)}
.b-caution{background:rgba(245,181,68,.14);color:#ffc46a;box-shadow:inset 0 0 0 1px rgba(245,181,68,.3)}
.b-deny{background:rgba(185,139,255,.14);color:#c7a6ff;box-shadow:inset 0 0 0 1px rgba(185,139,255,.3)}
.b-na{background:#1b2436;color:#8fa2c2;box-shadow:inset 0 0 0 1px #2c3a55}
.charts{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.chart{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:12px 14px}
.chart .t{display:flex;align-items:baseline;gap:8px}
.chart .t b{font-size:14px}
.chart .t span{color:var(--muted);font-size:11.5px;margin-left:auto}
svg{display:block;width:100%;height:180px}
.empty{color:#6f7f9b;font-size:13px;padding:26px 0;text-align:center}
.chips{display:flex;gap:10px;flex-wrap:wrap;margin:4px 0 14px}
.chip{border:1px solid var(--line);border-radius:10px;padding:8px 14px;background:var(--panel)}
.chip b{font-size:19px;margin-left:6px}
.chip.h b{color:#ff8f8f}.chip.c b{color:#ffc46a}.chip.d b{color:#c7a6ff}
.note{color:var(--muted);font-size:12px;margin-top:10px}
.footer{margin-top:26px;color:#6d7d99;font-size:11.5px;display:flex;gap:18px;flex-wrap:wrap}
"""

JS_COMMON = """
const $ = (s)=>document.querySelector(s);
const cn = (lv)=>({hazard:'危险',caution:'注意',deny:'拒绝',NA:'—'}[lv]||lv);
const f = (v,d=1)=> (v===null||v===undefined||Number.isNaN(v)) ? 'NA' : (Math.round(v*10**d)/10**d).toFixed(d);
const ago = (s)=> s===null||s===undefined ? '无' : (s<60? s.toFixed(1)+' s' : (s/60).toFixed(1)+' min');
const onlineCn = {online:['在线','ok'],abnormal:['链路异常','warn'],offline:['离线','bad'],silent:['无数据','gray']};
"""

PAGE_NODES_JS = """
function renderNodes(s){
  const seen = s.nodes.filter(n=>n.online!=='silent');
  const onlineN = s.nodes.filter(n=>n.online==='online').length;
  $('.kpi-online b').textContent = onlineN + ' / ' + s.nodes.length;
  $('.kpi-online small').textContent = seen.length< s.nodes.length ? '有节点未上报' : '心跳 '+s.hb_interval_s+' s';
  $('.kpi-rx b').textContent = s.integrity.rx;
  $('.kpi-rx small').textContent = '窗口 '+ (s.integrity.window_s/60).toFixed(1) +' min';
  $('.kpi-exp b').textContent = s.integrity.expected;
  $('.kpi-exp small').textContent = 'duration_s / 2 s';
  $('.kpi-loss b').textContent = s.integrity.loss_pct===null?'NA':s.integrity.loss_pct.toFixed(2)+' %';
  $('.kpi-loss small').textContent = '1 − rx / expected';

  $('#nodes').innerHTML = s.nodes.map(n=>{
    const [txt, cls] = onlineCn[n.online] || ['未知','gray'];
    const lvlBars = [0,1,2].map(i=>`<i class="${n.level>=i+1?(i===0?'a':i===1?'b':'c'):''}"></i>`).join('');
    const e=n.env;
    return `<div class="card ${n.online==='online'?'on':n.online==='abnormal'?'ab':'off'}">
      <div class="nhead"><span class="nid">${n.id}</span><span class="ip">${n.ip}</span>
        <span class="pills"><span class="pill ${cls}">${txt}</span></span></div>
      <div class="lvl"><b>等级 ${n.level} · ${cn(n.level_name)}</b><span class="pill ${n.level===2?'bad':n.level===1?'warn':'ok'}">${n.level===2?'hazard':n.level===1?'caution':'正常'}</span></div>
      <div class="bar">${lvlBars}</div>
      <div class="env">
        <div class="med"><span>温度 ℃</span><b class="${e.t===null?'na':''}">${f(e.t,1)}</b></div>
        <div class="med"><span>湿度 %RH</span><b class="${e.h===null?'na':''}">${f(e.h,1)}</b></div>
        <div class="med"><span>烟雾 0–255</span><b class="${e.smoke===null?'na':''}">${e.smoke===null?'NA':e.smoke}</b></div>
        <div class="med"><span>火焰 0–255</span><b class="${e.flame===null?'na':''}">${e.flame===null?'NA':e.flame}</b></div>
      </div>
      <div class="foot"><span>最后 @E：${ago(n.age)} 前</span><span>门磁：${n.door===null?'NA':(n.door?'开':'关')}</span>
        <span>光电人次：${n.count===null?'NA':n.count}</span><span>rst：${e.rst===null?'NA':e.rst}</span></div>
    </div>`;
  }).join('') || '<div class="empty">等 B 的 /ingest 推送，或先跑 mock_feed.py</div>';

  $('#integrity').innerHTML = s.nodes.map(n=>`<tr><td>${n.id}</td><td class="num">${n.frames}</td>
    <td class="num">${n.expected}</td><td class="num">${n.loss_pct===null?'NA':n.loss_pct.toFixed(2)} %</td>
    <td>${ago(n.age)}</td><td><span class="pill ${(onlineCn[n.online]||['','gray'])[1]}">${(onlineCn[n.online]||['未知'])[0]}</span></td></tr>`).join('');
}
"""

PAGE_CURVES_JS = """
function draw(id, key, unit, th){
  const el = document.getElementById(id);
  const W=620,H=182,L=48,R=14,T=12,B=26;
  const s = window.S;
  const now = s.now, t0 = now - s.window_s;
  let vmin=1e9,vmax=-1e9;
  const lines = [];
  const cols = {'milky-a':'#4ea1ff', 'milky-b':'#37d39a', 'milky-c':'#f5b544', 'milky-d':'#b98bff'};
  Object.keys(s.series).forEach((nid,idx)=>{
    const pts = s.series[nid].map(p=>[p[0],p[key]]).filter(p=>Number.isFinite(p[1]));
    if(!pts.length) return;
    pts.forEach(p=>{vmin=Math.min(vmin,p[1]);vmax=Math.max(vmax,p[1]);});
    lines.push({name:nid, pts, color:cols[nid]||'#8fa2c2'});
  });
  if(!lines.length){ el.innerHTML = `<div class="empty">等待数据…</div>`; return; }
  const rawMin=vmin;
  if(vmax===vmin){ vmax += 1; vmin -= 1; }
  const pad=(vmax-vmin)*0.12; vmin-=pad; vmax+=pad;
  if(rawMin>=0 && vmin<0) vmin=0;   // 0–255 传感器不画负轴
  if(th){ th.forEach(t=>{vmin=Math.min(vmin,t.v); vmax=Math.max(vmax,t.v);}); }
  const X=(ts)=> L + (ts-t0)/s.window_s*(W-L-R);
  const Y=(v)=> T + (vmax-v)/(vmax-vmin)*(H-T-B);
  let g='';
  for(let i=0;i<=3;i++){
    const v=vmin+(vmax-vmin)*i/3, y=Y(v);
    g+=`<line x1="${L}" y1="${y}" x2="${W-R}" y2="${y}" stroke="#22304a" stroke-width="1"/>`;
    g+=`<text x="${L-8}" y="${y+4}" fill="#7e90ad" font-size="10.5" text-anchor="end">${v.toFixed(vmax>=100?0:1)}</text>`;
  }
  for(let m=5;m>=0;m--){
    const ts=now-m*60, x=X(ts);
    if(x<L-2||x>W-R+2) continue;
    g+=`<line x1="${x}" y1="${T}" x2="${x}" y2="${H-B}" stroke="#202c42" stroke-width="1"/>`;
    g+=`<text x="${x}" y="${H-8}" fill="#6d7d99" font-size="10.5" text-anchor="middle">${m===0?'now':'-'+m+'m'}</text>`;
  }
  (th||[]).forEach(t=>{
    const y=Y(t.v);
    g+=`<line x1="${L}" y1="${y}" x2="${W-R}" y2="${y}" stroke="${t.c}" stroke-width="1" stroke-dasharray="5 4" opacity=".7"/>`;
    g+=`<text x="${W-R-2}" y="${y-4}" fill="${t.c}" font-size="10" text-anchor="end" opacity=".9">${t.label}</text>`;
  });
  lines.forEach(l=>{
    const d = l.pts.map((p,i)=>`${i?'L':'M'}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(' ');
    g+=`<path d="${d}" fill="none" stroke="${l.color}" stroke-width="2" stroke-linejoin="round"/>`;
    const last=l.pts[l.pts.length-1];
    g+=`<circle cx="${X(last[0]).toFixed(1)}" cy="${Y(last[1]).toFixed(1)}" r="3" fill="${l.color}"/>`;
  });
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${g}</svg>`;
}
function renderCurves(s){
  window.S = s;
  const th = s.thresholds;
  draw('c-temp',1,'℃',[{v:th.temp_l2,c:'#ff6b6b',label:'hazard 45.0'}]);
  draw('c-hum',2,'%RH',null);
  draw('c-smoke',3,'0–255',[{v:th.smoke_l1,c:'#f5b544',label:'caution 120'},{v:th.smoke_l2,c:'#ff6b6b',label:'hazard 200'}]);
  draw('c-flame',4,'0–255',[{v:th.flame_l1,c:'#f5b544',label:'caution 150'},{v:th.flame_l2,c:'#ff6b6b',label:'hazard 250'}]);
}
"""

PAGE_EVENTS_JS = """
function renderEvents(s){
  $('.chip.h b').textContent = s.counts.hazard||0;
  $('.chip.c b').textContent = s.counts.caution||0;
  $('.chip.d b').textContent = s.counts.deny||0;
  $('.kpi-ev').textContent = s.events.length + '';
  $('#ev-body').innerHTML = s.events.map(e=>{
    const lv = e.buzzer_level||'NA';
    const t = new Date(e.ts*1000).toLocaleTimeString('zh-CN',{hour12:false});
    return `<tr><td class="num">${t}</td><td>${e.node_id}</td><td>${e.src}</td><td>${e.event}</td>
      <td><span class="badge b-${lv.toLowerCase()}">${cn(lv)}</span></td><td class="num">${e.pattern_ms}</td><td style="color:#8fa2c2">${e.note||''}</td></tr>`;
  }).join('') || `<tr><td colspan="7"><div class="empty">还没有报警事件：等 smoke/flame 越界，或 mock_feed 注入一段烟雾</div></td></tr>`;
}
"""


TEMPLATE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%%TITLE%% · 四目边缘看板</title>
<style>%%CSS%%</style></head>
<body><div class="wrap">
<header>
  <div class="brand"><h1>四目边缘 · 实验室数字孪生</h1>
    <span>PC 看板（D 岗）· 契约 3 v1.1c · 监听 0.0.0.0:8000 · 心跳 2 s 常量</span></div>
  <nav>%%NAV%%</nav>
  <div class="live"><span class="dot" id="dot"></span><span id="gen">连接中…</span></div>
</header>
%%BODY%%
<div class="footer"><span>数据根 <b id="data-root">—</b></span><span>@E 2 s/帧 → 6 s 判链路异常、30 s 判离线</span>
  <span>报警只认 buzzer_level + pattern_ms（无 freq_hz）</span><span>mock 版：未接真流</span></div>
</div>
<script>
%%JS%%
async function tick(){
  try{
    const r = await fetch('/api/state',{cache:'no-store'});
    const s = await r.json();
    window.S = s;
    %%RENDER%%
    $('#gen').textContent = '更新 ' + new Date(s.now*1000).toLocaleTimeString('zh-CN',{hour12:false});
    $('#data-root').textContent = s.data_root;
    const bad = s.nodes.some(n=>n.online==='offline'||n.online==='abnormal');
    $('#dot').className = 'dot' + (bad?' warn':'');
  }catch(err){ $('#gen').textContent = '看板断开：' + err; }
}
tick(); setInterval(tick, 2000);
</script></body></html>"""


def page_html(page, title, body, js):
    nav_items = [("/", "节点状态"), ("/curves", "实时曲线"), ("/events", "报警时间线")]
    nav = "".join('<a href="%s" class="%s">%s</a>' % (u, "on" if u == page else "", n)
                  for u, n in nav_items)
    renderer = {"/": "renderNodes(s);", "/curves": "renderCurves(s);",
                "/events": "renderEvents(s);"}[page]
    html = TEMPLATE
    for key, val in (("%%TITLE%%", title), ("%%CSS%%", CSS), ("%%NAV%%", nav),
                     ("%%BODY%%", body), ("%%JS%%", JS_COMMON + "\n" + js),
                     ("%%RENDER%%", renderer)):
        if key not in html:
            raise SystemExit("template placeholder missing: " + key)
        html = html.replace(key, val)
    return html


NODES_BODY = """
<div class="kpis">
  <div class="kpi kpi-online"><b>—</b><span>在线节点</span><br><small>—</small></div>
  <div class="kpi kpi-rx"><b>—</b><span>收到帧数 frames_rx</span><br><small>—</small></div>
  <div class="kpi kpi-exp"><b>—</b><span>期望帧数 frames_expected</span><br><small>—</small></div>
  <div class="kpi kpi-loss"><b>—</b><span>丢包率 loss_pct</span><br><small>—</small></div>
</div>
<div class="grid" id="nodes"></div>
<h2>数据完整性（答辩小表：收到 / 期望 / 丢包）</h2>
<table><thead><tr><th>节点</th><th>frames_rx</th><th>frames_expected</th><th>loss_pct</th><th>最后 @E</th><th>状态</th></tr></thead>
<tbody id="integrity"></tbody></table>
"""

CURVES_BODY = """
<div class="charts">
  <div class="chart"><div class="t"><b>温度</b><span>℃ · 5 min</span></div><div id="c-temp"></div></div>
  <div class="chart"><div class="t"><b>湿度</b><span>%RH · 5 min</span></div><div id="c-hum"></div></div>
  <div class="chart"><div class="t"><b>烟雾 MQ-2</b><span>0–255 · 注意 120 / 危险 200</span></div><div id="c-smoke"></div></div>
  <div class="chart"><div class="t"><b>火焰</b><span>0–255 · 注意 150 / 危险 250</span></div><div id="c-flame"></div></div>
</div>
<div class="note">延迟 / 带宽 / 负载三路曲线在实验一接真流后加（依赖契约 4 的 JSON 与 `report.jsonl`）；本页当前只画 `@E` 的环境四路。</div>
"""

EVENTS_BODY = """
<div class="chips">
  <div class="chip h">hazard（危险）<b>0</b></div>
  <div class="chip c">caution（注意）<b>0</b></div>
  <div class="chip d">deny（拒绝）<b>0</b></div>
  <div class="chip">事件总数<b class="kpi-ev" style="font-size:19px">0</b></div>
</div>
<table><thead><tr><th>时刻 ts</th><th>节点</th><th>触发源 src</th><th>事件</th><th>buzzer_level</th><th>pattern_ms</th><th>备注</th></tr></thead>
<tbody id="ev-body"></tbody></table>
<div class="note">按 `ts` 倒序显示（契约 3 §6：表按 ts 单调递增，补发/重放不按到达顺序）。`deny` 只作事件，不计人次。</div>
"""


class Handler(BaseHTTPRequestHandler):
    store = None
    server_version = "SiMuEdgeDashboard/1.0"

    def log_message(self, fmt, *args):
        return  # 静默，避免每 2 s 刷屏

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, page_html("/", "节点状态", NODES_BODY, PAGE_NODES_JS))
        elif path == "/curves":
            self._send(200, page_html("/curves", "实时曲线", CURVES_BODY, PAGE_CURVES_JS))
        elif path == "/events":
            self._send(200, page_html("/events", "报警时间线", EVENTS_BODY, PAGE_EVENTS_JS))
        elif path == "/api/state":
            self._send(200, json.dumps(self.store.state(), ensure_ascii=False),
                       "application/json; charset=utf-8")
        elif path == "/health":
            self._send(200, json.dumps({"ok": True, "ts": time.time()}), "application/json")
        else:
            self._send(404, json.dumps({"error": "not found", "path": path}), "application/json")

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/ingest":
            self._send(404, json.dumps({"error": "not found"}), "application/json")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            obj = json.loads(raw.decode("utf-8") or "{}")
        except Exception as exc:
            self._send(400, json.dumps({"error": "bad json", "detail": str(exc)}), "application/json")
            return
        try:
            self.store.ingest(obj)
            self._send(200, json.dumps({"ok": True, "ts": time.time()}), "application/json")
        except Exception as exc:
            self._send(500, json.dumps({"error": str(exc)}), "application/json")


def main():
    ap = argparse.ArgumentParser(description="四目边缘 PC 看板（D 岗）")
    ap.add_argument("--data", default=str(Path(__file__).resolve().parent.parent / "data"),
                    help="数据根（默认 D/data；mock 演示用 ../data/mock）")
    ap.add_argument("--host", default="0.0.0.0", help="监听地址，必须是 0.0.0.0（写 127.0.0.1 板子推不上来）")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--default-node", default="milky-a",
                    help="上报里没有 node 字段时落到哪个节点（B 补 node 前先用它）")
    args = ap.parse_args()

    Handler.store = Store(args.data, args.default_node)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[dashboard] data={Handler.store.data}")
    print(f"[dashboard] listening http://{args.host}:{args.port}  (ingest: /ingest)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
