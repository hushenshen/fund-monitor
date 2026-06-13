#!/usr/bin/env python3
"""
LOF/ETF 溢价率实时监控脚本
============================
通过富途 OpenAPI 获取实时行情，计算溢价率，低于阈值时通过飞书 Webhook 发送通知。

依赖：
    pip install futu-api requests pyyaml

环境要求：
    - OpenD 必须运行，默认连接 127.0.0.1:11111
    - 可通过环境变量 FUTU_OPEND_HOST / FUTU_OPEND_PORT 修改

使用方式：
    python monitor.py              # 单次检测
    python monitor.py --loop 60    # 每60秒轮询一次（Ctrl+C 停止）
    python monitor.py --json       # JSON 格式输出（不发送通知）

扩展方式：
    修改 config.yml，添加更多 LOF/ETF 标的即可，无需重新构建 Docker 镜像。
"""

import argparse
import json
import logging
import os
import socket
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# ============================================================
# 立即关闭 Python 输出缓冲（Docker 场景下日志延迟的关键）
# ============================================================
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None
os.environ.setdefault("PYTHONUNBUFFERED", "1")

# ============================================================
# 依赖自检（启动时检查，给出明确修复指引）
# ============================================================
_MISSING_DEPS = []
for _mod, _pkg in [("futu", "futu-api"), ("requests", "requests"), ("yaml", "pyyaml")]:
    try:
        __import__(_mod)
    except ImportError:
        _MISSING_DEPS.append(f"{_mod} (pip install {_pkg})")

if _MISSING_DEPS:
    print(
        f"[ERROR] 缺少依赖: {', '.join(_mod for _mod, _pkg in [('futu','futu-api'),('requests','requests')] if _mod not in sys.modules)}\n"
        f"请使用以下命令安装:\n"
        f"  {sys.executable} -m pip install futu-api requests pyyaml\n",
        file=sys.stderr,
    )
    sys.exit(1)

import requests  # noqa: E402
import yaml   # noqa: E402
from futu import (  # noqa: E402
    OpenQuoteContext,
    RET_OK,
    SubType,
    KLType,
)

# ============================================================
# 日志配置
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("fund_monitor")

# ============================================================
# 代码自动识别：只输 6 位代码，自动判断 SZ/SH 和 LOF/ETF
# ============================================================

def _is_sh(code: str) -> bool:
    """判断 A 股代码是否为沪市。6xxxxx → 沪市，其余 → 深市"""
    return code.startswith("6")


def _is_etf(code: str) -> bool:
    """判断基金代码是否为 ETF（否则视为 LOF）"""
    sh_etf_prefixes = ("510", "511", "512", "513", "515", "516", "517", "518", "588")
    sz_etf_prefixes = ("159",)
    return code.startswith(sh_etf_prefixes + sz_etf_prefixes)


def _auto_detect(code: str) -> dict:
    """
    根据 6 位代码自动推断富途完整代码和基金类型。

    返回: {"futu_code": "SZ.160644", "market": "SZ", "type": "LOF", "name": ""}
    """
    code = str(code).strip()
    if "." in code:
        # 已经是完整富途代码，不做自动推断
        futu_code = code
        market = code.split(".")[0]
    else:
        market = "SH" if _is_sh(code) else "SZ"
        futu_code = f"{market}.{code}"

    fund_type = "ETF" if _is_etf(code) else "LOF"

    return {"futu_code": futu_code, "market": market, "type": fund_type}


def _normalize_item(item) -> dict:
    """
    将配置条目标准化为完整格式。

    支持三种写法：
      1. 纯代码字符串: "160644"
      2. 带名称的字典: {"code": "160644", "name": "鹏华港美互联网LOF"}
      3. 完整字典:     {"code": "SZ.160644", "type": "LOF", ...}

    返回完整格式字典，未填字段用自动推断结果 + 默认值补齐。
    """
    if isinstance(item, str):
        item = {"code": item}

    if not isinstance(item, dict) or "code" not in item:
        raise ValueError(f"配置条目格式错误: {item}")

    detected = _auto_detect(item["code"])

    return {
        "code": detected["futu_code"],
        "name": item.get("name", item["code"] if isinstance(item, str) else item.get("code", "")),
        "threshold": float(item.get("threshold", 2.0)),
        "type": item.get("type", detected["type"]),
        "nav_field": item.get("nav_field", "prev_close"),
    }


# ============================================================
# 配置文件加载
# ============================================================

def _load_config_file(path: str) -> dict:
    """加载 YAML/JSON 配置文件，返回 {webhook_url, monitor_list}"""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"配置文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        if path.endswith((".yml", ".yaml")):
            cfg = yaml.safe_load(f)
        else:
            cfg = json.load(f)

    if cfg is None:
        raise ValueError("配置文件为空")
    if "monitor_list" not in cfg or not isinstance(cfg["monitor_list"], list):
        raise ValueError("配置文件缺少 monitor_list 字段或格式错误")

    # 标准化所有条目（自动推断 SZ/SH、LOF/ETF，补齐默认值）
    cfg["monitor_list"] = [_normalize_item(item) for item in cfg["monitor_list"]]

    return cfg


def _resolve_config_path(cli_arg: str = None) -> str:
    """
    按优先级确定配置文件路径：
    1. 命令行 --config 参数
    2. 环境变量 MONITOR_CONFIG_FILE
    3. 默认: 脚本同目录下的 config.yml → config.yaml → config.json
    """
    if cli_arg:
        return cli_arg
    env_path = os.environ.get("MONITOR_CONFIG_FILE")
    if env_path:
        return env_path
    base = os.path.dirname(os.path.abspath(__file__))
    for name in ("config.yml", "config.yaml", "config.json"):
        candidate = os.path.join(base, name)
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(base, "config.yml")  # 默认名


# ============================================================
# 配置区域 —— 可通过 config.yml 覆盖，修改后无需重新打镜像
# ============================================================

# 默认值（config.yml 不存在时的兜底）
DEFAULT_WEBHOOK_URL = "XXX"

DEFAULT_MONITOR_LIST = [
    {
        "code": "SZ.160644",
        "name": "鹏华港美互联网LOF",
        "threshold": 2.0,
        "type": "LOF",
        "nav_field": "prev_close",
    },
]

# 以下变量在 main() 中通过 load_config() 最终赋值
FEISHU_WEBHOOK_URL = DEFAULT_WEBHOOK_URL
MONITOR_LIST = DEFAULT_MONITOR_LIST

# OpenD 连接配置
OPEND_HOST = os.environ.get("FUTU_OPEND_HOST", "127.0.0.1")
OPEND_PORT = int(os.environ.get("FUTU_OPEND_PORT", "11111"))


# ============================================================
# 数据模型
# ============================================================

@dataclass
class PremiumResult:
    """单只标的的溢价率检测结果"""
    code: str
    name: str
    fund_type: str
    threshold: float
    last_price: float          # 实时交易价
    ref_nav: float             # 参考净值（昨收/NAV/IOPV）
    nav_field: str             # 使用了哪个净值字段
    premium_pct: float         # 溢价率 (%)
    is_alert: bool             # 是否满足告警条件
    update_time: str           # 行情更新时间
    error: Optional[str] = None

    def premium_direction(self) -> str:
        """溢价/折价方向"""
        if self.premium_pct > 0:
            return "溢价"
        elif self.premium_pct < 0:
            return "折价"
        return "平价"

    NAV_FIELD_LABELS = {
        "prev_close": "昨收价",
        "nav": "基金净值(NAV)",
        "iopv": "实时参考净值(IOPV)",
        "": "未知",
    }

    def summary(self) -> str:
        """单行摘要（日志文件用）"""
        if self.error:
            return f"[{self.code} {self.name}] 错误: {self.error}"
        flag = "触发" if self.is_alert else "正常"
        direction = self.premium_direction()
        return (
            f"{flag} [{self.code}] {self.name} | "
            f"现价: {self.last_price:.3f} | "
            f"参考净值({self.nav_field}): {self.ref_nav:.4f} | "
            f"溢价率: {self.premium_pct:+.2f}% ({direction}) | "
            f"阈值: {self.threshold}% | "
            f"更新时间: {self.update_time}"
        )

    def detail_lines(self) -> list[str]:
        """生成多行详细信息（控制台输出用）"""
        if self.error:
            return [f"  !! {self.name}（{self.code}）查询异常: {self.error}"]

        nav_label = self.NAV_FIELD_LABELS.get(self.nav_field, self.nav_field)
        direction = self.premium_direction()
        alert_line = ""
        if self.is_alert:
            alert_line = f" ** 低于阈值 {self.threshold}%"

        lines = [
            f"  --- {self.code}  {self.name}（{self.fund_type}）",
            f"  |   实时价格     {self.last_price:.3f}",
            f"  |   参考净值     {self.ref_nav:.4f}（{nav_label}）",
            f"  |   溢价率       {self.premium_pct:+.2f}%（{direction}）{alert_line}",
            f"  |   行情时间     {self.update_time}",
            f"  ---",
        ]
        return lines


# ============================================================
# 富途行情客户端
# ============================================================

class FutuClient:
    """封装富途 OpenAPI 行情连接"""

    def __init__(self, host: str = OPEND_HOST, port: int = OPEND_PORT):
        self.host = host
        self.port = port
        self._ctx: Optional[OpenQuoteContext] = None

    def connect(self) -> OpenQuoteContext:
        """建立行情连接（带 10s 超时，避免 OpenD 不可用时无限卡死）"""
        if self._ctx is None:
            logger.info(f"正在连接 OpenD: {self.host}:{self.port} ...")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 正在连接 OpenD ({self.host}:{self.port}) ...", flush=True)
            old_timeout = socket.getdefaulttimeout()
            try:
                socket.setdefaulttimeout(10)
                self._ctx = OpenQuoteContext(host=self.host, port=self.port)
            except Exception as e:
                raise ConnectionError(
                    f"无法连接 OpenD ({self.host}:{self.port})，请确认 OpenD 已启动且端口可访问。"
                    f" 原始错误: {e}"
                )
            finally:
                socket.setdefaulttimeout(old_timeout)
            logger.info(f"已连接 OpenD: {self.host}:{self.port}")
        return self._ctx

    def close(self):
        """关闭行情连接"""
        if self._ctx is not None:
            self._ctx.close()
            self._ctx = None
            logger.info("已断开 OpenD 连接")

    def __enter__(self):
        return self.connect()

    def __exit__(self, *args):
        self.close()

    @staticmethod
    def _normalize_code(code: str) -> str:
        """去掉市场前缀，只保留数字部分，用于模糊匹配"""
        return code.split(".")[-1] if "." in code else code

    def get_snapshots(self, codes: list[str]) -> dict:
        """
        批量获取市场快照。
        返回 {code: DataFrame row} 的字典。

        注意：富途返回的 code 字段可能不带市场前缀（如 160644），
        因此同时用完整码和短码作为 key，确保后续 lookup 能命中。
        """
        ctx = self.connect()
        result = {}
        batch_size = 400
        for i in range(0, len(codes), batch_size):
            batch = codes[i:i + batch_size]
            ret, data = ctx.get_market_snapshot(batch)
            if ret != RET_OK:
                logger.error(f"获取快照失败: {data}")
                continue
            if data is not None and not data.empty:
                for idx in range(len(data)):
                    row = data.iloc[idx]
                    raw_code = str(row.get("code", ""))
                    short_code = self._normalize_code(raw_code)
                    # 同时以完整码和短码存储，覆盖不同查询方式
                    result[raw_code] = row
                    if short_code != raw_code:
                        result.setdefault(short_code, row)
        return result


# ============================================================
# 溢价率计算器
# ============================================================

class PremiumCalculator:
    """
    LOF/ETF 溢价率计算器

    支持三种净值来源（通过 nav_field 指定）：
    - "prev_close": 使用昨日收盘价（最通用，但精度最差）
    - "nav": 使用基金净值（需富途快照包含此字段）
    - "iopv": 使用盘中实时参考净值（最准确，需数据源支持）
    """

    # 富途快照中可能的净值字段名映射
    NAV_FIELD_CANDIDATES = {
        "prev_close": ["prev_close_price", "pre_price", "last_close"],
        "nav": ["net_value", "nav", "fund_nav"],
        "iopv": ["iopv", "estimated_nav", "reference_price"],
    }

    @staticmethod
    def _extract_field(row, candidates: list[str]) -> float:
        """从快照行中提取第一个存在的数值字段"""
        for field_name in candidates:
            try:
                val = row.get(field_name, None)
                if val is not None and not (isinstance(val, float) and val != val):  # 排除 NaN
                    f = float(val)
                    if f > 0:
                        return f
            except (ValueError, TypeError):
                continue
        return 0.0

    def calculate(self, code: str, name: str, row, config: dict) -> PremiumResult:
        """计算单只标的的溢价率"""
        fund_type = config.get("type", "LOF")
        threshold = config.get("threshold", 2.0)
        nav_field = config.get("nav_field", "prev_close")

        try:
            # 获取实时交易价格
            last_price = self._extract_field(row, ["last_price"])
            if last_price <= 0:
                return PremiumResult(
                    code=code, name=name, fund_type=fund_type,
                    threshold=threshold, last_price=0, ref_nav=0,
                    nav_field=nav_field, premium_pct=0, is_alert=False,
                    update_time="", error="无法获取交易价格"
                )

            # 获取参考净值
            candidates = self.NAV_FIELD_CANDIDATES.get(
                nav_field, self.NAV_FIELD_CANDIDATES["prev_close"]
            )
            ref_nav = self._extract_field(row, candidates)

            if ref_nav <= 0:
                # 兜底：如果指定字段不可用，尝试 prev_close
                ref_nav = self._extract_field(
                    row, self.NAV_FIELD_CANDIDATES["prev_close"]
                )
                actual_field = "prev_close"
            else:
                actual_field = nav_field

            if ref_nav <= 0:
                return PremiumResult(
                    code=code, name=name, fund_type=fund_type,
                    threshold=threshold, last_price=last_price, ref_nav=0,
                    nav_field=actual_field, premium_pct=0, is_alert=False,
                    update_time="", error="无法获取参考净值"
                )

            # 计算溢价率
            premium_pct = (last_price / ref_nav - 1.0) * 100.0

            # 判断是否触发告警：溢价率 < 阈值
            is_alert = premium_pct < threshold

            # 获取更新时间
            update_time = (
                str(row.get("update_time", ""))
                if row.get("update_time")
                else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

            return PremiumResult(
                code=code, name=name, fund_type=fund_type,
                threshold=threshold, last_price=last_price, ref_nav=ref_nav,
                nav_field=actual_field, premium_pct=round(premium_pct, 4),
                is_alert=is_alert, update_time=update_time,
            )

        except Exception as e:
            return PremiumResult(
                code=code, name=name, fund_type=fund_type,
                threshold=threshold, last_price=0, ref_nav=0,
                nav_field=nav_field, premium_pct=0, is_alert=False,
                update_time="", error=str(e),
            )


# ============================================================
# 飞书通知
# ============================================================

class FeishuNotifier:
    """飞书机器人 Webhook 通知"""

    def __init__(self, webhook_url: str = FEISHU_WEBHOOK_URL):
        self.webhook_url = webhook_url

    def _build_card(self, results: list[PremiumResult]) -> dict:
        """构建飞书消息卡片"""
        alert_results = [r for r in results if r.is_alert and not r.error]
        normal_results = [r for r in results if not r.is_alert and not r.error]
        error_results = [r for r in results if r.error]

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 构建卡片内容
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**LOF/ETF 溢价率监控报告**\n{now_str}",
                },
            },
            {"tag": "hr"},
        ]

        if alert_results:
            alert_lines = ["**溢价率低于阈值（需关注）：**\n"]
            for r in alert_results:
                alert_lines.append(
                    f"  **{r.name}**（{r.code}）\n"
                    f"  现价 {r.last_price:.3f} | 参考净值 {r.ref_nav:.4f} | "
                    f"溢价率 **{r.premium_pct:+.2f}%** | 阈值 {r.threshold}%"
                )
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "\n".join(alert_lines)},
            })

        if normal_results:
            normal_lines = ["\n**正常标的：**\n"]
            for r in normal_results:
                direction = "溢价" if r.premium_pct > 0 else "折价"
                normal_lines.append(
                    f"  {r.name}（{r.code}）溢价率 {r.premium_pct:+.2f}%（{direction}）"
                )
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "\n".join(normal_lines)},
            })

        if error_results:
            error_lines = ["\n**查询异常：**\n"]
            for r in error_results:
                error_lines.append(f"  {r.name}（{r.code}）: {r.error}")
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "\n".join(error_lines)},
            })

        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "LOF/ETF 溢价率监控",
                    },
                    "template": "red" if alert_results else "green",
                },
                "elements": elements,
            },
        }

    def send(self, results: list[PremiumResult]) -> bool:
        """发送飞书通知"""
        if not self.webhook_url:
            logger.warning("未配置飞书 Webhook URL，跳过通知")
            return False

        alert_count = sum(1 for r in results if r.is_alert and not r.error)
        if alert_count == 0:
            logger.info("无告警标的，跳过飞书通知")
            return True

        card = self._build_card(results)
        try:
            resp = requests.post(
                self.webhook_url,
                json=card,
                timeout=10,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            resp_data = resp.json()
            if resp_data.get("code") == 0:
                logger.info(f"飞书通知发送成功（{alert_count} 个告警标的）")
                return True
            else:
                logger.error(f"飞书通知失败: {resp_data}")
                return False
        except requests.RequestException as e:
            logger.error(f"飞书通知请求异常: {e}")
            return False


# ============================================================
# 监控主逻辑
# ============================================================

class Monitor:
    """溢价率监控主控制器"""

    def __init__(
        self,
        monitor_list: list[dict] = None,
        webhook_url: str = None,
    ):
        self.monitor_list = monitor_list or MONITOR_LIST
        self.calculator = PremiumCalculator()
        self.notifier = FeishuNotifier(webhook_url or FEISHU_WEBHOOK_URL)
        self.futu = FutuClient()
        self.last_alert_time: dict[str, float] = {}  # code -> last alert timestamp

    def run_once(self, verbose: bool = True) -> list[PremiumResult]:
        """执行一次检测"""
        codes = [item["code"] for item in self.monitor_list]
        msg = f"开始检测 {len(codes)} 个标的: {codes}"
        logger.info(msg)
        if verbose:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

        try:
            snapshots = self.futu.get_snapshots(codes)
            if verbose:
                print(f"  快照返回 {len(snapshots)} 条数据 (keys: {list(snapshots.keys())[:3]})", flush=True)
        except Exception as e:
            logger.error(f"获取快照失败: {e}")
            if verbose:
                print(f"  !! 行情连接失败: {e}", flush=True)
            return [
                PremiumResult(
                    code=item["code"], name=item["name"],
                    fund_type=item.get("type", "LOF"),
                    threshold=item.get("threshold", 2.0),
                    last_price=0, ref_nav=0, nav_field="",
                    premium_pct=0, is_alert=False, update_time="",
                    error=f"行情连接失败: {e}",
                )
                for item in self.monitor_list
            ]

        if not snapshots:
            msg = "快照数据为空，请检查 OpenD 连接和目标代码是否有效"
            logger.warning(msg)
            if verbose:
                print(f"  !! {msg}", flush=True)

        results = []
        for item in self.monitor_list:
            code = item["code"]
            name = item["name"]
            # 先用完整码查找，再用短码兜底
            row = snapshots.get(code)
            if row is None:
                short_code = code.split(".")[-1] if "." in code else code
                row = snapshots.get(short_code)

            if row is None:
                r = PremiumResult(
                    code=code, name=name, fund_type=item.get("type", "LOF"),
                    threshold=item.get("threshold", 2.0),
                    last_price=0, ref_nav=0, nav_field="",
                    premium_pct=0, is_alert=False, update_time="",
                    error=f"未获取到快照数据 (可用keys: {list(snapshots.keys())[:5]})",
                )
                results.append(r)
                for line in r.detail_lines():
                    print(line, flush=True)
                continue

            result = self.calculator.calculate(code, name, row, item)
            results.append(result)
            logger.info(result.summary())
            # 每个标的都输出详细的多行信息
            for line in result.detail_lines():
                print(line, flush=True)

        print("", flush=True)  # 空行分隔
        return results

    def send_alerts(self, results: list[PremiumResult]):
        """发送告警通知"""
        alert_results = [r for r in results if r.is_alert and not r.error]
        if alert_results:
            print(f"  发送飞书通知（{len(alert_results)} 个告警标的）...", flush=True)
            self.notifier.send(results)
        else:
            msg = "本次检测无告警"
            logger.info(msg)
            print(f"  OK {msg}", flush=True)

    def run_loop(self, interval: int = 60):
        """循环监控模式"""
        msg = f"启动循环监控，间隔 {interval} 秒，按 Ctrl+C 停止"
        logger.info(msg)
        print(f"\n{'=' * 60}")
        print(msg)
        print(f"{'=' * 60}")
        # 打印监控列表
        print(f"\n监控标的（共 {len(self.monitor_list)} 个）：")
        for item in self.monitor_list:
            print(f"  - {item['code']}  {item['name']}（{item.get('type', 'LOF')}）阈值 {item.get('threshold', 2.0)}%")
        print(f"\n{'=' * 60}\n", flush=True)

        cycle = 0
        try:
            while True:
                cycle += 1
                print(f"--- 第 {cycle} 轮检测 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ---", flush=True)
                results = self.run_once()
                self.send_alerts(results)
                print(f"等待 {interval} 秒后进行第 {cycle + 1} 轮检测...\n", flush=True)
                time.sleep(interval)
        except KeyboardInterrupt:
            print(f"\n监控已停止，共执行 {cycle} 轮检测", flush=True)
            logger.info("监控已停止")
        finally:
            self.futu.close()


# ============================================================
# 命令行入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="LOF/ETF 溢价率实时监控",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
配置说明:
  监控标的列表在 config.yml 中维护，修改后 docker-compose restart 即可生效，
  无需重新构建 Docker 镜像。

config.yml 示例 (只输 6 位代码即可，自动推断 SZ/SH 和 LOF/ETF):
  webhook_url: "XXX"
  monitor_list:
    - "160644"       # 纯代码 -- 自动识别
    - code: "513050" # 展开写法，自定义名称
      name: "易方达中概互联ETF"
      threshold: 2.0

使用示例:
  python monitor.py                       # 单次检测（使用默认 config.yml）
  python monitor.py --config my.yml       # 指定配置文件
  python monitor.py --loop 60             # 每60秒循环检测
  python monitor.py --json --no-notify    # JSON输出，不发通知
        """,
    )
    parser.add_argument(
        "--config", type=str, default=None,
        help="配置文件路径（YAML/JSON 格式，默认: 脚本同目录 config.yml）",
    )
    parser.add_argument(
        "--loop", type=int, default=0,
        help="循环检测模式，指定间隔秒数（默认: 0=单次）",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="JSON 格式输出结果",
    )
    parser.add_argument(
        "--no-notify", action="store_true",
        help="禁用飞书通知（仅打印结果）",
    )
    parser.add_argument(
        "--webhook", type=str, default=None,
        help="飞书 Webhook URL（覆盖配置文件中的值）",
    )
    args = parser.parse_args()

    # ---- 加载配置文件 ----
    global FEISHU_WEBHOOK_URL, MONITOR_LIST

    config_path = _resolve_config_path(args.config)
    try:
        cfg = _load_config_file(config_path)
        MONITOR_LIST = cfg["monitor_list"]
        FEISHU_WEBHOOK_URL = cfg.get("webhook_url", DEFAULT_WEBHOOK_URL)
        print(f"已加载配置文件: {config_path}（{len(MONITOR_LIST)} 个标的）", flush=True)
    except FileNotFoundError:
        print(f"  配置文件不存在: {config_path}，使用内置默认配置", flush=True)
    except (json.JSONDecodeError, ValueError, yaml.YAMLError) as e:
        print(f"  配置文件解析失败: {e}，使用内置默认配置", flush=True)

    # 环境变量覆盖 webhook（最高优先级）
    webhook_env = os.environ.get("FEISHU_WEBHOOK_URL")
    if webhook_env:
        FEISHU_WEBHOOK_URL = webhook_env

    # 命令行 --webhook 覆盖（最高优先级）
    webhook = args.webhook or FEISHU_WEBHOOK_URL

    monitor = Monitor(webhook_url=webhook if not args.no_notify else "")

    if args.loop > 0:
        monitor.run_loop(interval=args.loop)
    else:
        results = monitor.run_once()

        if args.json:
            output = []
            for r in results:
                output.append({
                    "code": r.code,
                    "name": r.name,
                    "type": r.fund_type,
                    "last_price": r.last_price,
                    "ref_nav": r.ref_nav,
                    "nav_field": r.nav_field,
                    "premium_pct": r.premium_pct,
                    "threshold": r.threshold,
                    "is_alert": r.is_alert,
                    "update_time": r.update_time,
                    "error": r.error,
                })
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            print("\n" + "=" * 70)
            print("LOF/ETF 溢价率检测结果")
            print("=" * 70)
            for r in results:
                print(f"  {r.summary()}")
            print("=" * 70)

            alert_count = sum(1 for r in results if r.is_alert and not r.error)
            if alert_count > 0:
                print(f"\n共 {alert_count} 个标的溢价率低于阈值，需要关注！")
            else:
                print("\n所有标的溢价率正常。")

        if not args.no_notify:
            monitor.send_alerts(results)

        monitor.futu.close()


if __name__ == "__main__":
    main()
