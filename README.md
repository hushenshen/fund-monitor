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
- **支持 OpenD 容器化部署**（无需在宿主机安装 OpenD）

## 前置条件

1. **富途账号**（需在富途官网开户）
2. **OpenD 网关**：可以选择以下任一方式
   - **方式 A（推荐）**：使用本项目提供的 `docker-compose.yml`，自动启动 OpenD 容器
   - **方式 B**：在宿主机单独运行 OpenD 客户端
3. Docker + Docker Compose

## 快速开始

### 方式一：Docker Compose 一键部署（推荐）

**1. 克隆项目**

```bash
git clone https://github.com/hushenshen/fund-monitor.git
cd fund-monitor
```

**2. 配置富途账号**

复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env`，填入富途账号和密码：

```bash
# .env
FUTU_ACCOUNT_ID=你的手机号或邮箱
FUTU_ACCOUNT_PWD=你的密码
```

**3. 配置监控标的**

编辑 `config.yml`，填入飞书 Webhook 和监控列表：

```yaml
webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"

monitor_list:
  - "160644"       # 自动识别为 SZ.160644 LOF
  - "164824"
  - "513050"
```

**4. 启动服务**

```bash
docker-compose up -d
```

**5. 首次运行：登录 OpenD**

首次运行需要短信验证码登录：

```bash
# 查看 OpenD 日志，找到验证码提示
docker-compose logs -f opend
```

按照日志提示，在富途 App 或短信中确认登录。**登录态会通过 volume 持久化**，后续重启无需重新登录。

**6. 查看监控日志**

```bash
docker-compose logs -f monitor
```

---

### 方式二：本地运行（需本地安装 OpenD）

```bash
pip install futu-api requests pyyaml

# 确保 OpenD 已在本地运行（默认 127.0.0.1:11111）

# 单次检测
python monitor.py

# 每 60 秒循环监控
python monitor.py --loop 60
```

---

### 方式三：仅使用 fund-monitor 镜像（OpenD 已在别处运行）

如果 OpenD 已经在其他机器或容器中运行，可以只启动 monitor：

```bash
# 修改 docker-compose.yml，注释掉 opend 服务
# 并设置 FUTU_OPEND_HOST 为 OpenD 的地址

docker-compose up -d monitor
```

## 配置（config.yml）

**只输 6 位代码即可**，脚本会自动推断 SZ/SH 和 LOF/ETF：

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
| **纯代码**（推荐） | `"160644"` | 自动推断一切，名称显示代码号 |
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

展开写法中可用的全部字段：

| 字段 | 必需 | 说明 | 默认值 |
|------|------|------|--------|
| `code` | ✅ | 6 位代码或完整富途代码 | - |
| `name` | | 标的名称 | 代码号 |
| `threshold` | | 溢价率告警阈值（%） | `2.0` |
| `type` | | `LOF` 或 `ETF` | 自动推断 |
| `nav_field` | | 参考净值来源：`prev_close` / `nav` / `iopv` | `prev_close` |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook（优先级最高） | - |
| `FUTU_OPEND_HOST` | OpenD 地址 | `opend`（容器内）/ `127.0.0.1`（本地） |
| `FUTU_OPEND_PORT` | OpenD 端口 | `11111` |
| `MONITOR_CONFIG_FILE` | 配置文件路径 | `./config.yml` |
| `PYTHONUNBUFFERED` | 关闭 Python 输出缓冲 | `1` |

### 配置优先级

飞书 Webhook 取值顺序：**命令行 --webhook → 环境变量 FEISHU_WEBHOOK_URL → config.yml webhook_url**

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

## Docker 部署

### 一键启动（含 OpenD）

```bash
docker-compose up -d      # 启动 OpenD + monitor
docker-compose logs -f    # 实时日志
docker-compose restart    # 改 config.yml 后重启即可，无需重新构建
docker-compose down       # 停止
```

### 仅启动 monitor（OpenD 已在别处运行）

编辑 `docker-compose.yml`，注释掉 `opend` 服务，并设置 `FUTU_OPEND_HOST` 为 OpenD 的地址。

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

## OpenD 容器化说明

### 为什么需要 OpenD？

OpenD 是富途提供的**本地网关程序**，负责：
- 连接富途的行情服务器
- 提供本地 TCP 接口（`127.0.0.1:11111`）给 `futu-api` 调用

### 登录态持久化

OpenD 的登录态保存在 Docker volume `opend-data` 中，重启容器不会丢失。

如果需要重新登录，删除 volume 并重启：

```bash
docker-compose down -v
docker-compose up -d
```

### 自行构建 OpenD 镜像

如果不想使用社区镜像，可以参考 `opend/Dockerfile` 自行构建：

```bash
# 1. 从富途官网下载 OpenD Linux 版本
#    https://www.futunn.com/download/openAPI

# 2. 解压到 opend/FutuOpenD/ 目录

# 3. 构建镜像
docker build -t deeplakehss/futu-opend:latest ./opend/
```

## CI / CD

### fund-monitor 镜像

镜像构建由 GitHub Actions 在云端完成，推送到 Docker Hub。不本地 `docker build`。

- **触发**：push `main` 分支（不含 .md/.gitignore/.env.example）
- **架构**：linux/amd64 + linux/arm64
- **标签**：`latest` + commit SHA
- **缓存**：GitHub Actions Cache

### OpenD 镜像

OpenD 镜像使用社区维护版本：`ghcr.io/manhinhang/futu-opend-docker:ubuntu-stable`

## 技术栈

- **监控脚本**：Python 3.13 + futu-api + PyYAML + requests
- **OpenD 网关**：富途 OpenD (Docker)
- **容器编排**：Docker Compose
- **CI/CD**：GitHub Actions → Docker Hub

## 常见问题

### Q: 为什么看不到价格输出？

A: 检查 OpenD 是否正常运行：

```bash
docker-compose logs opend
```

如果看到 "未获取到快照数据"，可能是：
1. OpenD 未登录或登录失效
2. 代码输入错误（确认是 6 位代码）
3. 富途账号没有该标的的行情权限

### Q: 如何修改监控间隔？

A: 修改 `docker-compose.yml` 中 monitor 的 command：

```yaml
command: ["--loop", "120"]  # 改为 120 秒
```

然后重启：

```bash
docker-compose restart monitor
```

## 仓库

- **GitHub**：https://github.com/hushenshen/fund-monitor
- **Docker Hub（监控脚本）**：`deeplakehss/fund-monitor:latest`
- **Docker Hub（OpenD）**：`ghcr.io/manhinhang/futu-opend-docker:ubuntu-stable`
