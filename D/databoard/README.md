# PC 看板（D3 mock 版）

> 验收物：节点状态 / 实时曲线 / 报警时间线 三页 + 4 张截图 + 交接卡。
> 现状：**D3 用 mock 数据跑通；`/ingest` 已按 B 的 `duo_bridge_v1_5.py` 收帧形状实测通过（heartbeat / env / alarm / count / door / rfid / infer）**。D6 接真流不需要改页面，只把喂数方从 `mock_feed.py` 换成 `duo_bridge_v1_5.py`。

## 一、怎么起（两个窗口 · A 复核第 5 条）

只用标准库，不用 `pip install`。**推荐两个窗口**，这样假数据和真流不会混：

```bash
cd D/dashboard
# 窗口 1：看板本体（0.0.0.0:8000 收帧 + 三页面）
python app.py --data ../data --port 8000

# 窗口 2：假数据（POST 到 127.0.0.1:8000，可单独跑、可 Ctrl-C 停）
python mock_feed.py
```

只想一条命令演示时：`python app.py --mock`（等价于窗口 1 + 内置假数据），
**但它会把落盘切到 `data/mock/`，不污染 `raw/`**。

- `--host 0.0.0.0`（默认）：**板子才推得进来**，别改成 127.0.0.1。
- `--port 8000`：与契约 3 §1.1 一致；换端口要同步改 `DASH_URL`。
- `--data ../data`：数据根，默认 `D/data`；`--mock` 时自动变成 `D/data/mock`。
- 不加 `--mock`：只起服务不造假数据，页面显示"真实节点"，等真帧。
- `mock_feed.py --host/--port/--span/--no-backfill`：可指到别的板子/端口、只发实时帧不回填。
- Windows 首次运行要放行防火墙 TCP 8000，否则双板 POST 不进来。

### 落盘目录（v1.1e 起）

| 内容 | 路径 |
|---|---|
| 事件表（7 列，按 `ts` 升序） | `data/raw/events/<YYYYMMDD>.csv` |
| 环境帧原始 JSON（一行一帧，只增不改） | `data/raw/env/<node>_<YYYYMMDD>.jsonl` |
| 假数据（可整目录删） | `data/mock/raw/{events,env}/…` |

> 实验采集期间 `raw/` 里出现 mock 痕迹即作废该段数据；`--mock` 已强制写到 `data/mock/`。

## 二、三个页面

| 页面 | URL | 内容 |
|---|---|---|
| 节点状态 | `/?tab=nodes` | 每节点一卡：在线点、等级（正常/注意/危险）、节奏 `pattern_ms`、最后心跳、报警来源、门磁、本组人次、帧完整性、`rst`/重启次数、**时钟偏差 / 丢帧**（v1.5 新增） |
| 实时曲线 | `/?tab=curves&sub=env` | 环境三路：温度 ℃ / 烟雾 0–255 / 火焰 0–255，带 L1/L2 阈值虚线 |
|  | `/?tab=curves&sub=link` | 链路三路：端到端延迟 ms / 上行带宽 B/s / PC CPU %（β 口径，模拟"只传结论"） |
| 报警时间线 | `/?tab=events` | 事件表 7 列，按 `ts` 倒序展示、落盘按 `ts` 升序；hazard/caution/deny 左侧色条 |

顶部总览条固定显示：在线 x/y、当前报警数、今日事件数、**超时口径 6 s / 30 s**、数据来源。

## 三、接口（`/ingest` 收的是 bridge 的 JSON，不是 `@` 帧也能收）

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/ingest` | 收 Duo→PC JSON（v1.5 六类：`heartbeat` / `env` / `alarm` / `count` / `door` / `rfid`；契约 4 还有 `infer`），也收裸 ASCII 帧 `@E,...`（自测用） |
| GET | `/api/state` | 页面每秒拉一次的完整快照（节点、事件、曲线、链路） |
| GET | `/api/health` | 存活性自检，返回 `{"ok":true,...}` |

自测（异机也行，把 127.0.0.1 换成 PC 实际 IP）：

```bash
curl -X POST http://127.0.0.1:8000/ingest -d "{\"type\":\"heartbeat\",\"node\":\"nodeA\"}"
curl -X POST http://127.0.0.1:8000/ingest -d "{\"type\":\"alarm\",\"node\":\"milky-a\",\"args\":[\"2\",\"SMOKE\"]}"
curl http://127.0.0.1:8000/api/health
```

## 四、等级 → 节奏（契约 3 §6.1，写死）

| lv | `buzzer_level` | 页面字样 | `pattern_ms` |
|---|---|---|---|
| 2 | `hazard` | 危险 | `1000/500` |
| 1 | `caution` | 注意 | `150/2850` |
| 0 | `NA` + `event=clear` | 正常 | `NA` |
| — | `deny`（刷卡失败） | 拒绝 | `80x2/400` |

**不显示频率**（`freq_hz`/`tone`）：有源蜂鸣器只有节奏，没有频率量。

## 五、落表规则（详见契约 3 §6.2）

- 事件写 `data/raw/events/<YYYYMMDD>.csv`，7 列，整表按 `ts` 升序重排（第 14 条）。环境帧另写 `data/raw/env/<node>_<YYYYMMDD>.jsonl`（原始证据，只增不改）。
- `@A,0,NONE` 解除 → `event=clear`，`src` 继承上一条 alarm 的来源（事件表枚举没有 `NONE`）。
- 门磁只进"节点状态"页，不进事件表；`deny` 不计人次。
- `@C` 累计值回退 → 判节点重启，本组人次重计，标 `#count_reset`。
- **心跳不落行**：2 s 帧龄在内存判 6 s 异常 / 30 s 离线，落表只落变化，避免一天几千行。v1.5 的 `heartbeat` 帧带 `link=dead` 时直接把节点标"链路异常"（即使 30 s 内还有心跳）。`dropped`/`failed` 只作诊断，**不算进 `loss_pct`**。

## 六、文件

| 文件 | 作用 |
|---|---|
| `app.py` | 纯标准库 `ThreadingHTTPServer`：`/`、`/api/state`、`/api/health`、`/static/*`、`/ingest`；事件落盘 |
| `mock_feed.py` | 假数据：先回填 5 min 剧本（危险→解除→注意→解除→拒绝→门磁→人次→重启），再每 2 s 一帧；env 值故意用**字符串**（复现 v1.4 行为，正好验证新旧两种都能收） |
| `templates/index.html` | 单页骨架：总览条 + 三页签 + 6 个 canvas + 事件表 |
| `static/style.css` | 深色主题 |
| `static/dash.js` | 无框架、无 CDN、断网可用；每秒 fetch `/api/state`；canvas 自绘 |
| `screenshots/` | 4 张截图（`01-节点状态.png`、`02-实时曲线-环境.png`、`03-实时曲线-链路.png`、`04-报警时间线.png`） |

## 七、D6 接真流只改三处

1. 板子侧：`duo_bridge_v1_5.py` 的 `DASH_URL` **必须显式传**——它默认是 `http://192.168.5.5:8000/ingest`（`.5`，与契约 `.20` 不符）：`DASH_URL=http://<PC实测IP>:8000/ingest NODE=nodeA python3 duo_bridge_v1_5.py`。
2. 页面侧：不加 `--mock` 启动，确认"数据来源"变成"真实节点"。
3. 字段侧：**v1.5 已按 D 的答复落地**——`node` 用 `milky-a`/`milky-b`（旧名 `nodeA`/`nodeB` 是输入别名，`norm_node()` 归一后落盘）；`env` 数值由 bridge 转数字（`num()` 仍兼容字符串）；缺测用 `null`（`count:null` 表示"从未检测到人"，页面显示 `—`），`num()` 已把 `""`/`null`/`NA`/`-`/`nan`/`inf` 都当缺失。

## 八、v1.5 收帧形状（`duo_bridge_v1_5.py`，实测通过）

| `type` | 字段 | 看板怎么用 |
|---|---|---|
| `heartbeat` | `node` `ts` `link`(`boot`/`ok`/`dead`) `dropped` `failed` | 判链路；`link=dead` 标"链路异常"；**不落事件表** |
| `env` | `t` `h` `smoke` `flame` `light` `sound` `rst`，数字或 `null` | 曲线三路 + `rst` 判重启 + 帧完整性 |
| `alarm` | `args: [lv, src]`（`lv` 0/1/2，`src` 由 bridge 归一到 `SMOKE`/`FLAME`/`TEMP`/`NONE`） | 等级变化才落事件；`lv=0` 落 `clear` |
| `count` | `passes`（累计人次，uint16 上电清零） | 差分成本组人次；回退判重启 |
| `door` | `open` 0/1 | 只更新状态页，不落事件表 |
| `rfid` | `uid` `ok`；失败时附 `buzzer_level:"deny"` `pattern_ms:"80/120"` | `ok=false` 落 `deny`；**`pattern_ms` 一律按契约 `80x2/400` 落表**，与上报不符时计 `pattern_warn` |
| `infer` | 契约 4 新增（B 已出 208 条真样本，只有这一类） | 暂存内存，D5 接契约 4 时再定落表 |

> `ts` 用**看板收到时刻** `ts_rx`；节点 `ts` 只存 `ts_node`/`skew_s` 作诊断（契约 3 §0 v1.1d）。

## 九、节点命名（契约 5，v1.1f 起）

| 项 | 值 |
|---|---|
| 合法 hostname | `milky-a` `.9` / `milky-b` `.10` / `milky-c` `.11` / `milky-d` `.12` |
| 旧名 | `nodeA…nodeD`、`node_a…node_d` —— **只作输入别名**，`norm_node()` 归一后打 `[warn] alias nodeA -> milky-a` |
| 未知名 | 不静默丢：打 `[warn] unknown node`，按原名落盘（便于发现 B 配错） |
| 显示 | 节点卡显示 `milky-a` + `192.168.5.9`；事件表 `node_id` 只写 `milky-*` |
| 注意 | `milkv` 是 ssh 密码、`Milk-V` 是型号，**都不是 hostname**；出现 `nodeA` 落盘即为口径错误 |