#!/bin/zsh
# 刷新题库 → 提交 → 推送到 GitHub（Pages 约 1 分钟后自动生效）
# 用法：./publish.sh
set -e
cd "$(dirname "$0")"

./refresh.sh

git add -A
if git diff --cached --quiet; then
  echo "题库没有变化，跳过推送。"
  exit 0
fi

git commit -q -m "题库更新 $(date +%F)"
git push -q origin main
echo "已推送 → https://ahazx.github.io/limit-up-concepts/  （约 1 分钟后生效）"
