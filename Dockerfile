# ===============================================================
# = BiliNote 一键镜像：单容器双端口
#   端口 80   — 前端（nginx 托管构建产物，/api /static /uploads 反代后端）
#   端口 8483 — 后端（FastAPI：/api、/docs、/mcp）
#
# 构建与运行（在仓库根目录）：
#   docker build -t bilinote .
#   docker run -d --name bilinote \
#     -p 8080:80 -p 8483:8483 \
#     -v ./data:/app/data \
#     bilinote
#
#   前端      http://localhost:8080
#   API 文档  http://localhost:8483/docs
#   MCP 入口  http://localhost:8483/mcp   （Streamable HTTP，AI 客户端直连）
#
# 基础镜像固定走华为云 SWR 加速源（与 backend/Dockerfile 一致），不依赖 docker.io。
# ===============================================================

# ===============================================================
# = 阶段1：前端构建
#   pnpm 钉死 10.32.1（与本地开发同版本）：不跟 @latest，
#   且它兼容 pnpm-workspace.yaml 无 packages 字段的配置写法（pnpm 9 会直接报错）。
# ===============================================================
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/node:20-bookworm-slim AS frontend

ARG APT_MIRROR=mirrors.tuna.tsinghua.edu.cn
ARG NPM_REGISTRY=https://registry.npmmirror.com

RUN sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
  && apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates \
  && rm -rf /var/lib/apt/lists/*

RUN npm install -g pnpm@10.32.1 --registry=${NPM_REGISTRY}

# 镜像里只做 web 构建，跳过 electron 二进制下载（省 ~100MB，也避开下载失败）
ENV ELECTRON_SKIP_BINARY_DOWNLOAD=1

WORKDIR /src/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile --registry=${NPM_REGISTRY}

COPY frontend/ ./
RUN pnpm build

# ===============================================================
# = 阶段2：Python 依赖编译
# ===============================================================
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.12.7-slim-bookworm AS backend-deps

ARG APT_MIRROR=mirrors.tuna.tsinghua.edu.cn
ARG PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple

RUN sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
  && apt-get update \
  && apt-get install -y --no-install-recommends build-essential cmake \
  && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip config set global.index-url ${PIP_INDEX} \
  && pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r /tmp/requirements.txt

# ===============================================================
# = 阶段3：运行时（nginx 前端 + FastAPI 后端，entrypoint 双进程拉起）
# ===============================================================
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.12.7-slim-bookworm

ARG APT_MIRROR=mirrors.tuna.tsinghua.edu.cn

# ffmpeg = 转写/截图硬依赖；nginx = 前端托管与 /api 反代；curl = 健康检查
RUN sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
    ffmpeg nginx curl logrotate libgomp1 procps tzdata \
  && rm -rf /tmp/* /var/lib/apt/lists/* \
  && rm -f /etc/nginx/sites-enabled/default

# 时区
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo 'Asia/Shanghai' > /etc/timezone

ENV HF_ENDPOINT=https://hf-mirror.com \
    PYTHONPATH=/app/backend \
    DATA_DIR=/app/data \
    BACKEND_PORT=8483 \
    BACKEND_HOST=0.0.0.0

COPY --from=backend-deps /usr/local/lib/python3.12/ /usr/local/lib/python3.12/
COPY --from=backend-deps /usr/local/bin/ /usr/local/bin/

# 后端代码（频繁变动的层放后面）
COPY backend/ /app/backend/
# 前端构建产物 + nginx 配置 + 启动脚本
COPY --from=frontend /src/frontend/dist/ /app/frontend/
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh && nginx -t

WORKDIR /app/backend

EXPOSE 80 8483

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=20s \
  CMD curl -f http://localhost:8483/api/sys_health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
