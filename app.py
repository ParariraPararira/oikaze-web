"""
oikaze web app - Flask UI
"""
from flask import Flask, render_template, jsonify, request
import json, os, glob
from datetime import datetime, timedelta
from supabase import create_client

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

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def load_prediction(date, jcd, rno):
    path = os.path.join(PREDICTIONS_DIR, f"{date}_{jcd}_{rno:02d}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)

def get_ranking_from_supabase(date):
    if not supabase:
        return []
    res = supabase.table("race_results").select("*").eq("ymd", date).eq("skipped", False).execute()
    rows = res.data or []
    if not rows:
        return []

    # jcd別に集計
    stats = {}
    for r in rows:
        jcd = r["jcd"]
        if jcd not in stats:
            stats[jcd] = {"jcd": jcd, "name": BASHO.get(jcd, jcd),
                         "total": 0, "hits_a": 0, "hits_b": 0,
                         "invest": 0, "payout": 0}
        s = stats[jcd]
        s["total"] += 1
        s["invest"] += 1200
        if r.get("hit_a"):
            s["hits_a"] += 1
            s["payout"] += r.get("haraimodoshi", 0) or 0
        elif r.get("hit_b"):
            s["hits_b"] += 1
            s["payout"] += r.get("haraimodoshi", 0) or 0

    results = []
    for jcd, s in stats.items():
        if s["total"] == 0:
            continue
        hit_rate = (s["hits_a"] + s["hits_b"]) / s["total"] * 100
        return_rate = s["payout"] / s["invest"] * 100 if s["invest"] > 0 else 0
        results.append({
            "jcd": jcd,
            "name": s["name"],
            "total": s["total"],
            "hits_a": s["hits_a"],
            "hits_b": s["hits_b"],
            "hit_rate": round(hit_rate, 1),
            "return_rate": round(return_rate, 1),
        })

    results.sort(key=lambda x: (-x["return_rate"], -x["hit_rate"]))
    return results

@app.route("/")
def index():
    return render_template("index.html", basho=BASHO)

@app.route("/api/ranking/<date>")
def api_ranking_by_date(date):
    return jsonify(get_ranking_from_supabase(date)[:3])

@app.route("/api/results", methods=["POST"])
def api_save_results():
    data = request.json
    date = data.get("date")
    jcd = data.get("jcd")
    races = data.get("races", [])
    if supabase:
        for r in races:
            row = {
                "ymd": date, "jcd": jcd, "rno": r["rno"],
                "kumiban": r["trifecta"], "haraimodoshi": r.get("payout", 0),
                "hit_a": False, "hit_b": False, "skipped": False,
            }
            supabase.table("race_results").upsert(row, on_conflict="ymd,jcd,rno").execute()
    return jsonify({"status": "ok", "saved": len(races)})

@app.route("/api/yosou", methods=["POST"])
def api_yosou():
    data = request.json
    basho_code = data.get("basho")
    race_no = data.get("race_no")
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
    return jsonify({
        "pattern_a": ["1-2-3","1-2-4","1-3-2","1-3-4","1-4-2","1-4-3",
                      "2-1-3","2-1-4","2-3-1","3-1-2","3-2-1","1-5-2"],
        "pattern_b": ["1-2-3","1-3-2","2-1-3","2-3-1","3-1-2","3-2-1",
                      "1-4-2","1-2-4","2-4-1","1-5-2","2-4-1","3-1-4"],
        "basho": BASHO.get(basho_code, basho_code),
        "race_no": race_no,
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)