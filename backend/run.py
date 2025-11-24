import os
import io
import base64
import json
import numpy as np
import cv2
from flask import Flask, request, jsonify
from flask_cors import CORS
from ultralytics import YOLO
from PIL import Image

# ---------------------------------------------------------
# Flask Initialization
# ---------------------------------------------------------
app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------
# Load YOLO Model
# ---------------------------------------------------------
MODEL_PATH = r"E:\road-damage\runs\detect\train22\weights\best.pt"
try:
    model = YOLO(MODEL_PATH)
    print("✅ YOLOv11 model loaded successfully.")
except Exception as e:
    print(f"❌ Failed to load YOLO model: {e}")
    model = None

REPORTS_FILE = "reports.json"
if not os.path.exists(REPORTS_FILE):
    with open(REPORTS_FILE, "w") as f:
        json.dump([], f)

# ---------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------
def clamp(v, lo, hi):
    """Limit value between lo and hi"""
    return max(lo, min(hi, v))

def expand_box(x1, y1, x2, y2, w, h, factor=0.15):
    """Expand detection box slightly"""
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    bw, bh = (x2 - x1) * (1 + factor), (y2 - y1) * (1 + factor)
    nx1, ny1 = int(clamp(cx - bw / 2, 0, w - 1)), int(clamp(cy - bh / 2, 0, h - 1))
    nx2, ny2 = int(clamp(cx + bw / 2, 0, w - 1)), int(clamp(cy + bh / 2, 0, h - 1))
    return nx1, ny1, nx2, ny2

def is_road_scene(image_bgr):
    """
    Returns False if image is unlikely to be a road.
    Uses edge density, texture, brightness, and color tone.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    total = H * W

    # Brightness and contrast check
    brightness = np.mean(gray)
    contrast = gray.std()

    if brightness < 30 or brightness > 230 or contrast < 20:
        return False

    # Edge & texture analysis
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 70, 130)
    edge_ratio = np.sum(edges > 0) / total
    texture_var = np.var(gray) / 255.0

    # Color analysis (roads = darker gray, not white walls)
    avg_color = np.mean(image_bgr, axis=(0, 1))  # (B, G, R)
    avg_brightness = np.mean(avg_color)

    # Typical road edge ratio: 0.02–0.08, texture var: >0.08, brightness: <150
    if edge_ratio < 0.018 or texture_var < 0.07 or avg_brightness > 160:
        return False

    return True

# ---------------------------------------------------------
# Detection Route
# ---------------------------------------------------------
@app.route('/detect', methods=['POST'])
def detect():
    if model is None:
        return jsonify({'error': 'Model not loaded'}), 500

    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    image_file = request.files['image']

    try:
        pil_image = Image.open(image_file.stream).convert("RGB")
        img_bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    except Exception as e:
        return jsonify({'error': f'Invalid image file: {e}'}), 400

    H, W = img_bgr.shape[:2]
    total_pixels = H * W

    # -----------------------------------------------------
    # Step 1: Check if image is actually a road
    # -----------------------------------------------------
    if not is_road_scene(img_bgr):
        print("⚠️ No road detected in image.")
        black = np.zeros_like(img_bgr)
        _, buf = cv2.imencode(".jpg", black)
        img_b64 = base64.b64encode(buf).decode("utf-8")
        img_url = f"data:image/jpeg;base64,{img_b64}"

        return jsonify({
            "damage_percentage": "0.00",
            "annotated_image": img_url,
            "detection_count": 0,
            "severity_label": "No Road Detected"
        })

    # -----------------------------------------------------
    # Step 2: YOLO Detection
    # -----------------------------------------------------
    results = model.predict(source=pil_image, conf=0.25, iou=0.45, save=False)
    det_count, damage_pct, severity = 0, 0.0, "No Damage"

    if results and results[0].boxes is not None:
        r = results[0]
        det_count = len(r.boxes)
        avg_conf = 0.0
        union_mask = np.zeros((H, W), dtype=np.uint8)

        for box in r.boxes:
            conf = float(box.conf) if box.conf is not None else 1.0
            avg_conf += conf
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            expand_factor = 0.2 if conf < 0.5 else 0.12
            x1, y1, x2, y2 = expand_box(x1, y1, x2, y2, W, H, expand_factor)
            cv2.rectangle(union_mask, (x1, y1), (x2, y2), 255, -1)

        avg_conf /= max(det_count, 1)
        union_pixels = np.count_nonzero(union_mask)
        union_ratio = union_pixels / total_pixels

        # Edge and texture analysis
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 70, 130)
        dark_mask = (gray < 90).astype(np.uint8) * 255

        dark_ratio = np.sum(dark_mask > 0) / total_pixels
        edge_ratio = np.sum(edges > 0) / total_pixels

        visual_weight = (dark_ratio * 0.25 + edge_ratio * 0.75)
        raw_ratio = (union_ratio * 0.8) + (visual_weight * 0.2)
        raw_ratio *= (1.0 + (det_count * 0.25))

        if avg_conf < 0.45:
            raw_ratio *= 1.1

        # Cap estimation
        if det_count <= 1:
            raw_ratio = min(raw_ratio, 0.70)
        else:
            raw_ratio = min(raw_ratio, 1.0)

        damage_pct = round(clamp(raw_ratio, 0.0, 1.0) * 100.0, 2)

        # Severity Label
        if damage_pct < 30:
            severity = "Minor"
        elif damage_pct <= 60:
            severity = "Moderate"
        else:
            severity = "Severe"

    # -----------------------------------------------------
    # Step 3: Annotate and Return Image
    # -----------------------------------------------------
    annotated = results[0].plot()
    ann_pil = Image.fromarray(annotated[..., ::-1])
    buf = io.BytesIO()
    ann_pil.save(buf, format="JPEG")
    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    ann_url = f"data:image/jpeg;base64,{img_b64}"

    return jsonify({
        "damage_percentage": f"{damage_pct:.2f}",
        "annotated_image": ann_url,
        "detection_count": det_count,
        "severity_label": severity
    })

# ---------------------------------------------------------
# Report Submission Route
# ---------------------------------------------------------
@app.route('/report', methods=['POST'])
def report():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No report data'}), 400
    with open(REPORTS_FILE, "r") as f:
        reports = json.load(f)
    reports.append(data)
    with open(REPORTS_FILE, "w") as f:
        json.dump(reports, f, indent=4)
    return jsonify({'message': 'Report saved'}), 200

# ---------------------------------------------------------
# Officer Dashboard Route
# ---------------------------------------------------------
@app.route('/get_reports', methods=['GET'])
def get_reports():
    if not os.path.exists(REPORTS_FILE):
        return jsonify([])
    with open(REPORTS_FILE, "r") as f:
        data = json.load(f)
    return jsonify(data), 200

# ---------------------------------------------------------
# Run the App
# ---------------------------------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
