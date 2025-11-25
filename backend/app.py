import os
import io
import base64
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS
from ultralytics import YOLO
from PIL import Image

# 1. Create Flask app
app = Flask(__name__)
CORS(app)

# 2. Load YOLO model
model_path = r"c:\Users\ninje\Downloads\Road damage\runs\detect\train22\weights\best.pt"
try:
    model = YOLO(model_path)
    print("✅ YOLO model loaded successfully.")
except Exception as e:
    print(f"❌ Error loading YOLO model: {e}")
    model = None


# 3. Define detection route
@app.route('/detect', methods=['POST'])
def detect():
    if model is None:
        return jsonify({'error': 'Model could not be loaded'}), 500

    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    image_file = request.files['image']

    try:
        image = Image.open(image_file.stream)
    except Exception as e:
        return jsonify({'error': f'Invalid image file: {e}'}), 400

    # Run YOLO detection
    results = model.predict(source=image, save=False)
    detection_count = 0
    damage_percentage = 0.0

    if results and results[0].boxes is not None:
        result = results[0]
        detection_count = len(result.boxes)

        if detection_count > 0:
            img_height, img_width = result.orig_shape
            mask = np.zeros((img_height, img_width), dtype=np.uint8)

            for box in result.boxes:
                coords = box.xyxy.tolist()[0]
                x1, y1, x2, y2 = map(int, coords)
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(img_width, x2), min(img_height, y2)
                mask[y1:y2, x1:x2] = 1  # mark damaged pixels

            total_damage_area = np.sum(mask)
            total_image_area = img_width * img_height
            damage_percentage = (total_damage_area / total_image_area) * 100

            # Clamp to 100% just in case
            damage_percentage = min(damage_percentage, 100.0)

    # Annotate image
    annotated_image_array = results[0].plot()
    img_pil = Image.fromarray(annotated_image_array[..., ::-1])

    # Convert to Base64
    buffered = io.BytesIO()
    img_pil.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    image_data_url = f"data:image/jpeg;base64,{img_str}"

    return jsonify({
        'damage_percentage': f"{damage_percentage:.2f}",
        'annotated_image': image_data_url,
        'detection_count': detection_count
    })


# 4. Run app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
