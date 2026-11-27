#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
serial_rtt.py —— 测 Duo ↔ UNO 串口往返时延（对应 A 的判决实验 T5）

前置：固件能对 @Q 回一帧 @E（C 负责保证）。
用法（在 Duo 上）：
    python3 serial_rtt.py
    python3 serial_rtt.py /dev/ttyACM0 20

输出：每次往返毫秒 + 中位数 / 最小 / 最大，并给出可直接填表的结论行。

口径说明（写报告要用）：
  · 往返 = 从发出 "@Q\\n" 到收到一帧以 "@" 开头的完整行
  · 单次超时 1 s，超时的次数单独计数（不计入中位数）
  · 20 次取中位数，抗抖动
"""
import glob
import os
import statistics
import sys
import time


def pick_port():
    for pat in ("/dev/ttyACM*", "/dev/ttyUSB*"):
        c = sorted(glob.glob(pat))
        if c:
            return c[0]
    raise SystemExit("未找到串口：确认 UNO 已插在 Duo 的 USB-A 上、已切 host 模式\n"
                     "  lsusb\n  ls /dev/ttyACM* /dev/ttyUSB*")


class TermiosSerial(object):
    """最小串口实现，只依赖标准库（板上没有 pyserial 时用）。"""

    def __init__(self, path, baud=115200, timeout=1.0):
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


def open_serial(path, baud=115200, timeout=1.0):
    try:
        import serial
        return serial.Serial(path, baud, timeout=timeout), "pyserial"
    except ImportError:
        return TermiosSerial(path, baud, timeout), "termios"


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else pick_port()
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20

    ser, backend = open_serial(port)
    print("[port] %s  [serial] %s" % (port, backend), flush=True)
    time.sleep(1)
    ser.reset_input_buffer()

    samples, timeouts = [], 0
    for i in range(n):
        t0 = time.time()
        ser.write(b"@Q\n")
        got = False
        while time.time() - t0 < 1.0:
            line = ser.readline()
            if line and line.strip().startswith(b"@"):
                got = True
                break
        dt = (time.time() - t0) * 1000.0
        if got:
            samples.append(dt)
            print("  %2d: %7.1f ms" % (i + 1, dt), flush=True)
        else:
            timeouts += 1
            print("  %2d: timeout" % (i + 1), flush=True)
        time.sleep(0.05)

    ser.close()

    print("")
    if not samples:
        print("全部超时 —— 检查：UNO 是否在上报、固件是否回 @Q、波特率是否 115200")
        return 1

    print("=" * 46)
    print("往返时延（%d 次有效 / %d 次超时）" % (len(samples), timeouts))
    print("  中位数 : %.1f ms" % statistics.median(samples))
    print("  最小   : %.1f ms" % min(samples))
    print("  最大   : %.1f ms" % max(samples))
    print("  均值   : %.1f ms" % statistics.mean(samples))
    print("=" * 46)
    print("可直接填表：链路往返中位数 %.1f ms（%d 次，超时 %d 次）"
          % (statistics.median(samples), len(samples), timeouts))
    print("注意：这是 **往返**，单程约一半；报告里写清口径，别和『端到端 33 ms』混。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
