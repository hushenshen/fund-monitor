#!/usr/bin/env python3
"""
LOF/ETF 婧环鐜囧疄鏃剁洃鎺ц剼鏈?============================
閫氳繃瀵岄€?OpenAPI 鑾峰彇瀹炴椂琛屾儏锛岃绠楁孩浠风巼锛屼綆浜庨槇鍊兼椂閫氳繃椋炰功 Webhook 鍙戦€侀€氱煡銆?
渚濊禆锛?    pip install futu-api requests

鐜瑕佹眰锛?    - OpenD 蹇呴』杩愯锛岄粯璁よ繛鎺?127.0.0.1:11111
    - 鍙€氳繃鐜鍙橀噺 FUTU_OPEND_HOST / FUTU_OPEND_PORT 淇敼

浣跨敤鏂瑰紡锛?    python monitor.py              # 鍗曟妫€娴?    python monitor.py --loop 60    # 姣?0绉掕疆璇竴娆★紙Ctrl+C 鍋滄锛?    python monitor.py --json       # JSON 鏍煎紡杈撳嚭锛堜笉鍙戦€侀€氱煡锛?
鎵╁睍鏂瑰紡锛?    淇敼涓嬫柟 MONITOR_LIST锛屾坊鍔犳洿澶?LOF/ETF 鏍囩殑鍗冲彲銆?"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# ============================================================
# 绔嬪嵆鍏抽棴 Python 杈撳嚭缂撳啿锛圖ocker 鍦烘櫙涓嬫棩蹇楀欢杩熺殑鍏抽敭锛?# ============================================================
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None
os.environ.setdefault("PYTHONUNBUFFERED", "1")

# ============================================================
# 渚濊禆鑷锛堝惎鍔ㄦ椂妫€鏌ワ紝缁欏嚭鏄庣‘淇鎸囧紩锛?# ============================================================
_MISSING_DEPS = []
for _mod, _pkg in [("futu", "futu-api"), ("requests", "requests"), ("yaml", "pyyaml")]:
    try:
        __import__(_mod)
    except ImportError:
        _MISSING_DEPS.append(f"{_mod} (pip install {_pkg})")

if _MISSING_DEPS:
    print(
        f"[ERROR] 缂哄皯渚濊禆: {', '.join(_mod for _mod, _pkg in [('futu','futu-api'),('requests','requests')] if _mod not in sys.modules)}\n"
        f"璇蜂娇鐢ㄤ互涓嬪懡浠ゅ畨瑁?\n"
        f"  {sys.executable} -m pip install futu-api requests\n",
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
# 鏃ュ織閰嶇疆
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("fund_monitor")

# ============================================================
# 浠ｇ爜鑷姩璇嗗埆锛氬彧杈?6 浣嶄唬鐮侊紝鑷姩鍒ゆ柇 SZ/SH 鍜?LOF/ETF
# ============================================================

def _is_sh(code: str) -> bool:
    """鍒ゆ柇 A 鑲′唬鐮佹槸鍚︿负娌競銆?xxxxx 鈫?娌競锛屽叾浣?鈫?娣卞競"""
    return code.startswith("6")


def _is_etf(code: str) -> bool:
    """鍒ゆ柇鍩洪噾浠ｇ爜鏄惁涓?ETF锛堝惁鍒欒涓?LOF锛?""
    sh_etf_prefixes = ("510", "511", "512", "513", "515", "516", "517", "518", "588")
    sz_etf_prefixes = ("159",)
    return code.startswith(sh_etf_prefixes + sz_etf_prefixes)


def _auto_detect(code: str) -> dict:
    """
    鏍规嵁 6 浣嶄唬鐮佽嚜鍔ㄦ帹鏂瘜閫斿畬鏁翠唬鐮佸拰鍩洪噾绫诲瀷銆?
    杩斿洖: {"futu_code": "SZ.160644", "market": "SZ", "type": "LOF", "name": ""}
    """
    code = str(code).strip()
    if "." in code:
        # 宸茬粡鏄畬鏁村瘜閫斾唬鐮侊紝涓嶅仛鑷姩鎺ㄦ柇
        futu_code = code
        market = code.split(".")[0]
    else:
        market = "SH" if _is_sh(code) else "SZ"
        futu_code = f"{market}.{code}"

    fund_type = "ETF" if _is_etf(code) else "LOF"

    return {"futu_code": futu_code, "market": market, "type": fund_type}


def _normalize_item(item) -> dict:
    """
    灏嗛厤缃潯鐩爣鍑嗗寲涓哄畬鏁存牸寮忋€?
    鏀寔涓夌鍐欐硶锛?      1. 绾唬鐮佸瓧绗︿覆: "160644"
      2. 甯﹀悕绉扮殑瀛楀吀: {"code": "160644", "name": "楣忓崕娓編浜掕仈缃慙OF"}
      3. 瀹屾暣瀛楀吀:     {"code": "SZ.160644", "type": "LOF", ...}

    杩斿洖瀹屾暣鏍煎紡瀛楀吀锛屾湭濉瓧娈电敤鑷姩鎺ㄦ柇缁撴灉 + 榛樿鍊艰ˉ榻愩€?    """
    if isinstance(item, str):
        item = {"code": item}

    if not isinstance(item, dict) or "code" not in item:
        raise ValueError(f"閰嶇疆鏉＄洰鏍煎紡閿欒: {item}")

    detected = _auto_detect(item["code"])

    return {
        "code": detected["futu_code"],
        "name": item.get("name", item["code"] if isinstance(item, str) else item.get("code", "")),
        "threshold": float(item.get("threshold", 2.0)),
        "type": item.get("type", detected["type"]),
        "nav_field": item.get("nav_field", "prev_close"),
    }


# ============================================================
# 閰嶇疆鏂囦欢鍔犺浇
# ============================================================

def _load_config_file(path: str) -> dict:
    """鍔犺浇 YAML/JSON 閰嶇疆鏂囦欢锛岃繑鍥?{webhook_url, monitor_list}"""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"閰嶇疆鏂囦欢涓嶅瓨鍦? {path}")

    with open(path, "r", encoding="utf-8") as f:
        if path.endswith((".yml", ".yaml")):
            cfg = yaml.safe_load(f)
        else:
            cfg = json.load(f)

    if cfg is None:
        raise ValueError("閰嶇疆鏂囦欢涓虹┖")
    if "monitor_list" not in cfg or not isinstance(cfg["monitor_list"], list):
        raise ValueError("閰嶇疆鏂囦欢缂哄皯 monitor_list 瀛楁鎴栨牸寮忛敊璇?)

    # 鏍囧噯鍖栨墍鏈夋潯鐩紙鑷姩鎺ㄦ柇 SZ/SH銆丩OF/ETF锛岃ˉ榻愰粯璁ゅ€硷級
    cfg["monitor_list"] = [_normalize_item(item) for item in cfg["monitor_list"]]

    return cfg


def _resolve_config_path(cli_arg: str = None) -> str:
    """
    鎸変紭鍏堢骇纭畾閰嶇疆鏂囦欢璺緞锛?    1. 鍛戒护琛?--config 鍙傛暟
    2. 鐜鍙橀噺 MONITOR_CONFIG_FILE
    3. 榛樿: 鑴氭湰鍚岀洰褰曚笅鐨?config.yml 鈫?config.yaml 鈫?config.json
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
    return os.path.join(base, "config.yml")  # 榛樿鍚?

# ============================================================
# 閰嶇疆鍖哄煙 鈥斺€?鍙€氳繃 config.json 瑕嗙洊锛屼慨鏀瑰悗鏃犻渶閲嶆柊鎵撻暅鍍?# ============================================================

# 榛樿鍊硷紙config.json 涓嶅瓨鍦ㄦ椂鐨勫厹搴曪級
DEFAULT_WEBHOOK_URL = "XXX"

DEFAULT_MONITOR_LIST = [
    {
        "code": "SZ.160644",
        "name": "楣忓崕娓編浜掕仈缃慙OF",
        "threshold": 2.0,
        "type": "LOF",
        "nav_field": "prev_close",
    },
]

# 浠ヤ笅鍙橀噺鍦?main() 涓€氳繃 load_config() 鏈€缁堣祴鍊?FEISHU_WEBHOOK_URL = DEFAULT_WEBHOOK_URL
MONITOR_LIST = DEFAULT_MONITOR_LIST

# OpenD 杩炴帴閰嶇疆
OPEND_HOST = os.environ.get("FUTU_OPEND_HOST", "127.0.0.1")
OPEND_PORT = int(os.environ.get("FUTU_OPEND_PORT", "11111"))


# ============================================================
# 鏁版嵁妯″瀷
# ============================================================

@dataclass
class PremiumResult:
    """鍗曞彧鏍囩殑鐨勬孩浠风巼妫€娴嬬粨鏋?""
    code: str
    name: str
    fund_type: str
    threshold: float
    last_price: float          # 瀹炴椂浜ゆ槗浠?    ref_nav: float             # 鍙傝€冨噣鍊硷紙鏄ㄦ敹/NAV/IOPV锛?    nav_field: str             # 浣跨敤浜嗗摢涓噣鍊煎瓧娈?    premium_pct: float         # 婧环鐜?(%)
    is_alert: bool             # 鏄惁婊¤冻鍛婅鏉′欢
    update_time: str           # 琛屾儏鏇存柊鏃堕棿
    error: Optional[str] = None

    def premium_direction(self) -> str:
        """婧环/鎶樹环鏂瑰悜"""
        if self.premium_pct > 0:
            return "婧环"
        elif self.premium_pct < 0:
            return "鎶樹环"
        return "骞充环"

    NAV_FIELD_LABELS = {
        "prev_close": "鏄ㄦ敹浠?,
        "nav": "鍩洪噾鍑€鍊?NAV)",
        "iopv": "瀹炴椂鍙傝€冨噣鍊?IOPV)",
        "": "鏈煡",
    }

    def summary(self) -> str:
        """鍗曡鎽樿锛堟棩蹇楁枃浠剁敤锛?""
        if self.error:
            return f"[{self.code} {self.name}] 閿欒: {self.error}"
        flag = "鈿狅笍 瑙﹀彂" if self.is_alert else "鉁?姝ｅ父"
        direction = self.premium_direction()
        return (
            f"{flag} [{self.code}] {self.name} | "
            f"鐜颁环: {self.last_price:.3f} | "
            f"鍙傝€冨噣鍊?{self.nav_field}): {self.ref_nav:.4f} | "
            f"婧环鐜? {self.premium_pct:+.2f}% ({direction}) | "
            f"闃堝€? {self.threshold}% | "
            f"鏇存柊鏃堕棿: {self.update_time}"
        )

    def detail_lines(self) -> list[str]:
        """鐢熸垚澶氳璇︾粏淇℃伅锛堟帶鍒跺彴杈撳嚭鐢級"""
        if self.error:
            return [f"  鉂?{self.name}锛坽self.code}锛夋煡璇㈠紓甯? {self.error}"]

        nav_label = self.NAV_FIELD_LABELS.get(self.nav_field, self.nav_field)
        direction = self.premium_direction()
        alert_line = ""
        if self.is_alert:
            alert_line = f" 鈿狅笍 浣庝簬闃堝€?{self.threshold}%"

        lines = [
            f"  鈹屸攢 {self.code}  {self.name}锛坽self.fund_type}锛?,
            f"  鈹? 瀹炴椂浠锋牸     楼 {self.last_price:.3f}",
            f"  鈹? 鍙傝€冨噣鍊?    楼 {self.ref_nav:.4f}锛坽nav_label}锛?,
            f"  鈹? 婧环鐜?      {self.premium_pct:+.2f}%锛坽direction}锛墈alert_line}",
            f"  鈹? 琛屾儏鏃堕棿     {self.update_time}",
            f"  鈹斺攢",
        ]
        return lines


# ============================================================
# 瀵岄€旇鎯呭鎴风
# ============================================================

class FutuClient:
    """灏佽瀵岄€?OpenAPI 琛屾儏杩炴帴"""

    def __init__(self, host: str = OPEND_HOST, port: int = OPEND_PORT):
        self.host = host
        self.port = port
        self._ctx: Optional[OpenQuoteContext] = None

    def connect(self) -> OpenQuoteContext:
        """寤虹珛琛屾儏杩炴帴"""
        if self._ctx is None:
            self._ctx = OpenQuoteContext(host=self.host, port=self.port)
            logger.info(f"宸茶繛鎺?OpenD: {self.host}:{self.port}")
        return self._ctx

    def close(self):
        """鍏抽棴琛屾儏杩炴帴"""
        if self._ctx is not None:
            self._ctx.close()
            self._ctx = None
            logger.info("宸叉柇寮€ OpenD 杩炴帴")

    def __enter__(self):
        return self.connect()

    def __exit__(self, *args):
        self.close()

    def get_snapshots(self, codes: list[str]) -> dict:
        """
        鎵归噺鑾峰彇甯傚満蹇収銆?        杩斿洖 {code: DataFrame row} 鐨勫瓧鍏搞€?        """
        ctx = self.connect()
        result = {}
        # 鍒嗘壒璇锋眰锛屾瘡鎵规渶澶?400 涓?        batch_size = 400
        for i in range(0, len(codes), batch_size):
            batch = codes[i:i + batch_size]
            ret, data = ctx.get_market_snapshot(batch)
            if ret != RET_OK:
                logger.error(f"鑾峰彇蹇収澶辫触: {data}")
                continue
            if data is not None and len(data) > 0:
                for idx in range(len(data)):
                    row = data.iloc[idx]
                    code = str(row.get("code", ""))
                    result[code] = row
        return result


# ============================================================
# 婧环鐜囪绠楀櫒
# ============================================================

class PremiumCalculator:
    """
    LOF/ETF 婧环鐜囪绠楀櫒

    鏀寔涓夌鍑€鍊兼潵婧愶紙閫氳繃 nav_field 鎸囧畾锛夛細
    - "prev_close": 浣跨敤鏄ㄦ棩鏀剁洏浠凤紙鏈€閫氱敤锛屼絾绮惧害鏈€宸級
    - "nav": 浣跨敤鍩洪噾鍑€鍊硷紙闇€瀵岄€斿揩鐓у寘鍚瀛楁锛?    - "iopv": 浣跨敤鐩樹腑瀹炴椂鍙傝€冨噣鍊硷紙鏈€鍑嗙‘锛岄渶鏁版嵁婧愭敮鎸侊級
    """

    # 瀵岄€斿揩鐓т腑鍙兘鐨勫噣鍊煎瓧娈靛悕鏄犲皠
    NAV_FIELD_CANDIDATES = {
        "prev_close": ["prev_close_price", "pre_price", "last_close"],
        "nav": ["net_value", "nav", "fund_nav"],
        "iopv": ["iopv", "estimated_nav", "reference_price"],
    }

    @staticmethod
    def _extract_field(row, candidates: list[str]) -> float:
        """浠庡揩鐓ц涓彁鍙栫涓€涓瓨鍦ㄧ殑鏁板€煎瓧娈?""
        for field_name in candidates:
            try:
                val = row.get(field_name, None)
                if val is not None and not (isinstance(val, float) and val != val):  # 鎺掗櫎 NaN
                    f = float(val)
                    if f > 0:
                        return f
            except (ValueError, TypeError):
                continue
        return 0.0

    def calculate(self, code: str, name: str, row, config: dict) -> PremiumResult:
        """璁＄畻鍗曞彧鏍囩殑鐨勬孩浠风巼"""
        fund_type = config.get("type", "LOF")
        threshold = config.get("threshold", 2.0)
        nav_field = config.get("nav_field", "prev_close")

        try:
            # 鑾峰彇瀹炴椂浜ゆ槗浠锋牸
            last_price = self._extract_field(row, ["last_price"])
            if last_price <= 0:
                return PremiumResult(
                    code=code, name=name, fund_type=fund_type,
                    threshold=threshold, last_price=0, ref_nav=0,
                    nav_field=nav_field, premium_pct=0, is_alert=False,
                    update_time="", error="鏃犳硶鑾峰彇浜ゆ槗浠锋牸"
                )

            # 鑾峰彇鍙傝€冨噣鍊?            candidates = self.NAV_FIELD_CANDIDATES.get(
                nav_field, self.NAV_FIELD_CANDIDATES["prev_close"]
            )
            ref_nav = self._extract_field(row, candidates)

            if ref_nav <= 0:
                # 鍏滃簳锛氬鏋滄寚瀹氬瓧娈典笉鍙敤锛屽皾璇?prev_close
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
                    update_time="", error="鏃犳硶鑾峰彇鍙傝€冨噣鍊?
                )

            # 璁＄畻婧环鐜?            premium_pct = (last_price / ref_nav - 1.0) * 100.0

            # 鍒ゆ柇鏄惁瑙﹀彂鍛婅锛氭孩浠风巼 < 闃堝€?            is_alert = premium_pct < threshold

            # 鑾峰彇鏇存柊鏃堕棿
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
# 椋炰功閫氱煡
# ============================================================

class FeishuNotifier:
    """椋炰功鏈哄櫒浜?Webhook 閫氱煡"""

    def __init__(self, webhook_url: str = FEISHU_WEBHOOK_URL):
        self.webhook_url = webhook_url

    def _build_card(self, results: list[PremiumResult]) -> dict:
        """鏋勫缓椋炰功娑堟伅鍗＄墖"""
        alert_results = [r for r in results if r.is_alert and not r.error]
        normal_results = [r for r in results if not r.is_alert and not r.error]
        error_results = [r for r in results if r.error]

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 鏋勫缓鍗＄墖鍐呭
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"馃搳 **LOF/ETF 婧环鐜囩洃鎺ф姤鍛?*\n馃晲 {now_str}",
                },
            },
            {"tag": "hr"},
        ]

        if alert_results:
            alert_lines = ["**鈿狅笍 婧环鐜囦綆浜庨槇鍊硷紙闇€鍏虫敞锛夛細**\n"]
            for r in alert_results:
                alert_lines.append(
                    f"鈥?**{r.name}**锛坽r.code}锛塡n"
                    f"  鐜颁环 {r.last_price:.3f} | 鍙傝€冨噣鍊?{r.ref_nav:.4f} | "
                    f"婧环鐜?**{r.premium_pct:+.2f}%** | 闃堝€?{r.threshold}%"
                )
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "\n".join(alert_lines)},
            })

        if normal_results:
            normal_lines = ["\n**姝ｅ父鏍囩殑锛?*\n"]
            for r in normal_results:
                direction = "婧环" if r.premium_pct > 0 else "鎶樹环"
                normal_lines.append(
                    f"鈥?{r.name}锛坽r.code}锛夋孩浠风巼 {r.premium_pct:+.2f}%锛坽direction}锛?
                )
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "\n".join(normal_lines)},
            })

        if error_results:
            error_lines = ["\n**鉂?鏌ヨ寮傚父锛?*\n"]
            for r in error_results:
                error_lines.append(f"鈥?{r.name}锛坽r.code}锛? {r.error}")
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
                        "content": "LOF/ETF 婧环鐜囩洃鎺?,
                    },
                    "template": "red" if alert_results else "green",
                },
                "elements": elements,
            },
        }

    def send(self, results: list[PremiumResult]) -> bool:
        """鍙戦€侀涔﹂€氱煡"""
        if not self.webhook_url:
            logger.warning("鏈厤缃涔?Webhook URL锛岃烦杩囬€氱煡")
            return False

        alert_count = sum(1 for r in results if r.is_alert and not r.error)
        if alert_count == 0:
            logger.info("鏃犲憡璀︽爣鐨勶紝璺宠繃椋炰功閫氱煡")
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
                logger.info(f"椋炰功閫氱煡鍙戦€佹垚鍔燂紙{alert_count} 涓憡璀︽爣鐨勶級")
                return True
            else:
                logger.error(f"椋炰功閫氱煡澶辫触: {resp_data}")
                return False
        except requests.RequestException as e:
            logger.error(f"椋炰功閫氱煡璇锋眰寮傚父: {e}")
            return False


# ============================================================
# 鐩戞帶涓婚€昏緫
# ============================================================

class Monitor:
    """婧环鐜囩洃鎺т富鎺у埗鍣?""

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
        """鎵ц涓€娆℃娴?""
        codes = [item["code"] for item in self.monitor_list]
        msg = f"馃攳 寮€濮嬫娴?{len(codes)} 涓爣鐨? {codes}"
        logger.info(msg)
        if verbose:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

        try:
            snapshots = self.futu.get_snapshots(codes)
        except Exception as e:
            logger.error(f"鑾峰彇蹇収澶辫触: {e}")
            if verbose:
                print(f"  鉂?琛屾儏杩炴帴澶辫触: {e}", flush=True)
            return [
                PremiumResult(
                    code=item["code"], name=item["name"],
                    fund_type=item.get("type", "LOF"),
                    threshold=item.get("threshold", 2.0),
                    last_price=0, ref_nav=0, nav_field="",
                    premium_pct=0, is_alert=False, update_time="",
                    error=f"琛屾儏杩炴帴澶辫触: {e}",
                )
                for item in self.monitor_list
            ]

        results = []
        for item in self.monitor_list:
            code = item["code"]
            name = item["name"]
            row = snapshots.get(code)

            if row is None:
                r = PremiumResult(
                    code=code, name=name, fund_type=item.get("type", "LOF"),
                    threshold=item.get("threshold", 2.0),
                    last_price=0, ref_nav=0, nav_field="",
                    premium_pct=0, is_alert=False, update_time="",
                    error="鏈幏鍙栧埌蹇収鏁版嵁",
                )
                results.append(r)
                for line in r.detail_lines():
                    print(line, flush=True)
                continue

            result = self.calculator.calculate(code, name, row, item)
            results.append(result)
            logger.info(result.summary())
            # 姣忎釜鏍囩殑閮借緭鍑鸿缁嗙殑澶氳淇℃伅
            for line in result.detail_lines():
                print(line, flush=True)

        print("", flush=True)  # 绌鸿鍒嗛殧
        return results

    def send_alerts(self, results: list[PremiumResult]):
        """鍙戦€佸憡璀﹂€氱煡"""
        alert_results = [r for r in results if r.is_alert and not r.error]
        if alert_results:
            print(f"  馃摛 鍙戦€侀涔﹂€氱煡锛坽len(alert_results)} 涓憡璀︽爣鐨勶級...", flush=True)
            self.notifier.send(results)
        else:
            msg = "鏈妫€娴嬫棤鍛婅"
            logger.info(msg)
            print(f"  鉁?{msg}", flush=True)

    def run_loop(self, interval: int = 60):
        """寰幆鐩戞帶妯″紡"""
        msg = f"馃殌 鍚姩寰幆鐩戞帶锛岄棿闅?{interval} 绉掞紝鎸?Ctrl+C 鍋滄"
        logger.info(msg)
        print(f"\n{'=' * 60}")
        print(msg)
        print(f"{'=' * 60}")
        # 鎵撳嵃鐩戞帶鍒楄〃
        print(f"\n馃搵 鐩戞帶鏍囩殑锛堝叡 {len(self.monitor_list)} 涓級锛?)
        for item in self.monitor_list:
            print(f"  鈥?{item['code']}  {item['name']}锛坽item.get('type', 'LOF')}锛夐槇鍊?{item.get('threshold', 2.0)}%")
        print(f"\n{'=' * 60}\n", flush=True)

        cycle = 0
        try:
            while True:
                cycle += 1
                print(f"--- 绗?{cycle} 杞娴?[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ---", flush=True)
                results = self.run_once()
                self.send_alerts(results)
                print(f"馃挙 绛夊緟 {interval} 绉掑悗杩涜绗?{cycle + 1} 杞娴?..\n", flush=True)
                time.sleep(interval)
        except KeyboardInterrupt:
            print(f"\n馃洃 鐩戞帶宸插仠姝紝鍏辨墽琛?{cycle} 杞娴?, flush=True)
            logger.info("鐩戞帶宸插仠姝?)
        finally:
            self.futu.close()


# ============================================================
# 鍛戒护琛屽叆鍙?# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="LOF/ETF 婧环鐜囧疄鏃剁洃鎺?,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
閰嶇疆璇存槑:
  鐩戞帶鏍囩殑鍒楄〃鍦?config.yml 涓淮鎶わ紝淇敼鍚?docker-compose restart 鍗冲彲鐢熸晥锛?  鏃犻渶閲嶆柊鏋勫缓 Docker 闀滃儚銆?
config.yml 绀轰緥 (鍙緭 6 浣嶄唬鐮佸嵆鍙紝鑷姩鎺ㄦ柇 SZ/SH 鍜?LOF/ETF):
  webhook_url: "XXX"
  monitor_list:
    - "160644"       # 绾唬鐮?鈥?鑷姩璇嗗埆
    - code: "513050" # 灞曞紑鍐欐硶锛岃嚜瀹氫箟鍚嶇О
      name: "鏄撴柟杈句腑姒備簰鑱擡TF"
      threshold: 2.0

浣跨敤绀轰緥:
  python monitor.py                       # 鍗曟妫€娴嬶紙浣跨敤榛樿 config.yml锛?  python monitor.py --config my.yml       # 鎸囧畾閰嶇疆鏂囦欢
  python monitor.py --loop 60             # 姣?0绉掑惊鐜娴?  python monitor.py --json --no-notify    # JSON杈撳嚭锛屼笉鍙戦€氱煡
        """,
    )
    parser.add_argument(
        "--config", type=str, default=None,
        help="閰嶇疆鏂囦欢璺緞锛圷AML/JSON 鏍煎紡锛岄粯璁? 鑴氭湰鍚岀洰褰?config.yml锛?,
    )
    parser.add_argument(
        "--loop", type=int, default=0,
        help="寰幆妫€娴嬫ā寮忥紝鎸囧畾闂撮殧绉掓暟锛堥粯璁? 0=鍗曟锛?,
    )
    parser.add_argument(
        "--json", action="store_true",
        help="JSON 鏍煎紡杈撳嚭缁撴灉",
    )
    parser.add_argument(
        "--no-notify", action="store_true",
        help="绂佺敤椋炰功閫氱煡锛堜粎鎵撳嵃缁撴灉锛?,
    )
    parser.add_argument(
        "--webhook", type=str, default=None,
        help="椋炰功 Webhook URL锛堣鐩栭厤缃枃浠朵腑鐨勫€硷級",
    )
    args = parser.parse_args()

    # ---- 鍔犺浇閰嶇疆鏂囦欢 ----
    global FEISHU_WEBHOOK_URL, MONITOR_LIST

    config_path = _resolve_config_path(args.config)
    try:
        cfg = _load_config_file(config_path)
        MONITOR_LIST = cfg["monitor_list"]
        FEISHU_WEBHOOK_URL = cfg.get("webhook_url", DEFAULT_WEBHOOK_URL)
        print(f"馃搫 宸插姞杞介厤缃枃浠? {config_path}锛坽len(MONITOR_LIST)} 涓爣鐨勶級", flush=True)
    except FileNotFoundError:
        print(f"鈿狅笍  閰嶇疆鏂囦欢涓嶅瓨鍦? {config_path}锛屼娇鐢ㄥ唴缃粯璁ら厤缃?, flush=True)
    except (json.JSONDecodeError, ValueError, yaml.YAMLError) as e:
        print(f"鈿狅笍  閰嶇疆鏂囦欢瑙ｆ瀽澶辫触: {e}锛屼娇鐢ㄥ唴缃粯璁ら厤缃?, flush=True)

    # 鐜鍙橀噺瑕嗙洊 webhook锛堟渶楂樹紭鍏堢骇锛?    webhook_env = os.environ.get("FEISHU_WEBHOOK_URL")
    if webhook_env:
        FEISHU_WEBHOOK_URL = webhook_env

    # 鍛戒护琛?--webhook 瑕嗙洊锛堟渶楂樹紭鍏堢骇锛?    webhook = args.webhook or FEISHU_WEBHOOK_URL

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
            print("LOF/ETF 婧环鐜囨娴嬬粨鏋?)
            print("=" * 70)
            for r in results:
                print(f"  {r.summary()}")
            print("=" * 70)

            alert_count = sum(1 for r in results if r.is_alert and not r.error)
            if alert_count > 0:
                print(f"\n鈿狅笍 鍏?{alert_count} 涓爣鐨勬孩浠风巼浣庝簬闃堝€硷紝闇€瑕佸叧娉紒")
            else:
                print("\n鉁?鎵€鏈夋爣鐨勬孩浠风巼姝ｅ父銆?)

        if not args.no_notify:
            monitor.send_alerts(results)

        monitor.futu.close()


if __name__ == "__main__":
    main()
