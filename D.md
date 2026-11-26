# D · 交接卡（11-27 凌晨 · 契约 5 命名落地后）

**在做什么**：A 指出我上一轮三处判断错（`node` 该用 `milky-*`、契约 3 的 `node_id` 是旧值残留、改名不会丢帧），已全部改正 → **契约 3 升 v1.1f**（只动命名与 IP：`milky-a .9 / milky-b .10 / milky-c .11 / milky-d .12`），并按 A 的 D-1…D-10 派单补齐口径。

**做到哪**：
- 看板加 `NODE_ALIAS` + `norm_node()`：`nodeA` 帧自动归一成 `milky-a` 并打 `[warn] alias`，落盘/文件名永远 `milky-*`（实测：CSV 首列 `milky-a`、env 文件 `milky-a_20261126.jsonl`）。
- 新增 [`口径算例-带宽时延完整性.md`](../口径算例-带宽时延完整性.md)：D-4 带宽公式 + 55–75 B/s 算例、D-5 时延误差代入（410 ± 88 ms 示例）、D-6 完整性"99.9% 在 60 s 窗口算不出来"+ `rst≠0` 分段重算、D-7 尾随误报/漏报定义与"为什么钉在 bridge"。
- D-3 实验二排期表进 [`04 §3.4.1`](../04-实验设计.md)（2.5 min/人次 → 25 min/组 → 每天 4 组约 2 h）；D-9 报告 5 张图清单进 `04 §7.1`；D-8 真值口径一句话已在 `04 §3.2`。
- 4 张截图按 `milky-a .9 / milky-b .10` 重拍（`dashboard/screenshots/`）。
- 签字页 12 条 + 第 12 条命名；D/README、记录表、`11`、`dashboard/README` 全部对齐 v1.1f。

**下一步命令**：
```bash
cd D/dashboard
python app.py --data ../data --port 8000     # 窗口 1
python mock_feed.py                          # 窗口 2（写 data/mock/）
DASH_URL=http://192.168.5.20:8000/ingest NODE=milky-a python3 duo_bridge_v1_5.py   # 上机接真流
```

**卡在哪**：
1. **A**：`A/15-契约5` 与 `共享/16-网络绑定表` 两份依据**不在包里**（值我只有转述，`clean.py`/签字页引用不了）；实验室网段下的 **PC 实测 IP**（本机现在只有 `10.27.220.115/18`，不在 `192.168.5.0/24`）；契约 3 v1.1f **重签**；把 `A/02 §4.1` 的 150–300 B/s 改成 55–75 B/s。
2. **B**：`duo_bridge_v1_5.py` 的 `NODE` 主值改 `milky-*`（现在白名单只有 `nodeA..nodeD`）、默认 `DASH_URL` 改 `.20`、删 `pattern_ms:"80/120"`、`post()` 补 `node`、补 env/alarm/door/rfid 真样本、契约 4 定稿（含 §9 签字行）。
3. **C**：契约 1 签字页落笔 + 书面确认"门磁只发 `@D`、不参与判级"。

技术侧不卡：`--mock` 与真流两条路都跑通了。
