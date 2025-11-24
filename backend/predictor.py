# predictor_yolo11.py
from ultralytics import YOLO
import cv2

# Change this to your model filename
MODEL_PATH = r"E:\road-damage\runs\detect\train22\weights\best.pt"


# load model once
_model = None
def load_model():
    global _model
    if _model is None:
        _model = YOLO(MODEL_PATH)
    return _model

def predict(image_path, conf_thresh=0.15):
    """
    Runs YOLO-v11 on the image and returns detections list.
    Each detection is:
        {'label': <str>, 'confidence': <float>, 'xmin': <int>,
         'ymin': <int>, 'xmax': <int>, 'ymax': <int>}
    """
    model = load_model()
    results = model.predict(source=image_path, imgsz=640, conf=conf_thresh, verbose=False)
    detections = []
    if len(results) == 0:
        return detections

    # Assuming results[0] is the image result
    r = results[0]
    if hasattr(r, 'boxes') and r.boxes is not None:
        boxes = r.boxes
        xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, 'cpu') else boxes.xyxy.numpy()
        confs = boxes.conf.cpu().numpy() if hasattr(boxes.conf, 'cpu') else boxes.conf.numpy()
        clss = boxes.cls.cpu().numpy() if hasattr(boxes.cls, 'cpu') else boxes.cls.numpy()
        names = model.names if hasattr(model, 'names') else {}

        for (x1, y1, x2, y2), conf, cls in zip(xyxy, confs, clss):
            label = names[int(cls)] if int(cls) in names else str(int(cls))
            detections.append({
                'label': label,
                'confidence': float(conf),
                'xmin': int(x1),
                'ymin': int(y1),
                'xmax': int(x2),
                'ymax': int(y2)
            })
    return detections
