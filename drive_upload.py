import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import config

_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _load_credentials():
    creds = None
    if os.path.exists(config.GDRIVE_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(config.GDRIVE_TOKEN_PATH, _SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        # 최초 1회만 실행됨: 콘솔에 뜨는 URL을 아무 기기 브라우저로 열어 로그인하고,
        # 받은 코드를 여기 붙여넣으면 이후로는 토큰이 자동 갱신되어 다시 로그인할 필요 없다.
        flow = InstalledAppFlow.from_client_secrets_file(
            config.GDRIVE_CLIENT_SECRET_PATH, _SCOPES
        )
        creds = flow.run_console()
        with open(config.GDRIVE_TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return creds


def upload_photo(path, filename):
    """path의 사진 파일을 config.GDRIVE_FOLDER_ID 폴더에 filename으로 올리고 파일 id를 반환."""
    creds = _load_credentials()
    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    metadata = {"name": filename, "parents": [config.GDRIVE_FOLDER_ID]}
    media = MediaFileUpload(path, mimetype="image/jpeg")
    result = service.files().create(body=metadata, media_body=media, fields="id").execute()
    return result["id"]
