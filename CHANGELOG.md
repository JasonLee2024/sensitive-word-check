# 变更记录

本文件记录项目的所有重要变更，格式遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [2.1.0] — 2026-05-01

### 新增

- Unicode NFKC 归一化：`load_rules()` 和文件读取时各做一次 `unicodedata.normalize("NFKC", ...)`，防止全角/兼容字符变体绕过检测
- `scripts/common.py` 共享模块，集中管理常量、归一化函数和工具函数
- 行内跳过注释支持：行中出现 `# no-sensitive-check` 则跳过该行的检测和替换

### 变更

- `scripts/check.py` 和 `scripts/fix.py` 改为从 `scripts/common.py` 导入，消除约 70 行重复代码
- `scripts/fix.py` 的 `preview_changes()` 和 `apply_fixes()` 改为逐行处理，确保跳过注释准确生效

### 修复

- `manage.py cmd_add` 始终为新规则填充完整三维度（缺失时以 `"unclassified"` 补齐），新词在所有维度聚类中可见
- `manage.py cmd_update` 部分更新维度时自动补齐缺失的维度键
- `auto_extend_dimensions()` 不再将系统默认值 `"unclassified"` 加入维度目录

### 移除

- `references/words.json` 所有规则中的 `context` 字段（语义已由 `dimensions.domain` 覆盖）
- `manage.py add` 和 `manage.py update` 的 `--context` 选项
- `manage.py _print_rule()` 输出中的语境（context）行

## [2.0.0] — 2026-04

### 新增

- 三维度分类体系：`risk_type`（安全/隐私/法律）、`domain`（情报/监控/数据采集/网络）、`severity`（高/中/低）
- `check.py` 的 `--group-by` 选项，终端按维度聚类输出
- Markdown 和 HTML 报告中的维度聚类章节
- JSONL 审计日志中的 `dimension_breakdown` 字段
- `auto_extend_dimensions()` 自动注册新的维度值
- `scripts/manage.py` 词库管理脚本（list / add / remove / update / cluster）
- 五种审计输出格式：终端（ANSI 彩色）、`.log`（syslog 风格）、`.jsonl`（JSON Lines）、`.md`（Markdown）、`.html`（自包含 HTML）
- `references/integration-guide.md` 生态集成指南，涵盖 5 个社区集成场景

### 变更

- `references/words.json` 升级至 v2.0 模式，增加 `dimensions` 目录和每条规则的 `dimensions` 字典

## [1.0.0] — 2026-04

### 新增

- 初始发布，包含 5 个核心敏感词：情报、监控、抓取、爬虫、窃取
- `scripts/check.py` 目录扫描与彩色终端报告
- `scripts/fix.py` 交互式预览替换流程，支持 `--dry-run`
- `references/words.json` 词库单一事实来源
- `SKILL.md` 完整参考手册
- `README.md` 项目说明（vibe coding 背景叙事）
- Git pre-commit hook 和 CI/CD 流水线集成方案
- 零外部依赖，纯 Python 标准库
