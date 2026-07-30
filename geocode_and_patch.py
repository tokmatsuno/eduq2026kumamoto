#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全国教育機関ダッシュボード｜取引校 住所ジオコーディング＆座標自動置換スクリプト

役割：
  index.html に埋め込まれた取引校（type:"client"）を1校ずつオンライン検索し、
  住所・名称から緯度経度を特定して index.html の座標を実測値に置き換えます。
  （Cowork環境はネット制限で一括取得できないため、このスクリプトはお手元のMacで実行します）

使い方（ターミナル）：
  cd "このファイルのあるフォルダ"
  python3 geocode_and_patch.py

  ※ Python3 標準ライブラリのみで動作します（追加インストール不要）。
  ※ 途中で止めても geocode_cache.json に保存され、再実行で続きから再開します。
  ※ 実行前に index.html を index_beforeGeocode.html に自動バックアップします。

オプション：
  --limit N   先頭N校だけ試す（動作確認用）
  --engine gsi|nominatim   既定は nominatim（名称・住所検索に強い）。gsiは高速だが名称検索は弱め。
"""
import json, re, time, sys, os, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "index.html")
CACHE = os.path.join(HERE, "geocode_cache.json")
BACKUP = os.path.join(HERE, "index_beforeGeocode.html")

engine = "nominatim"
limit = None
for i, a in enumerate(sys.argv):
    if a == "--engine" and i+1 < len(sys.argv): engine = sys.argv[i+1]
    if a == "--limit" and i+1 < len(sys.argv): limit = int(sys.argv[i+1])

def load_cache():
    if os.path.exists(CACHE):
        try: return json.load(open(CACHE, encoding="utf-8"))
        except: return {}
    return {}

def save_cache(c):
    json.dump(c, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)

def geocode_nominatim(name, pref):
    q = f"{pref}{name}" if pref and pref != "不明" else name
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q + " 日本", "format": "json", "countrycodes": "jp", "limit": "1"})
    req = urllib.request.Request(url, headers={"User-Agent": "eduq-school-dashboard-geocoder/1.0 (matsuno@eduq.jp)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        arr = json.load(r)
    if arr:
        return float(arr[0]["lat"]), float(arr[0]["lon"])
    return None

def geocode_gsi(name, pref):
    q = f"{pref}{name}" if pref and pref != "不明" else name
    url = "https://msearch.gsi.go.jp/address-search/AddressSearch?" + urllib.parse.urlencode({"q": q})
    req = urllib.request.Request(url, headers={"User-Agent": "eduq-school-dashboard-geocoder/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        arr = json.load(r)
    if arr:
        lng, lat = arr[0]["geometry"]["coordinates"]
        return float(lat), float(lng)
    return None

def geocode(name, pref):
    try:
        return geocode_gsi(name, pref) if engine == "gsi" else geocode_nominatim(name, pref)
    except Exception as e:
        print("   ! error:", e)
        return None

def main():
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r"const DATA=(\[.*?\]);\nconst FEED=", html, re.S)
    if not m:
        print("ERROR: index.html 内の DATA が見つかりません。"); return
    DATA = json.loads(m.group(1))

    if not os.path.exists(BACKUP):
        open(BACKUP, "w", encoding="utf-8").write(html)
        print("バックアップ作成:", os.path.basename(BACKUP))

    cache = load_cache()
    clients = [d for d in DATA if d.get("type") == "client"]
    if limit: clients = clients[:limit]
    total = len(clients); ok = 0; done = 0
    delay = 0.4 if engine == "gsi" else 1.1  # Nominatimは1req/sec厳守
    print(f"対象取引校: {total}校 / エンジン: {engine} / 推定所要: 約{int(total*delay/60)+1}分")

    for d in clients:
        done += 1
        key = d["name"]
        if key in cache and cache[key]:
            d["lat"], d["lng"] = cache[key]; d["geo"] = "geocoded"; ok += 1
        else:
            res = geocode(d["name"], d.get("pref", ""))
            if res:
                d["lat"], d["lng"] = round(res[0], 6), round(res[1], 6)
                d["geo"] = "geocoded"; cache[key] = [d["lat"], d["lng"]]; ok += 1
            else:
                cache[key] = None
            time.sleep(delay)
        if done % 25 == 0:
            save_cache(cache)
            print(f"  {done}/{total}  成功 {ok}")

    save_cache(cache)
    # DATA を index.html に書き戻し
    new_data = json.dumps(DATA, ensure_ascii=False)
    html2 = html[:m.start(1)] + new_data + html[m.end(1):]
    open(HTML, "w", encoding="utf-8").write(html2)
    print(f"\n完了：{ok}/{total} 校を実測座標に更新し index.html を書き換えました。")
    print("失敗分は元の概略位置のままです（再実行で未取得のみ再試行します）。")

if __name__ == "__main__":
    main()
