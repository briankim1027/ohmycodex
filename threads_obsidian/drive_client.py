from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


class DriveUploadError(RuntimeError):
    pass


@dataclass(frozen=True)
class DriveClientConfig:
    root_folder_id: str
    credentials_file: Path
    token_file: Path


class GoogleDriveUploader:
    SCOPES = ["https://www.googleapis.com/auth/drive"]

    def __init__(self, config: DriveClientConfig) -> None:
        self.config = config
        self._service = None
        self._date_folder_cache: dict[str, str] = {}

    def _build_service(self):
        if self._service is not None:
            return self._service

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:  # pragma: no cover
            raise DriveUploadError(
                "Google Drive dependencies are missing. Install requirements.txt first."
            ) from exc

        creds = None
        if self.config.token_file.exists():
            creds = Credentials.from_authorized_user_file(str(self.config.token_file), self.SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.config.credentials_file.exists():
                    raise DriveUploadError(
                        f"OAuth client file not found: {self.config.credentials_file}"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.config.credentials_file), self.SCOPES
                )
                creds = flow.run_local_server(port=0)

            self.config.token_file.parent.mkdir(parents=True, exist_ok=True)
            self.config.token_file.write_text(creds.to_json(), encoding="utf-8")

        self._service = build("drive", "v3", credentials=creds)
        return self._service

    def ensure_date_folder(self, date_folder_name: str) -> str:
        if date_folder_name in self._date_folder_cache:
            return self._date_folder_cache[date_folder_name]

        service = self._build_service()
        escaped_name = date_folder_name.replace("'", "\\'")
        query = (
            f"name = '{escaped_name}' and '{self.config.root_folder_id}' in parents "
            "and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )

        try:
            result = (
                service.files()
                .list(q=query, spaces="drive", fields="files(id, name)", pageSize=1)
                .execute()
            )
        except Exception as exc:  # pragma: no cover
            raise DriveUploadError(f"Failed to list Drive date folder: {exc}") from exc

        files = result.get("files", [])
        if files:
            folder_id = files[0]["id"]
            self._date_folder_cache[date_folder_name] = folder_id
            return folder_id

        metadata = {
            "name": date_folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [self.config.root_folder_id],
        }
        try:
            folder = service.files().create(body=metadata, fields="id").execute()
        except Exception as exc:
            raise DriveUploadError(f"Failed to create Drive date folder '{date_folder_name}': {exc}") from exc

        folder_id = folder["id"]
        self._date_folder_cache[date_folder_name] = folder_id
        return folder_id

    def file_exists(self, folder_id: str, filename: str) -> bool:
        service = self._build_service()
        escaped_name = filename.replace("'", "\\'")
        query = (
            f"name = '{escaped_name}' and '{folder_id}' in parents and trashed = false"
        )
        try:
            result = service.files().list(q=query, fields="files(id)", pageSize=1).execute()
        except Exception as exc:  # pragma: no cover
            raise DriveUploadError(f"Failed to check duplicate on Drive: {exc}") from exc
        return bool(result.get("files"))

    def upload_markdown(self, folder_id: str, filename: str, content: str) -> None:
        service = self._build_service()
        try:
            from googleapiclient.http import MediaInMemoryUpload
        except ImportError as exc:  # pragma: no cover
            raise DriveUploadError(
                "google-api-python-client is missing. Install requirements.txt first."
            ) from exc

        media = MediaInMemoryUpload(content.encode("utf-8"), mimetype="text/markdown", resumable=False)
        metadata = {
            "name": filename,
            "parents": [folder_id],
            "mimeType": "text/markdown",
        }
        try:
            service.files().create(body=metadata, media_body=media, fields="id").execute()
        except Exception as exc:
            raise DriveUploadError(f"Failed to upload markdown '{filename}': {exc}") from exc
        logger.info("Uploaded file to Drive: %s", filename)

    def check_root_folder_access(self) -> dict[str, object]:
        service = self._build_service()
        try:
            root = (
                service.files()
                .get(
                    fileId=self.config.root_folder_id,
                    fields="id,name,mimeType,trashed,capabilities(canAddChildren,canEdit)",
                )
                .execute()
            )
        except Exception as exc:  # pragma: no cover
            raise DriveUploadError(f"Failed to access Drive root folder: {exc}") from exc

        capabilities = root.get("capabilities") or {}
        can_write = bool(capabilities.get("canAddChildren") or capabilities.get("canEdit"))
        return {
            "id": root.get("id"),
            "name": root.get("name"),
            "mimeType": root.get("mimeType"),
            "trashed": bool(root.get("trashed")),
            "can_write": can_write,
        }
