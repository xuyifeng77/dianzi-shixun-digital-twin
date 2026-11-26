#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
duo_bridge v1.5 —— 按 D 的《契约 4 三问答复 + 6 条》实现

=====================================================================
版本谱系（务必保留，交付/答辩要引用）
---------------------------------------------------------------------
  v1.1  项目早期原型（04-物联网项目/duo_bridge.py，69 行）
        有 06 报告的 P0-5 / P1-1 / P1-2 三个缺陷
  v1.2  只存在于 09-B岗-视觉节点.md §五 的代码片段，未落成文件
        修了上面三个缺陷
  v1.4  本次实现：v1.2 的三处修复 + B-通知 的四条要求
  v1.5  本文件：在 v1.4 基础上按 D 的契约 4 答复改 5 处（见下）
        ⚠️ v1.5 与 v1.4 行为不同（env 变成数字、heartbeat 10 s、alarm 用 args），
           **β 带宽必须重测**，旧数据不能与新代码混用。

=====================================================================
v1.5 相对 v1.4 改了 5 处（依据 D 2026-11-26 的答复）
---------------------------------------------------------------------
  ① env 数值由 bridge 转数字：t/h→float(1 位小数)，smoke/flame/light/sound→int
     缺测一律 null（**含固件打印的字符串 "nan"**，这是 D 没提但必须处理的坑）
  ② heartbeat 周期 5 s → 10 s
  ③ alarm 改为 args:[lv, src]，lv∈{0,1,2}，src∈{NONE,SMOKE,FLAME,TEMP}
  ④ @E 兼容 8 字段（C 的契约 1 v1.1 在末尾新增 rst = 复位原因），rst 可选上报
  ⑤ NODE 白名单校验：只允许 nodeA/nodeB/nodeC/nodeD，写错立即报错退出
     （D 说未知 node 的帧会被看板丢弃，静默丢数据比报错更糟）

=====================================================================
未采纳 / 需要向 D 反馈的两点（代码里已按最保守方式处理）
---------------------------------------------------------------------
  · ts 保持**节点时间**（两板均有 ntpd，UTC epoch）。D 建议"ts = bridge 发送时
    的 PC 时间"不成立——bridge 跑在 Duo 上，拿不到 PC 时钟。
    建议 PC 看板自行记录到达时间 ts_rx，CSV 写 ts_rx，两者不冲突。
  · alarm 的 args:[lv,src] 枚举里**没有"刷卡拒绝"这一种**（B-通知 §五 要求有 deny）。
    本文件不改枚举，拒绝事件仍走 type="rfid" + ok=false + buzzer_level="deny"。
    若要并入 alarm，请 D 在 src 枚举里加 RFID。

=====================================================================
用法
---------------------------------------------------------------------
  python3 duo_bridge_v1_5.py                       # 默认 nodeA
  NODE=nodeB python3 duo_bridge_v1_5.py            # B 板
  DASH_URL=http://192.168.5.5:8000/ingest ...      # 覆盖接收端

三项上机自测（需真 UNO）
  1) 拔 UNO → 35 s 内打印 [LINK] DEAD，脚本不退出
  2) DASH_URL 指向坏地址 → 串口照读，只有 [post] 报错
  3) 插回 → 自动恢复，[LINK] DEAD 不重复打印
"""
import glob
import json
import math
import os
import queue
import threading
import time
import urllib.request

# ---------------------------------------------------------------- 配置

NODE = os.environ.get("NODE", "nodeA")
ALLOWED_NODES = {"nodeA", "nodeB", "nodeC", "nodeD"}   # ④ 白名单，写错直接退出

DASH_URL = os.environ.get(
    "DASH_URL",
    os.environ.get("SERVER", "http://192.168.5.20:8000/ingest"))

CARDS = set(x.strip().upper() for x in
            os.environ.get("CARDS", "A1B2C3D4").split(",") if x.strip())

BAUD        = int(os.environ.get("BAUD", "115200"))
LOCK_MS     = 3000
HB_SERIAL   = 10     # 往 UNO 发 @Q 的周期（链路存活探测）
HB_TIMEOUT  = 35     # 这么久没回执 → 判链路死
HB_JSON     = 10     # 往看板发 heartbeat 的周期（② 由 5 s 改为 10 s）

SRC_ENUM = {"NONE", "SMOKE", "FLAME", "TEMP"}          # ③ D 定的枚举


# ---------------------------------------------------------------- 数值清洗

def to_num(x, kind):
    """把串口文本转成数字；缺测一律 None。

    kind: "f" → 保留 1 位小数的 float；"i" → int

    ⚠️ 固件的坑：DHT11 / DS18B20 读失败时 Arduino 打印的是 **字符串 "nan"**
       （Serial.print(NAN) 的结果），不是空、也不是 0。
       float("nan") 是合法浮点，会让整列均值变成 NaN，且 JSON 里 NaN 是非法字面量，
       所以必须在这里转成 None。
    """
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.lower() in ("nan", "na", "null", "-", "inf", "-inf"):
        return None
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return round(v, 1) if kind == "f" else int(round(v))


# ---------------------------------------------------------------- 串口层

class TermiosSerial(object):
    """最小串口实现（只用标准库）。pyserial 缺失时用它。"""

    def __init__(self, path, baud=115200, timeout=0.2):
        import termios
        self.timeout = timeout
        self.buf = b""
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        attrs = termios.tcgetattr(self.fd)
        speed = getattr(termios, "B%d" % baud)
        attrs[0] = 0
        attrs[1] = 0
        attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        attrs[3] = 0
        attrs[4] = speed
        attrs[5] = speed
        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        termios.tcflush(self.fd, termios.TCIOFLUSH)

    def readline(self):
        import select
        deadline = time.time() + self.timeout
        while True:
            i = self.buf.find(b"\n")
            if i >= 0:
                line, self.buf = self.buf[:i + 1], self.buf[i + 1:]
                return line
            if time.time() > deadline:
                if self.buf:
                    line, self.buf = self.buf, b""
                    return line
                return b""
            r, _, _ = select.select([self.fd], [], [], 0.05)
            if r:
                chunk = os.read(self.fd, 512)
                if chunk:
                    self.buf += chunk

    def write(self, data):
        os.write(self.fd, data)

    def reset_input_buffer(self):
        import termios
        self.buf = b""
        termios.tcflush(self.fd, termios.TCIFLUSH)

    def close(self):
        try:
            os.close(self.fd)
        except Exception:
            pass


def pick_port():
    for pat in ("/dev/ttyACM*", "/dev/ttyUSB*"):   # ACM 优先：正品 UNO 是 16U2
        c = sorted(glob.glob(pat))
        if c:
            return c[0]
    raise SystemExit("未找到串口：确认是数据线、Duo 已切 host 模式\n"
                     "  lsusb\n  ls /dev/ttyACM* /dev/ttyUSB*")


def open_serial(path, baud=BAUD, timeout=0.2):
    try:
        import serial
        return serial.Serial(path, baud, timeout=timeout), "pyserial"
    except ImportError:
        return TermiosSerial(path, baud, timeout), "termios(标准库)"


# ---------------------------------------------------------------- 上报队列

_q = queue.Queue(maxsize=64)
_stats = {"dropped": 0, "posted": 0, "failed": 0}


def post(url, obj):
    body = json.dumps(obj, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=2).read()


def _worker():
    while True:
        url, obj = _q.get()
        try:
            post(url, obj)
            _stats["posted"] += 1
        except Exception as e:
            _stats["failed"] += 1
            print("[post]", e, flush=True)
        finally:
            _q.task_done()


def enqueue(obj):
    if _q.full():                      # 队列满：丢最旧一帧并计数（实验数据完整性证据）
        try:
            _q.get_nowait()
            _stats["dropped"] += 1
        except queue.Empty:
            pass
    _q.put((DASH_URL, obj))


def send(ser, s):
    ser.write((s + "\n").encode())


def now_ts():
    # ④ ts = **节点本地时间**（UTC epoch，两板均有 ntpd 校时，跨节点可比）
    #    不加"PC 时间"——bridge 跑在 Duo 上，拿不到 PC 时钟，见文件头说明
    return round(time.time(), 3)


# ---------------------------------------------------------------- 主循环

def main():
    if NODE not in ALLOWED_NODES:
        raise SystemExit(
            "NODE=%r 不在白名单 %s 内。看板会丢弃未知 node 的帧（静默丢数据），"
            "所以这里直接退出。" % (NODE, sorted(ALLOWED_NODES)))

    threading.Thread(target=_worker, daemon=True).start()

    print("[cfg] NODE=%s" % NODE, flush=True)
    print("[cfg] DASH_URL=%s" % DASH_URL, flush=True)
    print("[cfg] HB_JSON=%ss  HB_SERIAL=%ss" % (HB_JSON, HB_SERIAL), flush=True)

    port = pick_port()
    print("[port]", port, flush=True)
    ser, backend = open_serial(port)
    print("[serial]", backend, "baud", BAUD, flush=True)

    time.sleep(2)                      # 等 UNO 复位
    ser.reset_input_buffer()
    send(ser, "@M,0")
    send(ser, "@Q")

    # 心跳先行：启动立即发一条
    enqueue({"type": "heartbeat", "node": NODE, "ts": now_ts(),
             "link": "boot", "dropped": 0, "failed": 0})

    last_rx = time.time()
    last_hb_serial = 0.0
    last_hb_json = 0.0
    dead = False
    foreign = {}           # 统计未知 tag，便于发现协议变更（不参与上报）

    while True:
        now = time.time()

        # heartbeat：每 10 s 一条（②）
        if now - last_hb_json >= HB_JSON:
            last_hb_json = now
            enqueue({"type": "heartbeat", "node": NODE, "ts": now_ts(),
                     "link": "dead" if dead else "ok",
                     "dropped": _stats["dropped"], "failed": _stats["failed"]})

        # 串口心跳必须早于任何 continue（v1.1 的 P1-1 就是这么错的）
        if now - last_hb_serial >= HB_SERIAL:
            last_hb_serial = now
            if now - last_rx > HB_TIMEOUT and not dead:
                print("[LINK] DEAD  (%.0fs 无回执)" % (now - last_rx), flush=True)
                dead = True
            try:
                send(ser, "@Q")
            except Exception as e:
                print("[send]", e, flush=True)

        try:
            raw = ser.readline().decode("utf-8", "ignore").strip()
        except Exception as e:
            print("[serial]", e, "-> reconnect", flush=True)
            try:
                ser.close()
            except Exception:
                pass
            time.sleep(2)
            try:
                ser, backend = open_serial(port)
                time.sleep(1)
                send(ser, "@M,0")
            except Exception as e2:
                print("[open]", e2, flush=True)
                time.sleep(3)
            continue

        if not raw:
            continue
        last_rx = now
        dead = False
        if not raw.startswith("@"):
            continue
        print("[rx]", raw, flush=True)

        f = raw[1:].split(",")
        tag = f[0]

        # ---- @E 环境帧：6 或 8 字段（8 字段时末尾多一个 rst）
        if tag == "E" and len(f) >= 6:
            ev = {"type": "env", "node": NODE, "ts": now_ts(),
                  "t":     to_num(f[1], "f"),
                  "h":     to_num(f[2], "f"),
                  "smoke": to_num(f[3], "i"),
                  "flame": to_num(f[4], "i"),
                  "light": to_num(f[5], "i")}
            if len(f) >= 7:
                ev["sound"] = to_num(f[6], "i")
            if len(f) >= 8:            # ④ C 的契约 1 v1.1：末尾 rst = 复位原因
                ev["rst"] = to_num(f[7], "i")
            enqueue(ev)

        # ---- @A 报警帧：改为 args:[lv, src]（③）
        elif tag == "A" and len(f) >= 3:
            try:
                lv = int(f[1].strip())
            except (ValueError, IndexError):
                lv = 0
            if lv not in (0, 1, 2):
                lv = 0                # 越界归零，不往上送脏数据
            src = (f[2].strip().upper() or "NONE")
            if src not in SRC_ENUM:    # 未知来源也归 NONE，保证枚举固定
                src = "NONE"
            enqueue({"type": "alarm", "node": NODE, "ts": now_ts(),
                     "args": [lv, src]})

        elif tag == "C" and len(f) >= 2:
            n = to_num(f[1], "i")
            if n is not None:
                enqueue({"type": "count", "node": NODE, "ts": now_ts(),
                         "passes": n})

        elif tag == "D" and len(f) >= 2:
            v = to_num(f[1], "i")
            enqueue({"type": "door", "node": NODE, "ts": now_ts(),
                     "open": v if v is not None else None})

        # ---- @R 刷卡：拒绝用 rfid + buzzer_level=deny（alarm 枚举里没有 RFID）
        elif tag == "R" and len(f) >= 2:
            uid = f[1].strip().upper()
            ok = uid in CARDS
            print("[RFID]", uid, "ALLOW" if ok else "DENY", flush=True)
            send(ser, "@L,%d" % (LOCK_MS if ok else 0))
            ev = {"type": "rfid", "node": NODE, "ts": now_ts(),
                  "uid": uid, "ok": ok}
            if not ok:
                ev["buzzer_level"] = "deny"
                ev["pattern_ms"] = "80x2/400"
            enqueue(ev)

        else:
            # 未知帧：只计数不报错（协议可能演进），便于现场发现不一致
            foreign[tag] = foreign.get(tag, 0) + 1
            if foreign[tag] == 1:
                print("[warn] 未知帧类型 %r：%s（后续同类只计数）"
                      % (tag, raw[:60]), flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[bye] dropped=%d posted=%d failed=%d"
              % (_stats["dropped"], _stats["posted"], _stats["failed"]), flush=True)

