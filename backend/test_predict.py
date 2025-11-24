from ultralytics import YOLO
import os
import torch

# Load your trained model
model = YOLO(r"E:\road-damage\runs\detect\train22\weights\best.pt")

# Test image
image_path = "test_image.jpg"

# Set save directory inside backend folder
save_dir = os.path.join(os.getcwd(), "predictions")
os.makedirs(save_dir, exist_ok=True)

# Run prediction
results = model.predict(source=image_path, project=save_dir, name="", save=True, exist_ok=True)

# --- NEW CODE STARTS HERE ---

# Initialize variables
total_image_area = 0
total_damage_area = 0

# Check if there are any results
if results and results[0]:
    # Get the first result object
    result = results[0]

    # Get the original image shape [height, width]
    img_height, img_width = result.orig_shape

    # Calculate the total area of the image
    total_image_area = img_width * img_height

    # Get the bounding boxes
    boxes = result.boxes

    # Loop through each bounding box
    for box in boxes:
        # Get coordinates [x1, y1, x2, y2]
        # .tolist() converts tensor to a standard Python list
        # [0] gets the first (and only) list of coordinates
        coords = box.xyxy.tolist()[0]
        x1, y1, x2, y2 = coords
        
        # Calculate the area of the bounding box
        box_area = (x2 - x1) * (y2 - y1)
        
        # Add the box area to the total damage area
        total_damage_area += box_area

# Calculate the damage percentage
damage_percentage = 0
if total_image_area > 0:
    damage_percentage = (total_damage_area / total_image_area) * 100

# --- NEW CODE ENDS HERE ---

# Print prediction details
print("\n--- Prediction Result ---")
print("Bounding Boxes:", results[0].boxes.xyxy)
print("Confidence:", results[0].boxes.conf)
print("Classes:", results[0].boxes.cls)

# Print the new damage percentage
print(f"\nTotal Image Area: {total_image_area:.0f} pixels")
print(f"Total Damage Area: {total_damage_area:.0f} pixels")
print(f"Damage Percentage: {damage_percentage:.2f}%")

print(f"\n✅ Predicted image saved in: {save_dir}")