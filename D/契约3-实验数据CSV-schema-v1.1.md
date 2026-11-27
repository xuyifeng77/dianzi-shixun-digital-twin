# 契约 3 · 实验数据 CSV schema（v1.1f，文件名仍为 v1.1.md）

> 出方：D ｜ 用方：全员 ｜ 状态：**v1.1f（v1.1e + A 订正 §1.1 与 §6 的节点名/IP 旧值）** ｜ 冻结日 2026-11-26 ｜ 签字见 [`契约3-签字页.md`](契约3-签字页.md)
> 版本链：v1.1a（D2 出稿）→ v1.1b（11-25 A 用方复核，2 处意见）→ v1.1c（11-26 D 主持冻结）→ v1.1d（11-26 晚 B 交 `duo_bridge_v1_5.py` 后的语义补注）→ v1.1e（11-26 晚 A 复核第 5/7 条的落盘目录口径）→ **v1.1f（11-26 深夜 A 订正 `nodeA`/`.7`/`.8` 旧值；语义不变、签名继续有效）**
> 依据：`04-实验设计.md §2.4/§3.4/§5`、`06-项目审查报告.md P1-6`、`11-D岗-数据与实验.md §四`、**`13-决策记录-有源蜂鸣器与A板IP.md`（D-01 / D-02）**
> 变更规则：冻结后改一次要 A 签字，并同步改本文件 + `实验记录表-v1.2.md` + `clean.py`

## 修订记录

| 版本 | 日期 | 改了什么 |
|---|---|---|
| v0.1 | 11-23 | 初稿：三套实验列定义、目录结构 |
| v1.0 | 11-23 | ①统一命名 `exp1_<arch>_n<N>_r<NN>` / `exp2_g<GG>_r<NN>`；②实验一增 `duration_s` `frame_count` `fps` `node_fps` `rec_fps` `time_res_ms` `lat_e2e_err_ms`；③实验二增 `tp` `fn` `fp`；④`mean_conf` 仅检出；⑤`passes.csv` 增 `truth_pass` `matched_event_id`；⑥新增质量校验；⑦目录权限写明 |
| **v1.1a** | 11-23 | 排查修正（未改动任何列定义，只改量纲口径）：①§节奏表"心跳 1 s/帧、3 s 判离线"与固件 `@E` 2 s/帧、bridge `@Q` 10 s 保活不符 → 改为 **2 s/帧、6 s 异常、30 s 离线**；②补一句显式声明"α=集中式 / β=分布式（边缘）"，与 `01 §1.4`、`02 §4.3`、`04 §2.1` 对齐（`lat_pipe_ms` 仅 β 组测的含义不变）。改动记录：[`15-矛盾排查-2026-11-23`](../共享/15-矛盾排查-2026-11-23.md) |
| **v1.1b** | 11-25 | **A 按用方复核**，提 2 处必改（均已并入本版）：①§2 `frames_expected` 仍写"默认 1 s 一帧"，与固件 `@E` 2 s/帧 不符，会把丢包率算高一倍；②§6.1 触发场景与 `UNO_Node.ino` 的 `judge()` 不符（温度 ≥45 ℃ 属 hazard；"门磁强开""陌生人靠近"固件未实现）。A 签字页：`契约3-签字页.md` |
| **v1.1c** | 11-26 | **D 主持冻结**：①§1 目录树改为仓库实际的 `D/` 结构（旧树写的是 `04-物联网项目/` 老路径）；②真值口径三处统一为"U 型光电为主、人工为降级并打标"（`04 §3.2` / `11 §四` / 本文件 §3 同步）；③全包清除"延迟 33 ms / ±17 ms"固定值，只写逐次实测 + §2 误差公式；④新增 §6.2 落表映射（帧→事件表→看板），把 clear 的 `src` 继承、`#count_reset`、`@D` 不进事件表等口径写死；⑤§9 五问定稿；⑥新增 §10 冻结签字表 |
| **v1.1d** | 11-26 晚 | **B 交 `duo_bridge_v1_5.py` 后的语义补注，未动任何列名/量纲/边界，冻结条款不变**：①§0 补"落表 `ts` = 看板收到时刻 `ts_rx`"，并说明节点的 `ts` 只作诊断；②§0 增"节点时间"与"bridge 版本绑定"两行（v1.5 起 env 数值化、心跳 5→10 s，**v1.4 及更早的数据不得与 v1.5 混用**，β 带宽必须重测）；③§1.1 标出 v1.5 默认 `DASH_URL` 是 `.5` 而非契约的 `.20`，上机必须显式传；④§2 `note` 与 §9 增 `#bridge=v1.5` 标签；⑤§6.2 补 `type:"rfid"` 与 `type:"heartbeat"` 两行，并写明 v1.5 的 `pattern_ms:"80/120"` 与 D-01 不符、以 `80x2/400` 为准 |
| **v1.1e** | 11-26 晚 | **A 复核第 5、7 条的落盘目录口径（列名/量纲/边界均未动）**：①事件表由 `raw/events_<YYYYMMDD>.csv` 改 **`raw/events/<YYYYMMDD>.csv`**；②新增 **`raw/env/<node>_<YYYYMMDD>.jsonl`**（环境帧原始 JSON，一行一帧，只增不改）；③新增 **`data/mock/`**（`--mock` 与 `mock_feed.py` 默认都写这里，**假数据永不进 `raw/`**）；④补 §1.2 本机跑法（两个窗口）；⑤`04 §2.1` 上行带宽 150–300 B/s → 55–75 B/s |
| **v1.1f** | 11-26 深夜 | **A 订正与本文件其余部分自相矛盾的节点名/地址旧值（语义未变，B/C/D 已签意见继续有效，不需重签）**：①§1.1 主机表 `.7/.8` → **`.9/.10`**、`nodeA / .7` 写法 → `milky-a` + 完整四段 IP、扩展位 `.9/.10` → **`.11/.12`**；②§6 事件表 `node_id` 枚举 → **`milky-a…milky-d`**，并写明旧 `nodeA…nodeD` **只作输入别名**、归一后落盘；③§1.2 真流示例 `NODE=nodeA` → `NODE=milky-a`。**历史数据不回改**：11-25/11-26 已采的 208 条样本仍带 `nodeA`，属原始证据，读取时统一按别名表归一即可 |
---

## 0. 通用约定

| 项 | 约定 |
|---|---|
| 编码 / 分隔符 | UTF-8（无 BOM）、逗号分隔、小数点 `.`、表头必须存在 |
| 时间 | **一律 PC 侧 `time.time()`（Unix 秒，3 位小数）**；不在板上取时间。看板落表时 `ts` 就是**收到该帧的时刻 `ts_rx`**（`app.py` 里 `ts = time.time()`）；bridge v1.5 上报的节点 `ts` 只用于诊断，**不写进 CSV**（见下一行） |
| 缺失 | 写 `NA`。不写 0、不空着、不写 `-`。bridge v1.5 把缺失转成 JSON `null`，看板落表时仍写 `NA` |
| **节点时间** | bridge v1.5 每帧带节点 `ts`（ntpd 后的 UTC epoch）。看板存 `ts_node` 与 `skew_s = ts_rx − ts_node` 作诊断，用于发现"节点时钟没对上"；**CSV 里永远只有 PC 时间**。时钟偏差 >1 s 时看板节点卡会显示出来，实验前应≤0.5 s |
| 布尔 | `1` / `0`，不用 `TRUE/FALSE` |
| 命名 | `alpha` / `beta`（小写，CSV 与路径通用）；重复次数 `r01` `r02` `r03` |
| **α/β 语义（唯一口径）** | **`alpha` = α = 集中式（节点只推流，PC 推理；对照组）**；**`beta` = β = 分布式 / 边缘（节点本地推理，只传结论；本系统）**。与 `01 §1.4`、`02 §4.3`、`04 §2.1` 一致。任何文档里"α=边缘、β=中心"的写法均为错误，见 [`15-矛盾排查-2026-11-23`](../共享/15-矛盾排查-2026-11-23.md) |
| **报警字段** | **只允许 `buzzer_level` + `pattern_ms`；禁止 `freq_hz`、`tone`、`音调`** —— 蜂鸣器为有源件，`buzzTask()` 用 `digitalWrite` 打节奏，没有频率这个量 |
| 事件排序 | 事件表按 `ts` 单调递增；**不按到达顺序**（补发/重放会乱序） |
| **bridge 版本绑定** | 本轮数据只认 **`duo_bridge_v1_5.py`**。v1.5 相对 v1.4 改了数据形态（env 数值化、心跳 5→10 s、`@C`/`@D` 字段名、新增 heartbeat 帧），**v1.4 及更早采集的 exp1 数据不得与 v1.5 混算**；凡 `arch=beta` 的 run，`note` 必须写 `#bridge=v1.5`。切到 v1.5 之前采的带宽数据作废，需重测（见 §2 与 `04 §2.4`） |

---

## 1. 目录结构、权限与主机

```
D/
├─ 契约3-实验数据CSV-schema-v1.1.md      # 本文件：字段 / 单位 / 校验的唯一权威
├─ 契约3-签字页.md                       # 冻结签字（出方 D + 用方 A/B/C）
├─ 实验记录表-v1.2.md                    # 现场纸笔版，与本文档同口径
├─ 04-实验设计.md ｜ 11-D岗-数据与实验.md # 方法与岗位作业书
├─ dashboard/                            # PC 看板（D2 骨架 → D3 三页 mock → D6 接真流）
│  ├─ app.py        mock_feed.py         # POST /ingest + GET /api/state；--mock 喂假数据
│  ├─ templates/index.html  static/      # 节点状态 / 实时曲线 / 报警时间线
│  ├─ screenshots/                       # D3 验收截图 4 张
│  └─ README.md                          # 起法、接口表、等级对照
├─ data/
│  ├─ raw/                               # 原始层：只读，禁止人工修改
│  │  ├─ exp1/<run_id>/                  # report.jsonl（每条报文）netdev.csv（5 s）cpu.csv
│  │  ├─ exp2/<run_id>/                  # passes.csv（人次级）video.mp4（录像留证）
│  │  ├─ events/<YYYYMMDD>.csv           # 报警事件流（§6）；看板每次落盘整表按 ts 重排
│  │  ├─ env/<node>_<YYYYMMDD>.jsonl     # 环境帧原始 JSON，一行一帧，只增不改（§6.2 不落事件表的那部分留在这里）
│  │  └─ exp3/
│  ├─ mock/                              # 假数据专用（--mock 与 mock_feed.py 默认写这里，**不污染 raw/**）
│  │  ├─ raw/{events,env}/               # 结构与 raw/ 同构，可整目录删除
│  │  └─ clean|exp1|exp2/
│  ├─ exp1/                              # 表格层：一次 run 一行
│  │     exp1_<arch>_n<N>_r<NN>.csv
│  │     summary_exp1.csv                # 清洗产物，画图只读这个
│  ├─ exp2/
│  │     exp2_g<GG>_r<NN>.csv
│  │     summary_exp2.csv
│  ├─ exp3/
│  └─ clean/                             # 清洗中间产物，可随时重生成
├─ figures/                              # 报告 5 张图（D11 起）
├─ tools/clean.py                        # python clean.py 一条命令重跑（D4 建）
└─ handoff/D.md                          # 每日交接卡（≤300 字）
```

> 数据根目录是 **`D/data/`**（不是全局 `data/`）；看板 `app.py --data <路径>` 可指到别处，默认 `D/data`。命名里的 `<GG>`/`<NN>` 一律两位补零。`mock` 走 `data/mock/`（`--mock` 自动切换，`mock_feed.py` 也默认写那里），**假数据永不进 `raw/`**。

| 层 | 权限 | 谁能改 |
|---|---|---|
| `raw/` | **只读** | 只有采集程序写；任何人不得编辑，改了就作废 |
| `exp1/`、`exp2/`、`exp3/` | 结构性 | D 写入；他人只读 |
| `mock/` | 可整目录删除 | 假数据，D3/D6 演示用；结构与 `raw/` 同构 |
| `clean/` | 可删可重建 | 脚本产物，不手改 |
| `summary_*.csv` | 脚本生成 | 只由 `clean.py` 生成，不手改 |

### 1.1 主机与端口（D-02 决策）

| 角色 | 地址 | 说明 |
|---|---|---|
| 节点 A（`milky-a`） | `192.168.5.9` | 节点状态页显示 `milky-a` + `192.168.5.9` |
| 节点 B（`milky-b`） | `192.168.5.10` | 同上 |
| 扩展位 C/D | `.11` / `.12` | 未接入时写 `NA` |
| PC 看板 | `192.168.5.20`（**暂记，待实测**） | 监听 `0.0.0.0:8000`，不能写 `127.0.0.1` |
| 桥接推送 | `http://192.168.5.20:8000/ingest` | 契约地址；**但 `duo_bridge_v1_5.py` 的默认值是 `http://192.168.5.5:8000/ingest`（`.5`），与本节不符**。上机必须显式传环境变量，例：`DASH_URL=http://192.168.5.20:8000/ingest NODE=milky-a python3 duo_bridge_v1_5.py`（`NODE` 取值按契约 5 的 `milky-a…milky-d`）。已请 B 把默认值改回 `.20`（见 `2026-11-26-口径修正与契约4答复.md` §六） |
| 心跳 / 数据帧 | 节点上行 `@E`：**2 s / 帧**（固件固定，见 `UNO_Node.ino` 注释"环境帧，2s"）；bridge 每 **10 s** 发一次 `@Q` 保活拉帧 | 看板 **6 s**（3 帧）无新 `@E` 判"链路异常"，**30 s** 判"离线"（旧口径"1 s/帧、3 s 超时"与固件实现不符，已作废） |

> PC 实测 IP 若不是 `.20`，**要么路由器绑成 `.20`，要么改 `duo_bridge.py` 的 `SERVER`**，二选一，不许两边都不动。实测结果回报 A 更新 `13`。
### 1.2 本机跑法（两个窗口 · A 复核第 5 条）

```
cd D                                          # app.py 在 D 根（旧 dashboard/ 已取消）
python app.py --port 8000                     # 窗口 1：0.0.0.0:8000 收帧 + 三页面（默认数据根 D/data）
python mock_feed.py                           # 窗口 2：假数据 POST 到 127.0.0.1:8000
```

| 项 | 口径 |
|---|---|
| 监听 | `0.0.0.0:8000`（写 `127.0.0.1` 本地 curl 通、板子推不进来） |
| 页面 | `http://127.0.0.1:8000/?tab=nodes`（节点状态）/ `?tab=curves`（实时曲线，`&sub=env|link`）/ `?tab=events`（报警时间线） |
| 一步跑 | `python app.py --mock` = 收帧 + 内置假数据；**但落盘自动切到 `data/mock/`**，不污染 `raw/` |
| 真流 | `DASH_URL=http://192.168.5.20:8000/ingest NODE=milky-a python3 duo_bridge_v1_5.py`（`DASH_URL` 必须显式传，v1.5 默认是 `.5`；`NODE` 取 `milky-a…milky-d`） |
| 监听判定 | 6 s 无新 `@E` = 链路异常（黄）；30 s = 离线（灰）；两者都来自"最后一帧到达时刻"，不看 `@Q` |
| 落盘 | 事件 `data/raw/events/<YYYYMMDD>.csv`（7 列、按 `ts` 升序）；环境 `data/raw/env/<node>_<YYYYMMDD>.jsonl`（原始 JSON，一行一帧） |

> 只听真流时**不要**并跑 mock；实验采集期间 `raw/` 里出现 `mock` 字样即作废该段数据。

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
| `frames_expected` | int | 帧 | **期望帧数** = `duration_s / hb_interval_s`，其中 **`hb_interval_s = 2`**（固件 `@E` 2 s 一帧，见契约 1 §5）。按 1 s 算会把 `loss_pct` 虚高约一倍 |
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
| `note` | str | — | 异常、时长偏差、设备更换；**用 v1.5 跑的 β 组必须写 `#bridge=v1.5`** |

> **口径提示**：`lat_e2e_ms` 与 `lat_pipe_ms` 不是同一段，误差分别标注，不得互相替代。
> **`hb_interval_s` 固定 2 s**（固件 `sendEnv()` 每 2 s 一帧），不由实测间隔反推；`duration_s` 变化时 `frames_expected` 跟着变。
> **延迟只写实测值**：本项目不再有"33 ms""±17 ms"这类固定延迟口径（`04 §2.4` 的 ±17 ms 已作废）；每 run 的 `lat_e2e_ms` 是当次回放计数结果，误差按 `lat_e2e_err_ms = ±(time_res_ms + 1000/rec_fps/2)` 逐次算，`node_fps`、`rec_fps` 必须实测并填进记录表。

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
| `truth_total` | int | 人 | **真值合计**（= `tp + fn`）。真值默认取 **U 型光电传感器**（遮挡即 1 人次，与视觉物理独立）；光电未接通时降级为**人工逐人次真值**，并在 `note` 标 `#manual_truth` |
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
>
> ⚠️ **真值只有一个口径**：**U 型光电为主**（`04 §3.2`、`11 §四` 已同步改成这个说法）。光电确实接不通时，才降级为人工逐人次记录，且该组 `note` 必须写 `#manual_truth`；**同一组内不得光电与人工混用**，汇总表按 `note` 分组统计，报告里注明哪几组是人工真值。答辩若问"真值可靠吗"，答案只能是"光电物理通道 + 逐人次录像复核"，不能是"我们数了一遍"。

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

## 6. 事件表：`raw/events/<YYYYMMDD>.csv`（D-01 决策）

报警与心跳的统一事件流，看板"报警时间线"页与 §6 汇总都读它。

| 列 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `ts` | float | s | PC 时钟，**表按此列单调递增** |
| `node_id` | enum | — | `milky-a` / `milky-b` / `milky-c` / `milky-d`（**契约 5 §一 唯一取值**）。旧写法 `nodeA…nodeD` 只允许作为**输入别名**：看板收帧时归一成上表值再落盘，事件表里不得出现 `nodeA` |
| `src` | enum | — | `SMOKE` / `FLAME` / `TEMP` / `HUM` / `DOOR` / `CARD` / `HEARTBEAT`（`HUM`、`DOOR` 当前固件不产生事件行——门磁只发 `@D`，见 §6.2；枚举保留，不得自行扩展） |
| `event` | enum | — | `alarm` / `clear` / `deny` / `heartbeat` |
| `buzzer_level` | enum | — | `hazard` / `caution` / `deny` / `NA`（`heartbeat` 无蜂鸣写 `NA`） |
| `pattern_ms` | str | ms | `1000/500`、`150/2850`、`80x2/400`；与 `buzzer_level` 一一对应，无蜂鸣写 `NA` |
| `note` | str | — | 自由备注，可用 `#replay` 标补发 |

### 6.1 三级语义与节奏（写死，填表不用问）

| `buzzer_level` | 响 | 停 | 周期 | 触发场景（以固件 `judge()` 实际实现为准） | `pattern_ms` 写法 |
|---|---|---|---|---|---|
| `hazard` | 1000 ms | 500 ms | 1500 ms | **烟雾 ≥ 200**（`SMOKE_L2`）/ **火焰 ≥ 250**（`FLAME_L2`）/ **温度 ≥ 45.0 ℃**（`TEMP_L2`） | `1000/500` |
| `caution` | 150 ms | 2850 ms | 3000 ms | **烟雾 ≥ 120**（`SMOKE_L1`）/ **火焰 ≥ 150**（`FLAME_L1`）；温度不产生注意级 | `150/2850` |
| `deny` | 80 ms × 2 | 400 ms | — | 刷卡失败 / 无权限（`@R` 校验不通过） | `80x2/400` |

> **触发场景只认上表**（`UNO_Node.ino` v1.2 `judge()` L186-190 + `judgeAndAct()` L205-218）：
> - **温度 ≥ 45 ℃ 直接进 hazard**，没有"温度注意级"；注意级只有烟雾/火焰的 L1。
> - **"门磁强开"不参与判级**：干簧管只走 `doorTask()` 发 `@D,0|1`，`judge()` 不读它。门磁不进事件表，看板只在"节点状态"页显示开/关（见 §6.2）。
> - **"陌生人靠近""湿度越界"固件未实现**：`HUM` 目前没有任何帧会产生，`DHT11` 只报温湿度数值，不判级。这两类场景**不许写进事件表、不许写进报告**。
> - `@A` 的 `src` 优先级：`SMOKE` > `FLAME` > `TEMP`（同时越限时报第一个）；`lv=0` 回落时发 `@A,0,NONE`。

**三条硬规则**
1. **禁止 `freq_hz` / `tone`**：固件 `buzzTask()` 用 `digitalWrite` 打节奏，没有频率量；写了只会产生空列或假数据。质量校验第 13 条直接拒收。
2. **按 `ts` 排序**，不按到达顺序（补发/重放会乱序），第 14 条校验。
3. **`deny` 不计人次**，只作为事件进入本表与 `exp2.deny_evt`。

### 6.2 落表映射（帧 → 事件表 → 看板）

看板实现见 [`app.py`](app.py)（`Store.ingest()` + 落盘函数；11-26 起在 D 根，旧 `dashboard/` 已取消）。下表是"哪条帧写哪一行"的唯一口径，D6 接真流时**只换数据来源，不改这张表**。

| 上行帧 | 进事件表 | `event` | `buzzer_level` | `pattern_ms` | 要点 |
|---|---|---|---|---|---|
| `@A,2,<SMOKE\|FLAME\|TEMP>` | 是 | `alarm` | `hazard` | `1000/500` | 仅等级**变化**时发，不是每帧 |
| `@A,1,<SMOKE\|FLAME>` | 是 | `alarm` | `caution` | `150/2850` | 同上 |
| `@A,0,NONE` | 是 | `clear` | `NA` | `NA` | `src` **继承上一条 alarm 的 `src`**（事件表 `src` 枚举不含 `NONE`），`note=#clear` |
| `@R,<UID>` 校验失败 | 是 | `deny` | `deny` | `80x2/400` | `src=CARD`，`note=uid=<UID>`；成功刷卡**不落表**。v1.5 的 JSON 是 `{"type":"rfid","uid":..,"ok":false,"buzzer_level":"deny","pattern_ms":"80/120"}`——其中 `pattern_ms:"80/120"` 与 D-01 的节奏 `80x2/400` **不符**，看板一律按 `80x2/400` 落表并计数告警，已请 B 改正 |
| `{"type":"heartbeat",...}` | 否 | — | — | — | v1.5 每 10 s 一条，带 `link`（`boot`/`ok`/`dead`）、`dropped`（队列丢弃）、`failed`（POST 失败）。看板只用它判链路：`link=dead` 直接把节点标"链路异常"，**不写事件行**（事件表 `event` 枚举只有 alarm/clear/deny/heartbeat，这里不占用）。`dropped`/`failed` 只作诊断，**不进 `loss_pct`**（那是 `@E` 帧级的丢包） |
| `@C,<n>` | 否 | — | — | — | 只更新看板计数与 exp2；**计数回退 = 节点重启**，用于差分，不写事件行 |
| `@D,0\|1` | 否 | — | — | — | 门磁只在"节点状态"页显示开/关；`event` 枚举**没有** open/close，硬写会触发第 13 条校验 |
| `@E,...`（2 s） | 否 | — | — | — | 只进曲线与完整性统计（`frames_rx`） |
| `@Q`（10 s 保活） | 否 | — | — | — | 心跳不写行，否则事件表被保活帧淹没；`event=heartbeat` 保留待用 |

**两条落地约定**
1. **只在等级变化时落一行**：同一等级持续期间不重复写；`clear` 与 `alarm` 成对出现，便于算"报警持续时长"。
2. **落盘后整表按 `ts` 升序重写**（§8 第 14 条）；补发/重放的数据必须带 `#replay` 标记，不得插到表中间。

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

## 9. 原"待确认"五项 —— v1.1c / v1.1d / v1.1e 定稿

| # | 原问题 | 定稿（冻结，按此执行） | 影响谁 |
|---|---|---|---|
| 1 | `cpu_scope` 默认值 | **`all_cores`**（对齐 Windows 任务管理器口径）；取不到写 `NA`，不许留空 | D 填表、`clean.py` |
| 2 | `lat_pipe_ms` 是否只测 β | **只测 β**；α 组写 `NA`，`note` 写"α 无节点结论步骤" | D、图 3 |
| 3 | `mean_conf_all` 是否保留 | **保留**，仅辅助列，不进图、不进结论文字 | D |
| 4 | `note` 固定标签 | `#merge` `#recalib` `#swap` `#count_only` `#replay` + **新增 `#manual_truth`**（该组用人工真值）+ **新增 `#bridge=v1.5`**（该 run 用 v1.5 采集，β 组必写）；标签之外用自然语言，不再造新 `#` | 全员 |
| 5 | PC 实测 IP 是否 `.20` | **仍待实测**（D-02 遗留，D6 接真流前必须定）：不是 `.20` 就二选一——路由器绑定 `.20`，或改 `duo_bridge.py` 的 `SERVER`；结果追加到 `../A/13-决策记录-有源蜂鸣器与A板IP.md` | A、B、D |

## 10. 冻结签字

| 岗 | 确认内容（可验证的一句话） | 签字 | 日期 |
|---|---|---|---|
| **D**（出方） | 契约 3 v1.1e 冻结：§2 列定义与 §8 十四条校验按本文件实现，`clean.py` 逐条检查；事件表只写 §6.2 映射内的行；v1.1d 只补语义（`ts_rx`/节点时间/`#bridge=v1.5`/heartbeat），列名与量纲未动 | ____ | 11-26 |
| **A**（用方 / 拍板） | 已按 v1.1b 复核并确认两处修改（`frames_expected` 按 2 s、§6.1 触发场景以 `judge()` 为准）；全文不再出现"延迟 33 ms / ±17 ms"固定值 | ____ | 11-25 |
| **B**（用方） | 交 `duo_bridge_v1_5.py`：`@A` 透传与 `@R` 失败分支按 §6.2 产生 `alarm/clear/deny`；`env` 不回传 `freq_hz`；**待办：删掉或改正 `pattern_ms:"80/120"`（应为 `80x2/400`）、把默认 `DASH_URL` 改回 `.20`** | ____ | 11-26 |
| **C**（用方） | `judge()` 等级与 §6.1 一致（烟雾/火焰 L1/L2 + 温度 ≥45 ℃）；门磁只发 `@D` 不参与判级 | ____ | 11-__ |

> 未签字 = 仍可改；签字后改动走 [`../共享/契约冻结与签字规则.md`](../共享/契约冻结与签字规则.md) §六 五步，并由 A 重新签字。
> 独立签字页（随决策记录一起提交）：[`契约3-签字页.md`](契约3-签字页.md)。







