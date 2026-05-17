"""
Low Float Catalyst Scanner — Web App
=====================================
Full web application with dashboard, live alerts, and push notifications.
Deploy free on Railway or Render.
"""

from flask import Flask, render_template, jsonify, request
import requests
import time
import datetime
import threading
import logging
import re
import json
import os
from bs4 import BeautifulSoup

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("scanner")

# ─────────────────────────────────────────────
# SETTINGS — edit these or set as environment variables
# ─────────────────────────────────────────────

PUSHOVER_USER  = os.environ.get("PUSHOVER_USER",  "YOUR_PUSHOVER_USER_TOKEN")
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_TOKEN", "YOUR_PUSHOVER_APP_TOKEN")

MIN_SCORE  = int(os.environ.get("MIN_SCORE",  "6"))
MIN_GAP    = float(os.environ.get("MIN_GAP",  "20.0"))
MAX_FLOAT  = float(os.environ.get("MAX_FLOAT", "5.0"))
MIN_PRICE  = float(os.environ.get("MIN_PRICE", "0.50"))
MAX_PRICE  = float(os.environ.get("MAX_PRICE", "50.0"))
MIN_VOLUME = int(os.environ.get("MIN_VOLUME", "100000"))
MIN_RVOL   = float(os.environ.get("MIN_RVOL",  "2.0"))
SCAN_SECS  = int(os.environ.get("SCAN_SECS",  "60"))
OPEN_HOUR  = int(os.environ.get("OPEN_HOUR",  "4"))
CLOSE_HOUR = int(os.environ.get("CLOSE_HOUR", "20"))

FEED_LIST = [
    ["GlobeNewswire Bio",     "https://www.globenewswire.com/RssFeed/subjectcode/15-Biomedical"],
    ["GlobeNewswire Defence", "https://www.globenewswire.com/RssFeed/subjectcode/28-Defense"],
    ["GlobeNewswire Energy",  "https://www.globenewswire.com/RssFeed/subjectcode/23-Energy"],
    ["GlobeNewswire Mergers", "https://www.globenewswire.com/RssFeed/subjectcode/36-Mergers+Acquisitions"],
    ["GlobeNewswire Finance", "https://www.globenewswire.com/RssFeed/subjectcode/6-Financial"],
    ["PR Newswire",           "https://www.prnewswire.com/rss/news-releases-list.rss"],
    ["Business Wire",         "https://feed.businesswire.com/rss/home/?rss=G1"],
    ["Yahoo Finance",         "https://finance.yahoo.com/news/rssindex"],
]

BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
PUSHOVER_URL = "https://api.pushover.net/1/messages.json"

SKIP = [
    "INC","LLC","CORP","LTD","THE","AND","FOR","SEC","ACT","NEW",
    "COM","NET","US","USA","FDA","CEO","CFO","COO","IPO","ETF",
    "NYSE","NASDAQ","AM","PM","EST","ET","AI","EV","UK","EU","UN",
    "WHO","DOD","DOE","NASA","M","B","Q","A","AN","IN","OF","TO",
    "BY","ON","AS","AT","HIGH","LOW","TOP","HOT","KEY","EPS",
    "NDA","BLA","CRL","RX","PR","TV","FM","RP","PO",
]

# ─────────────────────────────────────────────
# GLOBAL STATE
# ─────────────────────────────────────────────

state = {
    "alerts":        [],
    "seen":          [],
    "alerted":       [],
    "scanning":      False,
    "last_scan":     None,
    "feeds_status":  {},
    "scan_count":    0,
    "start_time":    datetime.datetime.now().isoformat(),
}

# ─────────────────────────────────────────────
# SCORING
# ─────────────────────────────────────────────

def has(text, words):
    for w in words:
        if w in text:
            return True
    return False

def score_text(text):
    t = text.lower()
    score = 0
    name = "General News"
    fda1 = ["fda", "food and drug"]
    fda2 = ["approv", "cleared", "clearance", "breakthrough", "fast track", "nda", "bla", "510k", "pdufa", "granted"]
    fda3 = ["reject", "refus", "crl", "clinical hold"]
    if has(t, fda1) and has(t, fda2):
        score = 3 if has(t, fda3) else 10
        name = "FDA Approval"
    trial1 = ["phase", "trial", "endpoint", "readout", "topline"]
    trial2 = ["positive", "success", "met", "significant", "strong", "favorable", "benefit"]
    trial3 = ["failed", "miss", "negative", "halt"]
    if score < 8:
        if has(t, trial1) and has(t, trial2):
            if not has(t, trial3):
                score = 8
                name = "Clinical Trial Win"
    merge1 = ["acqui", "merger", "takeover", "buyout", "definitive agreement", "tender offer", "going private"]
    if score < 9:
        if has(t, merge1):
            score = 9
            name = "Merger Acquisition"
    con1 = ["contract", "award", "awarded", "selected", "procurement"]
    con2 = ["pentagon", "military", "army", "navy", "air force", "government", "federal", "nasa", "darpa", "department of defense"]
    if score < 8:
        if has(t, con1) and has(t, con2):
            score = 8
            name = "Government Contract"
    earn1 = ["earnings", "eps", "revenue", "quarterly", "q1", "q2", "q3", "q4"]
    earn2 = ["beat", "exceed", "surpass", "above", "better than expected", "record", "topped"]
    earn3 = ["miss", "below", "disappoint", "fell short"]
    if score < 7:
        if has(t, earn1) and has(t, earn2):
            if not has(t, earn3):
                score = 7
                name = "Earnings Beat"
    sq1 = ["short squeeze", "short interest", "heavily shorted", "most shorted", "gamma squeeze", "unusual options"]
    if score < 7:
        if has(t, sq1):
            score = 7
            name = "Short Squeeze"
    def1 = ["defense", "defence", "weapon", "missile", "drone", "ammunition", "radar", "warfare"]
    def2 = ["war", "conflict", "escalat", "nato", "sanction", "surge", "spending"]
    if score < 7:
        if has(t, def1) and has(t, def2):
            score = 7
            name = "Defence Surge"
    en1 = ["oil", "natural gas", "crude", "lithium", "uranium", "opec", "lng"]
    en2 = ["surge", "spike", "soar", "war", "conflict", "sanction", "shortage"]
    if score < 6:
        if has(t, en1) and has(t, en2):
            score = 6
            name = "Energy Surge"
    deal1 = ["licensing", "collaboration", "joint venture", "exclusive agreement", "distribution agreement"]
    deal2 = ["terminat", "cancel", "dissolv"]
    if score < 6:
        if has(t, deal1):
            if not has(t, deal2):
                score = 6
                name = "Partnership Deal"
    if score == 0:
        return 0, "General News"
    if has(t, ["billion", "landmark", "historic", "first ever", "pivotal"]):
        score = min(10, score + 1)
    if has(t, ["bankrupt", "chapter 11", "going concern", "delist"]):
        score = max(1, score - 2)
    return score, name

def get_tickers(text):
    found = []
    for m in re.findall(r'\$([A-Z]{1,5})\b', text):
        found.append(m)
    for m in re.findall(r'\(([A-Z]{1,5})\)', text):
        if len(m) >= 2:
            found.append(m)
    for m in re.findall(r'(?:NYSE|NASDAQ|Nasdaq)[\s:]+([A-Z]{1,5})\b', text):
        found.append(m)
    seen = []
    out = []
    for t in found:
        if t not in SKIP and t not in seen and len(t) >= 2:
            seen.append(t)
            out.append(t)
    return out

def get_grade(score, gap, fm, rvol):
    pts = 0
    if score >= 7: pts = pts + 1
    if gap >= 30:  pts = pts + 1
    if fm <= 2:    pts = pts + 1
    if rvol >= 5:  pts = pts + 1
    if pts == 4: return "A"
    if pts == 3: return "B"
    if pts == 2: return "C"
    return "D"

def vol_str(v):
    if v >= 1000000:
        return str(round(v / 1000000.0, 1)) + "M"
    if v >= 1000:
        return str(int(v / 1000)) + "K"
    return str(v)

# ─────────────────────────────────────────────
# FEED FETCHER
# ─────────────────────────────────────────────

def get_feed(name, url):
    hdrs = {"User-Agent": BROWSER, "Accept": "text/html,*/*"}
    try:
        r = requests.get(url, headers=hdrs, timeout=15)
        if r.status_code >= 400:
            state["feeds_status"][name] = "HTTP " + str(r.status_code)
            return []
    except Exception as e:
        state["feeds_status"][name] = "Error: " + str(e)[:50]
        return []
    out = []
    try:
        soup = BeautifulSoup(r.content, "html.parser")
        entries = soup.find_all(["item", "entry"])
        for entry in entries:
            tt = entry.find("title")
            if not tt:
                continue
            title = tt.get_text(separator=" ", strip=True)
            link = ""
            lt = entry.find("link")
            if lt:
                link = lt.get("href", "") or lt.get_text(strip=True)
            if not link:
                gt = entry.find("guid")
                if gt:
                    link = gt.get_text(strip=True)
            summary = ""
            for sname in ["description", "summary", "content", "encoded"]:
                st = entry.find(sname)
                if st:
                    summary = st.get_text(separator=" ", strip=True)[:400]
                    break
            if title:
                out.append({"title": title, "link": link.strip(), "summary": summary})
        state["feeds_status"][name] = str(len(out)) + " items"
    except Exception as e:
        state["feeds_status"][name] = "Parse error"
    return out

# ─────────────────────────────────────────────
# PRICE DATA
# ─────────────────────────────────────────────

def get_price(ticker):
    hdrs = {"User-Agent": BROWSER}
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + ticker + "?interval=1d&range=5d&includePrePost=true"
    try:
        r = requests.get(url, headers=hdrs, timeout=10)
        if r.status_code != 200:
            return None
        meta = r.json()["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice", 0)
        prev = meta.get("chartPreviousClose", 0)
        vol = meta.get("regularMarketVolume", 0)
        avg = meta.get("averageDailyVolume10Day", vol) or vol
        pre = meta.get("preMarketPrice") or price
        if pre and abs(pre - prev) > abs(price - prev):
            price = pre
        gap = 0.0
        if prev:
            gap = (price - prev) / prev * 100.0
    except Exception:
        return None
    fm = 99.0
    try:
        u2 = "https://query1.finance.yahoo.com/v11/finance/quoteSummary/" + ticker + "?modules=defaultKeyStatistics"
        r2 = requests.get(u2, headers=hdrs, timeout=10)
        if r2.status_code == 200:
            raw = r2.json()["quoteSummary"]["result"][0]["defaultKeyStatistics"].get("floatShares", {}).get("raw", None)
            if raw:
                fm = raw / 1000000.0
    except Exception:
        pass
    return {"price": price, "gap": gap, "vol": int(vol), "avg": int(avg), "fm": fm}

# ─────────────────────────────────────────────
# PUSH NOTIFICATION
# ─────────────────────────────────────────────

def send_push(alert):
    if PUSHOVER_USER.startswith("YOUR_"):
        return
    g = alert["grade"]
    if g == "A":
        pri = 1
        sound = "siren"
    elif g == "B":
        pri = 0
        sound = "bugle"
    else:
        pri = -1
        sound = "pushover"
    title = alert["ticker"] + " Grade " + g + " " + str(round(alert["gap"])) + "% " + alert["cat"]
    body = (alert["cat"] + "\n\n" + alert["headline"][:140] + "\n\n" +
            "$" + str(round(alert["price"], 2)) + " Gap " + str(round(alert["gap"], 1)) + "%" +
            "\nVol " + vol_str(alert["vol"]) + " Float " + str(round(alert["fm"], 1)) + "M" +
            "\nScore " + str(alert["score"]) + "/10" +
            "\n" + alert["time"])
    data = {
        "token": PUSHOVER_TOKEN, "user": PUSHOVER_USER,
        "title": title, "message": body,
        "priority": pri, "sound": sound,
        "url": alert.get("url", ""), "url_title": "Read article",
    }
    try:
        r = requests.post(PUSHOVER_URL, data=data, timeout=10)
        if r.json().get("status") == 1:
            log.info("Push sent - " + alert["ticker"] + " Grade " + g)
    except Exception as e:
        log.warning("Push failed: " + str(e))

# ─────────────────────────────────────────────
# SCANNER LOGIC
# ─────────────────────────────────────────────

def check_seen(key):
    if key in state["seen"]:
        return True
    state["seen"].append(key)
    if len(state["seen"]) > 2000:
        state["seen"].pop(0)
    return False

def check_alerted(ticker):
    key = ticker + str(datetime.date.today())
    if key in state["alerted"]:
        return True
    state["alerted"].append(key)
    return False

def check_stock(ticker, headline, cat, score, url):
    try:
        q = get_price(ticker)
    except Exception:
        return
    if not q:
        return
    price = q["price"]
    gap = q["gap"]
    vol = q["vol"]
    avg = q["avg"]
    fm = q["fm"]
    if price < MIN_PRICE or price > MAX_PRICE:
        return
    if fm > MAX_FLOAT:
        return
    if gap < MIN_GAP:
        return
    if vol < MIN_VOLUME:
        return
    rvol = vol / avg if avg > 0 else 0
    if rvol < MIN_RVOL:
        return
    g = get_grade(score, gap, fm, rvol)
    if g == "C" or g == "D":
        return
    if check_alerted(ticker):
        return
    alert = {
        "id":       len(state["alerts"]) + 1,
        "ticker":   ticker,
        "headline": headline,
        "cat":      cat,
        "score":    score,
        "url":      url,
        "time":     datetime.datetime.now().strftime("%H:%M:%S ET"),
        "date":     datetime.date.today().strftime("%b %d %Y"),
        "price":    round(price, 2),
        "gap":      round(gap, 1),
        "vol":      vol,
        "vol_str":  vol_str(vol),
        "fm":       round(fm, 1),
        "rvol":     round(rvol, 1),
        "grade":    g,
    }
    state["alerts"].insert(0, alert)
    if len(state["alerts"]) > 100:
        state["alerts"] = state["alerts"][:100]
    log.info("ALERT " + ticker + " Grade:" + g + " Gap:" + str(round(gap, 1)) + "% " + cat)
    send_push(alert)

def handle_item(item):
    headline = item.get("title", "").strip()
    link = item.get("link", "").strip()
    summary = item.get("summary", "").strip()
    if not headline:
        return
    if check_seen(link or headline):
        return
    score, cat = score_text(headline + " " + summary)
    if score < MIN_SCORE:
        return
    tickers = get_tickers(headline + " " + summary)
    if not tickers:
        return
    for ticker in tickers[:3]:
        check_stock(ticker, headline, cat, score, link)

def scan_loop():
    while True:
        try:
            hour = datetime.datetime.now().hour
            if hour >= OPEN_HOUR and hour < CLOSE_HOUR:
                state["scanning"] = True
                state["scan_count"] = state["scan_count"] + 1
                state["last_scan"] = datetime.datetime.now().strftime("%H:%M:%S")
                for row in FEED_LIST:
                    name = row[0]
                    url = row[1]
                    try:
                        items = get_feed(name, url)
                        for item in items:
                            handle_item(item)
                    except Exception as e:
                        log.error("Feed error [" + name + "]: " + str(e))
                state["scanning"] = False
            else:
                state["scanning"] = False
        except Exception as e:
            log.error("Scan loop error: " + str(e))
            state["scanning"] = False
        time.sleep(SCAN_SECS)

# ─────────────────────────────────────────────
# WEB ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/alerts")
def api_alerts():
    return jsonify(state["alerts"])

@app.route("/api/status")
def api_status():
    return jsonify({
        "scanning":     state["scanning"],
        "last_scan":    state["last_scan"],
        "scan_count":   state["scan_count"],
        "alert_count":  len(state["alerts"]),
        "feeds":        state["feeds_status"],
        "pushover_ok":  not PUSHOVER_USER.startswith("YOUR_"),
        "uptime_since": state["start_time"],
        "market_open":  OPEN_HOUR <= datetime.datetime.now().hour < CLOSE_HOUR,
    })

@app.route("/api/settings")
def api_settings():
    return jsonify({
        "MIN_SCORE":  MIN_SCORE,
        "MIN_GAP":    MIN_GAP,
        "MAX_FLOAT":  MAX_FLOAT,
        "MIN_PRICE":  MIN_PRICE,
        "MAX_PRICE":  MAX_PRICE,
        "MIN_VOLUME": MIN_VOLUME,
        "MIN_RVOL":   MIN_RVOL,
        "SCAN_SECS":  SCAN_SECS,
        "OPEN_HOUR":  OPEN_HOUR,
        "CLOSE_HOUR": CLOSE_HOUR,
    })

@app.route("/api/clear", methods=["POST"])
def api_clear():
    state["alerts"] = []
    state["alerted"] = []
    return jsonify({"ok": True})

# ─────────────────────────────────────────────
# START
# ─────────────────────────────────────────────

scanner_thread = threading.Thread(target=scan_loop, daemon=True)
scanner_thread.start()
log.info("Scanner thread started")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
