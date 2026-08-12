from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import config

_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def upload_photo(path, filename):
    """path의 사진 파일을 config.GDRIVE_FOLDER_ID 폴더에 filename으로 올리고 파일 id를 반환."""
    creds = service_account.Credentials.from_service_account_file(
        config.GDRIVE_KEY_PATH, scopes=_SCOPES
    )
    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    metadata = {"name": filename, "parents": [config.GDRIVE_FOLDER_ID]}
    media = MediaFileUpload(path, mimetype="image/jpeg")
    result = service.files().create(body=metadata, media_body=media, fields="id").execute()
    return result["id"]
