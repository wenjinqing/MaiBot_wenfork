# MaiBot (JunJun 实例) 容器镜像
# 基于项目实际结构,去掉了上游的 MaiMBot-LPMM 编译阶段
FROM python:3.13-slim AS base

# 时区与基础工具
ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

# 用 uv 加速依赖安装
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /MaiMBot

# 先复制依赖清单,利用 Docker 层缓存
COPY requirements.txt ./
RUN uv pip install --system -r requirements.txt

# 复制项目代码
COPY . .

# WebUI 端口;消息服务端口 8091 运行时由 .env 决定
EXPOSE 8001

ENTRYPOINT ["python", "bot.py"]