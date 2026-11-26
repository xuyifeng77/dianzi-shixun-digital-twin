# 交接卡 · D（数据与实验）

> 2026-11-26（D3）｜交接人：D｜按 `共享/07 §九`，上限 300 字

**在做什么**：契约 3（CSV schema）+ 现场记录表 + PC 看板 + 三个实验的数据与图。

**做到哪**：契约 3 升 **v1.1c 并冻结**（A 的 7 条全部落字），签字页 `D/契约3-签字页.md`；记录表升 **v1.2a**；看板 `D/dashboard/` **mock 三页 + 4 张截图跑通**（`app.py`/`mock_feed.py`，标准库无依赖）；`data/` 目录树落地。

**下一步（按顺序）**：
1. D4 用 B 的样例 JSON 跑一遍 `/ingest`（不接真流），写 `meta.json` 入库脚本。
2. D5 契约 4 联调：把 `@E/@A/@C/@D/@R` 字段钉死，`/ingest` 改定稿；届时契约 3 若动字段 → 升 v1.1d 重签。
3. D6 接真流 + 数据完整性看板 + **`tools/clean.py`（14 条校验）**。

**卡在哪**：UNO 在 C 手上（T4/T5 排队）；PC 实测 IP 未测（`.20` 仍是暂记）；B 的 `post()` 缺 `node` 字段；120 人次人力待预演（D7）。

**跑法一句话**：`cd D\dashboard && python app.py --data ../data --port 8000`，另开 `python mock_feed.py`。

**口径别记错**：心跳 2 s 常量、6 s 异常、30 s 离线；报警只有 `buzzer_level`+`pattern_ms`；真值只认 U 型光电，人工组标 `#manual_truth`。
