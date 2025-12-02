import os
from flask import Flask, request, jsonify
from ultralytics import YOLO
from PIL import Image
import io
import base64

app = Flask(__name__)

# Load Model
MODEL_PATH = "best.pt"
try:
    model = YOLO(MODEL_PATH)
    print(f"✅ YOLOv11 model loaded successfully from {MODEL_PATH}")
except Exception as e:
    print(f"❌ Failed to load YOLO model: {e}")
    model = None

@app.route('/')
def home():
    return "TarFixer AI Service is Running!"

@app.route('/detect', methods=['POST'])
def detect():
    if not model:
        return jsonify({'error': 'Model not loaded'}), 500
    
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    file = request.files['image']
    img_bytes = file.read()
    
    try:
        # Open image
        img = Image.open(io.BytesIO(img_bytes))
        
        # Run inference
        results = model(img)
        
        # Process results
        result = results[0]
        
        # Calculate damage percentage (simple approximation based on box area)
        total_area = result.orig_shape[0] * result.orig_shape[1]
        damage_area = 0
        detections = []
        
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls = int(box.cls[0])
            label = result.names[cls]
            
            w = x2 - x1
            h = y2 - y1
            damage_area += w * h
            
            detections.append({
                'box': [x1, y1, x2, y2],
                'confidence': conf,
                'class': cls,
                'label': label
            })
            
        damage_percentage = (damage_area / total_area) * 100 if total_area > 0 else 0
        damage_percentage = min(damage_percentage * 2.5, 100) # Scale up for visibility
        
        # Determine severity
        if damage_percentage < 5:
            severity = "Minor"
        elif damage_percentage < 15:
            severity = "Moderate"
        else:
            severity = "Severe"
            
        # Generate annotated image
        im_array = result.plot()  # plot() returns BGR numpy array
        im = Image.fromarray(im_array[..., ::-1])  # RGB PIL image
        
        buffered = io.BytesIO()
        im.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        return jsonify({
            'damage_percentage': round(damage_percentage, 2),
            'severity': severity,
            'detection_count': len(detections),
            'annotated_image': img_str,
            'detections': detections
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)
