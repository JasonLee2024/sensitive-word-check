# sensitive-word-check

Claude Code 技能 — 跨项目中文敏感词检查与修复。

检测并替换项目中的敏感词汇（如情报、监控、抓取、爬虫、窃取），支持终端/Markdown/HTML/JSONL/log 五种报告格式、三维度自动聚类、CI/CD 集成。

## 快速开始

```bash
# 扫描当前目录
python scripts/check.py /path/to/project

# 按严重程度聚类扫描
python scripts/check.py /path/to/project --group-by severity

# 预览修复
python scripts/fix.py /path/to/project --dry-run

# 管理词库
python scripts/manage.py list
python scripts/manage.py add "新词" -r "替代1,替代2" --severity high
```

## 完整文档

参见 [SKILL.md](./SKILL.md)
