#!/bin/sh
# 单容器双进程：nginx（前端 :80）+ FastAPI（后端 :8483，含 /mcp）。
# python 以 exec 作为主进程接信号；nginx 以守护进程方式在后台运行。
set -e

nginx
cd /app/backend
exec python main.py
