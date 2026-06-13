# OpenD Dockerfile
# 构建时通过 --build-arg OPEND_PKG=xxx.tar.gz 传入 OpenD Linux 安装包
# 或从指定 URL 下载
#
# 获取 OpenD Linux 版：
#   1. 登录富途官网 https://www.futunn.com/download/openAPI
#   2. 下载对应版本的 .tar.gz 包
#   3. 构建时传入本地路径或 URL
#
# 构建示例：
#   docker build --build-arg OPEND_URL=https://your-download-url/OpenD_x.x.x_Ubuntu22.04.tar.gz \
#     -t deeplakehss/futu-opend:latest ./opend/

FROM --platform=linux/amd64 ubuntu:22.04 AS builder

ARG OPEND_URL
ARG OPEND_PKG=FutuOpenD.tar.gz

WORKDIR /tmp

# 下载 OpenD（如果提供了 URL）
# 如果没提供 URL，需要在构建上下文里放入安装包
RUN if [ -n "${OPEND_URL}" ]; then \
      apt-get update && apt-get install -y wget ca-certificates && \
      wget -O "${OPEND_PKG}" "${OPEND_URL}" || \
      curl -o "${OPEND_PKG}" "${OPEND_URL}"; \
    fi

# 解压（假设上下文里已有安装包，或者通过上面的 RUN 下载了）
RUN if [ -f "${OPEND_PKG}" ]; then \
      tar -xzf "${OPEND_PKG}" || true; \
    fi

# 查找解压后的目录，复制到 /opt/opend
RUN ls -la /tmp/

# --- 最终镜像 ---
FROM --platform=linux/amd64 ubuntu:22.04

# 安装运行依赖（OpenD 需要一些 GUI 库，即使无头运行）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libx11-6 \
    libxcb1 \
    libxau6 \
    libxdmcp6 \
    libxext6 \
    libxrender1 \
    libxtst6 \
    libxi6 \
    libxfixes3 \
    libxrandr2 \
    libxss1 \
    libgl1 \
    libglib2.0-0 \
    libnss3 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libfreetype6 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgdk-pixbuf2.0-0 \
    ca-certificates \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# 创建 futu 用户
RUN groupadd -r futu && useradd -r -g futu -m -d /home/futu futu && \
    mkdir -p /data/opend /.futu && \
    chown -R futu:futu /data/opend /.futu /home/futu

WORKDIR /opt/opend

# 复制 OpenD 二进制（从构建上下文或 builder 阶段）
# 用户需要在构建上下文里提供 OpenD 的解压目录
# 例如：COPY --from=builder /tmp/FutuOpenD_x.x.x_Ubuntu22.04/* ./
# 这里先写占位，实际构建时通过 COPY 或 --from=builder 复制
# 为简化，假设用户把 OpenD 解压后的目录放在 opend/ 子目录里一起构建
COPY --chown=futu:futu FutuOpenD/ /opt/opend/

# 复制启动脚本和配置文件
COPY --chown=futu:futu start.sh /opt/opend/start.sh
COPY --chown=futu:futu FutuOpenD.xml /opt/opend/FutuOpenD.xml

RUN chmod +x /opt/opend/start.sh

USER futu

EXPOSE 11111

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD bash -c "pgrep -f FutuOpenD || exit 1"

CMD ["/opt/opend/start.sh"]
