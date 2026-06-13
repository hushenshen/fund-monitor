#!/bin/bash
# OpenD 启动脚本
# 支持通过环境变量自动登录

set -e

OPEND_DIR="/opt/opend"
CONFIG_FILE="${OPEND_DIR}/FutuOpenD.xml"
DATA_DIR="/data/opend"

mkdir -p "${DATA_DIR}"

echo "[$(date '+%H:%M:%S')] 启动 OpenD..."
echo "  配置: ${CONFIG_FILE}"
echo "  数据: ${DATA_DIR}"

# 如果提供了账号密码，写入配置
if [ -n "${FUTU_ACCOUNT_ID}" ] && [ -n "${FUTU_ACCOUNT_PWD}" ]; then
    echo "[$(date '+%H:%M:%S')] 检测到登录信息，将自动登录"
    # OpenD 支持通过命令行参数登录
    LOGIN_ARGS="--login-account ${FUTU_ACCOUNT_ID} --login-pwd ${FUTU_ACCOUNT_PWD}"
else
    echo "[$(date '+%H:%M:%S')] 未配置账号密码，将使用已保存的登录态"
    echo "  （首次运行请在宿主机的富途客户端登录一次，或配置 FUTU_ACCOUNT_ID / FUTU_ACCOUNT_PWD 环境变量）"
    LOGIN_ARGS=""
fi

# 启动 OpenD（无头模式）
cd "${OPEND_DIR}"

# OpenD 二进制文件名可能带版本号，找一下
OPEND_BIN=$(find "${OPEND_DIR}" -name "FutuOpenD*" -type f | head -1)

if [ -z "${OPEND_BIN}" ] || [ ! -x "${OPEND_BIN}" ]; then
    echo "!! 未找到 OpenD 可执行文件，请检查 /opt/opend/ 目录"
    echo "   目录内容:"
    ls -la "${OPEND_DIR}/"
    exit 1
fi

echo "[$(date '+%H:%M:%S')] 使用二进制: ${OPEND_BIN}"

# 启动 OpenD
# 注意：OpenD 需要 DISPLAY 环境变量（即使无头），设置虚拟显示
export DISPLAY=:99
Xvfb :99 -screen 0 1024x768x24 &
XVFB_PID=$!
echo "[$(date '+%H:%M:%S')] Xvfb 已启动 (PID: ${XVFB_PID})"

# 等待 Xvfb 就绪
sleep 2

# 启动 OpenD（后台运行，保持容器不退出）
"${OPEND_BIN}" --config "${CONFIG_FILE}" ${LOGIN_ARGS} &
OPEND_PID=$!

echo "[$(date '+%H:%M:%S')] OpenD 已启动 (PID: ${OPEND_PID})"
echo "[$(date '+%H:%M:%S')] 监听端口: 11111"

# 等待 OpenD 进程
wait ${OPEND_PID}
