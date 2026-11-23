# 契约 3 · 实验数据 CSV schema（v1.1）

> 出方：D ｜ 用方：全员 ｜ 状态：**v1.1a（v1.1 D2 出稿；11-23 口径修正，待 D3 冻结签字）**
> 依据：`04-实验设计.md §2.4/§3.4/§5`、`06-项目审查报告.md P1-6`、`11-D岗-数据与实验.md §四`、**`13-决策记录-有源蜂鸣器与A板IP.md`（D-01 / D-02）**
> 变更规则：冻结后改一次要 A 签字，并同步改本文件 + `实验记录表-v1.2.md` + `clean.py`

## 修订记录

| 版本 | 日期 | 改了什么 |
|---|---|---|
| v0.1 | 11-23 | 初稿：三套实验列定义、目录结构 |
| v1.0 | 11-23 | ①统一命名 `exp1_<arch>_n<N>_r<NN>` / `exp2_g<GG>_r<NN>`；②实验一增 `duration_s` `frame_count` `fps` `node_fps` `rec_fps` `time_res_ms` `lat_e2e_err_ms`；③实验二增 `tp` `fn` `fp`；④`mean_conf` 仅检出；⑤`passes.csv` 增 `truth_pass` `matched_event_id`；⑥新增质量校验；⑦目录权限写明 |
| **v1.1a** | 11-23 | 排查修正（未改动任何列定义，只改量纲口径）：①§节奏表"心跳 1 s/帧、3 s 判离线"与固件 `@E` 2 s/帧、bridge `@Q` 10 s 保活不符 → 改为 **2 s/帧、6 s 异常、30 s 离线**；②补一句显式声明"α=集中式 / β=分布式（边缘）"，与 `01 §1.4`、`02 §4.3`、`04 §2.1` 对齐（`lat_pipe_ms` 仅 β 组测的含义不变）。改动记录：[`15-矛盾排查-2026-11-23`](../共享/15-矛盾排查-2026-11-23.md) |

---

## 0. 通用约定

| 项 | 约定 |
|---|---|
| 编码 / 分隔符 | UTF-8（无 BOM）、逗号分隔、小数点 `.`、表头必须存在 |
| 时间 | **一律 PC 侧 `time.time()`（Unix 秒，3 位小数）**；不在板上取时间 |
| 缺失 | 写 `NA`。不写 0、不空着、不写 `-` |
| 布尔 | `1` / `0`，不用 `TRUE/FALSE` |
| 命名 | `alpha` / `beta`（小写，CSV 与路径通用）；重复次数 `r01` `r02` `r03` |
| **α/β 语义（唯一口径）** | **`alpha` = α = 集中式（节点只推流，PC 推理；对照组）**；**`beta` = β = 分布式 / 边缘（节点本地推理，只传结论；本系统）**。与 `01 §1.4`、`02 §4.3`、`04 §2.1` 一致。任何文档里"α=边缘、β=中心"的写法均为错误，见 [`15-矛盾排查-2026-11-23`](../共享/15-矛盾排查-2026-11-23.md) |
| **报警字段** | **只允许 `buzzer_level` + `pattern_ms`；禁止 `freq_hz`、`tone`、`音调`** —— 蜂鸣器为有源件，`buzzTask()` 用 `digitalWrite` 打节奏，没有频率这个量 |
| 事件排序 | 事件表按 `ts` 单调递增；**不按到达顺序**（补发/重放会乱序） |

---

## 1. 目录结构、权限与主机

```
04-物联网项目/
├─ data/
│  ├─ raw/                            # 原始层：只读，禁止人工修改
│  │  ├─ exp1/20261124-beta-n1-r01/
│  │  │     report.jsonl              # 每条 UDP 报文（原始）
│  │  │     netdev.csv                # 带宽采样（每 5 s）
│  │  │     cpu.csv                   # PC 进程 CPU 采样
│  │  ├─ exp2/20261202-g01-r01/
│  │  │     passes.csv                # 人次级明细
│  │  │     video.mp4                 # 录像留证
│  │  ├─ events/20261130-a-b.csv      # 报警 / 心跳事件流（见 §6）
│  │  └─ exp3/...
│  ├─ exp1/                           # 表格层：一次 run 一个 CSV（一行）
│  │     exp1_alpha_n1_r01.csv
│  │     summary_exp1.csv             # 汇总层：clean.py 生成，画图只读这个
│  ├─ exp2/
│  │     exp2_g01_r01.csv
│  │     summary_exp2.csv
│  ├─ exp3/
│  └─ clean/                          # 清洗中间产物，可随时重生成
├─ tools/clean.py                     # python clean.py 一条命令重跑
└─ 实验记录表-v1.2.md
```

| 层 | 权限 | 谁能改 |
|---|---|---|
| `raw/` | **只读** | 只有采集程序写；任何人不得编辑，改了就作废 |
| `exp1/`、`exp2/`、`exp3/` | 结构性 | D 写入；他人只读 |
| `clean/` | 可删可重建 | 脚本产物，不手改 |
| `summary_*.csv` | 脚本生成 | 只由 `clean.py` 生成，不手改 |

### 1.1 主机与端口（D-02 决策）

| 角色 | 地址 | 说明 |
|---|---|---|
| 节点 A | `192.168.5.7` | 节点状态页显示 `nodeA / .7` |
| 节点 B | `192.168.5.8` | 同上 |
| 扩展位 C/D | `.9` / `.10` | 未接入时写 `NA` |
| PC 看板 | `192.168.5.20`（**暂记，待实测**） | 监听 `0.0.0.0:8000`，不能写 `127.0.0.1` |
| 桥接推送 | `http://192.168.5.20:8000/ingest` | `duo_bridge.py` L11，与看板地址必须一致 |
| 心跳 / 数据帧 | 节点上行 `@E`：**2 s / 帧**（固件固定，见 `UNO_Node.ino` 注释"环境帧，2s"）；bridge 每 **10 s** 发一次 `@Q` 保活拉帧 | 看板 **6 s**（3 帧）无新 `@E` 判"链路异常"，**30 s** 判"离线"（旧口径"1 s/帧、3 s 超时"与固件实现不符，已作废） |

> PC 实测 IP 若不是 `.20`，**要么路由器绑成 `.20`，要么改 `duo_bridge.py` 的 `SERVER`**，二选一，不许两边都不动。实测结果回报 A 更新 `13`。

---

## 2. 实验一：`exp1_<arch>_n<N>_r<NN>.csv`

一次 run 一行（60 s 测量窗口）。

| 列 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `run_id` | str | — | `20261124-beta-n1-r01` |
| `ts_start` | float | s | 窗口起点（PC 时钟） |
| `ts_end` | float | s | 窗口终点 |
| `duration_s` | float | s | **实际测量时长**（`ts_end - ts_start`，可能≠60） |
| `arch` | enum | — | `alpha` / `beta` |
| `n_nodes` | int | — | 1 / 2（**只允许这两个值**） |
| `run` | int | — | 1–3（与文件名 `rNN` 一致） |
| `tx_bytes` | int | B | 窗口内各节点 `tx_bytes` 增量之和 |
| `bw_Bps` | float | B/s | **`tx_bytes / duration_s`**（不是除 60） |
| `frame_count` | int | 帧 | 窗口内处理的总帧数 |
| `frames_rx` | int | 帧 | **实际收到的上报帧数**（看板计数） |
| `frames_expected` | int | 帧 | **期望帧数** = `duration_s / hb_interval_s`（默认 1 s 一帧） |
| `loss_pct` | float | % | `1 − frames_rx / frames_expected`（数据完整性，答辩小表用） |
| `fps` | float | 帧/s | `frame_count / duration_s`（实测处理帧率） |
| `node_fps` | float | 帧/s | 节点出帧/推理帧率（如 30.0） |
| `rec_fps` | float | 帧/s | 录像帧率（手机实测，如 60.0） |
| `time_res_ms` | float | ms | 系统量化：`1000 / node_fps` |
| `lat_e2e_ms` | float | ms | 端到端：人进画面 → 看板出事件 |
| `lat_e2e_err_ms` | float | ms | 端到端误差：`±(time_res_ms + 1000/rec_fps/2)` |
| `lat_pipe_ms` | float | ms | 流水线：节点出结论 → PC 收到（辅助，仅 β 组测） |
| `infer_ms` | float | ms | 单帧推理耗时 |
| `pc_cpu_pct` | float | % | PC 侧均值 |
| `cpu_scope` | enum | — | `per_core` / `all_cores`（**必填**，无数据写 `NA`） |
| `duo_cpu_pct` | float | % | 节点侧均值；α 组写 `NA` |
| `npu_pct` | float | % | NPU 占用；无数据写 `NA` |
| `dropped` | int | 帧 | 桥接队列丢帧数（B 提供） |
| `note` | str | — | 异常、时长偏差、设备更换 |

> **口径提示**：`lat_e2e_ms` 与 `lat_pipe_ms` 不是同一段，误差分别标注，不得互相替代。

## 3. 实验二 · 组级：`exp2_g<GG>_r<NN>.csv`

一组 10 人次一行。组号 ↔ 条件对照见 `实验记录表-v1.2.md §2.1`。

| 列 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `group_id` | int | — | 1–12 |
| `light` | enum | — | `on` / `off` / `backlit` |
| `speed` | enum | — | `walk` / `fast` |
| `orientation` | enum | — | `front` / `side` |
| `ts_start` | float | s | 组开始时刻 |
| `n_pass` | int | 人 | 计划人次（10） |
| `truth_total` | int | 人 | 光电真值合计（= `tp + fn`） |
| `auto_total` | int | 人 | 视觉计数合计（= `tp + fp`） |
| `tp` | int | 人 | 正确匹配人次（视觉检出且真值存在） |
| `fn` | int | 人 | 漏检人次（真值存在、视觉未检出） |
| `fp` | int | 人 | 误检人次（视觉报出但无对应真值：重复框/虚警） |
| `miss` | int | 人 | 计数差值 = `truth_total − auto_total`（= `fn − fp`），**不是漏检数** |
| `bias_pct` | float | % | `(auto_total − truth_total) / truth_total × 100` |
| `mean_conf` | float | — | **仅对 `tp` 人次**求平均；全组无检出自写 `NA` |
| `mean_conf_all` | float | — | 全部计划人次的平均，未检出按 0 计（辅助指标） |
| `deny_evt` | int | 次 | **本组 `buzzer_level=deny` 事件数**（刷卡失败/无权限）。**只记录，不计入 `truth_total`/`auto_total`** |
| `video_file` | str | — | 录像文件名 |
| `note` | str | — | 如"含 2 次合并事件" |

> ⚠️ **`tp/fn/fp` 必须由人次级事件匹配（录像 + `passes.csv`）得出，不能用两个总数反推。**
> 若某组只做了总数核对、没有逐人次匹配，则 `tp/fn/fp` 写 `NA`，`miss` 照常填，并在 `note` 写 `#count_only`；报告中该组只能称"计数偏差"，不得称"检测准确率"。
>
> ⚠️ **`deny` 不是通行**：拒绝通行是事件，不是"一次访问"。把它算进人次会让准确率虚高。只在 `deny_evt` 与 §6 事件表里出现。

## 4. 实验二 · 人次级：`data/raw/exp2/<run_id>/passes.csv`

| 列 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `ts` | float | s | 该人次时刻（PC 时钟，按录像打点） |
| `group_id` | int | — | 1–12 |
| `seq` | int | — | 组内第几人次（1–10） |
| `truth_pass` | int | — | 该人次是否真实发生：1 / 0（0 表示视觉虚警，仅用于 fp） |
| `detected` | int | — | 视觉是否检出：1 / 0 |
| `conf` | float | — | 检出置信度；未检出写 `NA` |
| `matched_event_id` | str | — | 对应的视觉检测事件编号（如 `ev-0042`）；无匹配写 `NA` |
| `merge_flag` | int | — | 与前一人次间隔 <3 s、可能被合并：1 / 0 |
| `note` | str | — | 侧身/遮挡/回头/重复框 |

**由本表可复算**：`tp = Σ(truth_pass=1 且 detected=1)`；`fn = Σ(truth_pass=1 且 detected=0)`；`fp = Σ(truth_pass=0)`。

## 5. 实验三：`exp3_s<SS>_r<NN>.csv`

| 列 | 类型 | 说明 |
|---|---|---|
| `scenario` | int | 1–5，对应 `04 §4` |
| `run` | int | 1–10 |
| `expected` | enum | `alarm` / `no_alarm` / `known_blind` |
| `actual` | enum | `alarm` / `no_alarm` |
| `buzzer_level` | enum | 实际触发的等级：`hazard` / `caution` / `deny` / `NA` |
| `correct` | int | 1 / 0；`scenario=5` 时写 `NA` |
| `note` | str | 侧绕、倒退等 |

> 场景 5（侧绕）标 `known_blind`，**单独统计"漏报次数"，不计入 1–4 的成功率**。
> 场景 2 正常预期为 `hazard · 1000/500`；若实际是 `caution`，`correct` 记 0（等级不对也算错）。

---

## 6. 事件表：`events_<YYYYMMDD>.csv`（D-01 决策）

报警与心跳的统一事件流，看板"报警时间线"页与 §6 汇总都读它。

| 列 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `ts` | float | s | PC 时钟，**表按此列单调递增** |
| `node_id` | enum | — | `nodeA`（.7）/ `nodeB`（.8）/ `.9` / `.10` |
| `src` | enum | — | `SMOKE` / `FLAME` / `TEMP` / `HUM` / `DOOR` / `CARD` / `HEARTBEAT` |
| `event` | enum | — | `alarm` / `clear` / `deny` / `heartbeat` |
| `buzzer_level` | enum | — | `hazard` / `caution` / `deny` / `NA`（`heartbeat` 无蜂鸣写 `NA`） |
| `pattern_ms` | str | ms | `1000/500`、`150/2850`、`80x2/400`；与 `buzzer_level` 一一对应，无蜂鸣写 `NA` |
| `note` | str | — | 自由备注，可用 `#replay` 标补发 |

### 6.1 三级语义与节奏（写死，填表不用问）

| `buzzer_level` | 响 | 停 | 周期 | 触发场景 | `pattern_ms` 写法 |
|---|---|---|---|---|---|
| `hazard` | 1000 ms | 500 ms | 1500 ms | 烟雾、火焰、门磁强开 | `1000/500` |
| `caution` | 150 ms | 2850 ms | 3000 ms | 温湿度越界、陌生人靠近 | `150/2850` |
| `deny` | 80 ms × 2 | 400 ms | — | 刷卡失败 / 无权限 | `80x2/400` |

**三条硬规则**
1. **禁止 `freq_hz` / `tone`**：固件 `buzzTask()` 用 `digitalWrite` 打节奏，没有频率量；写了只会产生空列或假数据。质量校验第 13 条直接拒收。
2. **按 `ts` 排序**，不按到达顺序（补发/重放会乱序），第 14 条校验。
3. **`deny` 不计人次**，只作为事件进入本表与 `exp2.deny_evt`。

---

## 7. 汇总表（`clean.py` 生成）

- `data/exp1/summary_exp1.csv`：每 run 一行 + `median_of_3` 标记 + `loss_pct` 均值
- `data/exp2/summary_exp2.csv`：12 组一行，含 `acc_count = 1 − |miss| / truth_total`、`tp/fn/fp` 汇总、`deny_evt` 合计、`n_groups_with_matching`
- `data/summary_events.csv`：按 `buzzer_level` 计数（hazard / caution / deny），供看板"报警时间线"与报告引用

## 8. 数据质量校验规则（`clean.py` 必须逐条检查，失败即报错）

| # | 检查项 | 规则 | 失败处理 |
|---|---|---|---|
| 1 | 时间戳 | `ts_end ≥ ts_start`；`ts` 落在录像起止区间内 | 拒收该行 |
| 2 | 测量时长 | 实验一 `duration_s` 与 60 s 偏差 >10% 必须在 `note` 说明 | 无说明则告警 |
| 3 | 节点数 | `n_nodes ∈ {1, 2}` | 拒收 |
| 4 | 架构枚举 | `arch ∈ {alpha, beta}` | 拒收 |
| 5 | 缺失值 | 只允许 `NA`；空值/0/- 视为格式错误 | 拒收 |
| 6 | 置信度 | `0 ≤ conf ≤ 1`；`mean_conf` 仅在 `tp>0` 时有值 | 拒收 |
| 7 | 布尔 | `detected`、`truth_pass`、`merge_flag` ∈ {0,1} | 拒收 |
| 8 | 重复编号 | 同一 `(arch, n_nodes)` 下 `run` 不得重复 | 拒收 |
| 9 | 组号完整性 | exp2 必须有 1–12 全部组；缺组在汇总表标 `MISSING` | 告警 |
| 10 | 计数自洽 | `truth_total = tp + fn`；`auto_total = tp + fp`（有匹配数据时） | 不一致则告警并保留原值 |
| 11 | 原始数据完整性 | `raw/` 文件 mtime 与归档清单一致，且未被改写（哈希比对） | 报警，禁止进报告 |
| 12 | 汇总可复算 | 由 `summary_*.csv` 重跑 `clean.py` 得到的结果与报告数字一致 | 阻断出图 |
| **13** | **报警字段合法** | 事件表**出现 `freq_hz` / `tone` 即拒收**；`buzzer_level` ∈ {hazard,caution,deny,NA}；`pattern_ms` 必须与等级对应 | 拒收该行 |
| **14** | **事件序** | `events` 表 `ts` 单调递增；乱序则按 `ts` 重排并告警 | 告警 + 重排 |

---

## 9. 待确认（D2 前答复）

1. `cpu_scope` 默认值：建议 `all_cores`。
2. `lat_pipe_ms` 是否只在 β 组测（α 组写 `NA`）？
3. `mean_conf_all` 是否保留（已有 `mean_conf`，此项仅作辅助）？
4. `note` 固定标签：`#merge` `#recalib` `#swap` `#count_only` `#replay`，脚本按标签过滤。
5. **PC 实测 IP 是否为 `.20`**（D-02 遗留）：不是的话，路由绑定或改 `duo_bridge.py`，二选一并回报 A。
