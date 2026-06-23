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

def get_results_from_supabase(date):
    if not supabase:
        return []
    res = supabase.table("race_results").select("*").eq("ymd", date).execute()
    return res.data or []

def calc_stats(date, jcd):
    rows = get_results_from_supabase(date)
    rows = [r for r in rows if r["jcd"] == jcd and not r.get("skipped")]
    if not rows:
        return None

    hits_a = hits_b = total = invest = payout_sum = 0
    for r in rows:
        pred = load_prediction(date, jcd, r["rno"])
        if not pred:
            continue
        total += 1
        invest += 1200
        kumiban = r.get("kumiban", "")
        pay = r.get("haraimodoshi", 0) or 0
        if kumiban in pred.get("pattern_a", []):
            hits_a += 1
            payout_sum += pay
        elif kumiban in pred.get("pattern_b", []):
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