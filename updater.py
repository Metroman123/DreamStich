import json
import shutil
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path


GITHUB_REPO = "Metroman123/DreamStich"
CURRENT_VERSION_FILE = Path("version.txt")

PROTECTED = {
    "Videos",
    "videos",
    "audio",
    "dream_renders",
    "models",
    "model",
    "ai",
    "dreamstitch_settings.json",
    "dream_index.json",
    ".venv",
    "venv",
    "__pycache__",
    ".git",
}


def read_local_version():
    if CURRENT_VERSION_FILE.exists():
        return CURRENT_VERSION_FILE.read_text(encoding="utf-8").strip()
    return "0.0.0"


def github_api(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "DreamStitch-Updater",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def download_file(url, output_path):
    request = urllib.request.Request(url, headers={"User-Agent": "DreamStitch-Updater"})
    with urllib.request.urlopen(request, timeout=60) as response:
        output_path.write_bytes(response.read())


def copy_update_files(source_dir, project_dir, backup_dir):
    for item in source_dir.iterdir():
        if item.name in PROTECTED:
            continue

        destination = project_dir / item.name

        if destination.exists():
            backup_target = backup_dir / item.name
            if destination.is_dir():
                shutil.copytree(destination, backup_target)
                shutil.rmtree(destination)
            else:
                shutil.copy2(destination, backup_target)
                destination.unlink()

        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)


def check_for_update(status_callback=None):
    def status(text):
        print(text)
        if status_callback:
            status_callback(text)

    project_dir = Path.cwd()
    local_version = read_local_version()

    status(f"Current version: {local_version}")
    status("Checking GitHub for updates...")

    release = github_api(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest")
    latest_version = release.get("tag_name", "").replace("v", "").strip()
    zip_url = release.get("zipball_url")

    if not latest_version or not zip_url:
        return {
            "updated": False,
            "message": "Could not read latest GitHub release.",
        }

    if latest_version == local_version:
        return {
            "updated": False,
            "message": f"DreamStitch is already up to date: {local_version}",
        }

    updates_dir = project_dir / "_dreamstitch_update"
    if updates_dir.exists():
        shutil.rmtree(updates_dir)
    updates_dir.mkdir()

    zip_path = updates_dir / "update.zip"
    extract_dir = updates_dir / "extract"
    extract_dir.mkdir()

    status(f"Downloading DreamStitch {latest_version}...")
    download_file(zip_url, zip_path)

    status("Extracting update...")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_dir)

    extracted_roots = [p for p in extract_dir.iterdir() if p.is_dir()]
    if not extracted_roots:
        return {
            "updated": False,
            "message": "Update ZIP did not contain a project folder.",
        }

    update_source = extracted_roots[0]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = project_dir / f"DreamStitch_backup_before_update_{timestamp}"
    backup_dir.mkdir()

    status("Backing up current files...")
    status("Installing update...")
    copy_update_files(update_source, project_dir, backup_dir)

    CURRENT_VERSION_FILE.write_text(latest_version, encoding="utf-8")

    shutil.rmtree(updates_dir, ignore_errors=True)

    return {
        "updated": True,
        "message": f"Updated to DreamStitch {latest_version}. Restart the app.",
        "backup": str(backup_dir),
    }