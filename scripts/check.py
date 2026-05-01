#!/usr/bin/env python3
"""
敏感词扫描工具 — check 模式
用法: python check.py <target_dir> [--custom words.json] [--output report.md]
"""

import argparse
import json
import os
import sys
from pathlib import Path

# 文件扩展名白名单
DEFAULT_EXTENSIONS = {".md", ".py", ".js", ".ts", ".html", ".css", ".yaml", ".yml", ".json", ".txt", ".java", ".go", ".rs", ".c", ".cpp", ".sh", ".ps1", ".xml", ".toml", ".ini", ".cfg", ".conf"}

# 默认排除目录
DEFAULT_EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".obsidian", ".trash", ".claude", "dist", "build", "target"}


def load_rules(words_path: str) -> list[dict]:
    """加载敏感词规则"""
    path = Path(words_path)
    if not path.exists():
        print(f"错误：词库文件不存在 — {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("rules", [])


def load_dimensions(words_path: str) -> dict | None:
    """加载维度定义"""
    path = Path(words_path)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("dimensions", None)


def should_scan(filepath: Path, extensions: set, exclude_dirs: set, exclude_files: set) -> bool:
    """判断文件是否需要扫描"""
    # 检查是否在排除文件列表中（按文件名或相对路径匹配）
    fname = filepath.name
    if fname in exclude_files:
        return False
    # 检查扩展名
    if filepath.suffix.lower() not in extensions:
        return False
    # 检查是否在排除目录中
    for part in filepath.parts:
        if part in exclude_dirs:
            return False
    # 跳过二进制大文件
    try:
        size = filepath.stat().st_size
        if size > 10 * 1024 * 1024:  # 10MB
            return False
    except Exception:
        return False
    return True


def scan_directory(target_dir: str, rules: list[dict], extensions: set, exclude_dirs: set, exclude_files: set) -> tuple[list[dict], int]:
    """扫描目录，返回 (违规记录列表, 已扫描文件数)"""
    violations = []
    base = Path(target_dir).resolve()

    if not base.exists():
        print(f"错误：目录不存在 — {base}")
        sys.exit(1)

    files = [f for f in base.rglob("*") if f.is_file() and should_scan(f, extensions, exclude_dirs, exclude_files)]
    files_scanned = len(files)

    for fpath in sorted(files):
        try:
            lines = fpath.read_text(encoding="utf-8", errors="ignore").split("\n")
        except Exception:
            files_scanned -= 1
            continue

        for rule in rules:
            word = rule["word"]
            for i, line in enumerate(lines, 1):
                if word in line:
                    violations.append({
                        "file": str(fpath.relative_to(base)),
                        "line": i,
                        "content": line.strip()[:120],
                        "word": word,
                        "replacements": rule["replacements"],
                        "note": rule.get("note", ""),
                        "dimensions": rule.get("dimensions", {}),
                    })

    return violations, files_scanned


def generate_report(violations: list[dict], target_dir: str, rules_count: int, group_by: str | None = None, dimensions: dict | None = None) -> str:
    """生成终端彩色报告"""
    # ANSI 颜色
    RED = "\033[91m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"

    lines = []
    lines.append(f"{BOLD}{'='*60}{RESET}")
    lines.append(f"{BOLD}  敏感词扫描报告{RESET}")
    lines.append(f"{'='*60}")
    lines.append(f"  扫描目录 : {Path(target_dir).resolve()}")
    lines.append(f"  检查词数 : {rules_count}")
    lines.append(f"  发现违规 : {len(violations)} 处")
    if group_by:
        dim_label = (dimensions or {}).get(group_by, {}).get("description", group_by)
        lines.append(f"  聚类维度 : {dim_label}")
    lines.append(f"{'='*60}")
    lines.append("")

    if not violations:
        lines.append(f"{GREEN}✅ 未发现敏感词，检查通过。{RESET}")
        return "\n".join(lines)

    # 按文件分组
    by_file = {}
    for v in violations:
        by_file.setdefault(v["file"], []).append(v)

    for fpath, items in by_file.items():
        lines.append(f"{CYAN}📄 {fpath}{RESET} ({len(items)} 处)")
        for v in items:
            preview = v["content"]
            # 高亮违规词
            preview = preview.replace(v["word"], f"{RED}{BOLD}{v['word']}{RESET}")
            lines.append(f"   {YELLOW}L{v['line']:4d}{RESET} │ {preview}")
            lines.append(f"         → {GREEN}建议替换为: {', '.join(v['replacements'])}{RESET}")
            if v["note"]:
                lines.append(f"         {v['note']}")
        lines.append("")

    # 维度聚类（在违规词统计之前）
    if group_by and dimensions:
        dim_info = dimensions.get(group_by, {})
        dim_values = dim_info.get("values", {})
        # 按维度值分组
        groups: dict[str, list] = {}
        for v in violations:
            d = v.get("dimensions", {}).get(group_by, "unclassified")
            groups.setdefault(d, []).append(v)

        lines.append(f"{BOLD}维度聚类 — {dim_info.get('description', group_by)}:{RESET}")
        for val_key, val_label in dim_values.items():
            if val_key in groups:
                gv = groups[val_key]
                words_in_group = set(v["word"] for v in gv)
                lines.append(f"  {MAGENTA}{val_label}{RESET} ({len(gv)} 处)")
                for w in sorted(words_in_group):
                    count = sum(1 for v in gv if v["word"] == w)
                    lines.append(f"    {RED}{w}{RESET} — {count} 次")
        if "unclassified" in groups:
            lines.append(f"  {MAGENTA}未分类{RESET} ({len(groups['unclassified'])} 处)")
        lines.append("")

    # 统计
    word_counts = {}
    for v in violations:
        word_counts[v["word"]] = word_counts.get(v["word"], 0) + 1

    lines.append(f"{BOLD}违规词统计:{RESET}")
    for word, count in sorted(word_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {RED}{word}{RESET} — {count} 次")

    lines.append("")
    lines.append(f"💡 运行 {BOLD}/敏感词修复{RESET} 自动替换所有违规词。")
    return "\n".join(lines)


def generate_audit_log(violations: list[dict], target_dir: str, rules_count: int, files_scanned: int, elapsed_ms: int, group_by: str | None = None) -> dict:
    """生成单次审计日志条目（JSON 格式，可追加写入 JSONL 文件）"""
    from datetime import datetime, timezone

    # 按文件分组
    by_file = {}
    for v in violations:
        by_file.setdefault(v["file"], []).append(v)

    # 按词统计
    word_counts = {}
    for v in violations:
        word_counts[v["word"]] = word_counts.get(v["word"], 0) + 1

    # 按维度聚类
    dim_breakdown = None
    if group_by:
        groups: dict[str, list] = {}
        for v in violations:
            d_key = v.get("dimensions", {}).get(group_by, "unclassified")
            groups.setdefault(d_key, []).append(v)
        dim_breakdown = {
            "dimension": group_by,
            "groups": {
                k: {
                    "count": len(gv),
                    "words": list(set(v["word"] for v in gv)),
                }
                for k, gv in groups.items()
            },
        }

    entry = {
        "audit_id": datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")[:20],
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "target": str(Path(target_dir).resolve()),
        "result": "PASS" if len(violations) == 0 else "FAIL",
        "summary": {
            "rules_checked": rules_count,
            "files_scanned": files_scanned,
            "violations_found": len(violations),
            "files_affected": len(by_file),
            "words_breakdown": [{"word": w, "count": c} for w, c in sorted(word_counts.items(), key=lambda x: -x[1])],
        },
        "violations": [
            {
                "file": v["file"],
                "line": v["line"],
                "word": v["word"],
                "dimensions": v.get("dimensions", {}),
                "suggested_replacement": v["replacements"][0] if v["replacements"] else "",
                "context": v["content"],
            }
            for v in violations
        ],
        "elapsed_ms": elapsed_ms,
    }

    if dim_breakdown:
        entry["dimension_breakdown"] = dim_breakdown

    return entry


def generate_html_report(violations: list[dict], target_dir: str, rules_count: int, files_scanned: int, elapsed_ms: int, group_by: str | None = None, dimensions: dict | None = None) -> str:
    """生成自包含 HTML 格式的审计报告"""
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    status = "PASS" if len(violations) == 0 else "FAIL"
    status_color = "#059669" if len(violations) == 0 else "#dc2626"
    status_bg = "#ecfdf5" if len(violations) == 0 else "#fef2f2"

    # 统计
    word_counts = {}
    files_affected = set()
    for v in violations:
        word_counts[v["word"]] = word_counts.get(v["word"], 0) + 1
        files_affected.add(v["file"])

    # 违规表格行
    violation_rows = ""
    for v in violations:
        replacement = v["replacements"][0] if v["replacements"] else "-"
        ctx = v["content"].replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;").replace("\"", "&quot;")
        # 高亮违规词
        ctx_hl = ctx.replace(v["word"], f'<mark>{v["word"]}</mark>')
        violation_rows += f"""
        <tr>
          <td><code>{v['file']}</code></td>
          <td>{v['line']}</td>
          <td class="word-cell">{v['word']}</td>
          <td class="replacement-cell">{replacement}</td>
          <td class="context-cell">{ctx_hl}</td>
        </tr>"""

    # 统计卡片
    stats_cards = f"""
      <div class="card">
        <div class="card-number">{files_scanned}</div>
        <div class="card-label">文件扫描</div>
      </div>
      <div class="card">
        <div class="card-number">{rules_count}</div>
        <div class="card-label">检查规则</div>
      </div>
      <div class="card">
        <div class="card-number">{len(violations)}</div>
        <div class="card-label">发现违规</div>
      </div>
      <div class="card">
        <div class="card-number">{len(files_affected)}</div>
        <div class="card-label">涉及文件</div>
      </div>"""

    # 词频统计
    word_stats = ""
    for word, count in sorted(word_counts.items(), key=lambda x: -x[1]):
        word_stats += f'<li><strong>{word}</strong> — {count} 次</li>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>敏感词审计报告 — {ts}</title>
<style>
  :root {{ --bg: #f8fafc; --card: #fff; --text: #1e293b; --muted: #64748b; --border: #e2e8f0; --pass: #059669; --fail: #dc2626; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; padding: 24px; }}
  .container {{ max-width: 1100px; margin: 0 auto; }}
  .header {{ background: var(--card); border-radius: 12px; padding: 24px 32px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .header h1 {{ font-size: 22px; margin-bottom: 8px; }}
  .header .meta {{ color: var(--muted); font-size: 13px; }}
  .status-badge {{ display: inline-block; padding: 3px 14px; border-radius: 20px; font-weight: 600; font-size: 13px; background: {status_bg}; color: {status_color}; }}
  .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
  @media (max-width: 640px) {{ .cards {{ grid-template-columns: repeat(2, 1fr); }} }}
  .card {{ background: var(--card); border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .card-number {{ font-size: 32px; font-weight: 700; color: #4f46e5; }}
  .card-label {{ font-size: 13px; color: var(--muted); margin-top: 4px; }}
  .section {{ background: var(--card); border-radius: 12px; padding: 24px 32px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .section h2 {{ font-size: 17px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: left; padding: 10px 12px; background: #f1f5f9; font-weight: 600; color: var(--muted); border-radius: 4px; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); }}
  tr:last-child td {{ border-bottom: none; }}
  code {{ font-size: 12px; background: #f1f5f9; padding: 2px 6px; border-radius: 3px; word-break: break-all; }}
  .word-cell {{ font-weight: 700; color: var(--fail); white-space: nowrap; }}
  .replacement-cell {{ color: var(--pass); white-space: nowrap; }}
  .context-cell {{ max-width: 340px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: monospace; font-size: 12px; }}
  .context-cell mark {{ background: #fecaca; color: #991b1b; padding: 0 2px; border-radius: 2px; }}
  .word-stats {{ list-style: none; columns: 3; column-gap: 32px; }}
  @media (max-width: 640px) {{ .word-stats {{ columns: 2; }} }}
  .word-stats li {{ padding: 4px 0; font-size: 14px; }}
  .footer {{ text-align: center; color: var(--muted); font-size: 12px; padding: 16px; }}
</style>
</head>
<body>
<div class="container">

  <div class="header">
    <h1>敏感词审计报告 <span class="status-badge">{status}</span></h1>
    <div class="meta">
      扫描目标: <code>{Path(target_dir).resolve()}</code> &nbsp;|&nbsp;
      时间: {ts} &nbsp;|&nbsp;
      耗时: {elapsed_ms}ms
    </div>
  </div>

  <div class="cards">{stats_cards}
  </div>

  <div class="section">
    <h2>违规详情</h2>
    <table>
      <thead><tr><th>文件</th><th>行</th><th>敏感词</th><th>建议替换</th><th>上下文</th></tr></thead>
      <tbody>{violation_rows if violation_rows else '<tr><td colspan="5" style="text-align:center;color:var(--pass);padding:24px">✅ 未发现敏感词，检查通过</td></tr>'}
      </tbody>
    </table>
  </div>
{"".join([
    _generate_html_dimension_section(violations, group_by, dimensions) if group_by and dimensions else '',
    f'<div class="section"><h2>词频统计</h2><ul class="word-stats">{word_stats}</ul></div>' if word_stats else '',
])}
  <div class="footer">生成自 sensitive-word-check 技能 · {ts}</div>

</div>
</body>
</html>"""


def _generate_html_dimension_section(violations: list[dict], group_by: str, dimensions: dict) -> str:
    """生成 HTML 维度聚类区块"""
    dim_info = dimensions.get(group_by, {})
    dim_values = dim_info.get("values", {})
    groups: dict[str, list] = {}
    for v in violations:
        d = v.get("dimensions", {}).get(group_by, "unclassified")
        groups.setdefault(d, []).append(v)

    section = f'<div class="section"><h2>维度聚类 — {dim_info.get("description", group_by)}</h2>'
    for val_key, val_label in dim_values.items():
        if val_key in groups:
            gv = groups[val_key]
            words_in_group = set(v["word"] for v in gv)
            items = ""
            for w in sorted(words_in_group):
                count = sum(1 for v in gv if v["word"] == w)
                items += f'<li><strong style="color:#dc2626">{w}</strong> — {count} 次</li>'
            section += f'<h3 style="font-size:14px;color:#64748b;margin:12px 0 4px">{val_label}</h3><ul class="word-stats">{items}</ul>'
    section += "</div>"
    return section


def generate_text_audit_log(violations: list[dict], target_dir: str, rules_count: int, files_scanned: int, elapsed_ms: int) -> str:
    """生成纯文本格式的审计日志（可追加写入 .log 文件）"""
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    status = "PASS" if len(violations) == 0 else "FAIL"
    lines = []
    lines.append(f"[{ts}] AUDIT {status} | target={Path(target_dir).resolve()} | rules={rules_count} | files={files_scanned} | violations={len(violations)} | elapsed={elapsed_ms}ms")
    for v in violations:
        lines.append(f"  VIOLATION file={v['file']} line={v['line']} word=\"{v['word']}\" suggestion={v['replacements'][0] if v['replacements'] else 'N/A'}")
    return "\n".join(lines)


def generate_markdown_report(violations: list[dict], target_dir: str, rules_count: int, group_by: str | None = None, dimensions: dict | None = None) -> str:
    """生成 Markdown 格式报告"""
    lines = [
        f"# 敏感词扫描报告",
        f"",
        f"- **扫描目录**：`{Path(target_dir).resolve()}`",
        f"- **检查词数**：{rules_count}",
        f"- **发现违规**：{len(violations)} 处",
    ]
    if group_by:
        dim_label = (dimensions or {}).get(group_by, {}).get("description", group_by)
        lines.append(f"- **聚类维度**：{dim_label}")
    lines.append("")

    if not violations:
        lines.append("✅ 未发现敏感词，检查通过。")
        return "\n".join(lines)

    # 维度聚类
    if group_by and dimensions:
        lines.append("## 维度聚类")
        lines.append("")
        dim_info = dimensions.get(group_by, {})
        dim_values = dim_info.get("values", {})
        groups: dict[str, list] = {}
        for v in violations:
            d = v.get("dimensions", {}).get(group_by, "unclassified")
            groups.setdefault(d, []).append(v)
        for val_key, val_label in dim_values.items():
            if val_key in groups:
                gv = groups[val_key]
                words_in_group = set(v["word"] for v in gv)
                lines.append(f"### {val_label}")
                for w in sorted(words_in_group):
                    count = sum(1 for v in gv if v["word"] == w)
                    lines.append(f"- **{w}**：{count} 次")
                lines.append("")
        if "unclassified" in groups:
            lines.append("### 未分类")
            lines.append("")

    lines.append("## 违规详情")
    lines.append("")
    lines.append("| 文件 | 行号 | 敏感词 | 建议替换 | 上下文 |")
    lines.append("|------|------|--------|---------|--------|")

    for v in violations:
        ctx = v["content"].replace("|", "\\|")
        lines.append(f"| {v['file']} | {v['line']} | **{v['word']}** | {', '.join(v['replacements'])} | {ctx} |")

    lines.append("")
    lines.append("## 统计")
    lines.append("")
    word_counts = {}
    for v in violations:
        word_counts[v["word"]] = word_counts.get(v["word"], 0) + 1
    for word, count in sorted(word_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- **{word}**：{count} 次")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="敏感词扫描工具")
    parser.add_argument("target", help="目标目录路径")
    parser.add_argument("--custom", "-c", help="自定义词库 JSON 文件路径")
    parser.add_argument("--output", "-o", help="输出 Markdown 报告文件（同 --audit-md）")
    parser.add_argument("--ext", help="额外文件扩展名，逗号分隔 (如 .vue,.jsx)")
    parser.add_argument("--exclude", help="额外排除目录，逗号分隔")
    parser.add_argument("--exclude-file", help="排除的特定文件名，逗号分隔 (如 PROJECT_RULES.md)")
    parser.add_argument("--audit-log", "-a", help="追加审计日志到文本文件 (.log)")
    parser.add_argument("--audit-json", "-j", help="追加审计日志到 JSONL 文件 (.jsonl)")
    parser.add_argument("--audit-md", "-m", help="输出 Markdown 格式审计报告 (.md)")
    parser.add_argument("--audit-html", help="输出自包含 HTML 格式审计报告 (.html)")
    parser.add_argument("--group-by", "-g", help="按维度聚类输出 (risk_type, domain, severity)")
    args = parser.parse_args()

    # 加载词库
    script_dir = Path(__file__).resolve().parent
    default_words = script_dir.parent / "references" / "words.json"
    words_path = args.custom or default_words
    rules = load_rules(str(words_path))
    dimensions = load_dimensions(str(words_path))

    # 验证 --group-by
    group_by = args.group_by
    if group_by and dimensions:
        if group_by not in dimensions:
            print(f"未知维度: {group_by}，可用维度: {', '.join(dimensions.keys())}")
            sys.exit(1)
    elif group_by and not dimensions:
        print("词库未定义维度体系（需要 words.json v2.0+），忽略 --group-by")
        group_by = None

    # 构建扩展名集合
    extensions = DEFAULT_EXTENSIONS.copy()
    if args.ext:
        for ext in args.ext.split(","):
            ext = ext.strip()
            if not ext.startswith("."):
                ext = f".{ext}"
            extensions.add(ext)

    # 构建排除目录集合
    exclude_dirs = DEFAULT_EXCLUDE_DIRS.copy()
    if args.exclude:
        for d in args.exclude.split(","):
            exclude_dirs.add(d.strip())

    # 构建排除文件集合
    exclude_files = set()
    if args.exclude_file:
        for f in args.exclude_file.split(","):
            exclude_files.add(f.strip())

    # 扫描（计时）
    import time
    t0 = time.monotonic()
    violations, files_scanned = scan_directory(args.target, rules, extensions, exclude_dirs, exclude_files)
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    # 终端报告
    report = generate_report(violations, args.target, len(rules), group_by=group_by, dimensions=dimensions)
    print(report)

    # Markdown 报告（--output 或 --audit-md）
    md_path = args.output or args.audit_md
    if md_path:
        md_report = generate_markdown_report(violations, args.target, len(rules), group_by=group_by, dimensions=dimensions)
        Path(md_path).parent.mkdir(parents=True, exist_ok=True)
        Path(md_path).write_text(md_report, encoding="utf-8")
        print(f"📄 Markdown 报告: {Path(md_path).resolve()}")

    # HTML 报告（--audit-html）
    if args.audit_html:
        html_report = generate_html_report(violations, args.target, len(rules), files_scanned, elapsed_ms, group_by=group_by, dimensions=dimensions)
        html_path = Path(args.audit_html)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html_report, encoding="utf-8")
        print(f"🌐 HTML 报告: {html_path.resolve()}")

    # 审计日志（文本格式，追加）
    if args.audit_log:
        text_log = generate_text_audit_log(violations, args.target, len(rules), files_scanned, elapsed_ms)
        log_path = Path(args.audit_log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(text_log + "\n")
        print(f"📋 审计日志(.log): {log_path.resolve()}")

    # 审计日志（JSONL 格式，追加）
    if args.audit_json:
        json_entry = generate_audit_log(violations, args.target, len(rules), files_scanned, elapsed_ms, group_by=group_by)
        jsonl_path = Path(args.audit_json)
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(json_entry, ensure_ascii=False) + "\n")
        print(f"📋 审计日志(.jsonl): {jsonl_path.resolve()}")

    # 返回非零退出码以便 CI/CD 使用
    if violations:
        sys.exit(1)


if __name__ == "__main__":
    main()
