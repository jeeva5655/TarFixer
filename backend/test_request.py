import requests

url = "http://127.0.0.1:5000/detect?type=image"
files = {"image": open(r"C:\path\to\test.jpg", "rb")}

response = requests.post(url, files=files)

if response.status_code == 200:
    with open("out.jpg", "wb") as f:
        f.write(response.content)
    print("✅ Annotated image saved as out.jpg")
else:
    print("❌ Error:", response.text)
