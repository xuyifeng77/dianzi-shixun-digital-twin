#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
capture_alpha.py —— α 架构采集（集中式：节点只推视频流，推理在 PC 侧）

口径依据 `02 §6.1` / `04 §2.1`：**α = 集中式**，节点把原始视频推给 PC，PC 解码 + 推理。
本脚本在**节点侧**只做两件事：
  1. 启动 `camera-test.sh`（VI 取帧 → VENC 编码 → RTSP 推流）
  2. 把 RTSP 地址与发送字节计数打到屏幕，便于记录上行带宽

**本脚本不做推理、不向 PC 发任何元数据**——这是 α 与 β 的关键区别。
若节点向 PC 发元数据，那测得的就是 β，不是 α。

用法（在 Duo 上）：
  python3 capture_alpha.py
  python3 capture_alpha.py --log /root/alpha.log

配套（PC 侧，二选一）：
  VLC:   vlc --rtsp-tcp "rtsp://192.168.5.9/h264"
  ffmpeg: ffmpeg -rtsp_transport tcp -i rtsp://192.168.5.9/h264 -t 60 -f null -

测带宽（另一窗口，本脚本保持运行）：
  A=$(cat /sys/class/net/eth0/statistics/tx_bytes); sleep 60; \
  B=$(cat /sys/class/net/eth0/statistics/tx_bytes); echo $(( (B-A)/60 )) B/s

⚠️ 前置：必须先把开机自启的 sample_vi_fd 停掉（kill，不加 -9），否则 VPSS 被占报 0xc0068004。
"""
import argparse
import os
import select
import subprocess
import sys
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", default="camera-test.sh", help="推流程序，默认 camera-test.sh")
    ap.add_argument("--log", default="/root/alpha.log", help="子进程日志")
    args = ap.parse_args()

    print("[alpha] 说明：本脚本只推流、不发元数据（推理在 PC 侧）", flush=True)
    print("[alpha] 启动：%s   日志：%s" % (args.cmd, args.log), flush=True)

    f = open(args.log, "wb")
    try:
        proc = subprocess.Popen(args.cmd, shell=True, stdin=subprocess.DEVNULL,
                                stdout=f, stderr=subprocess.STDOUT,
                                preexec_fn=os.setsid)
    except Exception as e:
        print("[alpha] 启动失败：", e, flush=True)
        return 1

    # 从日志里把 RTSP 地址捞出来打印，省得去翻文件
    deadline = time.time() + 30
    shown = False
    f.flush()
    while time.time() < deadline and not shown:
        time.sleep(1)
        try:
            txt = open(args.log, "r", errors="ignore").read()
        except Exception:
            continue
        for line in txt.splitlines():
            if "rtsp://" in line:
                print("[alpha] 推流地址： %s" % line.strip(), flush=True)
                print("[alpha] PC 侧用 VLC(加 --rtsp-tcp) 或 ffmpeg 拉这个地址", flush=True)
                shown = True
                break
        if proc.poll() is not None:
            print("[alpha] 子进程已退出，码 %s；看 %s" % (proc.poll(), args.log), flush=True)
            break

    # 保持前台，直到 Ctrl+C；期间每 30 s 报一次累计发送量
    t0 = time.time()
    last = t0
    try:
        while proc.poll() is None:
            time.sleep(0.5)
            if time.time() - last >= 30:
                last = time.time()
                try:
                    tx = open("/sys/class/net/eth0/statistics/tx_bytes").read().strip()
                    print("[alpha] 运行 %ds，eth0 tx_bytes 累计 %s" % (int(time.time() - t0), tx), flush=True)
                except Exception:
                    pass
    except KeyboardInterrupt:
        print("\n[alpha] 收到 Ctrl+C，停止", flush=True)
    finally:
        try:
            os.killpg(os.getpgid(proc.pid), 15)   # SIGTERM，让子进程清理 VPSS
        except Exception:
            pass
        f.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
