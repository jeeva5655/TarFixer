import cv2
import predictor  # This now correctly matches the file named predictor.py

def draw_boxes(img, detections):
    """
    Draws bounding boxes and labels on an image.
    
    Args:
        img: The image as a NumPy array.
        detections: A list of dictionaries, where each dictionary
                    represents a detected object with its coordinates,
                    label, and confidence.
    """
    if not detections:
        print("🔍 No detections were found to draw.")
        return img

    for det in detections:
        # Get detection details
        x1, y1, x2, y2 = det['xmin'], det['ymin'], det['xmax'], det['ymax']
        label = det['label']
        conf = det['confidence']
        
        # Draw the rectangle
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Add the label text with confidence score
        cv2.putText(img, f"{label} {conf:.2f}", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    return img

# Step 1: Load your test image
image_path = "test_image.jpg"
img = cv2.imread(image_path)

# Step 2: Run your model with a lower confidence threshold
# We are lowering the threshold to 0.10 to see if the model detects anything at all.
detections = predictor.predict(image_path, conf_thresh=0.10)

# Step 3: Print all detections to the console
print("\n--- All Detections Found ---")
for det in detections:
    print(det)
print("---------------------------\n")

# Step 4: Draw bounding boxes
img_with_boxes = draw_boxes(img, detections)

# Step 5: Save result
cv2.imwrite("result.jpg", img_with_boxes)
print("✅ Detection done! See result.jpg in your backend folder.")

# Step 6: Show result (optional)
# This will display the image in a new window until you press a key.
cv2.imshow("Detection Result", img_with_boxes)
cv2.waitKey(0)
cv2.destroyAllWindows()
