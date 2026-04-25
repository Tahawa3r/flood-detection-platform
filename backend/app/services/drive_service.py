"""
Google Drive sync service.
Downloads files from a shared Google Drive folder using a service account.
"""

import os
import io
from typing import List, Dict

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from app.core.config import settings
from app.services.job_service import update_job


SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def _get_drive_service():
    """Build an authenticated Google Drive API client."""
    creds = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


def list_drive_files(folder_id: str = None) -> List[Dict]:
    """List files in the configured Google Drive folder."""
    folder_id = folder_id or settings.GDRIVE_FOLDER_ID
    service = _get_drive_service()
    query = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType, size)",
        pageSize=100,
    ).execute()
    return results.get("files", [])


def download_file(file_id: str, dest_path: str):
    """Download a single file from Google Drive to a local path."""
    service = _get_drive_service()
    request = service.files().get_media(fileId=file_id)
    with open(dest_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def sync_drive_to_local(job_id: str, dataset_id: str, dest_dir: str):
    """
    Background task: download all files from the Drive folder that match
    the dataset_id into dest_dir.
    """
    update_job(job_id, log_line=f"Listing files in Drive folder {settings.GDRIVE_FOLDER_ID}")

    try:
        files = list_drive_files()
    except Exception as exc:
        update_job(job_id, log_line=f"Failed to list Drive files: {exc}")
        raise

    # Filter files that match the dataset_id or are GeoTIFFs
    matching = [f for f in files if dataset_id in f["name"] or f["name"].endswith(".tif")]

    if not matching:
        update_job(job_id, log_line="No matching files found in Drive folder")
        return

    update_job(job_id, log_line=f"Found {len(matching)} file(s) to download")

    for i, file_info in enumerate(matching):
        dest_path = os.path.join(dest_dir, file_info["name"])
        update_job(
            job_id,
            progress=(i / len(matching)) * 100,
            log_line=f"Downloading {file_info['name']}...",
        )
        try:
            download_file(file_info["id"], dest_path)
            update_job(job_id, log_line=f"  ✓ Saved to {dest_path}")
        except Exception as exc:
            update_job(job_id, log_line=f"  ✗ Failed: {exc}")
            raise
