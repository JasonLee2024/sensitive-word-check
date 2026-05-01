---
name: sensitive-word-check
description: |
  跨项目中文敏感词检查与修复技能。
  TRIGGER when: 用户提及「敏感词」「敏感词检查」「敏感词扫描」「敏感词过滤」「词汇合规」「禁用词」，
  或使用 /敏感词检查、/敏感词修复 斜杠命令，
  或要求在提交前检查项目文件中是否包含不当词汇。
  支持 check（扫描报告）和 fix（自动替换）两种模式。
---

# 敏感词检查与修复 — 完整参考手册

## 目录

- [快速开始](#快速开始)
- [内置敏感词清单](#内置敏感词清单)
- [模式一：check — 扫描与报告](#模式一check--扫描与报告)
  - [全部选项](#check-全部选项)
  - [审计输出格式](#审计输出格式)
  - [维度聚类](#维度聚类)
- [模式二：fix — 预览与替换](#模式二fix--预览与替换)
  - [全部选项](#fix-全部选项)
  - [交互流程](#交互流程)
- [词库管理](#词库管理)
  - [manage.py 脚本命令](#managepy-脚本命令)
  - [对话式管理](#对话式管理)
  - [自定义词库](#自定义词库)
- [维度体系](#维度体系)
- [CI/CD 集成](#cicd-集成)
  - [Git Hook](#git-hook)
  - [流水线脚本](#流水线脚本)
- [生态集成](#生态集成)
- [技术说明](#技术说明)
- [文件清单](#文件清单)
- [分享与分发](#分享与分发)
- [变更记录](#变更记录)

---

## 快速开始

```bash
# 扫描当前目录（终端彩色报告）
python ~/.claude/skills/sensitive-word-check/scripts/check.py .

# 预览修复（不实际修改）
python ~/.claude/skills/sensitive-word-check/scripts/fix.py . --dry-run

# 列出所有敏感词
python ~/.claude/skills/sensitive-word-check/scripts/manage.py list
```

---

## 内置敏感词清单

| 禁止词 | 替代词 | 风险类型 | 严重程度 |
|--------|--------|---------|---------|
| 情报 | 洞察 / 信息 / 数据 | security（安全/情报类） | high |
| 监控 | 监测 / 跟踪 / 观察 | security（安全/情报类） | high |
| 抓取 | 采集 / 提取 / 获取 | privacy（隐私/数据类） | medium |
| 爬虫 | 采集工具 / 自动采集 | legal（法律/合规类） | medium |
| 窃取 | 提取 / 读取 | legal（法律/合规类） | high |

> 词库文件：`references/words.json`，完整维度标注见[维度体系](#维度体系)。

---

## 模式一：check — 扫描与报告

扫描指定目录，检测所有包含敏感词的文件、行号，给出替换建议。**不修改任何文件**。返回非零退出码。

```bash
python <skill-path>/scripts/check.py <目标目录> [选项]
```

### Check 全部选项

| 选项 | 说明 |
|------|------|
| `--custom`, `-c` | 使用自定义词库 JSON 文件 |
| `--output`, `-o` | 输出 Markdown 报告文件（同 `--audit-md`） |
| `--ext` | 额外文件扩展名，逗号分隔（如 `.vue,.jsx`） |
| `--exclude` | 额外排除目录，逗号分隔 |
| `--exclude-file` | 排除特定文件名，逗号分隔（如 `PROJECT_RULES.md`） |
| `--group-by`, `-g` | 按维度聚类输出（`risk_type` / `domain` / `severity`） |
| `--audit-log`, `-a` | 追加纯文本审计日志到 `.log` 文件 |
| `--audit-json`, `-j` | 追加 JSON 审计日志到 `.jsonl` 文件 |
| `--audit-md`, `-m` | 输出 Markdown 格式审计报告（`.md`） |
| `--audit-html` | 输出自包含 HTML 格式审计报告（`.html`） |

### 审计输出格式

| 格式 | 标志 | 特点 | 适用场景 |
|------|------|------|---------|
| **终端** | 默认 | ANSI 彩色，按文件分组，词频统计 | 日常开发即时反馈 |
| `.log` | `--audit-log` | 纯文本 syslog 风格，可追加 | grep 搜索、日志系统 |
| `.jsonl` | `--audit-json` | 结构化 JSON，含维度数据 | 程序化处理、导入数据库 |
| `.md` | `--audit-md` / `--output` | Markdown 表格，含维度聚类区块 | GitHub/GitLab 直接查看 |
| `.html` | `--audit-html` | 自包含 HTML，响应式设计 | 浏览器打开、归档、邮件附件 |

**示例：**

```bash
# 基础扫描
python check.py .

# 按严重程度聚类
python check.py . --group-by severity

# 全量输出（4 种格式 + 终端）
python check.py . \
  --group-by risk_type \
  --audit-md report.md \
  --audit-html report.html \
  --audit-log audit.log \
  --audit-json audit.jsonl

# CI/CD 阻断（发现违规返回非零）
python check.py . --exclude-file PROJECT_RULES.md || exit 1
```

### 维度聚类

使用 `--group-by` 按任一维度对扫描结果进行分组展示：

```bash
# 按风险类型分组：安全/情报类 vs 隐私/数据类 vs 法律/合规类
python check.py . --group-by risk_type

# 按领域分组：情报/军事、监视/监控、数据采集、网络安全
python check.py . --group-by domain

# 按严重程度分组：高危、中等、低风险
python check.py . --group-by severity
```

**终端聚类输出示例：**

```
维度聚类 — 风险类型 — 该词触发的负面联想类别:
  安全/情报类 — espionage, surveillance, covert ops (2 处)
    情报 — 1 次
    监控 — 1 次
  法律/合规类 — theft, infringement, illegal access (2 处)
    爬虫 — 1 次
    窃取 — 1 次
```

聚类信息自动带入 Markdown/HTML 报告和 JSONL 审计日志的 `dimension_breakdown` 字段。

---

## 模式二：fix — 预览与替换

先展示将要修改的所有文件和替换内容，用户确认后执行。支持 dry-run 模式仅预览。

```bash
python <skill-path>/scripts/fix.py <目标目录> [选项]
```

### Fix 全部选项

| 选项 | 说明 |
|------|------|
| `--dry-run`, `-n` | 仅预览变更，不实际修改文件 |
| `--yes`, `-y` | 跳过确认提示，直接执行（CI/CD 自动修复） |
| `--custom`, `-c` | 使用自定义词库 JSON 文件 |
| `--ext` | 额外文件扩展名，逗号分隔 |
| `--exclude` | 额外排除目录，逗号分隔 |
| `--exclude-file` | 排除特定文件名，逗号分隔 |
| `--audit-log`, `-a` | 追加纯文本审计日志到 `.log` 文件 |
| `--audit-json`, `-j` | 追加 JSON 审计日志到 `.jsonl` 文件 |
| `--audit-md`, `-m` | 输出 Markdown 格式审计报告（`.md`） |
| `--audit-html` | 输出自包含 HTML 格式审计报告（`.html`） |

### 交互流程

```bash
# 步骤一：预览变更
python fix.py . --dry-run

# 步骤二：确认执行
python fix.py .
# 预览 → 输入 y 确认 → 执行替换

# 步骤三（可选）：查看修复报告
python fix.py . --dry-run --audit-md preview.md --audit-html preview.html

# 非交互模式（CI/CD）
python fix.py . --yes --audit-log fix.log --audit-json fix.jsonl
```

**交互输出示例：**

```
============================================================
  敏感词修复预览
============================================================
  目标目录 : /home/user/my-project
  影响文件 : 3 个
  替换总数 : 12 处
============================================================

📄 src/main.js
   情报 → 洞察 (2 处)
   抓取 → 采集 (3 处)

📄 docs/README.md
   情报 → 信息 (5 处)

即将在 3 个文件中替换 12 处敏感词。
确认执行？[y/N] y

✅ 修复完成！共修改 3 个文件，12 处替换。
  ✓ src/main.js
  ✓ docs/README.md
```

---

## 词库管理

词库文件 `references/words.json` 是单一事实来源，修改后全局生效。

### manage.py 脚本命令

| 命令 | 说明 |
|------|------|
| `list` | 列出所有敏感词 |
| `list --by <维度>` | 按维度聚类列出 |
| `dimensions` | 查看维度定义及每个值下的词数 |
| `cluster --by <维度>` | 按维度聚类展示（带替换词和说明） |
| `add <词> -r <替换词>` | 添加新敏感词 |
| `remove <词>` | 删除敏感词 |
| `update <词>` | 更新替换词/维度/说明 |

**完整示例：**

```bash
# 查看概览
python manage.py list
python manage.py list --by severity
python manage.py dimensions

# 聚类查看
python manage.py cluster --by risk_type
python manage.py cluster --by domain

# 添加新词（三维度标签齐全）
python manage.py add "卧底" \
  -r "线人,内应" \
  --risk-type security \
  --domain intelligence \
  --severity high \
  --note "covert ops 联想"

# 更新现有词
python manage.py update "情报" \
  --severity medium \
  --note "降级为中等敏感，已有广泛使用先例"

# 删除
python manage.py remove "卧底"
```

**add/update 完整参数：**

| 参数 | 说明 |
|------|------|
| `-r`, `--replacements` | 替代词，逗号分隔（必填） |
| `--risk-type` | 风险类型：`security` / `privacy` / `legal`（或任意自定义值） |
| `--domain` | 语义领域：`intelligence` / `surveillance` / `data_collection` / `cyber`（或任意自定义值） |
| `--severity` | 严重程度：`high` / `medium` / `low`（或任意自定义值） |
| `--context` | 语境分类（默认 `general`） |
| `--note` | 替换理由/备注 |

> 如果传入的维度值不在现有维度目录中（如 `--risk-type military`），系统会**自动将该值加入维度目录**并标记为 `[自定义]`，无需手动编辑 `words.json` 扩展维度定义。之后可在 `words.json` 中将 `[自定义] xxx` 替换为正式的中文描述。

### 对话式管理

在 Claude Code 中直接对话操作，无需手动运行脚本：

- 「把『xxx』加入敏感词清单，替换为『aaa』和『bbb』」
- 「从敏感词清单中删除『xxx』」
- 「查看当前敏感词清单」
- 「修改『xxx』的替代词，改成『ccc』」
- 「把『xxx』的风险类型改为 legal」

Claude 会直接编辑 `words.json` 或运行 `manage.py` 完成操作。

### 自定义词库

创建临时词库文件（格式参考 `references/words.json`），通过 `--custom` 加载：

```json
{
  "version": "1.0",
  "rules": [
    {
      "word": "敏感词",
      "replacements": ["替代词1", "替代词2"],
      "dimensions": {
        "risk_type": "security",
        "domain": "intelligence",
        "severity": "high"
      },
      "context": "语境说明",
      "note": "替换理由"
    }
  ]
}
```

```bash
python check.py . --custom my-words.json
```

`--custom` 只在当前扫描中生效，不影响全局词库。

---

## 维度体系

每个敏感词标注三个正交维度，实现多角度聚类分析。

### 维度一：风险类型 (`risk_type`)

| 值 | 含义 | 覆盖词汇 |
|----|------|---------|
| `security` | 安全/情报类 — espionage, surveillance, covert ops | 情报、监控 |
| `privacy` | 隐私/数据类 — scraping, unauthorized collection | 抓取 |
| `legal` | 法律/合规类 — theft, infringement, illegal access | 爬虫、窃取 |

### 维度二：语义领域 (`domain`)

| 值 | 含义 | 覆盖词汇 |
|----|------|---------|
| `intelligence` | 情报/军事领域 | 情报 |
| `surveillance` | 监视/监控领域 | 监控 |
| `data_collection` | 数据采集领域 | 抓取、爬虫 |
| `cyber` | 网络安全领域 | 窃取 |

### 维度三：严重程度 (`severity`)

| 值 | 含义 | 覆盖词汇 |
|----|------|---------|
| `high` | 高危 — 极易触发敏感审查，**必须替换** | 情报、监控、窃取 |
| `medium` | 中等 — 视上下文可能引发联想 | 抓取、爬虫 |
| `low` | 低风险 — 仅特定语境下敏感 | （暂无） |

### 维度在输出中的体现

| 输出格式 | 体现方式 |
|---------|---------|
| **终端** | `--group-by` 后在"违规词统计"前插入维度聚类区块 |
| **Markdown** | `## 维度聚类` 章节，含子标题分组 |
| **HTML** | 独立的"维度聚类"卡片区块 |
| **JSONL** | `dimensions` 字段（每条违规记录）+ `dimension_breakdown` 字段（汇总级别） |

**动态扩展**：当通过 `manage.py add/update` 传入的维度值不在现有目录中时，`auto_extend_dimensions()` 函数自动将其追加到 `words.json` 的维度定义中（标记为 `[自定义] xxx`），无需手动编辑 JSON 即可引入全新维度或领域。之后可将 `[自定义]` 标签改为正式中文描述。

---

## CI/CD 集成

### Git Hook

在项目 `.claude/settings.json` 中配置 PreCommit 钩子：

```json
{
  "hooks": {
    "PreCommit": [
      {
        "name": "敏感词检查",
        "command": "python ~/.claude/skills/sensitive-word-check/scripts/check.py . --exclude-file PROJECT_RULES.md"
      }
    ]
  }
}
```

每次 `git commit` 前自动扫描，发现敏感词则阻断提交。配合 `--exclude-file` 排除规则文件自身。

### 流水线脚本

```bash
#!/bin/bash
# 敏感词 CI 检查脚本

SKILL_DIR="$HOME/.claude/skills/sensitive-word-check"

# 检查：发现违规返回非零
python "$SKILL_DIR/scripts/check.py" . \
  --group-by severity \
  --audit-html ci-report.html \
  --audit-json ci-audit.jsonl \
  --exclude-file PROJECT_RULES.md \
  --exclude .claude,node_modules

if [ $? -ne 0 ]; then
  echo "❌ 敏感词检查未通过，详见 ci-report.html"
  exit 1
fi

# 可选：自动修复（谨慎使用）
# python "$SKILL_DIR/scripts/fix.py" . --yes --audit-json fix-audit.jsonl
```

---

## 生态集成

本技能可与社区已有项目组合，扩展词库规模、匹配精度和检测深度。详见 [references/integration-guide.md](references/integration-guide.md)。

**快速索引：**

| 需求 | 集成项目 | 方式 |
|------|---------|------|
| 挂载大词库（万级词汇） | [Sensitive-lexicon](https://github.com/konsheng/Sensitive-lexicon) | `--custom` 参数 |
| 高性能匹配 | [houbb/sensitive-word](https://github.com/houbb/sensitive-word) | `--engine ac` 引入 pyahocorasick |
| 防全角/繁体绕过 | OpenCC + 标准库 | 字符归一化预处理 |
| ML 语义二次审核 | [Chinese-offensive-language-detect](https://github.com/royal12646/Chinese-offensive-language-detect) | 后置 ML 审核层 |
| Claude Code 协同 | [glin-profanity-mcp](https://mcprepository.com/GLINCKER/glin-profanity) | settings.json 并排配置 |

---

## 技术说明

**扫描范围：**
- 支持文件类型：`.md` `.py` `.js` `.ts` `.html` `.css` `.yaml` `.yml` `.json` `.txt` `.java` `.go` `.rs` `.c` `.cpp` `.sh` `.ps1` `.xml` `.toml` `.ini` `.cfg` `.conf`
- 可通过 `--ext` 扩展（如 `--ext .vue,.jsx,.tf`）

**自动排除：**
- 目录：`.git` `node_modules` `__pycache__` `.venv` `venv` `.obsidian` `.trash` `.claude` `dist` `build` `target`
- 可通过 `--exclude` 扩展（如 `--exclude data,output`）
- 可通过 `--exclude-file` 排除特定文件名（如 `--exclude-file PROJECT_RULES.md,README.md`）

**性能保护：**
- 跳过 > 10MB 的文件
- UTF-8 解码失败的文件自动跳过
- 目录递归遍历，按文件名排序处理

**退出码：**
- `0` — 无违规（check）或修复成功（fix）
- `1` — 发现违规（check），可用于 CI 阻断

---

## 文件清单

```
sensitive-word-check/
├── CHANGELOG.md                # 版本变更历史（Keep a Changelog 格式）
├── SKILL.md                    # 本手册（Claude Code 技能定义）
├── README.md                   # 项目主页 README
├── .gitignore
├── references/
│   ├── words.json              # 敏感词词库（v2.1，含维度体系）
│   └── integration-guide.md    # 生态集成指南
└── scripts/
    ├── common.py               # 共享模块（常量、归一化、工具函数）
    ├── check.py                # 扫描检查脚本
    ├── fix.py                  # 预览替换脚本
    └── manage.py               # 词库管理脚本
```

---

## 分享与分发

技能零外部依赖（纯 Python 标准库），所有路径通过 `Path(__file__).resolve().parent` 相对计算，可直接复制目录分发。

### 方式一：直接复制

```bash
# 接收方将目录放入自己的 skills 目录
cp -r sensitive-word-check ~/.claude/skills/
```

### 方式二：Git 仓库分发

```bash
# 接收方
git clone <repo-url> ~/.claude/skills/sensitive-word-check

# 后续更新
cd ~/.claude/skills/sensitive-word-check && git pull
```

### 方式三：打包传输

```bash
# 打包
tar -czf sensitive-word-check.tar.gz -C ~/.claude/skills sensitive-word-check

# 接收方解包
tar -xzf sensitive-word-check.tar.gz -C ~/.claude/skills/
```

### 接收方立即可用

复制完成后无需任何配置，三种入口均可用：

```bash
# 脚本直接调用
python ~/.claude/skills/sensitive-word-check/scripts/check.py /some/project

# Claude Code 斜杠命令
/敏感词检查 /some/project

# 词库管理
python ~/.claude/skills/sensitive-word-check/scripts/manage.py list
```

### 共享自定义词库

若分享你的词库修改（新增敏感词、维度扩展等），将 `references/words.json` 一并覆盖即可：

```bash
scp ~/.claude/skills/sensitive-word-check/references/words.json user@host:~/.claude/skills/sensitive-word-check/references/
```

维度自动扩展机制确保接收方后续自行添加新词时不会与你共享的维度值冲突。

---

## 变更记录

完整的版本变更历史请见 [CHANGELOG.md](CHANGELOG.md)，遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) 格式。
