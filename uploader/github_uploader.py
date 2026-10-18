import os
import json
import base64
import time
import requests
from datetime import datetime

# 리그별 파일명 접미사 — MLB 파일(20261001.json)과 구분되도록
# 예: NHL → "20261001 nhl.json"
FILE_SUFFIX = {
    "NHL": " nhl",
    "NFL": " nfl",
    "KHL": " khl",
    "NBA": " nba",
    "KBL": " kbl",
    "KOVO": " kovo",
    "WKOVO": " wkovo",
    "DEL": " del",
    "CZE": " cze",
}


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
        filename = f"{date}{FILE_SUFFIX.get(league, '')}.json"
        path = f"data/{league}/{subfolder}/{filename}"
        content = json.dumps(data, ensure_ascii=False, indent=2)
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        url = f"{self.api_base}/contents/{path}"
        # 여러 워크플로우가 동시에 main에 커밋하면 409(브랜치 이동)·422(sha 불일치)가 난다
        # → sha를 다시 읽고 재시도 (이전엔 조용히 실패해 일부 날짜가 누락됐음)
        for attempt in range(5):
            sha = self._get_file_sha(path)   # 기존 파일 SHA 확인 (업데이트 시 필요)
            payload = {
                "message": f"[{league}] {date} 데이터 업데이트",
                "content": content_b64,
                "branch": "main"
            }
            if sha:
                payload["sha"] = sha
            resp = requests.put(url, headers=self.headers, json=payload)
            if resp.status_code in [200, 201]:
                print(f"  📁 {league}/{subfolder}/{filename} 업로드 완료")
                return True
            if resp.status_code in (409, 422, 500, 502, 503) and attempt < 4:
                time.sleep(2 * (attempt + 1))
                continue
            break
        print(f"  ❌ 업로드 실패: {resp.status_code} {resp.text[:200]}")
        return False

    def file_exists(self, league: str, date: str, subfolder: str = "daily") -> bool:
        filename = f"{date}{FILE_SUFFIX.get(league, '')}.json"
        return self._get_file_sha(f"data/{league}/{subfolder}/{filename}") is not None

    def _get_file_sha(self, path: str) -> str:
        url = f"{self.api_base}/contents/{path}"
        resp = requests.get(url, headers=self.headers)
        if resp.status_code == 200:
            return resp.json().get("sha")
        return None
