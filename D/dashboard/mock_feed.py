#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mock_feed：模拟 duo_bridge.py 的 POST，每 2 s 一条 @E（契约 1 字段序）

用途：看板 D3 联调，不依赖 B 的板子、不依赖 UNO。
行为：按固件 `judge()` 的实值判级（smoke≥120/200、flame≥150/250、temp≥45.0），
      等级变化时才发 @A（与固件一致，不重复发）；注入一次刷卡拒绝（deny）。

运行：
  python mock_feed.py --url http://127.0.0.1:8000/ingest --nodes milky-a,milky-b \
      --duration 200 --drop-b-after 50
"""
import argparse
import json
import math
import time
import urllib.request


def post(url, obj, timeout=2):
    try:
        req = urllib.request.Request(url, json.dumps(obj).encode(),
                                     {"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=timeout).read()
        return True
    except Exception as exc:
        print("[net]", exc)
        return False


def level_of(smoke, flame, temp):
    if smoke >= 200 or flame >= 250 or temp >= 45.0:
        return 2
    if smoke >= 120 or flame >= 150:
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000/ingest")
    ap.add_argument("--nodes", default="milky-a,milky-b")
    ap.add_argument("--duration", type=float, default=200, help="0 = 一直跑")
    ap.add_argument("--tick", type=float, default=2.0, help="@E 周期，固件=2 s")
    ap.add_argument("--drop-b-after", type=float, default=0, help="第 N 秒起停发 milky-b（模拟离线）")
    args = ap.parse_args()

    nodes = [n.strip() for n in args.nodes.split(",") if n.strip()]
    t0 = time.time()
    st = {n: {"level": 0, "door": 0, "count": -1, "deny": False,
              "door_open": False, "door_close": False} for n in nodes}
    print(f"[mock] -> {args.url}  nodes={nodes}  tick={args.tick}s")

    next_t = t0
    while True:
        el = time.time() - t0
        if args.duration and el >= args.duration:
            break
        for idx, nid in enumerate(nodes):
            if args.drop_b_after and nid == "milky-b" and el >= args.drop_b_after:
                continue

            temp = 24.2 + 1.6 * math.sin(el / 41 + idx * 1.3)
            hum = 46.0 + 5.0 * math.sin(el / 67 + idx)
            smoke = 16 + 6 * math.sin(el / 29 + idx)
            flame = 4 + 2 * math.sin(el / 17 + idx)

            # milky-a：18–24 s 注意级（烟雾 130），26–36 s 危险级（烟雾 215）
            if nid == "milky-a":
                if 18 <= el < 24:
                    smoke = 132
                elif 26 <= el < 36:
                    smoke = 216
            # milky-b：30–38 s 温度 46.2 ℃ → 危险级（温度没有注意级）
            if nid == "milky-b" and 30 <= el < 70:
                temp = 46.2

            post(args.url, {"type": "env", "node": nid, "t": round(temp, 1),
                            "h": round(hum, 1), "smoke": int(smoke), "flame": int(flame),
                            "light": 88, "sound": 7, "rst": 0, "ts": round(time.time(), 3)})

            lv = level_of(int(smoke), int(flame), temp)
            if lv != st[nid]["level"]:
                # 与固件 judgeAndAct() 一致：默认 NONE，按“当前等级的阈值”判 src
                if smoke >= (200 if lv >= 2 else 120):
                    src = "SMOKE"
                elif flame >= (250 if lv >= 2 else 150):
                    src = "FLAME"
                elif temp >= 45.0:
                    src = "TEMP"
                else:
                    src = "NONE"
                st[nid]["level"] = lv
                post(args.url, {"type": "A", "node": nid, "args": [lv, src],
                                "ts": round(time.time(), 3)})

            if nid == "milky-a" and el >= 14 and not st[nid]["door_open"]:
                st[nid]["door_open"] = True
                st[nid]["door"] = 1
                post(args.url, {"type": "D", "node": nid, "args": [1]})
            if nid == "milky-a" and el >= 34 and not st[nid]["door_close"]:
                st[nid]["door_close"] = True
                st[nid]["door"] = 0
                post(args.url, {"type": "D", "node": nid, "args": [0]})
            if nid == "milky-a" and el >= 21 and not st[nid]["deny"]:
                st[nid]["deny"] = True
                post(args.url, {"type": "card", "node": nid, "uid": "DEADBEEF", "ok": False})
            if nid == "milky-b":
                c = int(el // 10)
                if c != st[nid]["count"]:
                    st[nid]["count"] = c
                    if c > 0:
                        post(args.url, {"type": "C", "node": nid, "args": [c]})

        next_t += args.tick
        time.sleep(max(0, next_t - time.time()))

    print("[mock] done")


if __name__ == "__main__":
    main()
