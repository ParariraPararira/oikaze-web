"""
oikaze web app - Flask UI
"""
from flask import Flask, render_template, jsonify, request
import json, os, glob
from datetime import datetime, timedelta

app = Flask(__name__)

BASHO = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島",
    "05": "多摩川", "06": "浜名湖", "07": "蒲郡", "08": "常滑",
    "09": "津", "10": "三国", "11": "びわこ", "12": "住之江",
    "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島",
    "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
    "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}

BASE = os.path.join(os.path.dirname(__file__), "..")
PREDICTIONS_DIR = os.path.join(BASE, "predictions")
RESULTS_DIR = os.path.join(BASE, "results")

os.makedirs(RESULTS_DIR, exist_ok=True)

def load_prediction(date, jcd, rno):
    path = os.path.join(PREDICTIONS_DIR, f"{date}_{jcd}_{rno:02d}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)

def load_result(date, jcd, rno):
    path = os.path.join(RESULTS_DIR, f"{date}_{jcd}_{rno:02d}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)

def save_result(date, jcd, rno, trifecta, payout):
    path = os.path.join(RESULTS_DIR, f"{date}_{jcd}_{rno:02d}.json")
    with open(path, "w") as f:
        json.dump({"date": date, "jcd": jcd, "rno": rno,
                   "trifecta": trifecta, "payout": payout}, f)

def calc_stats(date, jcd):
    """指定日・会場の的中率・回収率を計算"""
    hits_a = hits_b = total = invest = payout_sum = 0
    for rno in range(1, 13):
        pred = load_prediction(date, jcd, rno)
        result = load_result(date, jcd, rno)
        if not pred or not result:
            continue
        tri = result.get("trifecta", "")
        pay = result.get("payout", 0) or 0
        total += 1
        invest += 1200  # 12点×100円
        if tri in pred.get("pattern_a", []):
            hits_a += 1
            payout_sum += pay
        elif tri in pred.get("pattern_b", []):
            hits_b += 1
            payout_sum += pay
    if total == 0:
        return None
    hit_rate = (hits_a + hits_b) / total * 100
    return_rate = payout_sum / invest * 100 if invest > 0 else 0
    return {
        "jcd": jcd,
        "name": BASHO.get(jcd, jcd),
        "total": total,
        "hits_a": hits_a,
        "hits_b": hits_b,
        "hit_rate": hit_rate,
        "return_rate": return_rate,
    }

def get_ranking(date):
    """指定日の全場ランキングを返す"""
    results = []
    jcds = set()
    # predictionsから対象日の会場を取得
    pattern = os.path.join(PREDICTIONS_DIR, f"{date}_*.json")
    for f in glob.glob(pattern):
        basename = os.path.basename(f)
        parts = basename.split("_")
        if len(parts) >= 2:
            jcds.add(parts[1])
    for jcd in jcds:
        stats = calc_stats(date, jcd)
        if stats:
            results.append(stats)
    results.sort(key=lambda x: (-x["hit_rate"], -x["return_rate"]))
    return results

@app.route("/")
def index():
    return render_template("index.html", basho=BASHO)

@app.route("/api/ranking/today")
def api_ranking_today():
    jst = datetime.utcnow() + timedelta(hours=9)
    date = jst.strftime("%Y%m%d")
    ranking = get_ranking(date)
    return jsonify(ranking[:3])

@app.route("/api/ranking/yesterday")
def api_ranking_yesterday():
    jst = datetime.utcnow() + timedelta(hours=9)
    date = (jst - timedelta(days=1)).strftime("%Y%m%d")
    ranking = get_ranking(date)
    return jsonify(ranking[:3])

@app.route("/api/results", methods=["POST"])
def api_save_results():
    """途中結果を一括保存"""
    data = request.json
    date = data.get("date")
    jcd = data.get("jcd")
    races = data.get("races", [])
    for r in races:
        save_result(date, jcd, r["rno"], r["trifecta"], r.get("payout", 0))
    return jsonify({"status": "ok", "saved": len(races)})

@app.route("/api/yosou", methods=["POST"])
def api_yosou():
    data = request.json
    basho_code = data.get("basho")
    race_no = data.get("race_no")
    boats_info = data.get("boats", [])

    # 実際の予想ファイルがあれば読み込む
    jst = datetime.utcnow() + timedelta(hours=9)
    date = jst.strftime("%Y%m%d")
    pred = load_prediction(date, basho_code, int(race_no))

    if pred:
        return jsonify({
            "pattern_a": pred["pattern_a"],
            "pattern_b": pred["pattern_b"],
            "basho": BASHO.get(basho_code, basho_code),
            "race_no": race_no,
        })

    # 予想ファイルがない場合はダミー
    return jsonify({
        "pattern_a": ["1-2-3","1-2-4","1-3-2","1-3-4","1-4-2","1-4-3",
                      "2-1-3","2-1-4","2-3-1","3-1-2","3-2-1","1-5-2"],
        "pattern_b": ["1-2-3","1-3-2","2-1-3","2-3-1","3-1-2","3-2-1",
                      "1-4-2","1-2-4","2-1-4","1-5-2","2-4-1","3-1-4"],
        "basho": BASHO.get(basho_code, basho_code),
        "race_no": race_no,
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)