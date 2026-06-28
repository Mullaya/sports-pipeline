import os
import json
import base64
import requests
from datetime import datetime

class GitHubUploader:

    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        self.repo = os.getenv("GITHUB_REPOSITORY")
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.api_base = f"https://api.github.com/repos/{self.repo}"

    def upload_json(self, data: dict, league: str, date: str, subfolder: str = "daily"):
        filename = f"{date}.json"
        path = f"data/{league}/{subfolder}/{filename}"
        content = json.dumps(data, ensure_ascii=False, indent=2)
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        # 기존 파일 SHA 확인 (업데이트 시 필요)
        sha = self._get_file_sha(path)

        payload = {
            "message": f"[{league}] {date} 데이터 업데이트",
            "content": content_b64,
            "branch": "main"
        }

        if sha:
            payload["sha"] = sha

        url = f"{self.api_base}/contents/{path}"
        resp = requests.put(url, headers=self.headers, json=payload)

        if resp.status_code in [200, 201]:
            print(f"  📁 {league}/{subfolder}/{filename} 업로드 완료")
            return True
        else:
            print(f"  ❌ 업로드 실패: {resp.status_code} {resp.text[:200]}")
            return False

    def _get_file_sha(self, path: str) -> str:
        url = f"{self.api_base}/contents/{path}"
        resp = requests.get(url, headers=self.headers)
        if resp.status_code == 200:
            return resp.json().get("sha")
        return None
