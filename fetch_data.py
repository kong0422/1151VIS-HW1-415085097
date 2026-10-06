#!/usr/bin/env python3
"""
直接呼叫中央氣象署 API，把資料存成檔案（不經過瀏覽器，所以沒有 CORS 問題）。

輸出（預設放在 ./data/）：
  county_weather.csv   縣市彙整 CSV，格式與網頁「下載縣市彙整 CSV」相同，可用網頁的「載入縣市彙整 CSV」讀入
  station_obs.csv      測站明細 CSV
  raw/*.json           氣象署原始回傳（O-A0003-001、O-A0005-001、F-C0032-001）

用法：
  python3 fetch_data.py                    # 抓一次
  python3 fetch_data.py --interval 600     # 每 10 分鐘抓一次（Ctrl+C 結束）
  python3 fetch_data.py --history          # 同時留一份帶時間戳記的歷史檔
  python3 fetch_data.py --embed            # 把縣市資料直接寫進 taiwan-temp-map.html，之後雙擊開啟即可使用
  python3 fetch_data.py --embed 其他.html  # 寫進指定的 HTML 檔
  CWA_KEY=CWA-xxxx python3 fetch_data.py   # 以環境變數指定授權碼
"""
import argparse, csv, io, json, os, re, ssl, sys, time, urllib.error, urllib.parse, urllib.request
from collections import Counter
from datetime import datetime

KEY = os.environ.get("CWA_KEY", "CWA-22E9C318-4D92-4C32-B734-9BE27E3B1005")
BASE = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/"

_ctx = ssl.create_default_context()
_ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT   # 仍會驗證憑證鏈，只是放寬部分政府憑證缺少的擴充欄位檢查

DEFAULT_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "taiwan-temp-map.html")
CJK = re.compile(r"[\u4e00-\u9fff]")


def norm(s):
    return (s or "").replace("台", "臺")


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch(dataset, key):
    qs = urllib.parse.urlencode({"Authorization": key, "format": "JSON"})
    with urllib.request.urlopen(f"{BASE}{dataset}?{qs}", timeout=60, context=_ctx) as r:
        return json.loads(r.read().decode("utf-8"))


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def summarize(obs, uvmax, fc):
    """把三份原始資料整理成縣市彙整與測站明細。任何一份可為 None。回傳 (縣市列, 測站列, 訊息)。"""
    notes = []
    stations = []                      # 測站層級
    info = {}                          # 測站代碼 → (名稱, 縣市)
    wx_obs = {}                        # 縣市 → [天氣文字]

    for x in ((obs or {}).get("records") or {}).get("Station", []):
        we = x.get("WeatherElement") or {}
        county = (x.get("GeoInfo") or {}).get("CountyName")
        if not county:
            continue
        name, sid = x.get("StationName"), str(x.get("StationId"))
        info[sid] = (name, county)
        t = num(we.get("AirTemperature"))
        acc = num((we.get("Now") or {}).get("Precipitation"))
        if acc == -998:                # -998 為微量，以 0 計
            acc = 0.0
        sun = num(we.get("SunshineDuration"))
        uv_rt = num(we.get("UVIndex"))
        stations.append({
            "name": name, "county": county, "id": sid,
            "temp": t if t is not None and -50 < t < 60 else None,
            "acc": acc if acc is not None and 0 <= acc <= 1500 else None,
            "sun": sun if sun is not None and 0 <= sun <= 24 else None,
            "uv": uv_rt if uv_rt is not None and 0 <= uv_rt <= 25 else None,
        })
        w = str(we.get("Weather") or "")
        if CJK.search(w):
            wx_obs.setdefault(norm(county), []).append(w)

    # 紫外線：優先用「每日最大值」，用測站代碼對應回縣市；沒有就沿用即時讀數
    uv_src = "即時讀數（夜間為 0）"
    if uvmax:
        rec = uvmax.get("records") or {}
        we = rec.get("weatherElement")
        we = (we[0] if isinstance(we, list) and we else we) or {}
        by_id = {}
        for l in we.get("location", []):
            sid = str(next((l[k] for k in ("StationID", "StationId", "stationId", "locationCode") if k in l), ""))
            v = num(l.get("UVIndex", l.get("value")))
            if sid in info and v is not None and 0 <= v <= 25:
                by_id[sid] = v
        if by_id:
            uv_src = "今日最大值" + (f" {str(we.get('Date'))[:10]}" if we.get("Date") else "")
            for s in stations:
                s["uv"] = by_id.get(s["id"])
            for sid, v in by_id.items():           # 氣溫清單裡沒有的測站也補進來
                if not any(s["id"] == sid for s in stations):
                    stations.append({"name": info[sid][0], "county": info[sid][1], "id": sid,
                                     "temp": None, "acc": None, "sun": None, "uv": v})
        else:
            notes.append("紫外線每日最大值：沒有可對應到縣市的有效數值，改用即時讀數")
    else:
        notes.append("紫外線每日最大值：未取得，改用即時讀數")

    # 降雨機率與天氣預報（縣市層級）
    pop, wx_fc = {}, {}
    for l in ((fc or {}).get("records") or {}).get("location", []):
        c = norm(l.get("locationName"))
        for e in l.get("weatherElement", []):
            try:
                val = e["time"][0]["parameter"]["parameterName"]
            except (KeyError, IndexError, TypeError):
                continue
            if e.get("elementName") == "PoP" and num(val) is not None:
                pop[c] = num(val)
            elif e.get("elementName") == "Wx" and val:
                wx_fc[c] = str(val)

    # 縣市彙整
    names = {}
    for s in stations:
        names.setdefault(norm(s["county"]), s["county"])
    for c in list(pop) + list(wx_fc):
        names.setdefault(c, c)

    rows = []
    for c, shown in sorted(names.items()):
        grp = [s for s in stations if norm(s["county"]) == c]
        pick = lambda k: mean([s[k] for s in grp if s[k] is not None])
        weather = Counter(wx_obs[c]).most_common(1)[0][0] if c in wx_obs else wx_fc.get(c, "")
        rows.append({
            "county": norm(shown), "temp": pick("temp"), "uv": pick("uv"), "rain": pop.get(c),
            "acc": pick("acc"), "sun": pick("sun"),
            "n": sum(1 for s in grp if s["temp"] is not None), "weather": weather,
        })
    return rows, stations, notes, uv_src


def fmt(v):
    return "" if v is None else f"{v:.1f}"


COUNTY_HEAD = ["縣市", "氣溫(°C)", "紫外線(指數)", "降雨機率(%)", "累積雨量(mm)", "日照時數(小時)", "氣溫測站數", "天氣"]


def county_body(rows):
    return [[r["county"], fmt(r["temp"]), fmt(r["uv"]), fmt(r["rain"]), fmt(r["acc"]), fmt(r["sun"]), r["n"], r["weather"]] for r in rows]


def county_csv_text(rows):
    buf = io.StringIO(newline="")
    w = csv.writer(buf)
    w.writerow(COUNTY_HEAD)
    w.writerows(county_body(rows))
    return buf.getvalue()


def embed_into_html(path, csv_text, when):
    """把縣市彙整 CSV 寫進 HTML 內 /*EMBED_START*/ … /*EMBED_END*/ 之間。"""
    with open(path, encoding="utf-8") as fh:
        html = fh.read()
    payload = json.dumps({"time": when, "csv": csv_text}, ensure_ascii=False).replace("</", "<\\/")
    new, n = re.subn(r"/\*EMBED_START\*/.*?/\*EMBED_END\*/",
                     lambda m: "/*EMBED_START*/const EMBEDDED = " + payload + ";/*EMBED_END*/",
                     html, count=1, flags=re.S)
    if n == 0:
        raise RuntimeError("在 HTML 裡找不到 /*EMBED_START*/ … /*EMBED_END*/ 標記（請使用最新版的 taiwan-temp-map.html）")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new)


def write_csvs(rows, stations, out_dir, stamp=None):
    os.makedirs(out_dir, exist_ok=True)
    head, body = COUNTY_HEAD, county_body(rows)
    shead = ["測站", "縣市", "氣溫(°C)", "紫外線(指數)", "累積雨量(mm)", "日照時數(小時)"]
    sbody = [[s["name"], s["county"], fmt(s["temp"]), fmt(s["uv"]), fmt(s["acc"]), fmt(s["sun"])]
             for s in sorted(stations, key=lambda s: (norm(s["county"]), s["name"] or ""))]
    paths = {"county_weather.csv": (head, body), "station_obs.csv": (shead, sbody)}
    written = []
    for fname, (h, b) in paths.items():
        targets = [fname] + ([f"{fname[:-4]}_{stamp}.csv"] if stamp else [])
        for t in targets:
            p = os.path.join(out_dir, t)
            with open(p, "w", encoding="utf-8-sig", newline="") as f:   # BOM：Excel 直接開啟不會亂碼
                w = csv.writer(f)
                w.writerow(h)
                w.writerows(b)
            written.append(p)
    return written


def run_once(key, out_dir, history, embed=None):
    raw_dir = os.path.join(out_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    got, errs = {}, []
    for ds in ("O-A0003-001", "O-A0005-001", "F-C0032-001"):
        try:
            got[ds] = fetch(ds, key)
            with open(os.path.join(raw_dir, ds + ".json"), "w", encoding="utf-8") as f:
                json.dump(got[ds], f, ensure_ascii=False)
            print(f"  ✓ {ds}")
        except urllib.error.HTTPError as e:
            errs.append(f"{ds}：氣象署回應 HTTP {e.code}" + ("（請確認授權碼）" if e.code in (401, 403) else ""))
        except Exception as e:
            errs.append(f"{ds}：{e}")
    for e in errs:
        print("  ✗", e)
    if "O-A0003-001" not in got:
        print("沒有取得現在天氣觀測（O-A0003-001），無法產生 CSV。")
        return False
    rows, stations, notes, uv_src = summarize(got.get("O-A0003-001"), got.get("O-A0005-001"), got.get("F-C0032-001"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M") if history else None
    for p in write_csvs(rows, stations, out_dir, stamp):
        print("  已寫入", p)
    for n in notes:
        print("  注意：", n)
    latest = max((x.get("ObsTime", {}).get("DateTime", "") for x in got["O-A0003-001"]["records"]["Station"]), default="")
    when = latest[:16].replace("T", " ") or datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"  共 {len(rows)} 個縣市、{len(stations)} 個測站；觀測時間 {when}；紫外線：{uv_src}")
    if embed:
        try:
            embed_into_html(embed, county_csv_text(rows), when)
            print(f"  已把資料內嵌到 {embed}（直接雙擊開啟即可使用，不需要 server.py）")
        except Exception as e:
            print("  ✗ 內嵌失敗：", e)
            return False
    return True


def main():
    ap = argparse.ArgumentParser(description="抓取中央氣象署資料並存成 CSV")
    ap.add_argument("--key", default=KEY, help="授權碼（預設讀 CWA_KEY 環境變數）")
    ap.add_argument("--out", default="data", help="輸出資料夾（預設 ./data）")
    ap.add_argument("--interval", type=int, default=0, help="每隔幾秒重複抓取；0 表示只抓一次")
    ap.add_argument("--history", action="store_true", help="另存帶時間戳記的歷史檔")
    ap.add_argument("--embed", nargs="?", const=DEFAULT_HTML, default=None, metavar="HTML",
                    help="把縣市資料寫進 HTML 檔（省略檔名時使用與本腳本同資料夾的 taiwan-temp-map.html）")
    a = ap.parse_args()
    while True:
        print(datetime.now().strftime("[%Y-%m-%d %H:%M:%S] 抓取中…"))
        ok = run_once(a.key, a.out, a.history, a.embed)
        if a.interval <= 0:
            sys.exit(0 if ok else 1)
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
