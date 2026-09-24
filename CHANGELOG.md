# Changelog

## 0.4.0（2026-09-24）

### 性能优化
- **SQL 侧聚合重构**：利用 SQLite JSON1 扩展在 SQL 层提取 token 字段（`json_extract` + `CASE WHEN json_valid()` 容错），避免 Python 逐行 `json.loads`，大数据量场景性能显著提升
- **价格规则缓存**：新增 `PriceCache` 类，同一模型的计价规则只解析一次，避免聚合循环中重复解析 dict

### 新功能
- **自定义日期范围**：`--since YYYY-MM-DD --until YYYY-MM-DD`，与 `--days` 互斥
- **会话维度聚合**：`--by session`，按对话统计 token 消耗，帮助定位高消耗会话
- **`--days all` 别名**：等同于 `--days 0`（全部历史），更直觉
- **CSV 导出**：HTML 仪表盘明细表新增「导出 CSV」按钮，支持按当前维度导出
- **`--top-projects` 参数**：`build_canvas.py` 项目排行条数可配置（默认 15）

### 改进
- **汇率集中配置**：`pricing.json` 新增顶层 `_exchangeRate` 字段，国际模型价格折算汇率集中管理
- **脚注统一**：`build_dashboard.py` 与 `build_canvas.py` 的脚注统一引用 `usage_report.FOOTNOTES`，避免多处维护不同步
- **update_pricing URL 白名单**：`fetch()` 仅允许 `https://` 协议，防止 `file://` / `http://` 等不安全协议
- **update_pricing diff 增强**：比对 `display_name` / `note` 元数据变更，不仅限于价格数值
- **HTML 模板 compact() 修复**：小于 1 万的数值使用千分位格式化，与大于 1 万的显示风格一致

## 0.3.3（2026-09-24）

- 插件图标精修（logo-generator skill 迭代）——剔除底色灰浑来源：移除 2 处环境光斑与主柱柔光层；金币焦点光晕收窄（stdDeviation 6→4、opacity 0.26→0.22）；币面内环增强（0.25/1.2 → 0.3/1.3）、¥ 符号线宽加粗（2.2→2.6），小尺寸下更清晰锐利；视觉结构（底板/边框/三柱/金币）保持不变。

## 0.3.2（2026-09-23）

- 修复中文（非 ASCII）工作区路径下 Canvas 画布写入目录与 Qoder 客户端不一致的问题——Qoder 客户端把工作区路径中所有非字母数字字符替换为 `-`，旧版脚本只替换 `/`（保留中文），两套规则分裂导致画布写入错误目录、点击画布链接报「文件不存在或无法访问。」；现统一为 `[^a-zA-Z0-9] → -` 规则（ASCII 路径行为不变）。

## 0.3.1（2026-09-23）

- 扩充国际模型参考价——`_otherCustomModels` 备选参考价由 18 款增至 30 款，新增 OpenAI（GPT-6 Astra / Sol / Luna、GPT-5.3 Codex）、Anthropic（Fable 5.1 / Opus 5.5 / Sonnet 5 / Haiku 4.5）、Google（Gemini 3.8 Flash / 3.1 Pro Preview）、xAI（Grok 4.7 / Build 0.1）共 12 款；国际厂商为美元官网价（note 内标注原价），按参考汇率 6.70 折算，价格均经官网复核（2026-09-23）。

## 0.3.0（2026-09-23）

- 新增**模型价格自动更新**——`update_pricing.py` 从插件公开仓库（Gitee 优先 / GitHub 兜底）同步最新官网参考价：结构 + 数值校验、原子写入、自动备份（保留 3 份）、24h 节流、失败重试窗口、离线开关（`--offline` / `TOKEN_USAGE_NO_NET=1`）；新增 `/update-pricing` 斜杠命令；`/token-usage` 流程加入价格自检；`pricing.json` 新增 `_version` 版本字段。

## 0.2.1（2026-09-23）

- 扩充计费模型范围——`_otherCustomModels` 备选参考价由 5 款增至 18 款，覆盖 DeepSeek / Kimi / 通义千问 / 智谱 GLM / 豆包 / MiniMax（新增 Kimi-K2.7-Code / HighSpeed / K2.6、Qwen-3.7-Plus / 3.8-Flash、GLM-5.3 / 5.2 / 5.3-Flash、Doubao-Seed-2.1-Pro / Turbo / Evolving、MiniMax-M3 / M2.7），价格均经官网复核（2026-09-23）。

## 0.2.0（2026-09-23）

- 跨平台通用化——数据库路径自动探测（macOS/Windows/Linux）+ `QODER_DB_PATH` 覆盖；仪表盘默认输出与浏览器打开改用跨平台标准库；Canvas 项目目录 slug 归一化；斜杠命令跨安装根定位。

## 0.1.0（2026-09-23）

- 首个版本——文本报表、可视化 HTML 仪表盘、IDE 内 Canvas 仪表盘与 `/token-usage` 斜杠命令。
