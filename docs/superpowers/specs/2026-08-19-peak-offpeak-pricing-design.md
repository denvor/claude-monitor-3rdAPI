# 设计：monitor.ini 峰谷分时计价支持

- 日期：2026-08-19
- 状态：已获用户批准
- 版本目标：1.0.0 → 1.1.0

## 背景

DeepSeek 于 2026-08-17 00:00（北京时间）启用峰谷定价（官方定价页
https://api-docs.deepseek.com/zh-cn/quick_start/pricing 确认）：

- 高峰时段：北京时间每日 9:00–12:00、14:00–18:00；其余（含夜间、周末、节假日）为空闲时段
- 空闲价恒为高峰价的一半
- 官方价格表（元/百万 tokens）：

| 价格项 | V4 Pro 空闲 | V4 Pro 高峰 | V4 Flash 空闲 | V4 Flash 高峰 |
|---|---|---|---|---|
| 输入·缓存命中 | 0.15 | 0.30 | 0.05 | 0.10 |
| 输入·缓存未命中 | 4.5 | 9.0 | 1.5 | 3.0 |
| 输出 | 13.5 | 27.0 | 4.5 | 9.0 |

现有 `monitor.ini` 中 v4-pro / v4-flash 的价格全部过期，不更新则费用统计严重偏低。

JSONL 数据中每条 assistant 记录带毫秒级 UTC 时间戳，现有代码已保留到
`TokenRecord.timestamp`（本地时区、aware），足以逐条判定峰/谷。

### 用户已确认的决策

1. **历史数据**：按变更日期分段计价——8/17 之前的记录用旧价，之后用新峰谷价（配置需支持价格生效日期）
2. **配置格式**：通用设计——section 名可带 `@日期` 生效日期，节内可选 `peak_hours` + `peak_*` 价格键；不写则维持现有单价格式，向后兼容，任意供应商可用
3. **展示**：表格与 CSV 在 Cost 列后新增 Peak / Off-peak 拆分两列
4. **代码组织**：方案 A——就地扩展现有 6 个模块，不新增文件

## 配置格式

在现有 section 格式上扩展，全部可选、向后兼容（不写新键行为不变）：

```ini
[default]                          ; 通用兜底，支持同样扩展
input_price=3.00
output_price=6.00
cache_write_price=3.00
cache_read_price=0.025
currency=CNY

[deepseek-v4-pro]                  ; 旧价：无日期后缀 = 在首个带日期版本生效前适用
input_price=3.00
output_price=6.00
cache_write_price=3.00
cache_read_price=0.025
currency=CNY

[deepseek-v4-pro@2026-08-17]       ; 新价：2026-08-17 00:00（tz 时区）起适用
peak_hours=9-12,14-18              ; 高峰时段（tz 时区），半开区间 [9:00,12:00) [14:00,18:00)
tz=Asia/Shanghai                   ; 时段判定与生效日期所用时区，缺省=系统本地时区
input_price=4.50                   ; 空闲价
output_price=13.50
cache_write_price=4.50
cache_read_price=0.15
peak_input_price=9.00              ; 高峰价
peak_output_price=27.00
peak_cache_write_price=9.00
peak_cache_read_price=0.30
currency=CNY
```

注意：生效日期**只**写在 section 名 `@日期` 后缀中，不设 `effective=` 键
（configparser 禁止重名 section，同一模型多版价格必须靠 section 名区分）。

### 定价解析规则

对每条记录（模型名 + 记录时间）：

1. **匹配**：section 基础名（去掉 `@` 后缀）对模型名做现有的大小写不敏感子串匹配
2. **版本选择**：匹配到的 section 中，选生效日期最大且 ≤ 记录时间的（无日期后缀视为 -∞）；没有任何版本满足时间条件（如记录早于所有带日期版本且该模型无无日期版本）→ 视为未匹配，走规则 3
3. **兜底**：无命名 section 匹配或版本选择落空 → 走 `[default]`（同样支持带日期版本与峰谷键）；`[default]` 也无可用版本时 → 现有内置默认定价
4. **峰谷判定**：记录时间转到 section 的 `tz` 后落入 `peak_hours` 任一区间 → 用 `peak_*` 价，否则用基础价
5. **边界**：12:00:00 整属于空闲（半开区间）；`peak_hours` 已写但缺某 `peak_*` 键 → 警告日志 + 该项按基础价

### Token 语义映射

DeepSeek 三项价格 ↔ JSONL 四种 token：

- 输入·缓存命中 → `cache_read_tokens`（`cache_read_price`）
- 输入·缓存未命中 → `input_tokens` + `cache_creation_tokens`（`input_price` / `cache_write_price`）
- 输出 → `output_tokens`（`output_price`）

## 代码改动（方案 A：就地扩展）

| 文件 | 改动 |
|---|---|
| `config.py` | 解析 section 名 `@YYYY-MM-DD` 后缀、`peak_hours`、`tz`、`peak_*` 键（内部以 datetime / ZoneInfo / 区间列表存于现有 pricing dict）；新增 `resolve_pricing(model, pricing, default, timestamp) -> (entry, is_peak)` 实现上述解析规则 |
| `reader.py` | `TokenRecord` 增加 `peak_cost: float = 0.0`、`offpeak_cost: float = 0.0` 两字段；JSONL 解析逻辑不变 |
| `calculator.py` | 逐条改调 `resolve_pricing(record.model, ..., record.timestamp)`；成本按层级计价，`total_cost` 算法不变，另拆写 `peak_cost` / `offpeak_cost`（两者之和恒等于 `total_cost`）；未匹配 info 日志逻辑保持 |
| `aggregator.py` | `AggregatedRow` 增加 `peak_cost` / `offpeak_cost` 并累加 |
| `display.py` | 静态表格在 `Cost (currency)` 列后加 `Peak` / `Off-peak` 两列（右对齐），Total 行汇总；CSV 加 `PeakCost` / `OffpeakCost` 两列 |
| `realtime.py` | 实时表格同静态表格处理 |

时区用标准库 `zoneinfo`（Python 3.9+，零新依赖）。

### 展示语义

Peak / Off-peak 两列表示「按峰/谷**费率**计的成本」。无峰谷配置的模型
（如本地 Qwen）成本全部计入 Off-peak 列，Peak 为 0。

## 错误处理

沿用现有宽容风格，全部 `logger.warning` 不中断：

| 情况 | 行为 |
|---|---|
| `@日期` 格式错误 | 当作无日期版本 |
| `peak_hours` 格式错误 | 该 section 按单价处理 |
| `tz` 无法识别 | 回退系统本地时区 |
| 未匹配到任何 section | 现有行为：`[default]` + info 日志 |

## 配套更新

- **仓库 `monitor.ini`**：v4-pro / v4-flash 各加 `@2026-08-17` 新价 section（官方价格表），旧 section 保留；用户本地未提交的 Qwen section 改动不触碰
- **README.md + README_zh.md**：配置格式章节补 `@日期`、`peak_hours`、`tz`、`peak_*` 说明及示例
- **CHANGELOG.md + CHANGELOG_zh.md**：新增条目（双语同步）
- **版本**：`pyproject.toml` 与 `src/claude_monitor/__init__.py` 均 1.0.0 → 1.1.0

## 验证方式

项目无测试基建，不新增测试框架：

1. **边界检查脚本**：用 8:59 / 9:00 / 12:00 / 13:59 / 18:00 / 8-16 23:59 / 8-17 00:00 等时刻的构造记录跑 `resolve_pricing` + `calculate_costs`，确认落价正确（含生效日期两侧、峰谷边界、无峰谷配置模型）
2. **真实数据**：`claude-monitor --view daily --days-back 0`，目检 8/17 前后费用跳变是否符合新价表
