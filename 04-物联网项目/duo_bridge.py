#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Duo 侧桥接：读 UNO 的 @行协议 → 转发 PC 看板；把鉴权结果回写给 UNO。
   运行：python3 duo_bridge.py       依赖：pyserial
"""
import json, time, urllib.request
import serial

PORT   = "/dev/ttyUSB0"                  # Duo 上 ls /dev/ttyUSB* 确认
BAUD   = 115200
SERVER = "http://192.168.5.20:8000/ingest"   # PC 看板（192.168.5.x 网段，按现场 PC 实际 IP 改）；无则置 None
CARDS  = {"A1B2C3D4"}                    # 授权卡 UID 白名单（大写十六进制）

def send(ser, line):
    ser.write((line + "\n").encode())

def post(obj):
    if not SERVER:
        return
    try:
        req = urllib.request.Request(
            SERVER, json.dumps(obj).encode(),
            {"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=2).read()
    except Exception as e:
        print("[net]", e)                # 网络异常不影响本地串口链路

def main():
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)                        # 等 UNO 复位完成
    send(ser, "@M,0")                    # 正常模式
    send(ser, "@Q")                      # 立即要一帧
    last = 0
    while True:
        try:
            raw = ser.readline().decode(errors="ignore").strip()
        except Exception as e:
            print("[serial]", e, "-> reconnect")
            try: ser.close()
            except Exception: pass
            time.sleep(2)
            try:
                ser = serial.Serial(PORT, BAUD, timeout=1)
                send(ser, "@M,0"); send(ser, "@Q")
            except Exception as e2:
                print("[open]", e2); time.sleep(5)
            continue
        if not raw.startswith("@"):
            continue
        print(raw)
        f = raw[1:].split(",")
        tag = f[0]

        if tag == "R":                   # 刷卡 → 鉴权 → 回写
            ok = (len(f) > 1 and f[1].upper() in CARDS)
            send(ser, "@L,3000" if ok else "@L,0")
            post({"type": "card", "uid": f[1] if len(f) > 1 else "", "ok": ok})
        elif tag == "E" and len(f) >= 7:  # 环境帧
            post({"type": "env", "t": f[1], "h": f[2], "smoke": f[3],
                  "flame": f[4], "light": f[5], "sound": f[6], "ts": time.time()})
        elif tag in ("A", "C", "D"):
            post({"type": tag, "args": f[1:], "ts": time.time()})

        if time.time() - last > 10:      # 心跳：10s 一次查询，保活链路
            last = time.time()
            send(ser, "@Q")

if __name__ == "__main__":
    main()
