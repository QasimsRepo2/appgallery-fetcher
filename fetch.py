import sys
import json
from appgallery_service import get_app_info

if len(sys.argv) < 2:
    raise SystemExit("Usage: python fetch.py <app_id>")

app_id = sys.argv[1]

try:
    app_info = get_app_info(app_id)
    result = {
        "status": "success",
        "data": {
            "app_id": app_info.get("appid"),
            "name": app_info.get("name"),
            "developer": app_info.get("developer"),
            "version": app_info.get("versionName") or app_info.get("version"),
            "size_mb": round((app_info.get("size") or 0) / (1024 * 1024), 2),
            "package": app_info.get("package") or app_info.get("package_name"),
            "portal_url": app_info.get("portalUrl"),
            "description": app_info.get("editorDescribe") or app_info.get("description"),
        }
    }
except Exception as e:
    result = {
        "status": "error",
        "message": str(e)
    }

with open("result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print("Result written to result.json")
