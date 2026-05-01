# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] — 2026-05-01

### Added

- Unicode NFKC normalization in `load_rules()` and file scanning to prevent full-width/compatibility character bypass
- `scripts/common.py` shared module consolidating constants, normalization, and utility functions
- Inline skip comment support: `# no-sensitive-check` on any line excludes it from detection and replacement

### Changed

- `scripts/check.py` and `scripts/fix.py` now import from `scripts/common.py` instead of duplicating ~70 lines each
- `scripts/fix.py` `preview_changes()` and `apply_fixes()` use line-by-line processing for accurate skip-comment handling

### Fixed

- `manage.py cmd_add` now always populates all three dimension keys (`risk_type`, `domain`, `severity`) with `"unclassified"` as default, ensuring new words are visible in all dimension clusters
- `manage.py cmd_update` fills missing dimension keys when partially updating dimensions
- `auto_extend_dimensions()` no longer adds the system-default `"unclassified"` value to the dimension catalog

### Removed

- `context` field from all rules in `references/words.json` (superseded by `dimensions.domain`)
- `--context` option from `manage.py add` and `manage.py update` commands
- `context` display from `manage.py _print_rule()` output

## [2.0.0] — 2026-04

### Added

- Three-axis dimension classification system: `risk_type` (security/privacy/legal), `domain` (intelligence/surveillance/data_collection/cyber), `severity` (high/medium/low)
- `--group-by` option on `check.py` for dimension-based terminal clustering output
- Dimension cluster sections in Markdown and HTML reports
- `dimension_breakdown` field in JSONL audit logs
- `auto_extend_dimensions()` to automatically register new dimension values
- `scripts/manage.py` for word library management (list/add/remove/update/cluster)
- Five audit output formats: terminal (ANSI colored), `.log` (syslog-style), `.jsonl` (JSON Lines), `.md` (Markdown), `.html` (self-contained HTML)
- `references/integration-guide.md` documenting 5 community integration scenarios

### Changed

- `references/words.json` schema upgraded to v2.0 with `dimensions` catalog and per-rule `dimensions` dict

## [1.0.0] — 2026-04

### Added

- Initial release with 5 core sensitive words: 情报, 监控, 抓取, 爬虫, 窃取
- `scripts/check.py` for scanning directories and reporting violations with colored terminal output
- `scripts/fix.py` for interactive preview-and-replace workflow with `--dry-run` support
- `references/words.json` as single source of truth for word rules and replacements
- `SKILL.md` as comprehensive reference manual for Claude Code skill integration
- `README.md` with vibe coding narrative and quick-start guide
- Git pre-commit hook and CI/CD pipeline integration recipes
- Zero external dependencies — pure Python standard library
