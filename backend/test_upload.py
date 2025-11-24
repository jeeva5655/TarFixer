import requests

# URL of your backend upload API
url = "http://127.0.0.1:5000/upload"

# Path to the image you want to send
image_path = "test_image.jpg"  # <-- put any image in backend folder or give full path

# Open the image and send
with open(image_path, "rb") as img:
    files = {"image": img}
    response = requests.post(url, files=files)

print("Response from backend:")
print(response.json())
