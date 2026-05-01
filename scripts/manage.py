#!/usr/bin/env python3
"""
敏感词词库管理工具
用法:
  python manage.py list                        # 列出所有敏感词
  python manage.py dimensions                  # 列出可用维度及其值
  python manage.py cluster --by risk_type      # 按维度聚类展示
  python manage.py add <词> -r <替换词>        # 添加新词
  python manage.py remove <词>                 # 删除敏感词
  python manage.py update <词> -r <替换词>     # 更新敏感词
"""

import argparse
import json
import sys
from pathlib import Path


def load_words(words_path: Path) -> dict:
    with open(words_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_words(words_path: Path, data: dict):
    with open(words_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def find_rule(rules: list[dict], word: str) -> int:
    for i, r in enumerate(rules):
        if r["word"] == word:
            return i
    return -1


def auto_extend_dimensions(data: dict, rule_dimensions: dict) -> list[str]:
    """如果新增词的维度值不在现有维度定义中，自动扩展维度目录。
    返回新增的维度值列表，用于告知用户。
    """
    if "dimensions" not in data:
        # 词库版本 < 2.0，自动初始化维度体系
        data["dimensions"] = {
            "risk_type": {
                "description": "风险类型 — 该词触发的负面联想类别",
                "values": {},
            },
            "domain": {
                "description": "语义领域 — 该词所属的概念领域",
                "values": {},
            },
            "severity": {
                "description": "严重程度 — 该词在审查中的敏感等级",
                "values": {},
            },
        }

    added = []
    dims_catalog = data["dimensions"]

    for dim_key, dim_value in rule_dimensions.items():
        if dim_key not in dims_catalog:
            # 维度本身不存在，创建新维度
            dims_catalog[dim_key] = {
                "description": f"自定义维度 — {dim_key}",
                "values": {},
            }

        values = dims_catalog[dim_key].get("values", {})
        if dim_value not in values:
            # 自动为新维度值生成标签
            values[dim_value] = f"[自定义] {dim_value}"
            added.append(f"{dim_key}={dim_value}")

    return added


def get_available_dimensions(data: dict) -> dict | None:
    return data.get("dimensions", None)


def cmd_list(words_path: Path, group_by: str | None = None):
    """列出所有敏感词"""
    data = load_words(words_path)
    rules = data.get("rules", [])
    dims = get_available_dimensions(data)

    if not rules:
        print("词库为空")
        return

    if group_by and dims and group_by in dims:
        # 按维度聚类输出
        _print_clustered(rules, dims, group_by)
        return

    print(f"共 {len(rules)} 个敏感词:\n")
    for i, r in enumerate(rules, 1):
        _print_rule(r, i, dims)
        print()


def _print_rule(rule: dict, index: int, dims: dict | None = None):
    """打印单条规则"""
    print(f"  {index}. {rule['word']}")
    print(f"     替代词: {', '.join(rule['replacements'])}")
    if dims and rule.get("dimensions"):
        d = rule["dimensions"]
        dim_tags = []
        for k, v in d.items():
            label = dims.get(k, {}).get("values", {}).get(v, v)
            dim_tags.append(f"{k}={v}")
        print(f"     维度: {', '.join(dim_tags)}")
    print(f"     语境: {rule.get('context', '-')}")
    print(f"     说明: {rule.get('note', '-')}")


def _print_clustered(rules: list[dict], dims: dict, group_by: str):
    """按指定维度聚类输出"""
    dim_info = dims.get(group_by, {})
    values = dim_info.get("values", {})

    # 按维度值分组
    groups: dict[str, list] = {}
    for r in rules:
        dim = r.get("dimensions", {}).get(group_by, "unclassified")
        groups.setdefault(dim, []).append(r)

    print(f"按「{dim_info.get('description', group_by)}」聚类:\n")

    for val_key in values:
        if val_key in groups:
            val_label = values[val_key]
            print(f"▸ {val_key} — {val_label}")
            for r in groups[val_key]:
                print(f"    • {r['word']} → {', '.join(r['replacements'])}")
                print(f"      {r.get('note', '')}")
            print()

    if "unclassified" in groups:
        print("▸ 未分类")
        for r in groups["unclassified"]:
            print(f"    • {r['word']} → {', '.join(r['replacements'])}")
        print()


def cmd_dimensions(words_path: Path):
    """列出所有可用维度"""
    data = load_words(words_path)
    dims = get_available_dimensions(data)

    if not dims:
        print("词库尚未定义维度体系（版本 < 2.0）")
        return

    print(f"共 {len(dims)} 个维度:\n")
    for dim_key, dim_info in dims.items():
        print(f"  ▸ {dim_key}")
        print(f"    {dim_info['description']}")
        for val_key, val_label in dim_info["values"].items():
            # 统计该维度下有多少词
            count = sum(
                1 for r in data.get("rules", [])
                if r.get("dimensions", {}).get(dim_key) == val_key
            )
            print(f"      {val_key} ({count} 个词) — {val_label}")
        print()


def cmd_add(
    words_path: Path,
    word: str,
    replacements: list[str],
    context: str = "general",
    note: str = "",
    risk_type: str | None = None,
    domain: str | None = None,
    severity: str | None = None,
):
    """添加敏感词"""
    data = load_words(words_path)
    rules = data.get("rules", [])

    if find_rule(rules, word) != -1:
        print(f"错误：「{word}」已存在于词库中。使用 update 命令修改。")
        sys.exit(1)

    entry: dict = {
        "word": word,
        "replacements": replacements,
        "context": context,
        "note": note,
    }

    # 添加维度
    if risk_type or domain or severity:
        dims = {}
        if risk_type:
            dims["risk_type"] = risk_type
        if domain:
            dims["domain"] = domain
        if severity:
            dims["severity"] = severity
        entry["dimensions"] = dims

        # 自动扩展维度目录
        new_dims = auto_extend_dimensions(data, dims)
        if new_dims:
            for nd in new_dims:
                print(f"📝 自动扩展维度目录：{nd}（可在 words.json 中修改描述）")

    rules.append(entry)
    data["rules"] = rules
    save_words(words_path, data)
    print(f"✅ 已添加：「{word}」→ {', '.join(replacements)}")


def cmd_remove(words_path: Path, word: str):
    """删除敏感词"""
    data = load_words(words_path)
    rules = data.get("rules", [])

    idx = find_rule(rules, word)
    if idx == -1:
        print(f"错误：「{word}」不在词库中。")
        sys.exit(1)

    removed = rules.pop(idx)
    data["rules"] = rules
    save_words(words_path, data)
    print(f"✅ 已删除：「{removed['word']}」（原替代词: {', '.join(removed['replacements'])}）")


def cmd_update(
    words_path: Path,
    word: str,
    replacements: list[str] | None = None,
    context: str | None = None,
    note: str | None = None,
    risk_type: str | None = None,
    domain: str | None = None,
    severity: str | None = None,
):
    """更新敏感词"""
    data = load_words(words_path)
    rules = data.get("rules", [])

    idx = find_rule(rules, word)
    if idx == -1:
        print(f"错误：「{word}」不在词库中。使用 add 命令添加。")
        sys.exit(1)

    if replacements:
        rules[idx]["replacements"] = replacements
    if context is not None:
        rules[idx]["context"] = context
    if note is not None:
        rules[idx]["note"] = note

    # 更新维度
    if risk_type or domain or severity:
        dims = rules[idx].get("dimensions", {})
        if risk_type:
            dims["risk_type"] = risk_type
        if domain:
            dims["domain"] = domain
        if severity:
            dims["severity"] = severity
        rules[idx]["dimensions"] = dims

        # 自动扩展维度目录
        new_dims = auto_extend_dimensions(data, dims)
        if new_dims:
            for nd in new_dims:
                print(f"📝 自动扩展维度目录：{nd}（可在 words.json 中修改描述）")

    data["rules"] = rules
    save_words(words_path, data)
    print(f"✅ 已更新：「{word}」")
    dims = get_available_dimensions(data)
    _print_rule(rules[idx], 0, dims)


def main():
    parser = argparse.ArgumentParser(description="敏感词词库管理工具")
    sub = parser.add_subparsers(dest="command", help="操作命令")

    # list
    p_list = sub.add_parser("list", help="列出所有敏感词")
    p_list.add_argument("--by", help="按维度聚类展示 (如 risk_type, domain, severity)")

    # dimensions
    sub.add_parser("dimensions", help="列出所有可用维度及其值")

    # cluster
    p_cluster = sub.add_parser("cluster", help="按维度聚类展示敏感词")
    p_cluster.add_argument("--by", required=True, help="聚类维度 (如 risk_type, domain, severity)")

    # add
    p_add = sub.add_parser("add", help="添加敏感词")
    p_add.add_argument("word", help="敏感词")
    p_add.add_argument("-r", "--replacements", required=True, help="替代词，逗号分隔")
    p_add.add_argument("--context", default="general", help="语境分类 (默认 general)")
    p_add.add_argument("--note", default="", help="替换理由/备注")
    p_add.add_argument("--risk-type", help="风险类型: security / privacy / legal")
    p_add.add_argument("--domain", help="语义领域: intelligence / surveillance / data_collection / cyber")
    p_add.add_argument("--severity", help="严重程度: high / medium / low")

    # remove
    p_rm = sub.add_parser("remove", help="删除敏感词")
    p_rm.add_argument("word", help="要删除的敏感词")

    # update
    p_up = sub.add_parser("update", help="更新敏感词")
    p_up.add_argument("word", help="要更新的敏感词")
    p_up.add_argument("-r", "--replacements", help="新的替代词，逗号分隔")
    p_up.add_argument("--context", help="新的语境分类")
    p_up.add_argument("--note", help="新的说明/备注")
    p_up.add_argument("--risk-type", help="修改风险类型")
    p_up.add_argument("--domain", help="修改语义领域")
    p_up.add_argument("--severity", help="修改严重程度")

    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    words_path = script_dir.parent / "references" / "words.json"

    if not words_path.exists():
        print(f"错误：词库文件不存在 — {words_path}")
        sys.exit(1)

    match args.command:
        case "list":
            cmd_list(words_path, group_by=getattr(args, "by", None))
        case "dimensions":
            cmd_dimensions(words_path)
        case "cluster":
            data = load_words(words_path)
            dims = get_available_dimensions(data)
            if not dims:
                print("词库尚未定义维度体系")
                sys.exit(1)
            if args.by not in dims:
                print(f"未知维度: {args.by}，可用维度: {', '.join(dims.keys())}")
                sys.exit(1)
            _print_clustered(data["rules"], dims, args.by)
        case "add":
            replacements = [r.strip() for r in args.replacements.split(",")]
            cmd_add(
                words_path, args.word, replacements, args.context, args.note,
                risk_type=getattr(args, "risk_type", None),
                domain=getattr(args, "domain", None),
                severity=getattr(args, "severity", None),
            )
        case "remove":
            cmd_remove(words_path, args.word)
        case "update":
            replacements = None
            if args.replacements:
                replacements = [r.strip() for r in args.replacements.split(",")]
            cmd_update(
                words_path, args.word, replacements, args.context, args.note,
                risk_type=getattr(args, "risk_type", None),
                domain=getattr(args, "domain", None),
                severity=getattr(args, "severity", None),
            )
        case None:
            parser.print_help()
            sys.exit(1)


if __name__ == "__main__":
    main()
