# 交接卡 · B（视觉节点）

> 规则：`共享/07 §九`——每人一页、300 字以内，四项内容。备份人 **D**。

**日期**：2026-11-26　**填表人**：B　**备份人**：D

## 1. 我在做什么

两块 Milk-V Duo 256M 从点亮到稳定出推理结果；桥接脚本（UNO 串口 → HTTP JSON）；α/β 两套采集程序；节点侧实验数据。

## 2. 做到哪

| 项 | 状态 | 证据 |
|---|---|---|
| 两板出图 + 推理 | ✅ | `B/evidence/D2`、`D3` |
| 两板各 1 h 稳定 | ✅ 139MB / 52.5·52.8℃ / 0 OOM / 29.97fps | `B/evidence/D4`、`D6` |
| 双板同时在线 | ✅ 双路 RTSP 同屏 | `B/evidence/D6` |
| α/β 采集 | ✅ 每组 3 次中位数 | `B/evidence/D7`、`D8` |
| 扩根分区 / NTP / 蓝灯 | ✅ 两板 29G | `B/evidence/` |
| 桥接上机联调 | ❌ 等 UNO | — |
| PC 侧串口宿主（落①后） | ❌ 未写 | — |

## 3. 下一步命令

```sh
# 看两块板在不在
powershell -File D:\DSHworkspace\B岗-上手指导\code\find_boards.ps1

# β 采集（A 板，注意 DASH_URL 每次按实际 PC IP 改）
cd /root && DASH_URL=http://<PC_IP>:8000/ingest python3 capture_beta.py 2>&1 | tee /root/beta.log

# α 采集（A 板推流，PC 侧 VLC/ffmpeg 拉流）
cd /root && python3 capture_alpha.py

# 测带宽（任一板）
A=$(cat /sys/class/net/eth0/statistics/tx_bytes); sleep 60; \
B=$(cat /sys/class/net/eth0/statistics/tx_bytes); echo $(( (B-A)/60 )) B/s

# 验证测量有效（必须为 0）
grep -c "post" /root/beta.log
```

## 4. 卡在哪

- **要 UNO**：D5 桥接三项自测、T2 host 枚举、T5a 时延，全排在"UNO 到手"之后（`17-待交清单` B-4/B-5）。
- **要 D 的看板 IP**：`SERVER` 现写 `192.168.5.20`，需 D 回填实测值（B-3）。
- **要 A/D 定 node 值域**：A 写 `milky-a`，D 写 `nodeA`，未统一（我按 `nodeA` 实现）。
