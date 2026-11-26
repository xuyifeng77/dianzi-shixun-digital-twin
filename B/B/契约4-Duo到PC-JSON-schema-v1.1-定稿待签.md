# 契约 4 · Duo → PC JSON Schema **v1.1（定稿待签）**

> 出方：B（视觉节点）｜用方：D（数据与实验）
> 依据：本文件已并入 **D 2026-11-26 的《契约 4 三问答复 + 6 条》**。
> 状态：**定稿待签** —— 签字前需 D 确认 §五 的三处。
> 传输：`HTTP POST http://<PC_IP>:8000/ingest`，`Content-Type: application/json`，一行一个 JSON 对象。

---

## 一、通用字段（每条消息都有）

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `type` | string | — | 枚举值，见 §二 |
| `node` | string | — | **只允许** `nodeA` / `nodeB` / `nodeC` / `nodeD` |
| `ts` | float | s | 节点本地时间，UTC Unix epoch，毫秒精度（见 §五-①） |

**`node` 的硬约束**：取值不在上述四个之内，**bridge 直接拒绝启动**（fail-fast）。
理由：D 的看板对未知 `node` 只记日志不落卡 —— 静默丢数据比报错更糟。

> ⚠️ **`node` ≠ hostname**：hostname 是设备名（`milkv-a`/`milkv-b`），`node` 是协议标识（`nodeA`/`nodeB`）。
> 两者由不同机制维护，**不要互相推导**。

---

## 二、消息类型（7 种，枚举固定）

### 2.1 `env` —— 环境帧（周期 2 s，由 UNO 决定）

```json
{"type":"env","node":"nodeA","ts":1795614322.9,
 "t":24.5,"h":55.0,"smoke":120,"flame":180,"light":90,"sound":30,"rst":0}
```

| 字段 | 类型 | 转换规则 |
|---|---|---|
| `t` `h` | **float** \| null | 保留 **1 位小数** |
| `smoke` `flame` `light` `sound` | **int** \| null | 四舍五入取整 |
| `rst` | int \| null | 可选；`@E` 第 8 字段（复位原因），无则省略 |

**缺失值规则（硬性）**：

| 源数据 | 上报 | 含义 |
|---|---|---|
| 正常数值 | 数字 | 测到了 |
| `nan`（固件读失败打的字符串） | **`null`** | 没测到 |
| `inf` / `-inf` | **`null`** | 异常值 |
| 空串 / `-` / 非数字 | **`null`** | 没测到 |
| —— | **绝不允许写 `0`** | `0` 是"测得 0"，与"没测"语义不同 |

> 📌 **为什么专门强调 `nan`**：DHT11 / DS18B20 读失败时，Arduino 的 `Serial.print(NAN)` 输出字符串 `"nan"`。
> 若直接 `float("nan")`：① 整列均值变 NaN；② JSON 里 `NaN` 是**非法字面量**，严格解析器会报错；③ 不报错但数据静默失真。

### 2.2 `alarm` —— 分级报警（等级变化时）

```json
{"type":"alarm","node":"nodeA","ts":1795614322.9,"args":[1,"SMOKE"]}
```

| 字段 | 约束 |
|---|---|
| `args[0]` | `lv ∈ {0,1,2}`（0 正常 / 1 注意 / 2 危险），越界归 0 |
| `args[1]` | `src ∈ {NONE, SMOKE, FLAME, TEMP}`，未知归 `NONE` |

> ⚠️ **该枚举缺"刷卡拒绝"**：`B-通知 §五` 与 `D-通知 §一` 都要求有 `deny`。
> 现方案：拒绝事件走 §2.6 `rfid` + `buzzer_level:"deny"`，不进 `alarm`。
> 若要并入 `alarm`，请 D 在 `src` 枚举里增加 `RFID`（见 §五-②）。

### 2.3 `count` —— 光电人次（变化时）

```json
{"type":"count","node":"nodeA","ts":1795614322.9,"passes":12}
```

### 2.4 `door` —— 门磁（变化时）

```json
{"type":"door","node":"nodeA","ts":1795614322.9,"open":1}
```

| 字段 | 说明 |
|---|---|
| `open` | 1=开 0=关；`null` 表示电平未知 |

> 按 C 的确认：门磁**只发 `@D`，不参与报警判级**，故本消息仅为状态事件。

### 2.5 `infer` —— 视觉推理结论（周期 2 s，β 架构）

```json
{"type":"infer","node":"nodeA","ts":1795614322.9,"count":1,"age_s":0.2}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `count` | int \| null | 画面内人数。**`null` = 自上电以来从未检测到人脸**，≠ 0 |
| `age_s` | float \| null | 距最近一次检测输出的秒数；越大越陈旧 |

**落库口径**（D 侧）：`null` → CSV 记 `NA`；看板显示 `—`（不显示 `0`）。
**已知约束**：① 上电后约 50 s 预热期只发 `null`；② 必须先出现过一张脸才会持续出 `0`。

### 2.6 `rfid` —— 刷卡事件

```json
{"type":"rfid","node":"nodeA","ts":1795614322.9,"uid":"A1B2C3D4","ok":false,
 "buzzer_level":"deny","pattern_ms":"80/120"}
```

| 字段 | 说明 |
|---|---|
| `uid` | 大写十六进制 UID |
| `ok` | `true` 授权 / `false` 拒绝 |
| `buzzer_level` `pattern_ms` | **仅拒绝时出现**，表示 UNO 侧的拒绝音 |

### 2.7 `heartbeat` —— 心跳（周期 **10 s**，先于数据）

```json
{"type":"heartbeat","node":"nodeA","ts":1795614322.9,"link":"ok","dropped":0,"failed":3}
```

| 字段 | 说明 |
|---|---|
| `link` | `boot` / `ok` / `dead`：串口链路状态 |
| `dropped` | 上报队列溢出丢弃帧数（数据完整性证据） |
| `failed` | HTTP 发送失败累计次数 |

> `link`/`dropped`/`failed` 是**附加字段**（D 只要求 `type`+`node`），若 D 要求严格最小集，删这三行即可。

---

## 三、频率与超时

| 项 | 值 |
|---|---|
| `infer` | 2 s |
| `env` | 2 s |
| `heartbeat` | **10 s** |
| HTTP 超时 | 2 s |
| 发送失败 | 不阻塞串口；累加 `failed`，继续下一条 |
| 队列溢出 | 丢最旧帧，累加 `dropped` |
| 串口断链 | 35 s 无回执 → `link:"dead"`，仅标记与打印，**不影响本地推理** |
| 看板侧判定 | 6 s 无新 `env` 判异常，30 s 判离线（D 侧实现） |

---

## 四、与旧版差异（v1.0 草案 → v1.1 定稿）

| 项 | v1.0 草案 | v1.1 定稿 |
|---|---|---|
| `env` 数值 | 字符串 | **数字**（float/int），缺测 `null` |
| 缺失/`nan` | 未规定 | **显式规定 `nan`/`inf`/空 → `null`** |
| `alarm` | 扁平 `level/src/buzzer_level/pattern_ms` | **`args:[lv,src]`** |
| `heartbeat` | 5 s | **10 s** |
| `node` | 未校验 | **白名单校验，写错拒绝启动** |
| `@E` 字段数 | 6/7 | 兼容 **8（含 `rst`）** |
| `rfid` 拒绝 | 有 `buzzer_level` | 保留（因 `alarm` 枚举无 RFID） |

---

## 五、签字前需 D 确认的三处

| # | 争议点 | B 的立场 | 若 D 不同意，改法 |
|---|---|---|---|
| ① | `ts` 是"PC 侧时间" | **不可行**：bridge 跑在 Duo 上，拿不到 PC 时钟。现方案 `ts`=节点 NTP 时间；建议 PC 侧另记到达时间 `ts_rx` 写 CSV | bridge 增加一次"向 PC 取时间"的请求（增加故障点，不推荐） |
| ② | `alarm` 枚举缺 `RFID` | 拒绝事件目前走 `rfid` 消息 | D 在 `src` 枚举加 `RFID`，B 改 1 行 |
| ③ | `heartbeat` 附加字段 | `link/dropped/failed` 对数据完整性有用 | D 要求最小集则 B 删 3 行 |

---

## 六、附：真实样例

`samples/ingest_2026-11-25.jsonl` —— 208 条实测（`infer` 类型，nodeA 136 + nodeB 72）。
其余 6 类需 UNO / 光电接入后补采（D5 之后）。

---

## 七、变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 草案 | 2026-11-26 | B 首版（env 为字符串、alarm 扁平、heartbeat 5 s） |
| **v1.1 定稿** | 2026-11-26 | 并入 D 的三问 + 6 条；新增 `nan→null`；`alarm` 改 `args`；heartbeat 10 s；`@E` 兼容 8 字段；`node` 白名单 |
