# 交接卡 · D（数据与实验）

> 2026-11-26（D3 收口 + 晚间复核）｜交接人：D｜按 `共享/07 §九`，上限 300 字

**在做什么**：契约 3（CSV schema）+ 现场记录表 + PC 看板 + 三个实验的数据与图。

**做到哪**：契约 3 升 **v1.1f 并冻结**（A 的 7 条 + 落盘目录口径），签字页 `D/契约3-签字页.md`；记录表升 **v1.2b**；看板已从 `D/dashboard/` **拆平到 D 根**（`app.py`/`mock_feed.py`/`templates/`/`static/` + 4 张截图），mock 三页跑通；`/ingest` 用 B 的 v1.5 八类真样本实测通过，答复见 `D/2026-11-26-口径修正与契约4答复.md`；`data/` 目录树落地。

**下一步（按顺序）**：
1. D5 契约 4 联调：钉死项已列（每帧带 `node`/`ts`、7 类 `type`、`alarm args=[lv,src]`、heartbeat 10 s），等 A 出 v1.0。
2. D6 接真流 + 数据完整性看板 + **`tools/clean.py`（14 条校验）**。
3. 板子侧 `DASH_URL` 必须显式传 `.20`（v1.5 默认是 `.5`，错的）。

**卡在哪**：UNO 在 C 手上（T4/T5 排队）；PC 实测 IP 未测（`.20` 仍是暂记）；B 的 `duo_bridge_v1_5.py` 尚未入库；120 人次人力待预演（D7）。

**跑法一句话**：`cd D && python app.py --mock`（默认数据根 `D/data`，mock 写 `D/data/mock/`）。

**口径别记错**：心跳 2 s 常量、6 s 异常、30 s 离线；报警只有 `buzzer_level`+`pattern_ms`（deny = `80x2/400`）；节点名用契约 5 的 `milky-a…d`（`nodeA` 是旧写法）；真值只认 U 型光电，人工组标 `#manual_truth`。
