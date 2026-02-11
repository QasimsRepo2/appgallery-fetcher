import argparse
import logging
import os
import time
import json
import requests
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed

# Setup general logger
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger("AppGalleryCLI")

# Setup failure logger
os.makedirs("logs", exist_ok=True)
failure_log_handler = logging.FileHandler("logs/cli_failures.log")
failure_log_handler.setLevel(logging.ERROR)
failure_log_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s'))
logger.addHandler(failure_log_handler)

INTERFACE_URL = 'https://web-drru.hispace.dbankcloud.ru/webedge/getInterfaceCode'
APP_INFO_URL_TEMPLATE = 'https://web-drru.hispace.dbankcloud.ru/uowap/index?method=internal.getTabDetail&uri=app%7C{app_id}'
APP_DETAIL_URL_TEMPLATE = 'https://web-drru.hispace.dbankcloud.ru/uowap/index?method=internal.getDetailInfo&uri={package_name}&params={{"appid":"{app_id}"}}'
APK_DOWNLOAD_URL_TEMPLATE = 'https://appgallery.cloud.huawei.com/appdl/{app_id}'

SUMMARY_DIR = "results"
os.makedirs(SUMMARY_DIR, exist_ok=True)

def get_interface_code():
    try:
        resp = requests.post(INTERFACE_URL, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Failed to retrieve Interface-Code: {e}")
        raise RuntimeError("Cannot get interface code.")

def build_headers():
    code = get_interface_code()
    timestamp = str(time.time()).replace('.', '')
    return {'Interface-Code': f"{code}_{timestamp}"}

def get_app_info(app_id):
    logger.info(f"Fetching app info for app_id: {app_id}")
    headers = build_headers()
    url = APP_INFO_URL_TEMPLATE.format(app_id=app_id)
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        layout_data = data.get('layoutData', [])

        app_item = None
        developer_name = None

        # Extract app info and developer
        for element in layout_data:
            layout_id = element.get("layoutId")
            for item in element.get("dataList", []):
                # App info is in detailhiddencard (layoutId 49)
                if layout_id == 49 and not app_item and item.get("appid") == app_id:
                    app_item = item
                # Developer info in textlistcard (layoutId 59)
                if layout_id == 59 and "list" in item:
                    for dev in item["list"]:
                        if dev.get("name") == "Developer":
                            developer_name = dev.get("text")

        if app_item:
            app_item["integration_type"] = "appgallery"
            if developer_name:
                app_item["developer"] = developer_name
            return app_item

        raise ValueError(f"App ID {app_id} not found in response.")
    except Exception as e:
        logger.error(f"Error fetching app info: {e}")
        logger.error(f"App ID: {app_id}")
        raise

def print_info(app_info, detail_info=None, as_json=False):
    if as_json:
        print(json.dumps({"app_info": app_info, "detail_info": detail_info}, indent=2, ensure_ascii=False))
        return

    print("\n📦 App Summary:")

    # App name
    name = app_info.get("name") or "N/A"
    # Version
    version = app_info.get("versionName") or app_info.get("version") or "N/A"
    # Size in bytes
    size_bytes = app_info.get("size") or app_info.get("fullSize") or 0
    size_mb = round(size_bytes / (1024 * 1024), 2)
    # Developer
    developer = app_info.get("developer") or "N/A"
    # App ID
    appid = app_info.get("appid") or "N/A"
    # Package
    package = app_info.get("package") or app_info.get("package_name") or "N/A"
    # SHA256
    sha256 = app_info.get("sha256") or "N/A"
    # Portal URL
    portal_url = app_info.get("portalUrl") or "N/A"
    # Description
    description = app_info.get("editorDescribe") or app_info.get("description") or "N/A"

    print(f"  Name       : {name}")
    print(f"  Version    : {version}")
    print(f"  Size       : {size_mb} MB ({size_bytes} bytes)")
    print(f"  App ID     : {appid}")
    print(f"  Developer  : {developer}")
    print(f"  Package    : {package}")
    print(f"  SHA256     : {sha256}")
    print(f"  Portal URL : {portal_url}")
    print(f"  Description: {description.strip()}")

def write_summary(app_id, app_info, detail_info, status):
    index_file = os.path.join(SUMMARY_DIR, "summary.csv")
    file_exists = os.path.isfile(index_file)
    with open(index_file, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["App ID", "Name", "Version", "Size_MB", "App Bytes", "Developer", "Package", "SHA256", "Portal URL", "Description", "Status"])

        name = app_info.get("name") or "N/A"
        version = app_info.get("versionName") or app_info.get("version") or "N/A"
        size_bytes = app_info.get("size") or app_info.get("fullSize") or 0
        size_mb = round(size_bytes / (1024 * 1024), 2)
        developer = app_info.get("developer") or "N/A"
        package = app_info.get("package") or app_info.get("package_name") or "N/A"
        sha256 = app_info.get("sha256") or "N/A"
        portal_url = app_info.get("portalUrl") or "N/A"
        description = app_info.get("editorDescribe") or app_info.get("description") or "N/A"

        writer.writerow([app_id, name, version, size_mb, size_bytes, developer, package, sha256, portal_url, description.strip(), status])

def cli():
    parser = argparse.ArgumentParser(description="Huawei AppGallery CLI Tool")
    parser.add_argument("command", choices=["info", "download"], help="Command to run")
    parser.add_argument("app_id", nargs="?", help="AppGallery app ID")
    parser.add_argument("--json", action="store_true", help="Print raw JSON output")
    parser.add_argument("--quiet", action="store_true", help="Suppress non-error output")
    parser.add_argument("--bulk", help="Path to file containing list of app IDs (one per line)")
    parser.add_argument("--path", default="./downloads", help="Download directory")
    parser.add_argument("--file", default=None, help="Custom file name (without .apk)")
    parser.add_argument("--threads", type=int, default=4, help="Number of threads for bulk operations")

    args, unknown_args = parser.parse_known_args()

    if args.quiet:
        logger.setLevel(logging.ERROR)

    def process_info(app_id):
        try:
            app_info = get_app_info(app_id)
            print_info(app_info, as_json=args.json)
            write_summary(app_id, app_info, None, "info_success")
        except Exception as e:
            logger.error(f"❌ Failed to get info for {app_id}: {e}")
            write_summary(app_id, {}, None, f"info_failed: {e}")

    def process_download(app_id):
        try:
            app_info = get_app_info(app_id)
            print_info(app_info, as_json=args.json)
            write_summary(app_id, app_info, None, "download_success")
        except Exception as e:
            logger.error(f"❌ Failed to download app {app_id}: {e}")
            write_summary(app_id, {}, None, f"download_failed: {e}")

    if args.bulk:
        if not os.path.exists(args.bulk):
            logger.error(f"Bulk file '{args.bulk}' does not exist.")
            return
        with open(args.bulk) as f:
            app_ids = [line.strip() for line in f if line.strip()]
        task_func = process_info if args.command == "info" else process_download
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            futures = {executor.submit(task_func, app_id): app_id for app_id in app_ids}
            for future in as_completed(futures):
                future.result()
    elif args.app_id:
        if args.command == "info":
            process_info(args.app_id)
        elif args.command == "download":
            process_download(args.app_id)
    else:
        logger.error("No app_id provided and --bulk not specified.")

if __name__ == "__main__":
    cli()
