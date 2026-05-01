#!/usr/bin/env python3
"""sensitive-word-check 共享模块 — check.py 和 fix.py 的公共依赖"""

import json
import sys
import unicodedata
from pathlib import Path

# ── 文件扩展名白名单 ──────────────────────────────────────────
DEFAULT_EXTENSIONS = {
    ".md", ".py", ".js", ".ts", ".html", ".css", ".yaml", ".yml",
    ".json", ".txt", ".java", ".go", ".rs", ".c", ".cpp", ".sh",
    ".ps1", ".xml", ".toml", ".ini", ".cfg", ".conf",
}

# ── 默认排除目录 ──────────────────────────────────────────────
DEFAULT_EXCLUDE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".obsidian", ".trash", ".claude", "dist", "build", "target",
}

# ── 行内跳过标记 ──────────────────────────────────────────────
SKIP_COMMENT = "# no-sensitive-check"


def normalize(text: str) -> str:
    """Unicode NFKC 归一化：全角 ASCII → 半角，兼容字符 → 标准形式。纯标准库，零依赖。"""
    return unicodedata.normalize("NFKC", text)


def load_rules(words_path: str) -> list[dict]:
    """加载敏感词规则，并对词本身做 NFKC 归一化"""
    path = Path(words_path)
    if not path.exists():
        print(f"错误：词库文件不存在 — {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    rules = data.get("rules", [])
    for rule in rules:
        rule["word"] = normalize(rule["word"])
    return rules


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
    # 按文件名或相对路径匹配排除
    if filepath.name in exclude_files:
        return False
    # 检查扩展名
    if filepath.suffix.lower() not in extensions:
        return False
    # 检查是否在排除目录中
    for part in filepath.parts:
        if part in exclude_dirs:
            return False
    # 跳过 > 10MB 的文件
    try:
        if filepath.stat().st_size > 10 * 1024 * 1024:
            return False
    except Exception:
        return False
    return True


def build_extensions(user_ext: str | None, base: set) -> set:
    """解析 --ext 参数，扩展文件类型集合"""
    result = base.copy()
    if user_ext:
        for ext in user_ext.split(","):
            ext = ext.strip()
            if not ext.startswith("."):
                ext = f".{ext}"
            result.add(ext)
    return result


def build_exclude_dirs(user_exclude: str | None, base: set) -> set:
    """解析 --exclude 参数，扩展排除目录集合"""
    result = base.copy()
    if user_exclude:
        for d in user_exclude.split(","):
            result.add(d.strip())
    return result


def build_exclude_files(user_exclude_file: str | None) -> set:
    """解析 --exclude-file 参数"""
    result = set()
    if user_exclude_file:
        for f in user_exclude_file.split(","):
            result.add(f.strip())
    return result


def resolve_words_path(custom: str | None, script_dir: Path) -> str:
    """解析词库路径：--custom 优先，否则使用默认 words.json"""
    if custom:
        return custom
    return str(script_dir.parent / "references" / "words.json")


def line_should_skip(line: str) -> bool:
    """检查行是否包含跳过标记"""
    return SKIP_COMMENT in line
