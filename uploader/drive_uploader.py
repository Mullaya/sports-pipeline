from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
import json
import os

class DriveUploader:

    SCOPES = ["https://www.googleapis.com/auth/drive"]
    OWNER_EMAIL = "lbs5208@gmail.com"

    FOLDER_IDS = {
        "KBO": "1OupJNXwKmIhZKRhD4MGOS47ABFQvW1qn",
        "NPB": "1KbEwMLrZwOZwpg7Rh0DJw_-_CVb-EYLH",
        "MLB": "1UPyfLeTEClfC0WQmd1tk9kFHf4cSKZF8",
    }

    def __init__(self):
        creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        creds_dict = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=self.SCOPES
        )
        self.service = build("drive", "v3", credentials=creds)

    def upload_json(self, data: dict, league: str, date: str, subfolder: str = "daily"):
        filename = f"{date}.json"
        content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")

        parent_id = self.FOLDER_IDS.get(league)
        if not parent_id:
            print(f"  ❌ {league} 폴더 ID 없음")
            return None

        subfolder_id = self._get_or_create_folder(subfolder, parent_id)

        existing = self._find_file(filename, subfolder_id)
        if existing:
            self.service.files().delete(fileId=existing).execute()

        file_metadata = {
            "name": filename,
            "parents": [subfolder_id],
            "mimeType": "application/json"
        }

        media = MediaInMemoryUpload(
            content,
            mimetype="application/json",
            resumable=False
        )

        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name"
        ).execute()

        file_id = file["id"]

        # 소유권 이전: 서비스 계정 → 개인 구글 계정
        try:
            self.service.permissions().create(
                fileId=file_id,
                transferOwnership=True,
                body={
                    "type": "user",
                    "role": "owner",
                    "emailAddress": self.OWNER_EMAIL
                }
            ).execute()
        except Exception as e:
            print(f"  ⚠️ 소유권 이전 실패 (무시): {e}")

        print(f"  📁 {league}/{subfolder}/{filename} 업로드 완료")
        return file_id

    def _get_or_create_folder(self, name: str, parent_id: str) -> str:
        results = self.service.files().list(
            q=(f"name='{name}' and '{parent_id}' in parents "
               f"and mimeType='application/vnd.google-apps.folder' "
               f"and trashed=false"),
            fields="files(id, name)"
        ).execute()

        files = results.get("files", [])
        if files:
            return files[0]["id"]

        folder = self.service.files().create(
            body={
                "name": name,
                "parents": [parent_id],
                "mimeType": "application/vnd.google-apps.folder"
            },
            fields="id"
        ).execute()

        return folder["id"]

    def _find_file(self, filename: str, folder_id: str):
        results = self.service.files().list(
            q=f"name='{filename}' and '{folder_id}' in parents and trashed=false",
            fields="files(id)"
        ).execute()
        files = results.get("files", [])
        return files[0]["id"] if files else None
