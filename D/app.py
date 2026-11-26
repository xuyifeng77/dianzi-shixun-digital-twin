#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PC 看板服务（D 岗 · D3 验收物）

收 Duo 桥接的 POST /ingest，提供三个页面：节点状态 / 实时曲线 / 报警时间线。

零依赖：只用 Python 标准库（3.8+），不需要 pip install，也不连 CDN。
监听必须 0.0.0.0:8000 —— 板子从网段推过来，写 127.0.0.1 本地 curl 通、板子收不到。

用法（两个窗口，A 的复核意见第 5 条）：
    窗口1  python app.py --data ../data --port 8000
    窗口2  python mock_feed.py              # 独立造数，POST 到 127.0.0.1:8000
    或一步  python app.py --mock            # 内置假数据，落盘到 data/mock/（不污染 raw/）

落盘：
    data/raw/events/<YYYYMMDD>.csv          事件表（7 列，按 ts 升序）
    data/raw/env/<node>_<YYYYMMDD>.jsonl    环境帧原始 JSON，一行一帧，只增不改
    data/mock/...                           假数据（--mock 或 mock_feed.py 默认都写这里）

接口：
    GET  /                  三页面（?tab=nodes|curves|events）
    GET  /api/state         当前快照 JSON（页面每 1 s 拉一次）
    GET  /api/health        {"ok": true}
    POST /ingest            收帧：JSON（bridge 格式）或裸 ASCII 帧（@E,...）
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import threading
import time
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

try:  # Windows 控制台默认 cp936，避免中文/符号打印时崩
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                     # D/
DEFAULT_DATA = os.path.join(ROOT, "data")

# ---- 契约 3 v1.1c §1.1：节奏与超时（唯一权威，别改成分数）----
HB_INTERVAL = 2.0        # @E 2 s / 帧
WARN_S = 6.0             # 6 s 无新 @E = 链路异常（3 帧）
OFFLINE_S = 30.0         # 30 s = 离线
WINDOW_S = 300.0         # 曲线保留 5 min
MOCK_MODE = False        # --mock 时置 True，仅用于页面标注“假数据”

# ---- 契约 3 §6.1 三级语义（D3 默认口径，见契约 3 §6.2 注）----
LEVELS = {
    2: ("hazard", "危险", "1000/500"),
    1: ("caution", "注意", "150/2850"),
    0: ("", "正常", ""),
}
DENY_LEVEL = ("deny", "拒绝", "80x2/400")

NODE_IPS = {
    "nodeA": "192.168.5.7",
    "nodeB": "192.168.5.8",
    "nodeC": "192.168.5.9",
    "nodeD": "192.168.5.10",
}
IP_NODES = {v: k for k, v in NODE_IPS.items()}

SRC_TEXT = {
    "SMOKE": "烟雾", "FLAME": "火焰", "TEMP": "温度",
    "HUM": "湿度", "DOOR": "门磁", "CARD": "刷卡", "HEARTBEAT": "心跳",
}
EVENT_TEXT = {"alarm": "报警", "clear": "解除", "deny": "拒绝", "heartbeat": "心跳"}

EVENT_COLS = ["ts", "node_id", "src", "event", "buzzer_level", "pattern_ms", "note"]


def num(v):
    """契约 3 §0：缺失只允许 NA。

    除空串 / None / NA / - 之外，**"nan" / "inf" 也必须当缺失**：
    固件 DHT11/DS18B20 读失败时 Arduino 打印的是字符串 "nan"，float("nan") 是合法浮点，
    会污染整列均值，且 JSON 里 NaN 是非法字面量。bridge v1.5 已转 null，这里再兜一层。
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        if v != v or v in (float("inf"), float("-inf")):
            return None
        return float(v)
    s = str(v).strip()
    if s == "" or s.upper() in ("NA", "NULL", "NAN", "NONE", "-", "INF", "-INF"):
        return None
    try:
        x = float(s)
    except ValueError:
        return None
    if x != x or x in (float("inf"), float("-inf")):
        return None
    return x


def fmt_ts(ts):
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


class Node:
    def __init__(self, name):
        self.name = name
        self.ip = NODE_IPS.get(name, "")
        self.last_seen = 0.0
        self.first_seen = None
        self.lv = 0
        self.src = "NONE"
        self.last_alarm_src = "NONE"
        self.door = None
        self.door_ts = 0.0
        self.count_prev = 0
        self.count = 0
        self.count_seen = False              # 从未收到 @C 时，页面显示 "—"，不是 0
        self.reboots = 0
        self.rst = 0
        self.frames_rx = 0
        self.series = deque(maxlen=400)      # (ts, t, h, smoke, flame, light, sound)
        self.link = deque(maxlen=400)        # (ts, lat_ms, bw_Bps, cpu_pct)
        # bridge v1.5 新字段：节点时间、自报链路状态、队列丢弃/失败计数
        self.ts_node = None                  # bridge 的 ts（节点 ntpd UTC epoch），仅诊断
        self.skew = None                     # ts（PC 收到）− ts_node，秒
        self.link_state = None               # boot / ok / dead（bridge 自报）
        self.hb_dropped = 0                  # bridge 上报队列丢弃帧数
        self.hb_failed = 0                   # bridge POST 失败次数
        self.pattern_warn = 0                # 上报 pattern_ms 与契约不一致的次数

    def seen(self, ts):
        if self.first_seen is None:
            self.first_seen = ts
        self.last_seen = max(self.last_seen, ts)

    def status(self, now):
        if not self.last_seen:
            return "off", None
        age = max(0.0, now - self.last_seen)
        # bridge 自报链路死（串口断）时，即使心跳还在也标"异常"，别让页面显示绿的
        if self.link_state == "dead" and age <= OFFLINE_S:
            return "warn", age
        if age <= WARN_S:
            return "ok", age
        if age <= OFFLINE_S:
            return "warn", age
        return "off", age

    def integrity(self, now):
        """数据完整性 = 收到帧数 / 期望帧数（expected 按 2 s 一帧推算）。"""
        if not self.first_seen:
            return None
        span = max(0.0, min(now, self.last_seen) - self.first_seen)
        expected = span / HB_INTERVAL + 1
        if expected <= 0:
            return None
        return max(0.0, min(1.0, self.frames_rx / expected))


class Store:
    def __init__(self, data_dir):
        self.lock = threading.Lock()
        self.nodes = {}
        self.events = []          # dict，按 ts 升序落盘
        self.data_dir = data_dir
        self.raw_dir = os.path.join(data_dir, "raw")
        for sub in ("raw", "raw/events", "raw/env", "clean", "exp1", "exp2"):
            os.makedirs(os.path.join(data_dir, sub), exist_ok=True)
        self.csv_path = None
        self._csv_day = None
        self.env_files = {}

    # ---------- 节点 ----------
    def node(self, name, ip=""):
        n = self.nodes.get(name)
        if n is None:
            n = Node(name)
            if ip and not n.ip:
                n.ip = ip
            self.nodes[name] = n
        return n

    def node_from(self, body, remote_ip):
        name = str(body.get("node") or "").strip()
        if name in NODE_IPS or (name and name.startswith("node")):
            return self.node(name, remote_ip)
        if remote_ip in IP_NODES:
            return self.node(IP_NODES[remote_ip], remote_ip)
        return self.node("nodeX", remote_ip)

    # ---------- 落盘 ----------
    # 目录口径（A 11-26 复核第 5、7 条）：
    #   事件  data/raw/events/<YYYYMMDD>.csv
    #   环境  data/raw/env/<node>_<YYYYMMDD>.jsonl（一行一帧原始 JSON，只增不改）
    #   mock  data/mock/...（不污染 raw/）
    def _events_dir(self):
        d = os.path.join(self.raw_dir, "events")
        os.makedirs(d, exist_ok=True)
        return d

    def _env_dir(self):
        d = os.path.join(self.raw_dir, "env")
        os.makedirs(d, exist_ok=True)
        return d

    def _csv_file(self, day):
        return os.path.join(self._events_dir(), "%s.csv" % day)

    def append_env(self, ts, node, body):
        """环境帧原样追加一行 JSONL：原始证据，只增不改（契约 3 §1）。"""
        day = datetime.fromtimestamp(ts).strftime("%Y%m%d")
        path = os.path.join(self._env_dir(), "%s_%s.jsonl" % (node, day))
        try:
            with open(path, "a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps({"ts_rx": round(ts, 3), "node": node,
                                    "raw": {k: v for k, v in body.items()
                                            if k not in ("sim", "ts_pc")}},
                                   ensure_ascii=False, separators=(",", ":")) + "\n")
        except OSError as e:
            print("[warn] env 落盘失败：%s" % e)

    def write_events(self):
        """每次改动整表按 ts 升序重写：契约 3 §8 第 14 条，事件表必须按 ts 单调递增。"""
        if not self.events:
            return
        day = datetime.fromtimestamp(self.events[-1]["ts"]).strftime("%Y%m%d")
        path = self._csv_file(day)
        rows = sorted(self.events, key=lambda e: (e["ts"], e["node_id"]))
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=EVENT_COLS, extrasaction="ignore")
            w.writeheader()
            for e in rows:
                w.writerow({k: e[k] for k in EVENT_COLS})
        os.replace(tmp, path)
        self.csv_path = path

    def emit(self, ts, node, src, event, level, pattern, note=""):
        self.events.append({
            "ts": round(float(ts), 3),
            "node_id": node.name,
            "src": src,
            "event": event,
            "buzzer_level": level,
            "pattern_ms": pattern,
            "note": note,
        })
        if len(self.events) > 5000:
            self.events = self.events[-5000:]
        self.write_events()

    # ---------- 收帧 ----------
    def ingest(self, body, remote_ip="127.0.0.1"):
        typ = str(body.get("type", "")).strip().lower()
        with self.lock:
            now = time.time()
            # mock 回填历史时才认 ts_pc；真流一律用 PC 当前时钟（契约 3 §0）
            ts = now
            if body.get("sim") and body.get("ts_pc") is not None:
                ts = float(body["ts_pc"])
            n = self.node_from(body, remote_ip)

            # bridge v1.5 的 ts 是节点时间（ntpd UTC epoch）：只存作诊断，不参与 CSV 时间
            # （契约 3 §0 要求 ts 用 PC 侧 time.time()，这里 ts 就是看板收到帧的时刻）
            ts_node = num(body.get("ts"))
            if ts_node is not None and ts_node > 1e9:
                n.ts_node = round(ts_node, 3)
                n.skew = round(ts - ts_node, 3)

            if typ in ("heartbeat", "hb"):
                n.seen(ts)
                ls = str(body.get("link") or "").strip().lower()
                if ls in ("boot", "ok", "dead"):
                    n.link_state = ls
                d = num(body.get("dropped"))
                f2 = num(body.get("failed"))
                if d is not None:
                    n.hb_dropped = int(d)
                if f2 is not None:
                    n.hb_failed = int(f2)
                return {"ok": True, "type": "heartbeat", "node": n.name}

            if typ in ("env", "e"):
                n.seen(ts)
                n.frames_rx += 1
                rst = num(body.get("rst"))
                if rst is not None:
                    rst = int(rst)
                    if rst != n.rst:
                        n.rst = rst
                        if rst != 0:
                            n.reboots += 1
                            n.note_reboot = True
                n.series.append((ts, num(body.get("t")), num(body.get("h")),
                                 num(body.get("smoke")), num(body.get("flame")),
                                 num(body.get("light")), num(body.get("sound"))))
                self.append_env(ts, n.name, body)
                return {"ok": True, "type": "env", "node": n.name}

            if typ in ("alarm", "a"):
                args = body.get("args") or []
                lv = int(num(args[0]) or 0) if args else 0
                src = str(args[1]).strip().upper() if len(args) > 1 else "NONE"
                n.seen(ts)
                if lv != n.lv:
                    old = n.lv
                    n.lv = lv
                    n.src = src
                    if lv == 0:
                        # 契约 3 §6 的 src 枚举没有 NONE：clear 继承上一状态来源
                        prev = n.last_alarm_src
                        self.emit(ts, n, prev, "clear", "NA", "NA", "#clear")
                    else:
                        level, _zh, pattern = LEVELS[lv]
                        n.last_alarm_src = src
                        self.emit(ts, n, src, "alarm", level, pattern)
                return {"ok": True, "type": "alarm", "node": n.name, "lv": lv}

            if typ in ("count", "c"):
                args = body.get("args") or []
                # v1.5 用 passes，早期 mock/bridge 用 args[0]，两种都认
                v = num(args[0]) if args else num(body.get("passes"))
                n.seen(ts)
                if v is not None:
                    v = int(v)
                    n.count_seen = True
                    if v < n.count_prev:            # 累计人次回退 = 节点重启，本组重开
                        n.count = v
                        self.emit(ts, n, "CARD", "heartbeat", "NA", "NA", "#count_reset")
                    else:
                        n.count += v - n.count_prev
                    n.count_prev = v
                return {"ok": True, "type": "count", "node": n.name, "count": n.count}

            if typ in ("door", "d"):
                args = body.get("args") or []
                # v1.5 用 open，早期用 args[0]
                v = num(args[0]) if args else num(body.get("open"))
                n.seen(ts)
                if v is not None:
                    n.door = 1 if int(v) else 0
                    n.door_ts = ts
                return {"ok": True, "type": "door", "node": n.name, "door": n.door}

            if typ in ("card", "rfid", "r"):
                n.seen(ts)
                ok = body.get("ok")
                if ok is None and body.get("args"):
                    ok = str(body["args"][0]).strip().lower() in ("1", "true")
                uid = str(body.get("uid") or "")
                # 契约 3 §6.1 的 deny 节奏是 80x2/400（A 的 D-01 决定）。
                # bridge v1.5 发的是 80/120，与契约不符：以契约为准，记一次告警。
                given = str(body.get("pattern_ms") or "").strip()
                if given and given != DENY_LEVEL[2]:
                    n.pattern_warn += 1
                if not ok:
                    self.emit(ts, n, "CARD", "deny", DENY_LEVEL[0], DENY_LEVEL[2],
                              "uid=%s" % uid)
                return {"ok": True, "type": "rfid", "node": n.name, "ok": bool(ok)}

            if typ in ("link", "metric"):
                n.seen(ts)
                n.link.append((ts, num(body.get("lat_ms")), num(body.get("bw_Bps")),
                               num(body.get("cpu_pct"))))
                return {"ok": True, "type": "link", "node": n.name}

            return {"ok": False, "error": "unknown type", "type": typ}

    # ---------- 快照 ----------
    def snapshot(self):
        with self.lock:
            now = time.time()
            nodes = []
            for name in sorted(self.nodes):
                n = self.nodes[name]
                st, age = n.status(now)
                level, level_zh, pattern = LEVELS.get(n.lv, ("", "正常", ""))
                integ = n.integrity(now)
                nodes.append({
                    "name": n.name,
                    "ip": n.ip or "—",
                    "status": st,
                    "age_s": None if age is None else round(age, 1),
                    "lv": n.lv,
                    "level": level,
                    "level_zh": level_zh,
                    "pattern": pattern,
                    "src": n.src,
                    "src_zh": "—" if (n.lv == 0 or n.src in ("", "NONE")) else SRC_TEXT.get(n.src, n.src),
                    "door": n.door,
                    "door_zh": "—" if n.door is None else ("开" if n.door else "关"),
                    "door_ago": None if not n.door_ts else round(max(0.0, now - n.door_ts), 1),
                    "count": n.count if n.count_seen else None,
                    "reboots": n.reboots,
                    "rst": n.rst,
                    "frames_rx": n.frames_rx,
                    "integrity": None if integ is None else round(integ * 100, 1),
                    "uptime_s": 0 if n.first_seen is None else round(n.last_seen - n.first_seen, 1),
                    "link_state": n.link_state,
                    "ts_node": n.ts_node,
                    "skew_s": n.skew,
                    "dropped": n.hb_dropped,
                    "post_failed": n.hb_failed,
                    "pattern_warn": n.pattern_warn,
                })
            evs = sorted(self.events, key=lambda e: e["ts"], reverse=True)[:200]
            events = [{
                "ts": e["ts"],
                "t": fmt_ts(e["ts"]),
                "node": e["node_id"],
                "src": e["src"],
                "src_zh": SRC_TEXT.get(e["src"], e["src"]),
                "event": e["event"],
                "event_zh": EVENT_TEXT.get(e["event"], e["event"]),
                "level": e["buzzer_level"],
                "level_zh": {"hazard": "危险", "caution": "注意", "deny": "拒绝"}.get(e["buzzer_level"], "—"),
                "pattern": e["pattern_ms"],
                "note": e["note"],
            } for e in evs]
            curves, links = {}, {}
            lo = now - WINDOW_S
            for name, n in self.nodes.items():
                pts = [p for p in n.series if p[0] >= lo]
                curves[name] = {
                    "ts": [round(p[0], 3) for p in pts],
                    "t": [p[1] for p in pts],
                    "smoke": [p[3] for p in pts],
                    "flame": [p[4] for p in pts],
                    "light": [p[5] for p in pts],
                }
                lp = [p for p in n.link if p[0] >= lo]
                links[name] = {
                    "ts": [round(p[0], 3) for p in lp],
                    "lat": [p[1] for p in lp],
                    "bw": [p[2] for p in lp],
                    "cpu": [p[3] for p in lp],
                }
            online = sum(1 for x in nodes if x["status"] == "ok")
            alarm = sum(1 for x in nodes if x["lv"] >= 1)
            return {
                "server_ts": round(now, 3),
                "now_text": fmt_ts(now),
                "online": online,
                "total": len(nodes),
                "alarms": alarm,
                "events_today": len(self.events),
                "warn_s": WARN_S,
                "offline_s": OFFLINE_S,
                "hb_interval": HB_INTERVAL,
                "mock": MOCK_MODE,
                "nodes": nodes,
                "events": events,
                "curves": curves,
                "links": links,
            }


STORE = Store(DEFAULT_DATA)


def frame_to_body(line, node=None):
    """裸 ASCII 帧 -> bridge 同形 body（便于 curl 自测，不经过 Duo）。"""
    line = line.strip()
    if not line.startswith("@"):
        return None
    f = line[1:].split(",")
    tag = f[0].strip().upper()
    body = {"type": tag.lower(), "node": node}
    if tag == "E":
        keys = ["t", "h", "smoke", "flame", "light", "sound", "rst"]
        for i, k in enumerate(keys):
            body[k] = f[i + 1] if len(f) > i + 1 else None
        body["type"] = "env"
    elif tag == "A":
        body["type"] = "alarm"
        body["args"] = f[1:]
    elif tag in ("C", "D"):
        body["type"] = "count" if tag == "C" else "door"
        body["args"] = f[1:]
    elif tag == "R":
        body["type"] = "card"
        body["uid"] = f[1] if len(f) > 1 else ""
        body["ok"] = False          # 裸 @R 只代表读到卡，鉴权在 bridge 侧
    else:
        return None
    return body


class Handler(BaseHTTPRequestHandler):
    server_version = "dsh-dashboard/0.3"

    def log_message(self, fmt, *args):   # 静音：每帧一条日志会淹掉控制台
        pass

    def _send(self, code, payload, ctype="application/json; charset=utf-8"):
        raw = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            self.wfile.write(raw)
        except Exception:
            pass

    def _file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                self._send(200, f.read(), ctype)
        except FileNotFoundError:
            self._send(404, {"ok": False, "error": "not found"})

    def do_GET(self):
        u = urlparse(self.path)
        p = u.path
        if p in ("/", "/index.html"):
            return self._file(os.path.join(HERE, "templates", "index.html"), "text/html; charset=utf-8")
        if p == "/api/state":
            return self._send(200, STORE.snapshot())
        if p == "/api/health":
            return self._send(200, {"ok": True, "ts": round(time.time(), 3)})
        if p.startswith("/static/"):
            name = os.path.basename(p)
            ext = os.path.splitext(name)[1].lower()
            ctype = {".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8"}.get(
                ext, "application/octet-stream")
            return self._file(os.path.join(HERE, "static", name), ctype)
        return self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/ingest":
            return self._send(404, {"ok": False, "error": "not found"})
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        text = raw.decode("utf-8", "replace").strip()
        ip = self.client_address[0]
        body = None
        if text.startswith("{"):
            try:
                body = json.loads(text)
            except Exception as e:
                return self._send(400, {"ok": False, "error": "bad json: %s" % e})
        elif text.startswith("@"):
            body = frame_to_body(text, parse_qs(urlparse(self.path).query).get("node", [None])[0])
            if body is None:
                return self._send(400, {"ok": False, "error": "bad frame"})
        else:
            return self._send(400, {"ok": False, "error": "expect json or @frame"})
        try:
            res = STORE.ingest(body, ip)
        except Exception as e:
            return self._send(500, {"ok": False, "error": "%s: %s" % (type(e).__name__, e)})
        return self._send(200, res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--data", default=DEFAULT_DATA,
                    help="数据根，默认 D/data；--mock 时自动改到 <data>/mock，不污染 raw/")
    ap.add_argument("--mock", action="store_true", help="同时启动内置假数据（写 data/mock/）")
    args = ap.parse_args()

    global STORE
    if args.mock:
        # A 的复核意见第 5 条：mock 不能污染 raw/
        args.data = os.path.join(args.data, "mock")
    STORE = Store(args.data)

    if args.mock:
        import mock_feed
        global MOCK_MODE
        MOCK_MODE = True
        threading.Thread(target=mock_feed.run, kwargs={"port": args.port}, daemon=True).start()
        print("[mock] 内置假数据已启动（5 min 回填 + 每 2 s 一帧）")

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    srv.daemon_threads = True
    print("[dash] listening http://%s:%d  (0.0.0.0 = 板子可推)" % (args.host, args.port))
    print("[dash] 页面 http://127.0.0.1:%d/?tab=nodes" % args.port)
    print("[dash] 自检 curl -X POST http://127.0.0.1:%d/ingest -d \"{\\\"type\\\":\\\"heartbeat\\\"}\"" % args.port)
    print("[dash] 数据根 %s" % args.data)
    print("[dash] 事件表 %s" % os.path.join(args.data, "raw", "events"))
    print("[dash] 环境原始 %s" % os.path.join(args.data, "raw", "env"))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[dash] bye")


if __name__ == "__main__":
    main()


