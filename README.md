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

## 前置条件

1. **OpenD 客户端** 必须在本机运行（默认 `127.0.0.1:11111`）
2. Python 3.10+ 或 Docker

## 快速开始

### 本地运行

```bash
pip install futu-api requests pyyaml

# 单次检测
python monitor.py

# 每 60 秒循环监控
python monitor.py --loop 60
```

### Docker 运行

```bash
docker-compose up -d          # 启动
docker-compose logs -f        # 查看日志
docker-compose restart        # 改配置后重启
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
| `FUTU_OPEND_HOST` | OpenD 地址 | `127.0.0.1` |
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

```bash
docker-compose up -d      # 启动
docker-compose logs -f    # 实时日志
docker-compose restart    # 改 config.yml 后重启即可，无需重新构建
docker-compose down       # 停止
```

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

## CI / CD

镜像构建由 GitHub Actions 在云端完成，推送到 Docker Hub。不本地 `docker build`。

- **触发**：push `main` 分支（不含 .md/.gitignore/.env.example）
- **架构**：linux/amd64 + linux/arm64
- **标签**：`latest` + commit SHA
- **缓存**：GitHub Actions Cache

## 技术栈

- Python 3.13 + futu-api + PyYAML + requests
- Docker + GitHub Actions CI/CD

## 仓库

- **GitHub**：https://github.com/hushenshen/fund-monitor
- **Docker Hub**：`deeplakehss/fund-monitor:latest`
