#!/usr/bin/env python3
"""
Smart Indian E-Ticket Fraud Detection — Flask Backend
Firebase Firestore (REST API) + ML Fraud Detection + Image Scanning
"""
import os, json, random, string, time, hashlib, pickle, hmac
from datetime import datetime, timedelta
import requests
import numpy as np
import pandas as pd
from flask import Flask, request, jsonify, send_from_directory, send_file
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Optional CV / OCR
try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False

try:
    import pytesseract
    OCR_OK = True
except ImportError:
    OCR_OK = False

# PDF
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# ─── App Setup ──────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend'), static_url_path='')
CORS(app, resources={r"/api/*": {"origins": "*"}})
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1) # Render IP Fix

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH  = os.path.join(BASE_DIR, '..', 'ml', 'fraud_model.pkl')
REPORTS_DIR = os.path.join(BASE_DIR, '..', 'reports')
UPLOADS_DIR = os.path.join(BASE_DIR, '..', 'uploads')
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

# ─── Firebase Config ─────────────────────────────────────────────────────────
FIREBASE_API_KEY    = "AIzaSyBg8DhrkbwRwUP7-OPbIpmjhsCjUcchtUA"
FIREBASE_PROJECT_ID = "trail-45113"
FS_BASE = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents"

def fs_url(collection, doc_id=""):
    base = f"{FS_BASE}/{collection}"
    return f"{base}/{doc_id}" if doc_id else base

def to_fs(data):
    """Python dict → Firestore REST fields"""
    def _cv(v):
        if v is None:           return {"nullValue": None}
        if isinstance(v, bool): return {"booleanValue": v}
        if isinstance(v, int):  return {"integerValue": str(v)}
        if isinstance(v, float):return {"doubleValue": v}
        if isinstance(v, str):  return {"stringValue": v}
        if isinstance(v, dict): return {"mapValue": {"fields": {k: _cv(x) for k, x in v.items()}}}
        if isinstance(v, list): return {"arrayValue": {"values": [_cv(i) for i in v]}}
        return {"stringValue": str(v)}
    return {"fields": {k: _cv(v) for k, v in data.items()}}

def from_fs(doc):
    """Firestore REST document → Python dict"""
    def _dc(v):
        if "nullValue"    in v: return None
        if "booleanValue" in v: return v["booleanValue"]
        if "integerValue" in v: return int(v["integerValue"])
        if "doubleValue"  in v: return v["doubleValue"]
        if "stringValue"  in v: return v["stringValue"]
        if "mapValue"     in v: return {k: _dc(x) for k, x in v["mapValue"].get("fields", {}).items()}
        if "arrayValue"   in v: return [_dc(i) for i in v["arrayValue"].get("values", [])]
        return None
    fields = doc.get("fields", {})
    result = {k: _dc(v) for k, v in fields.items()}
    # attach document id
    name = doc.get("name", "")
    if name:
        result["_id"] = name.split("/")[-1]
    return result

def fs_get(collection, doc_id):
    r = requests.get(f"{fs_url(collection, doc_id)}?key={FIREBASE_API_KEY}")
    if r.status_code == 200:
        return from_fs(r.json())
    return None

def fs_set(collection, doc_id, data):
    r = requests.patch(
        f"{fs_url(collection, doc_id)}?key={FIREBASE_API_KEY}",
        json=to_fs(data)
    )
    return r.status_code in (200, 201)

def fs_create(collection, data):
    """Auto-ID document creation"""
    r = requests.post(
        f"{fs_url(collection)}?key={FIREBASE_API_KEY}",
        json=to_fs(data)
    )
    if r.status_code in (200, 201):
        doc = r.json()
        return doc.get("name", "").split("/")[-1]
    return None

def fs_query(collection, field, op, value):
    """Simple equality / comparison query"""
    ops = {"==": "EQUAL", "<": "LESS_THAN", ">": "GREATER_THAN",
           "<=": "LESS_THAN_OR_EQUAL", ">=": "GREATER_THAN_OR_EQUAL"}
    payload = {
        "structuredQuery": {
            "from": [{"collectionId": collection}],
            "where": {
                "fieldFilter": {
                    "field": {"fieldPath": field},
                    "op": ops.get(op, "EQUAL"),
                    "value": to_fs({field: value})["fields"][field]
                }
            },
            "orderBy": [{"field": {"fieldPath": "__name__"}, "direction": "ASCENDING"}]
        }
    }
    r = requests.post(
        f"{FS_BASE}:runQuery?key={FIREBASE_API_KEY}",
        json=payload
    )
    if r.status_code == 200:
        return [from_fs(x["document"]) for x in r.json() if "document" in x]
    return []

def fs_list(collection, limit=50):
    r = requests.get(f"{fs_url(collection)}?key={FIREBASE_API_KEY}&pageSize={limit}")
    if r.status_code == 200:
        return [from_fs(d) for d in r.json().get("documents", [])]
    return []

# ─── ML Model ────────────────────────────────────────────────────────────────
fraud_model = None

def load_model():
    global fraud_model
    try:
        with open(MODEL_PATH, 'rb') as f:
            fraud_model = pickle.load(f)
        print(f"Fraud model loaded | Accuracy: {fraud_model.get('accuracy',0)*100:.1f}%")
    except Exception as e:
        print(f"Model not loaded: {e}")

load_model()

def predict_fraud(features: dict) -> dict:
    """Run ML fraud prediction on booking features"""
    if not fraud_model:
        return {"risk_score": 0, "risk_level": "LOW", "error": "Model not loaded"}

    try:
        # 1. Feature Engineering (match train_model.py)
        # Category Encoders
        tt_enc  = fraud_model["encoders"]["ticket_type"].transform([features.get("ticket_type", "train")])[0]
        cls_enc = fraud_model["encoders"]["class"].transform([features.get("class", "General")])[0]
        ch_enc  = fraud_model["encoders"]["booking_channel"].transform([features.get("booking_channel", "official_website")])[0]
        src_enc = fraud_model["encoders"]["start_station"].transform([features.get("start_station", "Delhi")])[0]
        dst_enc = fraud_model["encoders"]["end_station"].transform([features.get("end_station", "Mumbai")])[0]
        dev_enc = fraud_model["encoders"]["device_type"].transform([str(features.get("device_type", "unknown"))])[0]
        
        # Numerical
        price = float(features.get("price", 500))
        price_z = (price - 1000) / 500.0
        p_km    = float(features.get("price_per_km", 1.5))
        days    = int(features.get("days_until_travel", 7))
        pnr_v   = 1 if len(str(features.get("pnr", ""))) == 10 else 0
        bfreq   = int(features.get("booking_frequency", 1))
        ttsec   = int(features.get("time_taken_sec", 60))
        lfreq   = int(features.get("login_frequency", 1))
        ipc     = int(features.get("ip_change_flag", 0))

        X_raw = np.array([[
            tt_enc, cls_enc, ch_enc, src_enc, dst_enc,
            price, price_z, p_km, days, pnr_v,
            bfreq, ttsec, lfreq, dev_enc, ipc
        ]])

        # 2. Scaling
        X_scaled = fraud_model["scaler"].transform(X_raw)

        # 3. Prediction (Random Forest)
        final = float(fraud_model["rf"].predict_proba(X_scaled)[0][1]) * 100
        final = round(final, 1)
        
        risk  = "HIGH" if final >= 70 else ("MEDIUM" if final >= 30 else "LOW")
        return {"risk_score": final, "risk_level": risk, "ml_score": final}
        
    except Exception as e:
        print(f"Prediction Error: {e}")
        return {"risk_score": 15.0, "risk_level": "LOW", "error": str(e)}

# ─── OTP Store (in-memory for speed; also saved to Firestore) ────────────────
_otp_store: dict = {}   # {session_id: {otp, expires, booking_data}}

def gen_otp():
    return ''.join(random.choices(string.digits, k=6))

def gen_token(length=20):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def gen_pnr():
    return ''.join(random.choices(string.ascii_uppercase, k=2)) + \
           ''.join(random.choices(string.digits, k=8))

SECRET_KEY = "SECURE_TRAIL_SUPER_SECRET_KEY_2026"

def generate_qr_hash(payload):
    data_str = f"{payload.get('ticket_id')}|{payload.get('user_id')}|{payload.get('source')}|{payload.get('destination')}|{payload.get('company')}"
    return hmac.new(SECRET_KEY.encode(), data_str.encode(), hashlib.sha256).hexdigest()

# ─── Image Tamper Classifier (AI) ──────────────────────────────────────────
img_fraud_model = None

def load_img_fraud_model():
    global img_fraud_model
    path = os.path.join(BASE_DIR, '..', 'ml', 'img_fraud_model.pkl')
    try:
        if os.path.exists(path):
            with open(path, 'rb') as f:
                img_fraud_model = pickle.load(f)
            print(f"Image Fraud model loaded | Accuracy: {img_fraud_model.get('accuracy',0)*100:.1f}%")
    except Exception as e:
        print(f"Image Fraud model not loaded: {e}")

load_img_fraud_model()

def extract_img_features(img):
    """Extract features for tampering detection"""
    # Resize for consistency
    img_res = cv2.resize(img, (200, 100))
    gray = cv2.cvtColor(img_res, cv2.COLOR_BGR2GRAY)
    
    # Edge Density
    edges = cv2.Canny(gray, 100, 200)
    edge_density = np.sum(edges > 0) / edges.size
    
    # Blurriness
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # Color
    hsv = cv2.cvtColor(img_res, cv2.COLOR_BGR2HSV)
    h_mean, h_std = np.mean(hsv[:,:,0]), np.std(hsv[:,:,0])
    s_mean, s_std = np.mean(hsv[:,:,1]), np.std(hsv[:,:,1])
    v_mean, v_std = np.mean(hsv[:,:,2]), np.std(hsv[:,:,2])
    
    # HOG (subset)
    win_size = (200, 100)
    block_size = (20, 20)
    block_stride = (10, 10)
    cell_size = (10, 10)
    nbins = 9
    hog = cv2.HOGDescriptor(win_size, block_size, block_stride, cell_size, nbins)
    hog_feats = hog.compute(gray).flatten()
    
    basic_feats = [edge_density, blur_score, h_mean, h_std, s_mean, s_std, v_mean, v_std]
    combined = basic_feats + hog_feats[::50].tolist()
    return np.array([combined])

def check_img_tampering(img) -> bool:
    """Returns True if image appears tampered"""
    if not img_fraud_model: return False
    try:
        feats = extract_img_features(img)
        prob = img_fraud_model["model"].predict_proba(feats)[0][1]
        return prob > 0.5
    except: return False

# ─── Ticket Classifier (ML + Heuristic) ──────────────────────────────────────
scanner_model = None
TICKET_KEYWORDS = [
    "pnr", "passenger", "train", "coach", "seat", "fare", "irctc", 
    "railway", "bus", "flight", "boarding", "gate", "station", 
    "class", "sleeper", "quota", "confirmed", "waiting list", "berth",
    "travel date", "boarding pass", "ticket id", "transaction id",
    "total fare", "coach number", "seat number", "platform"
]

def load_scanner_model():
    global scanner_model
    path = os.path.join(BASE_DIR, '..', 'ml', 'scanner_model.pkl')
    try:
        if os.path.exists(path):
            with open(path, 'rb') as f:
                scanner_model = pickle.load(f)
            print(f"Scanner model loaded | Accuracy: {scanner_model.get('accuracy',0)*100:.1f}%")
    except Exception as e:
        print(f"Scanner model not loaded: {e}")

load_scanner_model()

def verify_ticket_text(text: str) -> dict:
    """Classify if text belongs to a ticket or not"""
    text_lower = text.lower()
    keyword_matches = [w for w in TICKET_KEYWORDS if w in text_lower]
    keyword_score = len(keyword_matches) / 3.0  # Normalized (needs at least 3 keywords)
    
    ml_prob = 0.5
    if scanner_model:
        try:
            vec = scanner_model["vectorizer"].transform([text])
            ml_prob = float(scanner_model["model"].predict_proba(vec)[0][1])
        except Exception: pass

    ml_threshold = 0.75
    is_ticket = (ml_prob > ml_threshold) or (len(keyword_matches) >= 3)
    return {
        "is_ticket": is_ticket,
        "confidence": round(max(ml_prob, min(keyword_score, 1.0)), 2),
        "keywords_found": keyword_matches
    }

# ─── Forensic Analysis Engine ────────────────────────────────────────────────
def analyze_forensics(filepath: str) -> dict:
    """Analyze image metadata and pixel patterns for tampering signatures"""
    from PIL import Image
    from PIL.ExifTags import TAGS
    
    forensic_results = {
        "software_detected": None,
        "is_forensic_fraud": False,
        "metadata_found": False,
        "creation_tool": "Unknown"
    }
    
    try:
        img = Image.open(filepath)
        info = img._getexif()
        if info:
            forensic_results["metadata_found"] = True
            for tag, value in info.items():
                decoded = TAGS.get(tag, tag)
                if decoded == "Software" or decoded == "ProcessingSoftware":
                    forensic_results["software_detected"] = value
                    # Flag common editing tools
                    tools = ["photoshop", "canva", "gimp", "snapseed", "picsart", "adobe"]
                    if any(t in str(value).lower() for t in tools):
                        forensic_results["is_forensic_fraud"] = True
                        forensic_results["creation_tool"] = str(value)
    except Exception as e:
        print(f"Forensic Error: {e}")
        
    return forensic_results

# ─── CV / OCR Ticket Scan ────────────────────────────────────────────────────
def scan_image(filepath: str, meta: dict) -> dict:
    checks = {
        "qr_detected": 0, "qr_decodable": 0, "qr_pnr_match": 0,
        "ocr_confidence": 0.0, "font_consistent": 1, "text_anomaly": 0,
        "price_reasonable": 1, "date_valid": 1, "is_ticket_format": 1,
        "metadata_fraud": 0, "pixel_tamper": 0
    }
    ocr_text = ""
    qr_data  = ""

    # Stage 1: Forensic Metadata Check
    forensics = analyze_forensics(filepath)
    if forensics["is_forensic_fraud"]:
        checks["metadata_fraud"] = 1

    if not CV2_OK:
        checks["font_consistent"] = 0
        return checks, ocr_text, qr_data

    img = cv2.imread(filepath)
    if img is None:
        return checks, ocr_text, qr_data

    # QR reading with highly robust ZXing-C++
    try:
        import zxingcpp
        
        # 1. Try original
        results = zxingcpp.read_barcodes(img)
        if not results:
            # 2. Try inverted grayscale for dark mode
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            inverted = cv2.bitwise_not(gray)
            results = zxingcpp.read_barcodes(inverted)
            
        if not results:
            # 3. Try Otsu binary thresholding on inverted (high contrast)
            _, thresh = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            results = zxingcpp.read_barcodes(thresh)
            
        if results:
            qr_data = results[0].text
            checks["qr_detected"] = 1
            checks["qr_decodable"] = 1
        else:
            checks["qr_detected"] = 0
            checks["qr_decodable"] = 0
            
    except Exception as e:
        print(f"DEBUG: ZXing Error: {e}")
        # Absolute fallback to OpenCV if ZXing fails entirely
        det = cv2.QRCodeDetector()
        qr_data, bbox, _ = det.detectAndDecode(img)
        if not qr_data:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            inverted = cv2.bitwise_not(gray)
            qr_data, bbox, _ = det.detectAndDecode(inverted)
        checks["qr_detected"]  = 1 if bbox is not None else 0
        checks["qr_decodable"] = 1 if qr_data else 0

    # OCR
    if OCR_OK:
        try:
            # Preprocessing: Grayscale, Blur, Threshold
            gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Invert dark mode tickets
            if np.mean(gray_img) < 127:
                gray_img = cv2.bitwise_not(gray_img)
            gray_img = cv2.medianBlur(gray_img, 3)
            _, thresh = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            ocr_data = pytesseract.image_to_data(thresh, output_type=pytesseract.Output.DICT)
            confs = [float(c) for c in ocr_data["conf"] if str(c).strip() and float(c) > 0]
            checks["ocr_confidence"] = round(sum(confs)/len(confs), 1) if confs else 0
            ocr_text = pytesseract.image_to_string(thresh)
            print(f"DEBUG: OCR Text Sample: {ocr_text[:50]}...")
        except Exception as e:
            print(f"DEBUG: OCR Error: {e}")
            checks["ocr_confidence"] = 0

    # OCR Fallback for PNR if QR fails
    if not qr_data and OCR_OK:
        import re
        # Pattern for SecureTrail PNR: 2 letters + 8 digits
        match = re.search(r"[A-Z]{2}[0-9]{8}", ocr_text.upper())
        if match:
            qr_data = match.group(0) # Re-use qr_data variable for the extracted PNR
            print(f"OCR Found PNR: {qr_data}")

    # QR / PNR matching
    pnr_input = str(meta.get("pnr", "")).lower().strip()
    if pnr_input and qr_data:
        checks["qr_pnr_match"] = 1 if pnr_input in qr_data.lower() else 0
    elif not pnr_input and qr_data:
        checks["qr_pnr_match"] = 1 # Implicit match if we extracted it without manual input
    else:
        checks["qr_pnr_match"] = 0

    print(f"DEBUG: Extracted PNR/QR Data = '{qr_data}'")

    # Document Verification
    v = verify_ticket_text(ocr_text)
    checks["is_ticket_format"] = 1 if v["is_ticket"] else 0

    # Image Tampering Check (AI)
    checks["is_tampered"] = 1 if check_img_tampering(img) else 0

    # Edge density for font consistency
    gray   = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges  = cv2.Canny(gray, 100, 200)
    density = float(np.sum(edges > 0)) / (edges.shape[0] * edges.shape[1] + 1e-5)
    checks["font_consistent"] = 1 if 0.02 < density < 0.35 else 0

    # Text anomaly
    checks["text_anomaly"] = 1 if len(ocr_text.strip()) < 15 else 0

    # Price check
    try:
        p_val = meta.get("price")
        price = float(p_val) if (p_val and str(p_val).strip()) else 0
    except:
        price = 0
        
    if price > 0:
        checks["price_reasonable"] = 1 if 50 < price < 50000 else 0

    return checks, ocr_text, qr_data

def score_scan(checks: dict) -> dict:
    fraud_score = 0
    # Forensic Checks (High Priority)
    if checks.get("metadata_fraud"):         fraud_score += 90
    if checks.get("pixel_tamper"):           fraud_score += 50
    if checks.get("is_tampered"):            fraud_score += 60

    # Strict Ticket Format Check
    if not checks.get("is_ticket_format"):  fraud_score += 70
    
    # QR Checks
    if not checks.get("qr_detected"):       
        fraud_score += 40  # Modern e-tickets MUST have a QR
    elif not checks.get("qr_decodable"):    
        fraud_score += 25
    elif not checks.get("qr_pnr_match"):    
        fraud_score += 20
    
    # Text / Layout Checks
    if checks.get("text_anomaly"):           fraud_score += 20
    if not checks.get("font_consistent"):    fraud_score += 15
    if not checks.get("price_reasonable"):   fraud_score += 15
    
    oconf = checks.get("ocr_confidence", 80)
    if oconf < 40:                           fraud_score += 20


    fraud_score = min(fraud_score, 100)
    # Thresholds: LOW (<35), MEDIUM (35-65), HIGH (>65)
    # But for scanning, we want to be safe.
    risk = "HIGH" if fraud_score >= 60 else ("MEDIUM" if fraud_score >= 30 else "LOW")
    return {"fraud_score": fraud_score, "risk_level": risk, "is_fraud": fraud_score >= 60}

def format_frontend_checks(checks: dict) -> dict:
    return {
        "qr_detected": checks.get("qr_detected", 0),
        "qr_decodable": checks.get("qr_decodable", 0),
        "qr_pnr_match": checks.get("qr_pnr_match", 0),
        "ocr_readable": 1 if checks.get("ocr_confidence", 0) >= 40 else 0,
        "font_consistent": checks.get("font_consistent", 0),
        "text_authentic": 0 if checks.get("text_anomaly", 0) else 1,
        "price_reasonable": checks.get("price_reasonable", 0),
        "is_ticket_format": checks.get("is_ticket_format", 0),
        "metadata_authentic": 0 if checks.get("metadata_fraud", 0) else 1,
        "image_authentic": 0 if checks.get("is_tampered", 0) else 1,
    }

def make_pdf_report(scan_id, scan_data, checks, path):
    doc  = SimpleDocTemplate(path, pagesize=letter)
    stys = getSampleStyleSheet()
    els  = []

    els.append(Paragraph("<b>SecureTrail AI — Ticket Fraud Report</b>", stys["Title"]))
    els.append(Paragraph(f"Scan ID: {scan_id} | Date: {scan_data.get('scan_date','')}", stys["Normal"]))
    els.append(Spacer(1, 12))

    verdict = "FRAUDULENT ❌" if scan_data.get("is_fraud") else "VALID ✅"
    col     = colors.red if scan_data.get("is_fraud") else colors.green
    els.append(Paragraph(
        f"<b>Verdict: {verdict}</b> (Score: {scan_data.get('fraud_score', 0)}/100)",
        stys["Heading2"]
    ))
    els.append(Spacer(1, 12))

    det_data = [
        ["Passenger", scan_data.get("passenger_name","—"), "PNR", scan_data.get("pnr","—")],
        ["Route", f"{scan_data.get('source','?')} → {scan_data.get('destination','?')}",
         "Travel Date", scan_data.get("travel_date","—")],
        ["Price", f"₹{scan_data.get('price',0)}", "Risk", scan_data.get("risk_level","—")],
    ]
    t1 = Table(det_data, colWidths=[80,160,80,160])
    t1.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), colors.whitesmoke),
        ("GRID",(0,0),(-1,-1),1,colors.lightgrey),
        ("FONTNAME",(0,0),(-1,-1),"Helvetica"),
    ]))
    els.append(t1)
    els.append(Spacer(1, 12))

    check_data = [["Check", "Result"]] + \
                 [[k.replace("_"," ").title(), "✅ Pass" if v else "❌ Fail"] for k, v in checks.items()]
    t2 = Table(check_data, colWidths=[240, 80])
    t2.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0), colors.darkblue),
        ("TEXTCOLOR",(0,0),(-1,0), colors.white),
        ("GRID",(0,0),(-1,-1),1,colors.lightgrey),
    ]))
    els.append(t2)
    doc.build(els)

# ─── Routes ──────────────────────────────────────────────────────────────────



# ── Fraud Prediction ──────────────────────────────────────────────────────────
@app.route("/api/predict_fraud", methods=["POST"])
def api_predict_fraud():
    data = request.get_json() or {}
    result = predict_fraud(data)
    return jsonify(result)

# ── Trip Scheduling ───────────────────────────────────────────────────────────
TRIP_SCHEDULES = {
    "train": ["06:00", "10:30", "14:00", "18:30", "22:00"],
    "bus":   ["06:00", "08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"],
    "flight":["07:00", "12:30", "19:00"]
}
# Average speed km/h for arrival time calculation
VEHICLE_SPEED = {"train": 80, "bus": 55, "flight": 700}
# Rough distance map (reused from utils)
DIST_MAP = {
    "Bangalore|Mysore":150,"Bangalore|Chennai":350,"Bangalore|Hyderabad":570,"Bangalore|Mumbai":980,
    "Bangalore|Delhi":2150,"Bangalore|Kolkata":1870,"Bangalore|Pune":840,"Bangalore|Kochi":590,
    "Bangalore|Goa":560,"Bangalore|Ahmedabad":1300,"Bangalore|Jaipur":2050,"Bangalore|Coimbatore":360,
    "Mumbai|Delhi":1400,"Mumbai|Chennai":1330,"Mumbai|Hyderabad":710,"Mumbai|Kolkata":2050,
    "Mumbai|Pune":150,"Mumbai|Ahmedabad":530,"Mumbai|Goa":590,"Mumbai|Jaipur":1150,
    "Delhi|Jaipur":280,"Delhi|Chandigarh":260,"Delhi|Amritsar":450,"Delhi|Agra":200,
    "Delhi|Lucknow":555,"Delhi|Varanasi":820,"Delhi|Kolkata":1480,"Delhi|Hyderabad":1570,
    "Delhi|Chennai":2170,"Delhi|Mumbai":1400,"Chennai|Hyderabad":630,"Chennai|Kochi":720,
    "Chennai|Coimbatore":490,"Hyderabad|Nagpur":490,"Hyderabad|Pune":570,
    "Kolkata|Patna":600,"Kolkata|Ranchi":410,"Kolkata|Bhubaneswar":440,
    "Ahmedabad|Surat":270,"Ahmedabad|Jaipur":660,"Jaipur|Agra":240,"Jaipur|Jodhpur":340,
    "Kochi|Thiruvananthapuram":220,"Kochi|Coimbatore":210,"Goa|Mangalore":330,
}

def get_distance(src, dst):
    k1 = f"{src}|{dst}"
    k2 = f"{dst}|{src}"
    return DIST_MAP.get(k1) or DIST_MAP.get(k2) or 500

def parse_time_mins(t):
    """'14:30' -> minutes since midnight"""
    h, m = map(int, t.split(":"))
    return h * 60 + m

def mins_to_time(m):
    m = m % (24 * 60)
    return f"{m//60:02d}:{m%60:02d}"

def calc_trip_price(base_price, departure_time, mode):
    """Peak hours cost 10% more"""
    mins = parse_time_mins(departure_time)
    is_peak = (360 <= mins <= 540) or (1020 <= mins <= 1260)  # 6-9AM or 5-9PM
    if mode == "flight":
        is_peak = mins < 480 or mins > 1080  # early/late flights cost more
    return round(base_price * 1.10) if is_peak else base_price

@app.route("/api/trips", methods=["GET"])
def api_get_trips():
    src   = request.args.get("source", "")
    dst   = request.args.get("destination", "")
    date  = request.args.get("date", "")
    mode  = request.args.get("mode", "train").lower()
    pref  = request.args.get("preferred_time", "")  # e.g. "13:00"

    if not all([src, dst, date, mode]):
        return jsonify({"error": "source, destination, date, mode required"}), 400

    dist = get_distance(src, dst)
    speed = VEHICLE_SPEED.get(mode, 80)
    duration_mins = int((dist / speed) * 60)

    # Base price per mode/distance
    BASE_RATES = {"train": 1.0, "bus": 1.2, "flight": 5.0}
    FLIGHT_BASE = {"flight": 800}
    base = round(BASE_RATES.get(mode, 1.0) * dist + FLIGHT_BASE.get(mode, 0))

    schedules = TRIP_SCHEDULES.get(mode, ["08:00", "14:00", "20:00"])

    # Check for admin-cancelled trips for this route/date
    cancelled_key = f"{mode}_{src}_{dst}_{date}".upper().replace(" ", "_")
    cancelled_doc = fs_get("cancelled_trips", cancelled_key) or {}
    cancelled_times = set(cancelled_doc.get("cancelled_times", []))

    # Build trip list
    trips = []
    for dep in schedules:
        if dep in cancelled_times:
            continue
        arr_mins = parse_time_mins(dep) + duration_mins
        arr = mins_to_time(arr_mins)
        trip_id = f"{mode}_{src}_{dst}_{date}_{dep}".upper().replace(" ", "_").replace(":", "")
        price = calc_trip_price(base, dep, mode)
        price = round(price * 1.05)  # GST

        # Fetch real-time booked seats for this trip
        booked_seats_res = fs_query("seats", "trip_id", "==", trip_id)
        booked_count = len(booked_seats_res)
        TOTAL_SEATS = {"train": 48, "bus": 36, "flight": 48}
        total = TOTAL_SEATS.get(mode, 40)
        available = max(0, total - booked_count)

        trips.append({
            "trip_id": trip_id,
            "source": src,
            "destination": dst,
            "travel_date": date,
            "departure_time": dep,
            "arrival_time": arr,
            "duration_mins": duration_mins,
            "mode": mode,
            "total_seats": total,
            "available_seats": available,
            "price": price,
            "is_peak": calc_trip_price(base, dep, mode) > base,
            "recommended": False
        })

    if not trips:
        return jsonify({"trips": [], "message": "No trips available for this route and date."})

    # Smart time matching — sort by proximity to preferred_time
    exact_match = False
    if pref:
        pref_mins = parse_time_mins(pref)
        for t in trips:
            diff = abs(parse_time_mins(t["departure_time"]) - pref_mins)
            t["_diff"] = diff
        trips.sort(key=lambda x: x["_diff"])
        # Mark the closest as recommended
        if trips:
            trips[0]["recommended"] = True
            if trips[0]["_diff"] == 0:
                exact_match = True
        # Clean up helper field
        for t in trips:
            t.pop("_diff", None)

    msg = None
    if pref and not exact_match:
        msg = f"No trips available at {pref}. Showing closest options."

    return jsonify({"trips": trips, "message": msg, "exact_match": exact_match})

@app.route("/api/cancel_trip", methods=["POST"])
def api_cancel_trip():
    """Admin: disable a specific departure time for a route/date"""
    data = request.get_json() or {}
    src  = data.get("source")
    dst  = data.get("destination")
    date = data.get("date")
    mode = data.get("mode")
    dep  = data.get("departure_time")
    if not all([src, dst, date, mode, dep]):
        return jsonify({"error": "Missing fields"}), 400
    key = f"{mode}_{src}_{dst}_{date}".upper().replace(" ", "_")
    existing = fs_get("cancelled_trips", key) or {}
    times = existing.get("cancelled_times", [])
    if dep not in times:
        times.append(dep)
    fs_set("cancelled_trips", key, {"cancelled_times": times, "updated_at": datetime.utcnow().isoformat()})
    return jsonify({"success": True, "cancelled_times": times})

@app.route("/api/restore_trip", methods=["POST"])
def api_restore_trip():
    """Admin: re-enable a cancelled trip departure"""
    data = request.get_json() or {}
    src  = data.get("source")
    dst  = data.get("destination")
    date = data.get("date")
    mode = data.get("mode")
    dep  = data.get("departure_time")
    key = f"{mode}_{src}_{dst}_{date}".upper().replace(" ", "_")
    existing = fs_get("cancelled_trips", key) or {}
    times = [t for t in existing.get("cancelled_times", []) if t != dep]
    fs_set("cancelled_trips", key, {"cancelled_times": times, "updated_at": datetime.utcnow().isoformat()})
    return jsonify({"success": True, "cancelled_times": times})


# ── Seat Booking ─────────────────────────────────────────────────────────────
@app.route("/api/seats", methods=["GET"])
def api_get_seats():
    trip_id = request.args.get("trip_id")
    if not trip_id: return jsonify({"error": "trip_id required"}), 400
    res = fs_query("seats", "trip_id", "==", trip_id)
    return jsonify({"seats": res})

@app.route("/api/book_seat", methods=["POST"])
def api_book_seat():
    data = request.get_json() or {}
    trip_id = data.get("trip_id")
    seat_num = data.get("seat_number")
    user_id = data.get("user_id", "guest")
    
    if not all([trip_id, seat_num]):
        return jsonify({"error": "Missing params"}), 400
        
    # Replace special chars for doc id if any
    seat_id = f"{trip_id}_{seat_num}".replace("/", "-").replace(" ", "")
    
    existing = fs_get("seats", seat_id)
    if existing and existing.get("status") == "BOOKED":
        return jsonify({"success": False, "error": "Seat already booked"}), 400
        
    seat_data = {
        "trip_id": trip_id,
        "seat_number": seat_num,
        "status": "BOOKED",
        "booked_by": user_id,
        "booking_time": datetime.utcnow().isoformat()
    }
    fs_set("seats", seat_id, seat_data)
    return jsonify({"success": True, "seat": seat_data})

# ── OTP ───────────────────────────────────────────────────────────────────────
@app.route("/api/generate_otp", methods=["POST"])
def api_generate_otp():
    data    = request.get_json() or {}
    sid     = gen_token(16)
    otp     = gen_otp()
    expires = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    _otp_store[sid] = {"otp": otp, "expires": expires, "booking": data.get("booking", {})}
    # persist to Firestore for cross-restart support
    fs_set("otp_sessions", sid, {"otp": otp, "expires": expires, "used": False})
    return jsonify({"session_id": sid, "otp": otp, "expires_in": 600})

@app.route("/api/verify_otp", methods=["POST"])
def api_verify_otp():
    data   = request.get_json() or {}
    sid    = data.get("session_id", "")
    inp    = str(data.get("otp", ""))
    # check in-memory first
    rec = _otp_store.get(sid) or fs_get("otp_sessions", sid)
    if not rec:
        return jsonify({"error": "Invalid session"}), 400
    if rec.get("used"):
        return jsonify({"error": "OTP already used"}), 400
    if datetime.fromisoformat(rec["expires"]) < datetime.utcnow():
        return jsonify({"error": "OTP expired"}), 400
    if rec.get("otp") != inp:
        return jsonify({"error": "Wrong OTP"}), 400
    # mark used
    fs_set("otp_sessions", sid, {**rec, "used": True})
    if sid in _otp_store: _otp_store[sid]["used"] = True
    return jsonify({"verified": True})

@app.route("/api/book_ticket", methods=["POST"])
def api_book_ticket():
    data = request.get_json() or {}
    user_id = data.get("user_id", "guest")

    # Fraud Check 3: Same user booking multiple trips in same time window
    existing_today = fs_query("tickets", "user_id", "==", user_id)
    dep_time = data.get("departure_time", "")
    if dep_time and existing_today:
        travel_date = data.get("travel_date", "")
        dep_mins = parse_time_mins(dep_time) if dep_time else -1
        for ex in existing_today:
            if ex.get("travel_date") == travel_date and ex.get("departure_time"):
                ex_mins = parse_time_mins(ex["departure_time"])
                if abs(ex_mins - dep_mins) < 60:  # within 1 hour
                    return jsonify({
                        "success": False,
                        "error": "FRAUD DETECTED: You already have a booking within 1 hour of this trip on the same day.",
                        "fraud_reason": "same_time_window"
                    }), 400
    
    # Generate PNR and Hash
    pnr = gen_pnr()
    qr_payload = {
        "ticket_id": pnr,
        "user_id": user_id,
        "source": data.get("source", ""),
        "destination": data.get("destination", ""),
        "travel_date": data.get("travel_date", ""),
        "seat_number": data.get("seat_number", "TBD"),
        "departure_time": data.get("departure_time", ""),
        "arrival_time": data.get("arrival_time", ""),
        "trip_id": data.get("trip_id", ""),
        "company": "MY_SYSTEM"
    }
    qr_payload["hash"] = generate_qr_hash(qr_payload)
    
    # Store ticket
    tkt = {
        "pnr": pnr,
        "user_id": user_id,
        "passenger_name": data.get("passenger_name", ""),
        "source": data.get("source", ""),
        "destination": data.get("destination", ""),
        "travel_date": data.get("travel_date", ""),
        "mode": data.get("mode", "train"),
        "seat_class": data.get("seat_class", ""),
        "seat_number": data.get("seat_number", "TBD"),
        "price": data.get("price", 0),
        "distance": data.get("distance", 0),
        "trip_id": data.get("trip_id", ""),
        "departure_time": data.get("departure_time", ""),
        "arrival_time": data.get("arrival_time", ""),
        "status": "NOT_USED",
        "payment_status": "SUCCESS",
        "qr_data": json.dumps(qr_payload),
        "created_at": datetime.utcnow().isoformat(),
        "risk_level": data.get("risk_level", "LOW"),
        "risk_score": data.get("risk_score", 0),
        "is_fraud": data.get("is_fraud", False),
        "device_type": request.headers.get('User-Agent', 'unknown'),
        "ip_address": request.remote_addr
    }
    
    doc_id = fs_create("tickets", tkt)
    tkt["id"] = doc_id
    
    return jsonify({"success": True, "ticket": tkt, "qr_payload": qr_payload})


# ── Ticket Scan — Public Basic ────────────────────────────────────────────────
@app.route("/api/scan", methods=["POST"])
def api_scan_public():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    f    = request.files["file"]
    meta = {k: request.form.get(k, "") for k in ["pnr","passenger_name","price","source","destination","travel_date"]}
    fname  = secure_filename(f.filename or "upload.jpg")
    fpath  = os.path.join(UPLOADS_DIR, f"{int(time.time())}_{fname}")
    f.save(fpath)
    checks, ocr_text, qr_data = scan_image(fpath, meta)
    
    # Unified Decision Logic (Simplified for Public)
    pnr_raw = qr_data.strip() or meta.get("pnr")
    pnr = pnr_raw
    
    print(f"DEBUG: pnr_raw = '{pnr_raw}'")
    
    # If QR data is JSON, extract the ticket_id
    qr_payload = {}
    if pnr_raw.startswith("{"):
        try:
            import json
            qr_payload = json.loads(pnr_raw)
            pnr = qr_payload.get("ticket_id") or qr_payload.get("pnr") or pnr_raw
        except:
            pass
            
    # Cryptographic Override for Public Scan
    if qr_payload and qr_payload.get("hash"):
        expected_hash = generate_qr_hash(qr_payload)
        if hmac.compare_digest(qr_payload.get("hash"), expected_hash):
            checks["is_tampered"] = 0
            checks["is_ticket_format"] = 1
            checks["text_anomaly"] = 0
            
    print(f"DEBUG: Final pnr = '{pnr}'")
            
    result = {"status": "VALID", "message": "Ticket is valid", "ticket_id": pnr}
    
    # 1. Database Validation (Check if exists)
    ticket_data = None
    if pnr and pnr != "UNKNOWN":
        print(f"DEBUG: Querying Firestore for PNR: '{pnr}'")
        res = fs_query("tickets", "pnr", "==", pnr)
        print(f"DEBUG: Query Result Count: {len(res)}")
        if res:
            ticket_data = res[0]
        else:
            result = {"status": "FAKE", "message": "Ticket ID not found in database", "ticket_id": pnr}
    else:
        result = {"status": "FAKE", "message": "Could not extract PNR from ticket", "ticket_id": "UNKNOWN"}

    # 2. Duplicate Detection
    if result["status"] == "VALID" and ticket_data:
        if ticket_data.get("status") == "USED":
            result = {"status": "DUPLICATE FRAUD", "message": "This ticket has already been used", "ticket_id": pnr}

    # 3. Image AI Tamper Detection
    if result["status"] == "VALID":
        if checks.get("is_tampered"):
            result = {"status": "FRAUD", "message": "Image appears to be tampered/edited", "ticket_id": pnr}

    score_res = score_scan(checks)
    result.update({
        "checks": format_frontend_checks(checks),
        "fraud_score": score_res.get("fraud_score", 0),
        "risk_level": score_res.get("risk_level", "LOW")
    })

    return jsonify(result)

# ── Ticket Scan — Pro (saves to Firestore) ────────────────────────────────────
@app.route("/api/scan/pro", methods=["POST"])
def api_scan_pro():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    f       = request.files["file"]
    user_id = request.form.get("user_id", "anonymous")
    meta    = {k: request.form.get(k, "") for k in ["pnr","passenger_name","price","source","destination","travel_date","issuer"]}
    fname   = secure_filename(f.filename or "upload.jpg")
    fpath   = os.path.join(UPLOADS_DIR, f"{int(time.time())}_{fname}")
    f.save(fpath)
    
    checks, ocr_text, qr_data = scan_image(fpath, meta)
    
    # 1. Parse QR Payload
    qr_payload = {}
    if qr_data:
        try:
            qr_payload = json.loads(qr_data)
        except json.JSONDecodeError:
            qr_payload = {"ticket_id": qr_data.strip()}
    
    pnr = qr_payload.get("ticket_id") or meta.get("pnr")
    
    rule_score = 0
    ml_score = 0
    image_score = 0
    status_flags = []
    
    # --- LAYER 1: Rule-Based System ---
    ticket_data = None
    if pnr:
        res = fs_query("tickets", "pnr", "==", pnr)
        if res:
            ticket_data = res[0]
            ml_score = ticket_data.get("risk_score", 0) # Base ML score from booking
        else:
            status_flags.append("FAKE")
            rule_score += 100
    else:
        status_flags.append("FAKE")
        rule_score += 100

    if qr_payload.get("company", "MY_SYSTEM") != "MY_SYSTEM":
        status_flags.append("EXTERNAL")
        rule_score += 40
        
    expected_hash = generate_qr_hash(qr_payload)
    qr_authentic = False
    if qr_payload.get("hash"):
        if hmac.compare_digest(qr_payload.get("hash"), expected_hash):
            qr_authentic = True
            # Cryptograph beats ML models! Override false positives for screenshots
            checks["is_tampered"] = 0
            checks["is_ticket_format"] = 1
            checks["text_anomaly"] = 0
        else:
            status_flags.append("TAMPERED")
            rule_score += 60

    if (ticket_data):
        if ticket_data.get("status") == "USED":
            # If it's already used, it's a duplicate scan, but we don't re-set it
            status_flags.append("DUPLICATE")
            rule_score += 50
        # REMOVED: Automatic marking as USED. Only checkers can do this now.
            
        travel_date_str = ticket_data.get("travel_date")
        if travel_date_str:
            try:
                travel_date = datetime.fromisoformat(travel_date_str.replace("Z", ""))
                if travel_date < datetime.utcnow() - timedelta(hours=24):
                    rule_score += 20
            except: pass
            
        scan_loc = request.form.get("location", "").lower()
        if scan_loc and scan_loc not in str(ticket_data.get("source", "")).lower() and scan_loc not in str(ticket_data.get("destination", "")).lower():
            rule_score += 25

    # --- LAYER 3: Image Validation ---
    if checks.get("is_tampered"):
        image_score += 80
        status_flags.append("TAMPERED")
    if not checks.get("qr_detected"):
        image_score += 50
        
    # --- LAYER 4: Final Fraud Scoring Engine ---
    rule_score = min(rule_score, 100)
    image_score = min(image_score, 100)
    
    final_score = (ml_score * 0.5) + (rule_score * 0.3) + (image_score * 0.2)
    final_score = min(final_score, 100)
    
    if "FAKE" in status_flags: final_status = "FAKE"
    elif "EXTERNAL" in status_flags: final_status = "EXTERNAL"
    elif "TAMPERED" in status_flags: final_status = "TAMPERED"
    elif "DUPLICATE" in status_flags: final_status = "DUPLICATE"
    else: final_status = "VALID"
    
    risk_level = "HIGH" if final_score >= 70 else ("MEDIUM" if final_score >= 30 else "LOW")

    scan_ts = datetime.utcnow().isoformat()
    scan_id = fs_create("scans_log", {
        "pnr": pnr,
        "scan_date": scan_ts,
        "timestamp": scan_ts,
        "user_id": user_id,
        "status": final_status,
        "fraud_score": round(final_score, 1),
        "score": round(final_score, 1),  # legacy field
        "risk_level": risk_level,
        "is_fraud": final_status != "VALID",
        "filename": f.filename or fname
    })

    message_map = {
        "VALID": "Ticket is VALID — Passenger cleared for boarding!",
        "FAKE": "Ticket NOT found in database — Possible FAKE or INVALID ticket!",
        "EXTERNAL": "Ticket belongs to an external system.",
        "TAMPERED": "Image appears to be tampered/edited.",
        "DUPLICATE": "This ticket has already been used."
    }

    formatted_checks = format_frontend_checks(checks)
    
    # Generate PDF report
    pdf_path = os.path.join(REPORTS_DIR, f"report_{scan_id}.pdf")
    scan_data = {
        "scan_date": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
        "is_fraud": final_status != "VALID",
        "fraud_score": round(final_score, 1),
        "risk_level": risk_level,
        "passenger_name": ticket_data.get("passenger_name", meta.get("passenger_name", "—")) if ticket_data else meta.get("passenger_name", "—"),
        "pnr": pnr,
        "source": ticket_data.get("source", meta.get("source", "—")) if ticket_data else meta.get("source", "—"),
        "destination": ticket_data.get("destination", meta.get("destination", "—")) if ticket_data else meta.get("destination", "—"),
        "travel_date": ticket_data.get("travel_date", meta.get("travel_date", "—")) if ticket_data else meta.get("travel_date", "—"),
        "price": ticket_data.get("price", meta.get("price", 0)) if ticket_data else meta.get("price", 0)
    }
    make_pdf_report(scan_id, scan_data, formatted_checks, pdf_path)

    result = {
        "status": final_status,
        "message": message_map.get(final_status, "Scan complete."),
        "fraud_score": round(final_score, 1),
        "risk_level": risk_level,
        "ticket_id": pnr,
        "checks": formatted_checks,
        "scan_id": scan_id
    }

    return jsonify(result)

# ── Batch Scan ────────────────────────────────────────────────────────────────
@app.route("/api/scan/batch", methods=["POST"])
def api_scan_batch():
    files   = request.files.getlist("files")
    user_id = request.form.get("user_id", "anonymous")
    if not files or len(files) > 10:
        return jsonify({"error": "Send 1–10 files"}), 400
    results = []
    for f in files:
        original_name = f.filename or "upload.jpg"
        fname  = secure_filename(original_name)
        fpath  = os.path.join(UPLOADS_DIR, f"{int(time.time())}_{fname}")
        f.save(fpath)
        checks, ocr_text, qr_data = scan_image(fpath, {})
        
        # Unified Decision Logic (Batch)
        pnr = qr_data.strip() if qr_data else ""
        # If QR data is JSON, extract ticket_id
        if pnr.startswith("{"):
            try:
                qr_obj = json.loads(pnr)
                pnr = qr_obj.get("ticket_id") or qr_obj.get("pnr") or pnr
            except:
                pass
        
        res_item = {"filename": original_name, "status": "VALID", "message": "Ticket is valid", "ticket_id": pnr}
        
        # Simplified checks for batch
        ticket_data = None
        if pnr:
            t_res = fs_query("tickets", "pnr", "==", pnr)
            if t_res: ticket_data = t_res[0]
            else: res_item.update({"status": "FAKE", "message": "PNR not found"})
        else:
            res_item.update({"status": "FAKE", "message": "QR not found or unreadable"})

        if res_item["status"] == "VALID" and ticket_data:
            if ticket_data.get("status") == "USED":
                res_item.update({"status": "DUPLICATE FRAUD", "message": "Already used"})
            if checks.get("is_tampered"):
                res_item.update({"status": "FRAUD", "message": "Tampered"})

        score_res = score_scan(checks)
        res_item.update({
            "fraud_score": score_res.get("fraud_score", 0),
            "risk_level": score_res.get("risk_level", "LOW"),
            "is_fraud": score_res.get("is_fraud", False) or res_item["status"] != "VALID",
            "checks": format_frontend_checks(checks)
        })

        scan_ts = datetime.utcnow().isoformat()
        # Log to scans_log (same collection as single scan)
        fs_create("scans_log", {
            "pnr": pnr,
            "scan_date": scan_ts,
            "timestamp": scan_ts,
            "user_id": user_id,
            "status": res_item["status"],
            "filename": original_name,
            "fraud_score": res_item["fraud_score"],
            "risk_level": res_item["risk_level"],
            "is_fraud": res_item["is_fraud"]
        })
        results.append(res_item)
    return jsonify({"results": results, "count": len(results)})

# ── Scan History ──────────────────────────────────────────────────────────────
@app.route("/api/scan/history/<user_id>", methods=["GET"])
def api_scan_history(user_id):
    # Scans are stored in "scans_log" collection (used by both /api/scan and /api/scan/batch)
    scans = fs_query("scans_log", "user_id", "==", user_id)
    # Normalise field names so frontend can use scan_date, fraud_score, risk_level, is_fraud
    for s in scans:
        if not s.get("scan_date") and s.get("timestamp"):
            s["scan_date"] = s["timestamp"]
        if "score" in s and "fraud_score" not in s:
            s["fraud_score"] = s["score"]
        if "risk_level" not in s:
            score = s.get("fraud_score", 0)
            s["risk_level"] = "HIGH" if score >= 70 else ("MEDIUM" if score >= 30 else "LOW")
        if "is_fraud" not in s:
            s["is_fraud"] = s.get("status", "VALID") != "VALID"
    # Sort newest first
    scans.sort(key=lambda x: x.get("scan_date", ""), reverse=True)
    return jsonify({"scans": scans, "total": len(scans)})

# ── PDF Report Download ───────────────────────────────────────────────────────
@app.route("/api/report/<scan_id>", methods=["GET"])
def api_download_report(scan_id):
    path = os.path.join(REPORTS_DIR, f"report_{scan_id}.pdf")
    if not os.path.exists(path):
        return jsonify({"error": "Report not found"}), 404
    return send_file(path, as_attachment=True, download_name=f"fraud_report_{scan_id}.pdf")

# ── Shareable Links ───────────────────────────────────────────────────────────
@app.route("/api/share/<scan_id>", methods=["POST"])
def api_create_share(scan_id):
    token   = gen_token(24)
    expires = (datetime.utcnow() + timedelta(days=7)).isoformat()
    scan    = fs_get("scans", scan_id)
    if not scan:
        return jsonify({"error": "Scan not found"}), 404
    fs_set("share_links", token, {"scan_id": scan_id, "expires": expires, "scan_data": scan})
    # Point to the frontend root so the React app can handle the token
    share_url = f"{request.host_url}?share={token}"
    return jsonify({"token": token, "share_url": share_url, "expires": expires})

@app.route("/api/share/view/<token>", methods=["GET"])
def api_view_share(token):
    rec = fs_get("share_links", token)
    if not rec:
        return jsonify({"error": "Link not found or expired"}), 404
    if datetime.fromisoformat(rec["expires"]) < datetime.utcnow():
        return jsonify({"error": "Link expired"}), 410
    return jsonify(rec.get("scan_data", {}))

# ── Feedback / False Positive ─────────────────────────────────────────────────
@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    data = request.get_json() or {}
    fp = {
        "scan_id":  data.get("scan_id"),
        "user_id":  data.get("user_id"),
        "feedback": data.get("feedback", "false_positive"),
        "reason":   data.get("reason", ""),
        "created_at": datetime.utcnow().isoformat()
    }
    doc_id = fs_create("false_positives", fp)
    return jsonify({"message": "Feedback recorded", "id": doc_id})

# ── Model Retrain (Admin) ─────────────────────────────────────────────────────
@app.route("/api/retrain", methods=["POST"])
def api_retrain():
    import subprocess
    script = os.path.join(BASE_DIR, '..', 'ml', 'train_model.py')
    try:
        subprocess.run(["python", script], check=True, capture_output=True, timeout=120)
        load_model()
        acc = fraud_model.get("accuracy", 0) if fraud_model else 0
        return jsonify({"message": "Model retrained", "accuracy": round(acc*100, 2)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Public Stats ──────────────────────────────────────────────────────────────
@app.route("/api/stats", methods=["GET"])
def api_stats():
    tickets = fs_list("tickets", 500)
    scans   = fs_list("scans_log", 500)
    
    fraud_t = sum(1 for t in tickets if t.get("is_fraud")) # Keep old field for legacy?
    # New logic: any status that isn't VALID is considered a fraud attempt
    fraud_s = sum(1 for s in scans if s.get("status") and s.get("status") != "VALID")
    
    return jsonify({
        "total_tickets": len(tickets),
        "total_scans":   len(scans),
        "fraud_tickets": fraud_t,
        "fraud_scans":   fraud_s,
        "model_loaded":  img_fraud_model is not None
    })

@app.errorhandler(404)
def serve_frontend(e):
    path = request.path.strip("/")
    print(f"404 caught for path: {path} | Static folder: {app.static_folder}")
    
    # Check if it's a static file that actually exists
    fp = os.path.join(app.static_folder, path)
    if path and os.path.exists(fp):
        return send_from_directory(app.static_folder, path)
        
    # Otherwise return index.html for React routing
    return send_from_directory(app.static_folder, "index.html")

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    print("SecureTrail Backend starting on http://localhost:5000")
    app.run(debug=True, port=5000)
