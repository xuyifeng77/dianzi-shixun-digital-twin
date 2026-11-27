#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
beta_count_report.py —— β 架构采集（真实人数版）

与 beta_meta_report.py 的区别：
  · **上报真实人数**（解析 `sample_vi_fd` 打印的 `face count: N`）
  · **不报 fps / infer_ms**（实测这两个量无法从该程序获得，见下）

2026-11-25 实测结论（务必保留，报告要引用）：
  1. `sample_vi_fd` 二进制里确实有 `face count: %d` 的格式串，且**会打印**：
     镜前有人时输出 `face count: 1`，人走开后输出 `face count: 0`。
  2. 但**必须用 pty 读**：stdout 接管道时是全缓冲，日志会被吞掉（pty 则按行刷出）。
  3. 打印**不是每帧一次**（观测到的间隔从几十毫秒到数秒不等），
     因此**不能**用它反推推理帧率——`fps` / `frame_ms` 这两个字段是伪量，已从本脚本移除。

字段设计：
  {"type":"infer","node":"nodeA","ts":...,"count":N,"age_s":k}
    count  最近一次解析到的人数（0 表示画面中无人）
    age_s  距上次打印 face count 的秒数（越大说明数据越陈旧，便于事后判断可信度）

用法：
  DASH_URL=http://192.168.5.5:8000/ingest python3 beta_count_report.py 2>&1 | tee /root/beta_count.log
  DASH_URL=http://192.168.5.5:8000/ingest NODE=nodeB python3 beta_count_report.py   # B 板

前提：跑之前必须先把开机自启的 sample_vi_fd 停掉（kill，不加 -9），否则 VPSS 被占。
"""
import json
import os
import re
import select
import subprocess
import threading
import time
import urllib.request

DASH_URL = os.environ.get("DASH_URL", "http://192.168.5.5:8000/ingest")
NODE     = os.environ.get("NODE", "nodeA")
INTERVAL = float(os.environ.get("INTERVAL", "2"))
CMD      = os.environ.get("CAM_CMD", "camera-test.sh")

PAT = re.compile(r"face\s*count\s*[:=]\s*(\d+)", re.I)

_state = {"count": None, "t_last": 0.0, "lines": 0}
_lock = threading.Lock()


def post(obj):
    body = json.dumps(obj, ensure_ascii=False).encode()
    req = urllib.request.Request(DASH_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=2).read()


def handle_line(line):
    line = line.rstrip("\r")
    if not line:
        return
    m = PAT.search(line)
    if m:
        with _lock:
            _state["count"] = int(m.group(1))
            _state["t_last"] = time.time()
            _state["lines"] += 1
        return
    # 只打印非高频行，避免 anchor/bbox 刷屏
    if not re.match(r"^(anchor|bbox|landmark|score):", line):
        print("[cam]", line[:120], flush=True)


def reader(fd, proc):
    buf = b""
    while True:
        try:
            r, _, _ = select.select([fd], [], [], 1.0)
        except (OSError, ValueError):
            break
        if not r:
            if proc.poll() is not None:
                break
            continue
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            handle_line(line.decode("utf-8", "ignore"))
    print("[cam] 子进程退出码 =", proc.poll(), flush=True)


def main():
    print("[beta] 启动本地推理：%s" % CMD, flush=True)
    print("[beta] 上报：%s  节点=%s  周期=%.1fs" % (DASH_URL, NODE, INTERVAL), flush=True)
    print("[beta] 不要开 VLC 拉流（否则视频出节点，就不是 β）", flush=True)

    try:
        import pty
        master, slave = pty.openpty()
        proc = subprocess.Popen(CMD, shell=True, stdin=slave, stdout=slave,
                                stderr=slave, preexec_fn=os.setsid, close_fds=True)
        os.close(slave)
        fd = master
        print("[beta] 输出通道 = pty（必须，管道会缓冲掉 face count）", flush=True)
    except Exception as e:
        print("[beta] pty 不可用(%s)，退回管道（可能读不到 face count）" % e, flush=True)
        proc = subprocess.Popen(CMD, shell=True, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                preexec_fn=os.setsid, bufsize=0)
        fd = proc.stdout.fileno()

    threading.Thread(target=reader, args=(fd, proc), daemon=True).start()

    sent = 0
    t0 = time.time()
    try:
        while proc.poll() is None:
            time.sleep(INTERVAL)
            now = time.time()
            with _lock:
                cnt = _state["count"]
                t_last = _state["t_last"]

            if cnt is None:
                # 还没解析到任何一次，说明镜前长期无人或程序未就绪
                obj = {"type": "infer", "node": NODE, "ts": round(now, 3),
                       "count": None, "age_s": None}
            else:
                obj = {"type": "infer", "node": NODE, "ts": round(now, 3),
                       "count": cnt, "age_s": round(now - t_last, 1)}

            line = json.dumps(obj, ensure_ascii=False)
            print("[infer] %s  (%d bytes)" % (line, len(line.encode())), flush=True)
            try:
                post(obj)
                sent += 1
            except Exception as e:
                print("[post]", e, flush=True)
    except KeyboardInterrupt:
        print("\n[beta] 收到 Ctrl+C", flush=True)
    finally:
        try:
            os.killpg(os.getpgid(proc.pid), 15)
        except Exception:
            pass
        with _lock:
            n = _state["lines"]
        print("[beta] 已发送 %d 条；共解析到 %d 次 face count；运行 %d 秒"
              % (sent, n, int(time.time() - t0)), flush=True)


if __name__ == "__main__":
    main()
