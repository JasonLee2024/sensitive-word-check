#!/usr/bin/env python3
"""
敏感词修复工具 — fix 模式
用法: python fix.py <target_dir> [--custom words.json] [--dry-run] [--yes]
"""

import argparse
import json
import os
import sys
from pathlib import Path

# 同 check.py 的白名单和排除目录
DEFAULT_EXTENSIONS = {".md", ".py", ".js", ".ts", ".html", ".css", ".yaml", ".yml", ".json", ".txt", ".java", ".go", ".rs", ".c", ".cpp", ".sh", ".ps1", ".xml", ".toml", ".ini", ".cfg", ".conf"}
DEFAULT_EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".obsidian", ".trash", ".claude", "dist", "build", "target"}


def load_rules(words_path: str) -> list[dict]:
    path = Path(words_path)
    if not path.exists():
        print(f"错误：词库文件不存在 — {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("rules", [])


def should_scan(filepath: Path, extensions: set, exclude_dirs: set, exclude_files: set) -> bool:
    fname = filepath.name
    if fname in exclude_files:
        return False
    if filepath.suffix.lower() not in extensions:
        return False
    for part in filepath.parts:
        if part in exclude_dirs:
            return False
    try:
        if filepath.stat().st_size > 10 * 1024 * 1024:
            return False
    except Exception:
        return False
    return True


def preview_changes(target_dir: str, rules: list[dict], extensions: set, exclude_dirs: set, exclude_files: set) -> dict:
    """预览将要做的修改，按文件分组"""
    base = Path(target_dir).resolve()
    files = [f for f in base.rglob("*") if f.is_file() and should_scan(f, extensions, exclude_dirs, exclude_files)]
    plan = {}

    for fpath in sorted(files):
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        changes = []
        new_content = content
        for rule in rules:
            word = rule["word"]
            replacement = rule["replacements"][0]  # 默认使用第一个替代词
            if word in new_content:
                count = new_content.count(word)
                changes.append({"word": word, "replacement": replacement, "count": count})
                new_content = new_content.replace(word, replacement)

        if changes:
            rel = str(fpath.relative_to(base))
            plan[rel] = {
                "changes": changes,
                "total_replacements": sum(c["count"] for c in changes),
            }

    return plan


def apply_fixes(target_dir: str, rules: list[dict], extensions: set, exclude_dirs: set, exclude_files: set) -> list[str]:
    """执行替换，返回修改过的文件列表"""
    base = Path(target_dir).resolve()
    files = [f for f in base.rglob("*") if f.is_file() and should_scan(f, extensions, exclude_dirs, exclude_files)]
    modified = []

    for fpath in sorted(files):
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        new_content = content
        for rule in rules:
            word = rule["word"]
            replacement = rule["replacements"][0]
            new_content = new_content.replace(word, replacement)

        if new_content != content:
            fpath.write_text(new_content, encoding="utf-8")
            modified.append(str(fpath.relative_to(base)))

    return modified


def generate_fix_audit_log(plan: dict, modified: list[str], target_dir: str, rules_count: int, elapsed_ms: int, dry_run: bool) -> dict:
    """生成修复操作的审计日志条目（JSON 格式）"""
    from datetime import datetime, timezone

    total_replacements = sum(p["total_replacements"] for p in plan.values())
    return {
        "audit_id": datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")[:20],
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "operation": "DRY_RUN" if dry_run else "FIX",
        "target": str(Path(target_dir).resolve()),
        "result": "DRY_RUN" if dry_run else "FIXED",
        "summary": {
            "rules_checked": rules_count,
            "files_affected": len(plan),
            "total_replacements": total_replacements,
            "files_modified": len(modified),
        },
        "details": [
            {
                "file": fpath,
                "changes": [
                    {"word": c["word"], "replacement": c["replacement"], "count": c["count"]}
                    for c in info["changes"]
                ],
            }
            for fpath, info in plan.items()
        ],
        "modified_files": modified,
        "elapsed_ms": elapsed_ms,
    }


def generate_text_fix_audit_log(plan: dict, modified: list[str], target_dir: str, rules_count: int, elapsed_ms: int, dry_run: bool) -> str:
    """生成修复操作的纯文本审计日志"""
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    op = "DRY_RUN" if dry_run else "FIX"
    total = sum(p["total_replacements"] for p in plan.values())
    lines = [f"[{ts}] {op} | target={Path(target_dir).resolve()} | rules={rules_count} | files_affected={len(plan)} | replacements={total} | files_modified={len(modified)} | elapsed={elapsed_ms}ms"]
    for fpath, info in plan.items():
        for c in info["changes"]:
            lines.append(f"  {op} file={fpath} word=\"{c['word']}\" → \"{c['replacement']}\" count={c['count']}")
    return "\n".join(lines)


def generate_fix_markdown_report(plan: dict, modified: list[str], target_dir: str, rules_count: int, elapsed_ms: int, dry_run: bool) -> str:
    """生成 Markdown 格式的修复审计报告"""
    total = sum(p["total_replacements"] for p in plan.values())
    op = "🔍 预览 (--dry-run)" if dry_run else "🔧 修复执行"

    lines = [
        f"# 敏感词修复报告",
        f"",
        f"- **操作模式**：{op}",
        f"- **扫描目录**：`{Path(target_dir).resolve()}`",
        f"- **检查词数**：{rules_count}",
        f"- **影响文件**：{len(plan)} 个",
        f"- **替换总数**：{total} 处",
        f"- **修改文件**：{len(modified)} 个",
        f"- **耗时**：{elapsed_ms}ms",
        f"",
    ]

    if not plan:
        lines.append("✅ 未发现敏感词，无需修复。")
        return "\n".join(lines)

    lines.append("## 修改详情")
    lines.append("")
    lines.append("| 文件 | 敏感词 | 替换为 | 次数 |")
    lines.append("|------|--------|--------|------|")

    for fpath, info in plan.items():
        for c in info["changes"]:
            lines.append(f"| {fpath} | **{c['word']}** | {c['replacement']} | {c['count']} |")

    if modified:
        lines.append("")
        lines.append("## 已修改文件")
        lines.append("")
        for f in modified:
            lines.append(f"- `{f}`")

    lines.append("")
    lines.append("## 词频统计")
    lines.append("")
    word_counts = {}
    for info in plan.values():
        for c in info["changes"]:
            word_counts[c["word"]] = word_counts.get(c["word"], 0) + c["count"]
    for word, count in sorted(word_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- **{word}**：{count} 次")

    return "\n".join(lines)


def generate_fix_html_report(plan: dict, modified: list[str], target_dir: str, rules_count: int, elapsed_ms: int, dry_run: bool) -> str:
    """生成自包含 HTML 格式的修复审计报告"""
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    total = sum(p["total_replacements"] for p in plan.values())
    op_label = "DRY_RUN" if dry_run else "FIXED"
    status_color = "#059669" if not dry_run else "#d97706"
    status_bg = "#ecfdf5" if not dry_run else "#fffbeb"

    # 修改详情表格行
    fix_rows = ""
    for fpath, info in plan.items():
        for c in info["changes"]:
            fix_rows += f"""
        <tr>
          <td><code>{fpath}</code></td>
          <td class="word-cell">{c['word']}</td>
          <td class="replacement-cell">{c['replacement']}</td>
          <td>{c['count']}</td>
        </tr>"""

    # 统计卡片
    stats_cards = f"""
      <div class="card">
        <div class="card-number">{rules_count}</div>
        <div class="card-label">检查规则</div>
      </div>
      <div class="card">
        <div class="card-number">{len(plan)}</div>
        <div class="card-label">影响文件</div>
      </div>
      <div class="card">
        <div class="card-number">{total}</div>
        <div class="card-label">替换总数</div>
      </div>
      <div class="card">
        <div class="card-number">{len(modified)}</div>
        <div class="card-label">已修改文件</div>
      </div>"""

    # 词频统计
    word_counts = {}
    for info in plan.values():
        for c in info["changes"]:
            word_counts[c["word"]] = word_counts.get(c["word"], 0) + c["count"]
    word_stats = ""
    for word, count in sorted(word_counts.items(), key=lambda x: -x[1]):
        word_stats += f'<li><strong>{word}</strong> — {count} 次</li>'

    # 已修改文件列表
    modified_list = ""
    if modified:
        for f in modified:
            modified_list += f'<li><code>{f}</code></li>'
    else:
        modified_list = '<li style="color:#64748b">无（--dry-run 模式，未实际修改）</li>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>敏感词修复报告 — {ts}</title>
<style>
  :root {{ --bg: #f8fafc; --card: #fff; --text: #1e293b; --muted: #64748b; --border: #e2e8f0; --pass: #059669; --warn: #d97706; }}
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
  .word-cell {{ font-weight: 700; color: var(--warn); white-space: nowrap; }}
  .replacement-cell {{ color: var(--pass); white-space: nowrap; }}
  .word-stats {{ list-style: none; columns: 3; column-gap: 32px; }}
  @media (max-width: 640px) {{ .word-stats {{ columns: 2; }} }}
  .word-stats li {{ padding: 4px 0; font-size: 14px; }}
  .modified-list {{ list-style: none; }}
  .modified-list li {{ padding: 4px 0; font-size: 13px; }}
  .footer {{ text-align: center; color: var(--muted); font-size: 12px; padding: 16px; }}
</style>
</head>
<body>
<div class="container">

  <div class="header">
    <h1>敏感词修复报告 <span class="status-badge">{op_label}</span></h1>
    <div class="meta">
      扫描目标: <code>{Path(target_dir).resolve()}</code> &nbsp;|&nbsp;
      时间: {ts} &nbsp;|&nbsp;
      耗时: {elapsed_ms}ms
    </div>
  </div>

  <div class="cards">{stats_cards}
  </div>

  <div class="section">
    <h2>修改详情</h2>
    <table>
      <thead><tr><th>文件</th><th>敏感词</th><th>替换为</th><th>次数</th></tr></thead>
      <tbody>{fix_rows if fix_rows else '<tr><td colspan="4" style="text-align:center;color:var(--pass);padding:24px">✅ 未发现敏感词，无需修复</td></tr>'}
      </tbody>
    </table>
  </div>

  <div class="section">
    <h2>已修改文件</h2>
    <ul class="modified-list">{modified_list}</ul>
  </div>

{"".join([
    f'<div class="section"><h2>词频统计</h2><ul class="word-stats">{word_stats}</ul></div>' if word_stats else ''
])}
  <div class="footer">生成自 sensitive-word-check 技能 · {ts}</div>

</div>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="敏感词修复工具")
    parser.add_argument("target", help="目标目录路径")
    parser.add_argument("--custom", "-c", help="自定义词库 JSON 文件路径")
    parser.add_argument("--dry-run", "-n", action="store_true", help="仅预览，不实际修改")
    parser.add_argument("--yes", "-y", action="store_true", help="跳过确认，直接执行")
    parser.add_argument("--ext", help="额外文件扩展名，逗号分隔")
    parser.add_argument("--exclude", help="额外排除目录，逗号分隔")
    parser.add_argument("--exclude-file", help="排除的特定文件名，逗号分隔 (如 PROJECT_RULES.md)")
    parser.add_argument("--audit-log", "-a", help="追加审计日志到文本文件 (.log)")
    parser.add_argument("--audit-json", "-j", help="追加审计日志到 JSONL 文件 (.jsonl)")
    parser.add_argument("--audit-md", "-m", help="输出 Markdown 格式审计报告 (.md)")
    parser.add_argument("--audit-html", help="输出自包含 HTML 格式审计报告 (.html)")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    default_words = script_dir.parent / "references" / "words.json"
    words_path = args.custom or default_words
    rules = load_rules(str(words_path))

    extensions = DEFAULT_EXTENSIONS.copy()
    if args.ext:
        for ext in args.ext.split(","):
            ext = ext.strip()
            if not ext.startswith("."):
                ext = f".{ext}"
            extensions.add(ext)

    exclude_dirs = DEFAULT_EXCLUDE_DIRS.copy()
    if args.exclude:
        for d in args.exclude.split(","):
            exclude_dirs.add(d.strip())

    exclude_files = set()
    if args.exclude_file:
        for f in args.exclude_file.split(","):
            exclude_files.add(f.strip())

    # 预览
    import time
    t0 = time.monotonic()
    plan = preview_changes(args.target, rules, extensions, exclude_dirs, exclude_files)
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    if not plan:
        print("✅ 未发现敏感词，无需修复。")
        return

    # 打印预览
    total = sum(p["total_replacements"] for p in plan.values())
    print("=" * 60)
    print("  敏感词修复预览")
    print("=" * 60)
    print(f"  目标目录 : {Path(args.target).resolve()}")
    print(f"  影响文件 : {len(plan)} 个")
    print(f"  替换总数 : {total} 处")
    print("=" * 60)
    print()

    for fpath, info in plan.items():
        print(f"📄 {fpath}")
        for c in info["changes"]:
            print(f"   {c['word']} → {c['replacement']} ({c['count']} 处)")
        print()

    modified = []

    if args.dry_run:
        print("🔍 --dry-run 模式：以上为预览，未实际修改。")
    else:
        # 确认
        if not args.yes:
            print(f"即将在 {len(plan)} 个文件中替换 {total} 处敏感词。")
            response = input("确认执行？[y/N] ").strip().lower()
            if response not in ("y", "yes"):
                print("已取消。")
                return

        # 执行
        modified = apply_fixes(args.target, rules, extensions, exclude_dirs, exclude_files)
        print()
        print(f"✅ 修复完成！共修改 {len(modified)} 个文件，{total} 处替换。")
        print()
        for f in modified:
            print(f"  ✓ {f}")

    # 审计日志（文本格式）
    if args.audit_log:
        text_log = generate_text_fix_audit_log(plan, modified, args.target, len(rules), elapsed_ms, args.dry_run)
        log_path = Path(args.audit_log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(text_log + "\n")
        print(f"\n📋 审计日志: {log_path.resolve()}")

    # 审计日志（JSONL 格式）
    if args.audit_json:
        json_entry = generate_fix_audit_log(plan, modified, args.target, len(rules), elapsed_ms, args.dry_run)
        jsonl_path = Path(args.audit_json)
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(json_entry, ensure_ascii=False) + "\n")
        print(f"📋 审计日志(JSONL): {jsonl_path.resolve()}")

    # Markdown 报告
    if args.audit_md:
        md_report = generate_fix_markdown_report(plan, modified, args.target, len(rules), elapsed_ms, args.dry_run)
        md_path = Path(args.audit_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(md_report, encoding="utf-8")
        print(f"📄 Markdown 报告: {md_path.resolve()}")

    # HTML 报告
    if args.audit_html:
        html_report = generate_fix_html_report(plan, modified, args.target, len(rules), elapsed_ms, args.dry_run)
        html_path = Path(args.audit_html)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html_report, encoding="utf-8")
        print(f"🌐 HTML 报告: {html_path.resolve()}")


if __name__ == "__main__":
    main()
