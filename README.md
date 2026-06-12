# fund-monitor

LOF / ETF 婧环鐜囧疄鏃剁洃鎺э紝杩炴帴 [瀵岄€?OpenAPI](https://openapi.futunn.com/) 鑾峰彇瀹炴椂琛屾儏锛屾孩浠风巼浣庝簬璁惧畾闃堝€兼椂鑷姩鎺ㄩ€侀涔﹂€氱煡銆?
---

## 鍔熻兘

- 瀹炴椂鑾峰彇 LOF / ETF 鐨勭洏涓氦鏄撲环鏍间笌鍙傝€冨噣鍊?- 璁＄畻婧环鐜囷細`(鐜颁环 / 鍙傝€冨噣鍊?鈭?1) 脳 100%`
- 浣庝簬闃堝€兼椂閫氳繃椋炰功鏈哄櫒浜?Webhook 鍗＄墖閫氱煡
- 鏀寔鍗曟妫€娴嬪拰寰幆鐩戞帶涓ょ妯″紡
- 閰嶇疆鏂囦欢澶栫疆锛屽鍒犳爣鐨勪笉闇€瑕侀噸鏂版瀯寤?Docker 闀滃儚

## 鍓嶇疆鏉′欢

1. **OpenD 瀹㈡埛绔?* 蹇呴』鍦ㄦ湰鏈鸿繍琛岋紙榛樿 `127.0.0.1:11111`锛?2. Python 3.10+ 鎴?Docker

## 蹇€熷紑濮?
### 鏈湴杩愯

```bash
# 瀹夎渚濊禆
pip install futu-api requests pyyaml

# 閰嶇疆椋炰功 Webhook锛堜簩閫変竴锛?cp .env.example .env
# 缂栬緫 .env 濉叆鐪熷疄鐨?FEISHU_WEBHOOK_URL

# 鍗曟妫€娴?python monitor.py

# 姣?60 绉掑惊鐜洃鎺?python monitor.py --loop 60
```

### Docker 杩愯

```bash
# 鎷夊彇闀滃儚
docker pull deeplakehss/fund-monitor:latest

# 鍗曟妫€娴?docker run --rm \
  -e FEISHU_WEBHOOK_URL="浣犵殑椋炰功Webhook" \
  deeplakehss/fund-monitor

# 寰幆鐩戞帶锛堟帹鑽?docker-compose锛?docker-compose up -d
```

## 閰嶇疆锛坈onfig.yml锛?
鐩戞帶鏍囩殑鍒楄〃鍜?Webhook 鍦板潃缁熶竴鍦?`config.yml` 涓淮鎶わ紝淇敼鍚?`docker-compose restart` 鍗冲彲鐢熸晥锛?
```yaml
webhook_url: "浣犵殑椋炰功Webhook"

monitor_list:
  - code: "SZ.160644"
    name: "楣忓崕娓編浜掕仈缃慙OF"
    threshold: 2.0          # 婧环鐜囦綆浜?2% 鏃跺憡璀?    type: "LOF"
    nav_field: "prev_close"  # 鍙傝€冨噣鍊兼潵婧?```

### 瀛楁璇存槑

| 瀛楁 | 璇存槑 |
|------|------|
| `code` | 瀵岄€旇偂绁ㄤ唬鐮侊紝娣卞競 `SZ.xxxxxx`锛屾勃甯?`SH.xxxxxx` |
| `name` | 鏍囩殑鍚嶇О锛岄涔﹂€氱煡涓樉绀?|
| `threshold` | 婧环鐜囬槇鍊硷紙%锛夛紝褰撳墠婧环鐜囦綆浜庢鍊兼椂瑙﹀彂閫氱煡 |
| `type` | `LOF` 鎴?`ETF` |
| `nav_field` | 鍙傝€冨噣鍊兼潵婧愶細`prev_close`锛堟槰鏀朵环锛夈€乣nav`锛堝熀閲戝噣鍊硷級銆乣iopv`锛堢洏涓疄鏃?IOPV锛?|

### 鎵╁睍绀轰緥

鍙栨秷娉ㄩ噴鍗冲彲娣诲姞鏇村鏍囩殑锛?
```yaml
monitor_list:
  - code: "SZ.160644"
    name: "楣忓崕娓編浜掕仈缃慙OF"
    threshold: 2.0
    type: "LOF"
    nav_field: "prev_close"

  - code: "SZ.164824"
    name: "宸ラ摱鍗板害鍩洪噾LOF"
    threshold: 2.5
    type: "LOF"
    nav_field: "prev_close"

  - code: "SH.513050"
    name: "鏄撴柟杈句腑姒備簰鑱擡TF"
    threshold: 2.0
    type: "ETF"
    nav_field: "prev_close"
```

## 鐜鍙橀噺

| 鍙橀噺 | 璇存槑 | 榛樿鍊?|
|------|------|--------|
| `FEISHU_WEBHOOK_URL` | 椋炰功鏈哄櫒浜?Webhook 鍦板潃锛堜紭鍏堢骇鏈€楂橈級 | - |
| `FUTU_OPEND_HOST` | OpenD 鍦板潃 | `127.0.0.1` |
| `FUTU_OPEND_PORT` | OpenD 绔彛 | `11111` |
| `MONITOR_CONFIG_FILE` | 閰嶇疆鏂囦欢璺緞 | `./config.yml` |
| `PYTHONUNBUFFERED` | 鍏抽棴 Python 杈撳嚭缂撳啿 | `1` |

### 閰嶇疆浼樺厛绾?
椋炰功 Webhook 鐨勬渶缁堝彇鍊奸『搴忥細**鍛戒护琛?--webhook 鈫?鐜鍙橀噺 FEISHU_WEBHOOK_URL 鈫?config.yml 涓殑 webhook_url**

## 鍛戒护琛屽弬鏁?
```
python monitor.py --help

閫夐」:
  --config PATH     閰嶇疆鏂囦欢璺緞锛圷AML/JSON锛岄粯璁? config.yml锛?  --loop SECONDS    寰幆妫€娴嬫ā寮忥紝鎸囧畾闂撮殧绉掓暟锛堥粯璁? 0=鍗曟锛?  --json            JSON 鏍煎紡杈撳嚭缁撴灉
  --no-notify       绂佺敤椋炰功閫氱煡锛堜粎鎵撳嵃缁撴灉锛?  --webhook URL     椋炰功 Webhook URL锛堣鐩栭厤缃枃浠讹級
```

## Docker 閮ㄧ讲

`docker-compose.yml` 宸插寘鍚棩蹇楄疆杞紙鍗曟枃浠?10MB锛屼繚鐣?3 浠斤級鍜?256MB 鍐呭瓨闄愬埗銆傜敓浜х幆澧冨彧闇€锛?
```bash
docker-compose up -d      # 鍚姩
docker-compose logs -f    # 鏌ョ湅瀹炴椂鏃ュ織
docker-compose restart    # 閰嶇疆鍙樻洿鍚庨噸鍚?docker-compose down       # 鍋滄
```

## 婧环鐜囪绠楅€昏緫

```
婧环鐜?= (瀹炴椂浜ゆ槗浠?/ 鍙傝€冨噣鍊?- 1) 脳 100%
```

- **姝ｅ€?*锛氭孩浠凤紙甯傚満浠烽珮浜庡噣鍊硷級
- **璐熷€?*锛氭姌浠凤紙甯傚満浠蜂綆浜庡噣鍊硷級

鍙傝€冨噣鍊兼牴鎹?`nav_field` 鍙栧€硷細

| nav_field | 璇存槑 | 閫傜敤鍦烘櫙 |
|-----------|------|----------|
| `prev_close` | 鏄ㄦ棩鏀剁洏浠?| 榛樿锛岄€傜敤浜庢棤 IOPV 鏁版嵁鐨?LOF |
| `nav` | 鍩洪噾鍑€鍊?| 闇€瀵岄€旀彁渚涜瀛楁 |
| `iopv` | 鐩樹腑瀹炴椂 IOPV | 鏈€鍑嗙‘锛岄渶鏁版嵁婧愭敮鎸?|

## CI / CD

闀滃儚鏋勫缓鐢?GitHub Actions 鍦ㄤ簯绔畬鎴愶紝鎺ㄩ€佸埌 Docker Hub銆傛湰鍦颁笉鍋?`docker build`銆?
- **瑙﹀彂**锛氭帹閫佸埌 `main` 鍒嗘敮锛堜笉鍚?`.md` / `.gitignore` / `.env.example` 鍙樻洿锛?- **鏋舵瀯**锛歭inux/amd64 + linux/arm64 鍙屾灦鏋?- **鏍囩**锛歚latest` + commit SHA 鐭爣绛?- **缂撳瓨**锛欸itHub Actions Cache 鍔犻€熸瀯寤?
## 鎶€鏈爤

- Python 3.13
- [futu-api](https://github.com/FutunnOpen/py-futu) 鈥?瀵岄€?OpenAPI SDK
- PyYAML 鈥?YAML 閰嶇疆鏂囦欢瑙ｆ瀽
- requests 鈥?椋炰功 HTTP 閫氱煡
- Docker + GitHub Actions 鈥?瀹瑰櫒鍖栦笌 CI/CD

## 浠撳簱

- **GitHub**锛歨ttps://github.com/hushenshen/fund-monitor
- **Docker Hub**锛歚deeplakehss/fund-monitor:latest`
