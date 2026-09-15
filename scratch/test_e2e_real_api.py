import os
import io
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app

def create_sample_rgb():
    img_arr = np.zeros((100, 100, 3), dtype=np.uint8)
    # Green vegetation region
    img_arr[10:50, 10:50] = (20, 200, 40)
    # Blue water region
    img_arr[60:90, 10:40] = (20, 80, 220)
    # Bright built-up region
    img_arr[10:40, 60:90] = (210, 210, 210)
    
    img = Image.fromarray(img_arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()

def run_all_e2e_tests():
    with TestClient(app) as client:
        img_bytes = create_sample_rgb()
        
        # 1. Vegetation Test
        resp_veg = client.post(
            "/api/analyze",
            files={"images": ("sample.png", img_bytes, "image/png")},
            data={"query": "Highlight vegetation"}
        )
        assert resp_veg.status_code == 200, f"Error: {resp_veg.text}"
        d_veg = resp_veg.json()
        print("\n--- 'Highlight vegetation' API Response ---")
        print("Task:", d_veg.get("task"))
        print("Target Analysis:", d_veg.get("target_analysis"))
        print("Vegetation Analysis:", d_veg.get("vegetation_analysis"))
        print("Evidence Images:")
        for img in d_veg.get("evidence", {}).get("images", []):
            print(f"  - [{img.get('caption')}] -> {img.get('url')}")
        
        ev_urls_veg = [img["url"] for img in d_veg["evidence"]["images"]]
        assert any("vegetation_mask.png" in u for u in ev_urls_veg), "MISSING vegetation_mask.png in evidence!"
        assert not any("water_mask.png" in u for u in ev_urls_veg), "INCORRECT water_mask.png found in vegetation query!"
        print("SUCCESS: Vegetation mask generated and returned correctly.")

        # 2. Water Test
        resp_water = client.post(
            "/api/analyze",
            files={"images": ("sample.png", img_bytes, "image/png")},
            data={"query": "Highlight water"}
        )
        assert resp_water.status_code == 200
        d_water = resp_water.json()
        print("\n--- 'Highlight water' API Response ---")
        print("Target Analysis:", d_water.get("target_analysis"))
        print("Water Analysis:", d_water.get("water_analysis"))
        print("Evidence Images:")
        for img in d_water.get("evidence", {}).get("images", []):
            print(f"  - [{img.get('caption')}] -> {img.get('url')}")
        
        ev_urls_water = [img["url"] for img in d_water["evidence"]["images"]]
        assert any("water_mask.png" in u for u in ev_urls_water), "MISSING water_mask.png in evidence!"
        assert not any("vegetation_mask.png" in u for u in ev_urls_water), "INCORRECT vegetation_mask.png found in water query!"
        print("SUCCESS: Water mask generated and returned correctly.")

        # 3. Built-up Test
        resp_built = client.post(
            "/api/analyze",
            files={"images": ("sample.png", img_bytes, "image/png")},
            data={"query": "Highlight built-up area"}
        )
        assert resp_built.status_code == 200
        d_built = resp_built.json()
        print("\n--- 'Highlight built-up area' API Response ---")
        print("Target Analysis:", d_built.get("target_analysis"))
        print("Built-up Analysis:", d_built.get("built_up_analysis"))
        print("Evidence Images:")
        for img in d_built.get("evidence", {}).get("images", []):
            print(f"  - [{img.get('caption')}] -> {img.get('url')}")
        
        ev_urls_built = [img["url"] for img in d_built["evidence"]["images"]]
        assert any("built_up_mask.png" in u for u in ev_urls_built), "MISSING built_up_mask.png in evidence!"
        assert not any("water_mask.png" in u for u in ev_urls_built)
        print("SUCCESS: Built-up mask generated and returned correctly.")

if __name__ == "__main__":
    run_all_e2e_tests()
