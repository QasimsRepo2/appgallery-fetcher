import sys
import json
from appgallery_service import fetch_single_app

if len(sys.argv) < 2:
    raise SystemExit("Usage: python fetch.py <app_id>")

app_id = sys.argv[1]

result = fetch_single_app(app_id)

with open("result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print("Result written to result.json")
