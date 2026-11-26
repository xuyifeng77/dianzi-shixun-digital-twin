#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
duo_bridge v1.4  —— 按 2026-11-23「B-通知-视觉节点」的三条硬要求改写

与 09 作业书 v1.2 相比，只做通知要求的事，不发明字段：
  ① SERVER 可被环境变量覆盖：DASH_URL（通知点名要这个变量名）
  ② 心跳先行：启动即发 {"type":"heartbeat"}，之后每 HB_JSON 秒一条（D 用它算缺帧率）
  ③ 报警不再有 freq_hz：只发 buzzer_level = hazard|caution|deny + pattern_ms

保留 v1.2 的三项修复（这三项 06 列为 P1，不能退）：
  · 端口自动探测（/dev/ttyACM* 优先）
  · 心跳判断在读取之前（不会被 continue 跳过）
  · HTTP 上报走独立队列线程（网络慢不阻塞串口）
额外保留：pyserial 缺失时降级到标准库 termios（musl 镜像装不了 pip）。

⚠️ 通知里写的是 requests.post(...)。板上**没有 requests**（musl 无 pip 生态），
   所以这里仍然用标准库 urllib —— 这一点要回报 A，别让报告写成 requests。

用法：
  python3 duo_bridge_v1_4.py
  DASH_URL=http://192.168.5.5:8000/ingest NODE=nodeA python3 duo_bridge_v1_4.py

自测（三项，必过）：
  1) 拔掉 UNO → 35 s 内打印 [LINK] DEAD，脚本不退出
  2) DASH_URL 指向不存在的地址 → 串口照读，只有 [post] 报错
  3) 插回 → 自动恢复，[LINK] DEAD 不再重复
"""
import glob
import json
import os
import queue
import threading
import time
import urllib.request

# ---- 端点与身份（全部可被环境变量覆盖，答辩现场改 IP 不用改代码）----
DASH_URL = os.environ.get(
    "DASH_URL",
    os.environ.get("SERVER", "http://192.168.5.5:8000/ingest"))
NODE     = os.environ.get("NODE", "nodeA")     # 通知里 hostname 是 milkv-a，见文末说明
CARDS    = set(x.strip().upper() for x in
               os.environ.get("CARDS", "A1B2C3D4").split(",") if x.strip())

BAUD        = int(os.environ.get("BAUD", "115200"))
LOCK_MS     = 3000
HB_SERIAL   = 10     # 每 10 s 往 UNO 发一次 @Q（链路存活探测）
HB_TIMEOUT  = 35     # 35 s 无回执判链路死
HB_JSON     = 5      # 每 5 s 往看板发一条 heartbeat（D 用它算缺帧率）

# 三级节奏（13-决策记录 D-01：有源蜂鸣器 + 节奏编码，没有频率）
PATTERN = {
    "caution": "150/2850",    # 注意：响 150 ms / 停 2850 ms，周期 3000 ms
    "hazard":  "1000/500",    # 危险：响 1000 ms / 停 500 ms，周期 1500 ms
    "deny":    "80/120",      # 拒绝：80 ms ×2
}
LEVEL_NAME = {0: "normal", 1: "caution", 2: "hazard"}


# ---------------------------------------------------------------- 串口层

class TermiosSerial(object):
    """最小串口实现，只依赖标准库；方法与 pyserial 用到的三个一致。"""

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
    for pat in ("/dev/ttyACM*", "/dev/ttyUSB*"):
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
    if _q.full():
        try:
            _q.get_nowait()
            _stats["dropped"] += 1
        except queue.Empty:
            pass
    _q.put((DASH_URL, obj))


def send(ser, s):
    ser.write((s + "\n").encode())


def now_ts():
    return round(time.time(), 3)


# ---------------------------------------------------------------- 主循环

def main():
    threading.Thread(target=_worker, daemon=True).start()

    print("[cfg] node=%s" % NODE, flush=True)
    print("[cfg] DASH_URL=%s" % DASH_URL, flush=True)
    print("[cfg] HB_JSON=%ss HB_SERIAL=%ss" % (HB_JSON, HB_SERIAL), flush=True)

    port = pick_port()
    print("[port]", port, flush=True)
    ser, backend = open_serial(port)
    print("[serial]", backend, "baud", BAUD, flush=True)

    time.sleep(2)
    ser.reset_input_buffer()
    send(ser, "@M,0")     # 正常模式
    send(ser, "@Q")

    # ② 心跳先行：启动就先发一条，之后周期发
    enqueue({"type": "heartbeat", "node": NODE, "ts": now_ts(),
             "state": "boot"})

    last_rx = time.time()
    last_hb_serial = 0.0
    last_hb_json = 0.0
    dead = False

    while True:
        now = time.time()

        # ③ 看板心跳（与串口心跳分开，D 用它算缺帧率）
        if now - last_hb_json >= HB_JSON:
            last_hb_json = now
            enqueue({"type": "heartbeat", "node": NODE, "ts": now_ts(),
                     "link": "dead" if dead else "ok",
                     "dropped": _stats["dropped"], "failed": _stats["failed"]})

        # 串口心跳必须早于任何 continue —— v1.1 的最大 bug
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

        if tag == "E" and len(f) >= 6:
            frame = {"type": "env", "node": NODE, "ts": now_ts(),
                     "t": f[1], "h": f[2], "smoke": f[3],
                     "flame": f[4], "light": f[5]}
            if len(f) >= 7:
                frame["sound"] = f[6]
            enqueue(frame)

        elif tag == "A" and len(f) >= 3:
            # ③ 报警只有 buzzer_level + pattern_ms，没有 freq_hz
            try:
                lv = int(f[1])
            except ValueError:
                lv = 0
            name = LEVEL_NAME.get(lv, "normal")
            ev = {"type": "alarm", "node": NODE, "ts": now_ts(),
                  "level": lv, "buzzer_level": name, "src": f[2]}
            if name in PATTERN:
                ev["pattern_ms"] = PATTERN[name]
            enqueue(ev)

        elif tag == "C" and len(f) >= 2:
            enqueue({"type": "count", "node": NODE, "ts": now_ts(),
                     "passes": int(f[1])})

        elif tag == "D" and len(f) >= 2:
            enqueue({"type": "door", "node": NODE, "ts": now_ts(),
                     "open": int(f[1])})

        elif tag == "R" and len(f) >= 2:
            uid = f[1].strip().upper()
            ok = uid in CARDS
            print("[RFID]", uid, "ALLOW" if ok else "DENY", flush=True)
            send(ser, "@L,%d" % (LOCK_MS if ok else 0))
            ev = {"type": "rfid", "node": NODE, "ts": now_ts(),
                  "uid": uid, "ok": ok}
            if not ok:                      # 拒绝 = 一个 buzzer_level，不是另一个字段
                ev["buzzer_level"] = "deny"
                ev["pattern_ms"] = PATTERN["deny"]
            enqueue(ev)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[bye] dropped=%d posted=%d failed=%d"
              % (_stats["dropped"], _stats["posted"], _stats["failed"]), flush=True)
