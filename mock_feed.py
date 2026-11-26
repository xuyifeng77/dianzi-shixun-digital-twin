#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""假数据源（D 岗 D3）：模拟 duo_bridge_v1_5.py 往 /ingest POST（节点名用契约 5 的 milky-a / milky-b）。

先回填 5 min 历史（让曲线/时间线一打开就有内容），再每 2 s 一帧实时。
字段值故意用**字符串**，与 duo_bridge.py 现在的实现一致 —— 顺便验证看板的类型强转。

单独跑（A 的复核意见第 5 条，两个窗口）：
    python app.py --data ../data --port 8000
    python mock_feed.py                     # 默认 POST 到 127.0.0.1:8000
随看板跑：python app.py --mock              # 等价，落盘 data/mock/
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def post(port, body, tries=3, host="127.0.0.1"):
    data = json.dumps(body).encode("utf-8")
    url = "http://%s:%d/ingest" % (host, port)
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data, {"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=2).read()
            return True
        except Exception:
            time.sleep(0.3)
    return False


def env(node, ts, t, h, smoke, flame, light, sound, rst=0):
    return {"type": "env", "node": node, "sim": True, "ts_pc": ts,
            "t": "%.1f" % t, "h": "%.1f" % h,
            "smoke": str(int(smoke)), "flame": str(int(flame)),
            "light": str(int(light)), "sound": str(int(sound)), "rst": str(rst)}


def alarm(node, ts, lv, src):
    return {"type": "alarm", "node": node, "sim": True, "ts_pc": ts,
            "args": [str(lv), src]}


def door(node, ts, v):
    return {"type": "door", "node": node, "sim": True, "ts_pc": ts, "args": [str(v)]}


def count(node, ts, n):
    return {"type": "count", "node": node, "sim": True, "ts_pc": ts, "args": [str(n)]}


def card(node, ts, uid, ok):
    return {"type": "card", "node": node, "sim": True, "ts_pc": ts, "uid": uid, "ok": ok}


def link(node, ts, lat, bw, cpu):
    return {"type": "link", "node": node, "sim": True, "ts_pc": ts,
            "lat_ms": lat, "bw_Bps": bw, "cpu_pct": cpu}


def history(now, span=300, step=2):
    """5 min 回填：环境帧 + 一条完整的“危险→解除→注意→解除→拒绝→门磁→人次→重启”剧本。"""
    items = []
    start = now - span
    # 剧本时间点（相对 start）
    smoke_on, smoke_off = span - 250, span - 228      # milky-a 烟雾越 L2
    flame_on, flame_off = span - 200, span - 184      # milky-b 火焰越 L1
    deny_at = span - 160
    door_open, door_close = span - 150, span - 136
    reboot_at = span - 42

    t = start
    i = 0
    while t <= now:
        for node in ("milky-a", "milky-b"):
            nb = (node == "milky-b")
            base_t = 24.2 + 0.6 * math.sin((t - start) / 90.0) + (2.6 if nb else 0)
            base_h = 45.0 + 1.5 * math.sin((t - start) / 70.0)
            smoke = 12 + 4 * math.sin((t - start) / 25.0) + (16 if nb else 0)
            flame = 4 + 2 * math.sin((t - start) / 17.0) + (9 if nb else 0)
            if node == "milky-a" and smoke_on <= t <= smoke_off:
                smoke = 180 + 40 * math.sin((t - start) / 3.0)
            if node == "milky-b" and flame_on <= t <= flame_off:
                flame = 145 + 30 * math.sin((t - start) / 3.0)
            light = 78 + 8 * math.sin((t - start) / 30.0)
            sound = 6 + 3 * abs(math.sin((t - start) / 11.0))
            rst = 1 if (node == "milky-a" and reboot_at <= t < reboot_at + 2) else 0
            items.append((t, env(node, t, base_t, base_h, smoke, flame, light, sound, rst)))
            # 链路三路（mock 合成：β 口径 —— 只传结论，带宽低、延迟稳）
            # 用绝对时间做相位，回填段和实时段才能接上，不出现“接缝跳变”
            lat = 32 + 6 * math.sin(t / 13.0) + (2.5 if node == "milky-b" else 0)
            bw = 190 + 25 * math.sin(t / 21.0) + (28 if node == "milky-b" else 0)
            cpu = 22 + 5 * math.sin(t / 19.0) + (5 if node == "milky-b" else 0)
            items.append((t, link(node, t, round(lat, 1), round(bw, 1), round(cpu, 1))))
        t += step
        i += 1

    items += [
        (start + smoke_on, alarm("milky-a", start + smoke_on, 2, "SMOKE")),
        (start + smoke_off, alarm("milky-a", start + smoke_off, 0, "NONE")),
        (start + flame_on, alarm("milky-b", start + flame_on, 1, "FLAME")),
        (start + flame_off, alarm("milky-b", start + flame_off, 0, "NONE")),
        (start + deny_at, card("milky-a", start + deny_at, "DEADBEEF", False)),
        (start + deny_at + 8, card("milky-a", start + deny_at + 8, "A1B2C3D4", True)),
        (start + door_open, door("milky-a", start + door_open, 1)),
        (start + door_close, door("milky-a", start + door_close, 0)),
    ]
    for k, off in enumerate((110, 95, 80, 65, 50, 35)):
        items.append((start + (span - off), count("milky-b", start + (span - off), k + 1)))
    items.append((start + reboot_at, count("milky-a", start + reboot_at, 0)))
    items.sort(key=lambda x: x[0])
    return items


def run(port=8000, span=300, host="127.0.0.1"):
    P = lambda b: post(port, b, host=host)
    now = time.time()
    print("[mock] 回填 %d s 历史 ..." % span)
    ok = 0
    for ts, body in history(now, span):
        if P(body):
            ok += 1
    print("[mock] 回填完成 %d 条；转入实时，每 2 s 一帧" % ok)

    t0 = time.time()
    n = 0
    cnt_b = 6
    door_a = 0
    while True:
        now = time.time()
        el = now - t0
        for node in ("milky-a", "milky-b"):
            nb = (node == "milky-b")
            smoke = 12 + 5 * math.sin(el / 9.0) + (16 if nb else 0) \
                + (60 if (node == "milky-a" and 40 < el % 120 < 48) else 0)
            flame = 4 + 2 * math.sin(el / 7.0) + (9 if nb else 0)
            t = 24.4 + 0.5 * math.sin(el / 40.0) + (2.6 if nb else 0)
            h = 45.2 + 1.2 * math.sin(el / 33.0)
            P(env(node, now, t, h, smoke, flame, 80 - (12 if nb else 0),
                           6 + 3 * abs(math.sin(el / 5.0))))
            P(link(node, now,
                            round(32 + 6 * math.sin(now / 13.0) + (2.5 if nb else 0), 1),
                            round(190 + 25 * math.sin(now / 21.0) + (28 if nb else 0), 1),
                            round(22 + 5 * math.sin(now / 19.0) + (5 if nb else 0), 1)))
        # 每 48 s 一次报警 -> 16 s 后解除（演示时间线持续有内容）
        if 40 < el % 120 < 46:
            P(alarm("milky-a", now, 2, "SMOKE"))
        elif 60 < el % 120 < 62:
            P(alarm("milky-a", now, 0, "NONE"))
        # 人次每 20 s +1（milky-b），门磁每 45 s 翻一次（milky-a）
        n += 1
        if n % 10 == 0:
            cnt_b += 1
            P(count("milky-b", now, cnt_b))
        if n % 23 == 0:
            door_a = 1 - door_a
            P(door("milky-a", now, door_a))
        time.sleep(2)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="假数据源：模拟 duo_bridge_v1_5.py 往看板 /ingest 推帧")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--span", type=int, default=300, help="回填多少秒历史")
    ap.add_argument("--no-backfill", action="store_true", help="只发实时帧，不回填")
    a = ap.parse_args()
    print("[mock] -> http://%s:%d/ingest  回填 %d s，然后每 2 s 一帧（Ctrl-C 停）"
          % (a.host, a.port, 0 if a.no_backfill else a.span))
    run(a.port, 0 if a.no_backfill else a.span, host=a.host)


