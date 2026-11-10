#!/bin/zsh
# 涨停概念记忆 · 一键刷新题库
# 读 Obsidian 的「80-交接文档/涨停概念分类.md」，增量并入 data/bank.json + data/bank.js
# 用法：./refresh.sh                手动刷新
#       ./refresh.sh --md 其他.md   换数据源
# 定时：见 com.zhangxu.conceptquiz.refresh.plist（每天 16:10，导出的 10 分钟后）
set -e
cd "$(dirname "$0")"
exec python3 scripts/build_bank.py "$@"
