#!/bin/zsh
# 局域网预览：手机连同一个 WiFi，打开打印出来的地址
# 用法：./serve.sh [端口]
cd "$(dirname "$0")"
PORT=${1:-8899}
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
echo "电脑： http://127.0.0.1:$PORT/"
[ -n "$IP" ] && echo "手机： http://$IP:$PORT/   （同一个 WiFi 下）"
echo "Ctrl+C 停止"
exec python3 -m http.server "$PORT" --bind 0.0.0.0
