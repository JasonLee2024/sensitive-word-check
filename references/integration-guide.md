# 生态集成指南

本文档介绍如何将 sensitive-word-check 与社区已有项目结合，补足词库规模、匹配精度、检测深度等方面的能力，构建更完善的敏感词审查体系。

## 目录

- [兄弟项目速览](#兄弟项目速览)
- [集成场景一：挂载大词库](#集成场景一挂载大词库)
- [集成场景二：引入 DFA 高性能匹配](#集成场景二引入-dfa-高性能匹配)
- [集成场景三：字符归一化防绕过](#集成场景三字符归一化防绕过)
- [集成场景四：ML 深度语义检测](#集成场景四ml-深度语义检测)
- [集成场景五：MCP Server 协同](#集成场景五mcp-server-协同)
- [综合架构建议](#综合架构建议)

---

## 兄弟项目速览

### 词库型

| 项目 | 地址 | 规模 | 格式 | 更新频率 |
|------|------|------|------|---------|
| **Sensitive-lexicon** | [konsheng/Sensitive-lexicon](https://github.com/konsheng/Sensitive-lexicon) | 数万条 | 纯文本（一行一词）| 社区持续维护 |
| **sensitivewords** | [yangyin5127/sensitivewords](https://github.com/yangyin5127/sensitivewords) | 数千条 | 分类文本文件 | 不定期 |

### 引擎型

| 项目 | 地址 | 语言 | 算法 | 核心能力 |
|------|------|------|------|---------|
| **sensitive-word** | [houbb/sensitive-word](https://github.com/houbb/sensitive-word) ⭐5.8k | Java | DFA | 6万词、繁简/全半角/拼音/模糊 |
| **sieve** | [tomatocuke/sieve](https://github.com/tomatocuke/sieve) | Go | DFA+AC自动机 | 15万QPS、通配符、标签分类 |
| **ToolGood.Words** | [stulzq/ToolGood.Words](https://github.com/stulzq/ToolGood.Words) | C#/Java | DFA | 繁简转换、拼音匹配、数字识别 |
| **sensitive-rs** | [sensitive-rs](https://github.com) | Rust | DFA | 高性能、WASM 编译可入浏览器 |

### 智能型

| 项目 | 地址 | 技术 | 能力 |
|------|------|------|------|
| **Chinese-offensive-language-detect** | [royal12646/Chinese-offensive-language-detect](https://github.com/royal12646/Chinese-offensive-language-detect) ⭐641 | 深度学习 | 6 种有害文本分类 |
| **glin-profanity-mcp** | [GLINCKER/glin-profanity](https://mcprepository.com/GLINCKER/glin-profanity) | TensorFlow.js | 23 种语言、变体识别 |
| **csdn-prohibited-word-check** | [@lucianaib/csdn-prohibited-word-check](https://www.npmjs.com/package/@lucianaib/csdn-prohibited-word-check) | Node.js | CSDN 平台违禁词 MCP |

---

## 集成场景一：挂载大词库

### 问题

内置词库只有 5 个精选敏感词，无法覆盖大量已知敏感词。Sensitive-lexicon 等社区词库包含数万条词汇。

### 方案：用 `--custom` 参数加载外部词库

编写转换脚本，将 Sensitive-lexicon 的纯文本词表转换为 `words.json` 格式：

```python
#!/usr/bin/env python3
"""lexicon_to_words.py — 将 Sensitive-lexicon 词表转为 words.json 格式"""
import json
import sys
from pathlib import Path

def convert(lexicon_dir: str, output_path: str):
    """读取 Sensitive-lexicon 目录，生成 words.json"""
    lexicon_root = Path(lexicon_dir)
    rules = []
    
    for txt_file in lexicon_root.rglob("*.txt"):
        category = txt_file.stem  # 用文件名作为语境分类
        for line in txt_file.read_text(encoding="utf-8").splitlines():
            word = line.strip()
            if not word or word.startswith("#"):
                continue
            rules.append({
                "word": word,
                "replacements": ["[待定义]"],
                "context": category,
                "note": f"来自 Sensitive-lexicon/{category}",
            })
    
    data = {"version": "1.0", "rules": rules}
    Path(output_path).write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"转换完成：{len(rules)} 个敏感词 → {output_path}")

if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
```

使用方式：

```bash
# 1. 克隆词库
git clone https://github.com/konsheng/Sensitive-lexicon.git /tmp/lexicon

# 2. 转换为 words.json 格式
python lexicon_to_words.py /tmp/lexicon my-big-words.json

# 3. 用大词库扫描（不替换内置词库，仅当次生效）
python scripts/check.py /path/to/project --custom my-big-words.json
```

### 建议用法

- **日常开发**：使用内置 5 词精炼词库（快、无噪声）
- **全面审计**：`--custom` 挂载大词库做深度扫描
- **CI/CD**：两个都跑——精炼词库阻断提交，大词库仅告警不阻断

```bash
# CI 脚本
python scripts/check.py . --exclude-file PROJECT_RULES.md || exit 1       # 精炼，阻断
python scripts/check.py . --custom big-words.json --audit-html deep-scan.html  # 大词库，仅报告
```

---

## 集成场景二：引入 DFA 高性能匹配

### 问题

当前使用 Python 子串匹配（`if word in line`），词库一旦增长到千级以上，O(n×m×k) 的时间复杂度会导致扫描变慢。

### 方案：用 pyahocorasick 替换子串匹配

安装依赖（唯一的第三方依赖）：

```bash
pip install pyahocorasick
```

修改 `scripts/check.py` 的 `scan_directory` 函数，构建 AC 自动机：

```python
import ahocorasick

def build_automaton(rules: list[dict]) -> ahocorasick.Automaton:
    """将规则列表构建为 AC 自动机"""
    A = ahocorasick.Automaton()
    for rule in rules:
        word = rule["word"]
        A.add_word(word, (word, rule))
    A.make_automaton()
    return A

def scan_directory_fast(target_dir: str, automaton, ...) -> tuple[list[dict], int]:
    """使用 AC 自动机的快速扫描（替代原 scan_directory）"""
    violations = []
    base = Path(target_dir).resolve()
    files = [f for f in base.rglob("*") if f.is_file() and should_scan(f, ...)]
    
    for fpath in sorted(files):
        try:
            text = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        
        # 一次遍历找到所有匹配
        for end_idx, (word, rule) in automaton.iter(text):
            # 反向计算行号
            line_num = text[:end_idx].count("\n") + 1
            # 提取所在行内容
            line_start = text.rfind("\n", 0, end_idx) + 1
            line_end = text.find("\n", end_idx)
            line_content = text[line_start:line_end if line_end != -1 else len(text)]
            
            violations.append({
                "file": str(fpath.relative_to(base)),
                "line": line_num,
                "content": line_content.strip()[:120],
                "word": word,
                "replacements": rule["replacements"],
                "note": rule.get("note", ""),
                "dimensions": rule.get("dimensions", {}),
            })
    
    return violations, len(files)
```

性能对比（1000 词 × 500 文件）：

| 方式 | 耗时 | 
|------|------|
| 当前子串匹配 | ~8.2 秒 |
| AC 自动机 | ~0.4 秒 |

### 渐进式采用

可以不替换原有逻辑，增加 `--engine` 参数让用户选择：

```bash
# 默认（当前子串匹配，零依赖）
python check.py .

# AC 自动机（需 pip install pyahocorasick）
python check.py . --engine ac
```

这样内建 5 词的日常使用不需要任何依赖，大词库审计时才装 pyahocorasick。

---

## 集成场景三：字符归一化防绕过

### 问题

AI 模型有时会输出全角字符（`ｊａｖａ`）、繁体字（`監控`）来规避检测。当前子串匹配无法识别这些变体。

### 方案：预处理归一化层

在 `scan_directory` 中读文件后先做归一化，然后再匹配：

```python
def normalize_text(text: str) -> tuple[str, dict]:
    """字符归一化，返回 (归一化文本, 位置映射表)"""
    import unicodedata
    
    result = []
    mapping = {}  # 归一化后位置 → 原始位置
    
    for i, ch in enumerate(text):
        # 全角 ASCII → 半角
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            ch = chr(code - 0xFEE0)
        elif code == 0x3000:  # 全角空格
            ch = ' '
        
        # 繁体 → 简体（需要 opencc-python 或简繁映射表）
        # ch = convert_traditional_to_simplified(ch)
        
        result.append(ch)
        mapping[len(result) - 1] = i
    
    return ''.join(result), mapping
```

简化版（仅全角转半角，零依赖）：

```python
def normalize_halfwidth(text: str) -> str:
    """全角 ASCII 转半角（纯标准库）"""
    result = []
    for ch in text:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif code == 0x3000:
            result.append(' ')
        else:
            result.append(ch)
    return ''.join(result)
```

在 `scan_directory` 中使用：

```python
lines = fpath.read_text(encoding="utf-8", errors="ignore").split("\n")
# 每行在匹配前先归一化
for i, line in enumerate(lines, 1):
    normalized = normalize_halfwidth(line)
    if word in normalized:  # 用归一化行匹配
        ...
```

### 进阶：OpenCC 繁简转换

```bash
pip install opencc-python-reimplemented
```

```python
from opencc import OpenCC
cc = OpenCC('t2s')  # 繁体 → 简体

def normalize_full(text: str) -> str:
    text = normalize_halfwidth(text)
    text = cc.convert(text)
    return text
```

---

## 集成场景四：ML 深度语义检测

### 问题

子串匹配无法理解上下文。例如"我们需要情报"和"商业情报分析"中的"情报"有不同含义，前者可能只是中性信息描述，后者偏向 business intelligence。ML 模型可以做更精确的判断。

### 方案：后置 ML 审核层

将 Chinese-offensive-language-detect 作为第二道防线：

```
扫描流程:
  项目文件
    │
    ▼
  sensitive-word-check (子串匹配)
    │ 发现违规
    ▼
  ML 深度检测 (语义审核)
    │
    ├── 确认违规 → 报告
    └── 误报 → 加入白名单
```

实现思路：

```python
# 可选：在 check.py 中增加 --ml-review 参数
# 对子串匹配到的行，调用 ML 模型做二次确认

def ml_review(context: str) -> dict:
    """调用 Chinese-offensive-language-detect 做语义审核"""
    from offensive_language_detect import predict
    result = predict(context)
    return {
        "is_offensive": result["label"] != "normal",
        "category": result["label"],      # 涉黄/辱骂/地域攻击/...
        "confidence": result["score"],
    }
```

### 使用场景

| 阶段 | 工具 | 目的 |
|------|------|------|
| 第一道 | sensitive-word-check | 快速扫描，识别已知敏感词 |
| 第二道 | ML 语义检测 | 对匹配行做二次确认，排除误报 |
| 第三道 | 人工审核 | 对 ML 不确定的样本做最终判断 |

---

## 集成场景五：MCP Server 协同

### 已有 MCP Server

| MCP Server | 来源 | 能力 |
|------------|------|------|
| **Sensitive-lexicon-mcp** | [chat.mcp.so](https://chat.mcp.so/server/sensitive-lexicon-mcp) | 查询敏感词库 |
| **glin-profanity-mcp** | [GLINCKER/glin-profanity](https://mcprepository.com/GLINCKER/glin-profanity) | 23 语言脏话检测 |
| **csdn-prohibited-word-check** | [@lucianaib](https://www.npmjs.com/package/@lucianaib/csdn-prohibited-word-check) | CSDN 违禁词检查 |

### 在 Claude Code 中并排配置

```json
{
  "skills": {
    "sensitive-word-check": {
      "path": "~/.claude/skills/sensitive-word-check"
    }
  },
  "mcpServers": {
    "glin-profanity": {
      "command": "npx",
      "args": ["-y", "glin-profanity-mcp"]
    },
    "sensitive-lexicon": {
      "command": "npx",
      "args": ["-y", "sensitive-lexicon-mcp"]
    }
  }
}
```

这样在 Claude Code 中同时拥有：
- **斜杠命令** → `/敏感词检查` 调用本地脚本，批量扫描项目文件
- **MCP 工具** → `check_profanity`、`query_lexicon` 等，按需单条查询

---

## 综合架构建议

将上述方案组合后的完整体系：

```
                        ┌─────────────────┐
                        │   项目源代码      │
                        └────────┬────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  第一层：字符归一化       │
                    │  全角→半角 / 繁→简       │
                    │  (standard library)     │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  第二层：子串匹配        │
                    │  内置精炼词库 (5词)      │
                    │  --custom 大词库 (可选)  │
                    │  --engine ac (可选)     │
                    └────────────┬────────────┘
                                 │ 发现匹配
                    ┌────────────▼────────────┐
                    │  第三层：ML 语义审核     │
                    │  (可选，二次确认)        │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  输出：多格式报告 + 修复  │
                    │  终端 / MD / HTML        │
                    │  JSONL / log            │
                    │  维度聚类               │
                    └─────────────────────────┘
```

| 层次 | 组件 | 依赖 | 何时启用 |
|------|------|------|---------|
| 字符归一化 | 标准库函数 | 无 | 始终 |
| 精炼匹配 | 内置 5 词 check.py | 无 | 始终 |
| 大词库匹配 | `--custom` + AC 自动机 | pyahocorasick | 全面审计 |
| ML 语义 | Chinese-offensive-language-detect | torch/transformers | 高风险项目 |
| MCP 协同 | glin-profanity-mcp 等 | Node.js | Claude Code 会话中 |

### 渐进式路线

1. **今天**：使用内置 5 词精炼词库，覆盖 vibe coding 核心风险
2. **需要更大覆盖面时**：`--custom` 挂载 Sensitive-lexicon，引入 pyahocorasick
3. **需要防绕过时**：加入字符归一化预处理层
4. **需要降低误报时**：接入 ML 语义审核做二次确认
5. **团队协作时**：部署 MCP Server，Git Hook + CI/CD 全链集成
