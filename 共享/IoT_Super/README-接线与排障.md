# 创乐博 UNO R3 IOT SUPER · 物联网最小系统

> 独立可跑项目：**温湿度 + 光照上云 · 超温自动散热 · 本地声光报警 · 串口远程控制**
> 与 [`../../A/03-Arduino端设计.md`](../../A/03-Arduino端设计.md) 的整机固件是**两套独立程序**：ESP-01 软串口必须占 D2/D3，二者引脚冲突，不能同时烧录。

## 1 数据链路

```
DHT11(D7) ┐
光敏(A0)  ├→ UNO R3 ─软串口 D2/D3→ ESP-01(AT固件) ─WiFi→ api.thingspeak.com
继电器(D6)┘                                              ↓
蜂鸣器(D4) / D13 状态灯 ←── 本地阈值判断              手机 / 网页曲线
```

## 2 接线表

| 模块 | 模块引脚 | 接到 UNO | 说明 |
|---|---|---|---|
| DHT11 | `+` / `OUT` / `-` | 5V / **D7** / GND | 裸件需 10kΩ 上拉到 5V；模块自带可省 |
| 光敏模块 | VCC / **AO** / GND | 5V / **A0** / GND | 用 AO 模拟量；DO 不用 |
| 继电器模块 | VCC / **IN** / GND | 5V / **D6** / GND | 低电平吸合；负载侧接套件风扇，独立 5V 供电 |
| 有源蜂鸣器 | VCC / **IN** / GND | 5V / **D4** / GND | 高电平响 |
| ESP-01 转接板 | **TXD** / **RXD** / VCC / GND | **D2** / **D3** / 5V / GND | TXD↔D2、RXD↔D3 **交叉**；转接板已含 3.3V 稳压与电平转换 |
| 板载 LED | — | D13 | 在线常亮 / 离线快闪 / 报警慢闪，免接线 |

**三条硬规矩**

1. ESP-01 工作 **3.3V、峰值约 300mA**：只能经**转接板**由 5V 供，**绝不接 UNO 的 3.3V 引脚**（仅 50mA，会无限重启）。
2. **所有模块共地**；UNO 与 ESP 的 GND 必须连在一起。
3. 继电器负载用套件风扇（配 4×AA 或 LM2596 降压独立供电）；**严禁接 220V**。

> 上传代码**无需拔 ESP 线**：下载走 D0/D1，软串口在 D2/D3，互不干扰。

## 3 软件准备（5 步）

1. **装库**：库管理器安装 `DHT sensor library`（Adafruit）+ `Adafruit Unified Sensor`。
2. **改 ESP 波特率**：ESP-01 出厂多为 115200，软串口跑不稳。用 USB-TTL 单独接模块，串口助手发一次
   `AT+UART_DEF=9600,8,1,0,0` → 回 `OK` 后永久生效（代码里 `ESP_BAUD 9600`）。
   *不想改速？把代码改成 `115200` 试，但可能丢包。*
3. **建 ThingSpeak 通道**：注册 → Channels → My Channels → New Channel，勾 4 个 Field：
   `Field1 温度 / Field2 湿度 / Field3 光照 / Field4 风扇` → Save → **API Keys 取 Write API Key**。
4. **填参数**：代码第 2 节填 WiFi 名、密码、Write Key（仅 2.4GHz，ESP-01 不支持 5G）。
5. **烧录**：开发板选 `Arduino Uno`，串口 115200，上传后开串口监视器（换行符 `NL`）。

## 4 故障排查清单

| # | 现象 | 原因 | 处理 |
|---|---|---|---|
| 1 | 串口全无输出 | 波特率/COM 口错 | 115200 + 选对 COM；上传后按一次复位 |
| 2 | 编译报 `DHT.h: No such file` | 缺库 | 装 Adafruit DHT + Unified Sensor 两个库 |
| 3 | `[ESP] 超时 AT` | 波特率不符 / TX-RX 未交叉 / 供电不足 | 先试 115200；TXD→D2、RXD→D3；换 5V/1A 电源 |
| 4 | 串口见乱码或 `ready` 后无 `OK` | 3.3V 供电跌落 | 加 100µF 电容在转接板 VCC-GND；勿用 UNO 3.3V 引脚 |
| 5 | `AT` 回 `ERROR` | 模块是 NodeMCU/透传固件，非 AT 固件 | 重刷 ESP-01S AT 固件（AT 1.7.x） |
| 6 | `CWJAP` 回 `FAIL` | SSID/密码错、5GHz、中文名 | 用纯英文 2.4GHz 热点；`AT+CWLAP` 扫网确认 |
| 7 | `CWJAP` 超时 | 信号弱 / DHCP 池满 | 靠近路由器；重启路由器 |
| 8 | `CIPSTART` 失败 | 未联网 / DNS 失败 | 先 `AT+PING="api.thingspeak.com"`；重连 WiFi |
| 9 | `CIPSEND` 无 `>` | 上次会话未关闭 | `AT+CIPCLOSE` 后重试；代码已带超时重连 |
| 10 | 上传返回失败但联网正常 | 上传间隔 <15s 被限流 | `UPLOAD_MS` 保持 ≥20000 |
| 11 | ThingSpeak 无曲线 | 用了 Read Key / 字段未勾选 | 必须用 **Write API Key**；通道勾满 4 个 Field |
| 12 | 数据零星中断 | WiFi 掉线（`+WIFI DISCONNECT`） | 代码 15s 自动重连，属正常；可加大 `UPLOAD_MS` |
| 13 | 温湿度显示 `nan` | DHT11 接触不良 / 读取过快 | 重插 D7、补上拉；读取间隔 ≥1s |
| 14 | 继电器一直吸合 | 模块是高电平触发 | 把 `LOW/HIGH` 两处互换 |
| 15 | 一开风扇 UNO 就重启 | 风扇从 UNO 5V 取电 | 改独立 5V，仅共地 |
| 16 | D13 灯一直快闪 | `online=false`，说明没连上 | 看串口 `[WiFi]` 日志，回到第 3~8 条 |

## 5 验收标准

- [ ] 串口每 2s 打印 `T=… H=… L=… 风扇=…`，数值合理
- [ ] 串口每 20s 打印 `[上云] OK`
- [ ] ThingSpeak 通道 4 条曲线正常刷出
- [ ] 温度 ≥30℃ 继电器吸合、≤28℃ 释放（回差无抖动）
- [ ] 温度 ≥35℃ 蜂鸣器长鸣，发 `m` 可静音；`1/0/a` 手动控制生效
