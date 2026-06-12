# ============================================================
# fund-monitor — LOF/ETF 溢价率监控 Docker 镜像
# ============================================================
# 构建：docker build -t deeplakehss/fund-monitor .
# 运行：docker run --rm deeplakehss/fund-monitor --loop 60
# ============================================================

FROM python:3.13-slim

LABEL org.opencontainers.image.title="fund-monitor"
LABEL org.opencontainers.image.description="LOF/ETF 溢价率实时监控，通过富途 OpenAPI 获取行情，溢价率低于阈值自动发送飞书通知"
LABEL org.opencontainers.image.source="https://github.com/hushenshen/fund-monitor"
LABEL org.opencontainers.image.authors="hushenshen"

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN useradd --create-home --shell /bin/bash app

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY monitor.py .

# 切换为非 root 用户
USER app

# 默认输出帮助信息
ENTRYPOINT ["python", "monitor.py"]
CMD ["--help"]
