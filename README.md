# fund-monitor

LOF / ETF 溢价率实时监控，连接 [富途 OpenAPI](https://openapi.futunn.com/) 获取实时行情，溢价率低于设定阈值时自动推送飞书通知。

---

## 功能

- 实时获取 LOF / ETF 的盘中交易价格与参考净值
- 计算溢价率：`(现价 / 参考净值 − 1) × 100%`
- 低于阈值时通过飞书机器人 Webhook 卡片通知
- 支持单次检测和循环监控两种模式
- **只输 6 位代码即可**，自动推断沪市/深市、LOF/ETF
- 配置文件外置，增删标的不需要重新构建 Docker 镜像
- **OpenD 容器化**，无需在宿主机额外安装

## 前置条件

1. **富途账号**（需在富途官网开户）
2. **Docker + Docker Compose**
3. **OpenSSL**（用于生成 RSA 密钥）

## 快速开始（Docker Compose 一键部署）

### 1. 克隆项目

```bash
git clone https://github.com/hushenshen/fund-monitor.git
cd fund-monitor
```

### 2. 生成 RSA 密钥

OpenD 需要 RSA 密钥文件进行安全通信：

```bash
openssl genrsa -out futu.pem 1024
```

> 该文件已加入 `.gitignore`，不会被提交到 Git。

### 3. 配置富途账号

```bash
cp .env.example .env
```

编辑 `.env`，填入账号和密码（**推荐使用 MD5，避免明文泄露**）：

```bash
# 生成密码 MD5（任选一种）：
# Linux / Git Bash：
echo -n "你的密码" | md5sum | awk '{print $1}'

# macOS：
echo -n "你的密码" | md5

# PowerShell：
# [System.BitConverter]::ToString([System.Security.Cryptography.MD5]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes('你的密码'))).Replace('-','').ToLower()
```

然后写入 `.env`：

```bash
FUTU_ACCOUNT_ID=你的手机号或邮箱
FUTU_ACCOUNT_PWD_MD5=上面生成的32位MD5值
```

### 4. 配置监控标的

编辑 `config.yml`，填入飞书 Webhook 和监控列表：

```yaml
webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"

monitor_list:
  - "160644"       # 自动识别为 SZ.160644 LOF
  - "164824"
  - "513050"
```

### 5. 启动服务

```bash
docker compose up -d
```

### 6. 首次运行：输入验证码

首次运行时 OpenD 会要求短信或图片验证码。通过 **Telnet 端口 22222** 输入：

```bash
# 短信验证码：
echo "input_phone_verify_code -code=123456" | telnet localhost 22222

# 图片验证码（先从容器提取验证码图片）：
docker cp fund-opend:/home/futu/.com.futunn.FutuOpenD/F3CNN/PicVerifyCode.png ./PicVerifyCode.png
# 查看图片后输入：
echo "input_pic_verify_code -code=ABCD" | telnet localhost 22222
```

验证通过后，**登录态通过 Docker volume 持久化**，后续重启无需重新验证。

### 7. 查看监控日志

```bash
docker compose logs -f monitor
```

正常输出示例：

```
快照返回 1 条数据 (keys: ['160644'])
  --- SZ.160644  鹏华港美互联网LOF（LOF）
  |   实时价格     1.234
  |   参考净值     1.2000（昨收价）
  |   溢价率       2.83%
  |   阈值         2.00%
  |   状态         OK
```

## 配置参考

### config.yml — 监控标的配置

```yaml
webhook_url: "你的飞书Webhook"

monitor_list:
  # 纯代码写法 — 零配置
  - "160644"       # → SZ.160644 LOF
  - "164824"       # → SZ.164824 LOF
  - "513050"       # → SH.513050 ETF

  # 想自定义名称或阈值？展开为字典：
  - code: "161128"
    name: "易方达标普信息科技LOF"
    threshold: 3.0
```

### 三种写法

| 写法 | 示例 | 说明 |
|------|------|------|
| **纯代码**（推荐） | `"160644"` | 自动推断一切 |
| 带名称 | `{code: "160644", name: "鹏华港美互联网"}` | 未填字段自动推断 |
| 完整展开 | `{code: "SZ.160644", type: "LOF", ...}` | 完全手动控制 |

### 自动识别规则

| 代码段 | 推断结果 |
|--------|----------|
| `6xxxxx` | 沪市（SH） |
| 其余 | 深市（SZ） |
| `510/511/512/513/515/516/517/518/588/159` | ETF |
| `160/161/162/163/164/165/501` | LOF（默认） |

### 完整字段

| 字段 | 必需 | 说明 | 默认值 |
|------|------|------|--------|
| `code` | ✅ | 6 位代码或完整富途代码 | — |
| `name` | | 标的名称 | 代码号 |
| `threshold` | | 溢价率告警阈值（%） | `2.0` |
| `type` | | `LOF` 或 `ETF` | 自动推断 |
| `nav_field` | | 参考净值来源：`prev_close` / `nav` / `iopv` | `prev_close` |

### .env — OpenD 环境变量

| 变量 | 说明 | 必填 |
|------|------|------|
| `FUTU_ACCOUNT_ID` | 富途账号（手机号/邮箱/牛牛号） | ✅ |
| `FUTU_ACCOUNT_PWD_MD5` | **推荐**。密码的 MD5 哈希 | 推荐 |
| `FUTU_ACCOUNT_PWD` | 已弃用。明文密码（如果设了 MD5 会被忽略） | 备选 |

## 溢价率计算逻辑

```
溢价率 = (实时交易价 / 参考净值 - 1) × 100%
```

- **正值**：溢价（市场价高于净值）
- **负值**：折价（市场价低于净值）

| nav_field | 说明 | 适用场景 |
|-----------|------|----------|
| `prev_close` | 昨日收盘价 | 默认，适用于无 IOPV 的 LOF |
| `nav` | 基金净值 | 需富途提供该字段 |
| `iopv` | 盘中实时 IOPV | 最准确，需数据源支持 |

## 运维操作

### 常用命令

```bash
docker compose up -d              # 启动
docker compose ps                 # 查看状态
docker compose logs -f monitor    # 实时监控日志
docker compose logs opend         # OpenD 日志（排查连接问题）
docker compose restart monitor    # 改了 config.yml 后重启监控
docker compose pull               # 拉取最新镜像
docker compose up -d              # 用新镜像重建
docker compose down               # 停止
```

### 强制重新登录

如果换账号或登录态过期，清除 volume 后重启：

```bash
docker compose down -v
docker compose up -d
# 然后通过 telnet 重新输入验证码
```

### 网络模式说明

`docker-compose.yml` 中 OpenD 默认使用 `host` 网络模式，因为 Docker bridge 可能导致连接富途认证服务器失败。如果你想让两个服务通过 Docker 内部网络通信：

1. 将 `opend` 的 `network_mode: host` 改为 `ports` 映射
2. 将 `monitor` 的 `network_mode: host` 删掉
3. 将 `monitor` 的 `FUTU_OPEND_HOST` 改为 `opend`（服务名）

## 命令行参数

```
python monitor.py --help

选项:
  --config PATH     配置文件（YAML/JSON，默认: config.yml）
  --loop SECONDS    循环检测间隔秒数（0=单次）
  --json            JSON 格式输出
  --no-notify       仅打印，不发飞书通知
  --webhook URL     飞书 Webhook URL（覆盖配置文件）
```

### 配置优先级

飞书 Webhook 取值顺序：**命令行 --webhook → 环境变量 FEISHU_WEBHOOK_URL → config.yml webhook_url**

## 本地开发（不需要 Docker）

```bash
pip install futu-api requests pyyaml

# 确保 OpenD 已在本地运行（127.0.0.1:11111）
python monitor.py --loop 60
```

## CI / CD

### fund-monitor 镜像

GitHub Actions 云端构建，推送到 Docker Hub：

- **触发**：push `main` 分支（不含 .md/.gitignore/.env.example）
- **架构**：linux/amd64 + linux/arm64
- **标签**：`latest` + commit SHA

### OpenD 镜像

使用社区维护版本：

- **镜像**：`ghcr.io/manhinhang/futu-opend-docker:ubuntu-stable`
- **仓库**：https://github.com/manhinhang/futu-opend-docker

如需自行构建，参考 `opend/` 目录下的 Dockerfile。

## 常见问题

### Q: 为什么看不到价格输出？

A: 检查 OpenD 是否正常运行和已登录：

```bash
docker compose logs opend | tail -20
```

常见原因：
1. OpenD 未登录或登录态失效 → 查看 opend 日志，必要时 `docker compose down -v` 重新登录
2. 代码输入错误 → 确认 config.yml 中是 6 位代码
3. 富途账号没有该标的行情权限

### Q: 第一次启动怎么输入验证码？

A: 通过 Telnet 端口 22222：

```bash
# 短信验证码
echo "input_phone_verify_code -code=123456" | telnet localhost 22222

# 图片验证码
docker cp fund-opend:/home/futu/.com.futunn.FutuOpenD/F3CNN/PicVerifyCode.png ./
# 查看后输入
echo "input_pic_verify_code -code=ABCD" | telnet localhost 22222
```

### Q: 如何修改监控间隔？

A: 修改 `docker-compose.yml` 中 monitor 的 command：

```yaml
command: ["--loop", "120"]  # 改为 120 秒
```

然后重启：

```bash
docker compose restart monitor
```

## 技术栈

- **监控脚本**：Python 3.13 + futu-api + PyYAML + requests
- **OpenD 网关**：富途 OpenD（Docker 容器化）
- **验证码输入**：Telnet 22222 端口
- **容器编排**：Docker Compose（host 网络模式）
- **CI/CD**：GitHub Actions → Docker Hub

## 仓库

- **GitHub**：https://github.com/hushenshen/fund-monitor
- **Docker Hub（监控脚本）**：`deeplakehss/fund-monitor:latest`
- **OpenD 镜像**：`ghcr.io/manhinhang/futu-opend-docker:ubuntu-stable`
