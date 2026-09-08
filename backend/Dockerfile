# ===============================================================
# = 单镜像：前后端一体
#   阶段1 Python 依赖编译（清华 pypi 源）
#   阶段2 运行时（slim + 代码 + 前端产物，FastAPI 直接服务页面）
#
# 注意：前端构建产物 BillNote_frontend/dist 已提交进仓库，
#   镜像直接 COPY 使用；前端有改动后需重新 build 并提交：
#     cd BillNote_frontend && DOCKER_BUILD=1 pnpm build
#
# 构建（仓库根目录为 context）：
#   docker build -f backend/Dockerfile -t bilinote:local .
#
# 数据目录（建议挂载持久化）：
#   /app/backend/bili_note.db           — SQLite 数据库
#   /app/backend/config/                — 转写器等运行时配置
#   /app/backend/static/screenshots/    — 视频截图
#   /app/backend/uploads/               — 上传的本地视频
#   /app/backend/models/                — 本地 whisper 模型
# ===============================================================

# ===============================================================
# = 阶段1：Python 依赖编译
# ===============================================================

FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.12.7-slim-bookworm AS build

# ---------------------------------------------------------------
# = 编译环境构建
RUN  sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources \
  && apt update \
  && apt install -y --no-install-recommends \
    build-essential \
    cmake \
    python-dev-is-python3 \
  && rm -rf /var/lib/apt/lists/* /tmp/*

# 清华 pypi 源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  && pip install --no-cache-dir --upgrade pip

# ---------------------------------------------------------------
# = 应用安装
COPY backend/requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt


# ===============================================================
# = 阶段2：运行时
# ===============================================================
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.12.7-slim-bookworm

# ---------------------------------------------------------------
# = 环境构建
# 安装apt补充包；ffmpeg 是转写/截图的硬依赖（ensure_ffmpeg_or_raise），
# curl 供健康检查使用
RUN  sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources \
  && apt update \
  && apt install -y --no-install-recommends \
    logrotate \
    libgomp1 \
    procps \
    vim \
    ffmpeg \
    curl \
  && rm -rf /tmp/* \
  && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制 python 环境和可执行文件
COPY --from=build /usr/local/lib/python3.12/ /usr/local/lib/python3.12/
COPY --from=build /usr/local/bin/ /usr/local/bin/

# ---------------------------------------------------------------
# = 运行时准备
# 时区同步
RUN rm -f /etc/localtime
RUN ln -s /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo 'Asia/Shanghai' > /etc/timezone

# HuggingFace 走国内镜像（whisper 模型下载）
ENV HF_ENDPOINT=https://hf-mirror.com
ENV PYTHONPATH=/app/backend

# 应用代码（频繁变动的层放后面）
COPY backend/ /app/backend/
# 前端静态产物：main.py 从 backend/static/frontend 挂载（见 main.py 候选路径）。
# 放在 static/frontend 子目录而非 static 根目录，避免 static 整体挂载
# volume（截图持久化）时遮蔽前端文件。
COPY BillNote_frontend/dist /app/backend/static/frontend

WORKDIR /app/backend

EXPOSE 8483

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=20s \
  CMD curl -f http://localhost:8483/api/sys_health || exit 1

CMD ["python", "main.py"]
