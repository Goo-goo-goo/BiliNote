# ===============================================================
# = 纯 Python API 服务镜像
#   阶段1 Python 依赖编译（清华 pypi 源）
#   阶段2 运行时（slim + 代码，FastAPI 提供 API）
#
# 构建（context 就是 backend/ 目录，见 .dockerignore 排除运行时文件）：
#   cd backend && docker build -t bilinote:local .
#   docker run -d -p 8483:8483 -e DATA_DIR=/app/data -v ./data:/app/data bilinote:local
#
# 数据目录：只挂载一个路径 /app/data（DATA_DIR），子目录启动时自动创建：
#   /app/data/bili_note.db        — SQLite 数据库
#   /app/data/config/             — 转写器/代理/Cookie 等运行时配置
#   /app/data/static/screenshots/ — 视频截图；static/cover/ — 封面
#   /app/data/uploads/            — 上传的本地视频
#   /app/data/note_results/       — 任务笔记与缓存；vector_db/ — RAG 向量索引
#   /app/data/downloads/          — 音视频下载缓存
#   /app/data/models/             — 本地 whisper 模型
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
COPY requirements.txt /
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
# 统一数据目录：所有持久化数据（db/config/uploads/static/note_results/...）都在其下
ENV DATA_DIR=/app/data

# 应用代码（频繁变动的层放后面）。
COPY . /app/backend/

WORKDIR /app/backend

EXPOSE 8483

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=20s \
  CMD curl -f http://localhost:8483/api/sys_health || exit 1

CMD ["python", "main.py"]
