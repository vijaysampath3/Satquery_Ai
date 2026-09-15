import requests
import io
from PIL import Image
import numpy as np

img_arr = np.zeros((100, 100, 3), dtype=np.uint8)
img_arr[10:50, 10:50] = (20, 200, 40) # Green
img = Image.fromarray(img_arr)
buf = io.BytesIO()
img.save(buf, format="PNG")
img_bytes = buf.getvalue()

queries = ["Highlight vegitation", "Highlight vegetation", "show vegitation"]

for q in queries:
    resp = requests.post(
        "http://127.0.0.1:8000/api/analyze",
        files={"images": ("sample.png", img_bytes, "image/png")},
        data={"query": q}
    )

    print(f"\n--- Query: '{q}' ---")
    print("Status Code:", resp.status_code)
    data = resp.json()
    print("Task:", data.get("task"))
    print("Target Analysis:", data.get("target_analysis"))
    print("Vegetation Analysis:", data.get("vegetation_analysis"))
    print("Evidence Images:")
    for img in data.get("evidence", {}).get("images", []):
        print("  -", img)
