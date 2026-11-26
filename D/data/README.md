# D/data · 数据根

> 契约出处：[`../契约3-实验数据CSV-schema-v1.1.md`](../契约3-实验数据CSV-schema-v1.1.md) §1（v1.1c）。
> 看板默认读这里：`python app.py --data ../data`；mock 演示用 `--data ../data/mock`，不污染本目录。

## 目录与写权限

| 路径 | 内容 | 谁能写 |
|---|---|---|
| `raw/exp1/<run_id>/` | `report.jsonl`（每条 UDP 报文）、`netdev.csv`（带宽采样）、`cpu.csv` | 采集脚本；**人不得编辑** |
| `raw/exp2/<run_id>/` | `passes.csv`（人次级明细）、`video.mp4` | 同上 |
| `raw/exp3/<run_id>/` | 防尾随 10 次/场景的原始记录 | 同上 |
| `raw/events/<YYYYMMDD>.csv` | 看板落的事件流（契约 3 §6 六列） | 看板 `app.py` 追加 |
| `raw/env/<YYYYMMDD>.jsonl` | 每帧 `@E` 原始值（看板落盘） | 看板 `app.py` 追加 |
| `exp1/ exp2/ exp3/` | 表格层：一次 run 一个 CSV + `summary_*.csv` | D 写入（汇总只由 `clean.py` 生成） |
| `clean/` | 清洗中间产物，可删可重生成 | `tools/clean.py` |

## 命名

- 实验一：`YYYYMMDD-<arch>-n<N>-r<NN>`（`arch` 小写 `alpha`/`beta`，如 `20261124-beta-n1-r01`）。
- 实验二组级：`exp2_g<GG>_r<NN>.csv`；人次级：`raw/exp2/<run_id>/passes.csv`。
- 实验三：`exp3_s<SS>_r<NN>.csv`。

## 纪律

1. `raw/` 只增不改；每天收工 `cp -r data data-$(date +%m%d)` 备份并记哈希。
2. 缺失写 `NA`，不写 `0`、不写空、不写 `-`。
3. 每个实验目录放一行 `README.txt`：`run_id | 日期 | 谁采的 | 配置（镜像/模型/IP）| 异常`。
4. `summary_*.csv` 与报告图只从 `clean.py` 出，不手改。

> 现状（2026-11-26）：目录树已建，**还没有真数据**；看板 mock 数据写在 `data/mock/`，验收前清掉即可。`tools/clean.py` 待 D6 交付（14 条校验）。
