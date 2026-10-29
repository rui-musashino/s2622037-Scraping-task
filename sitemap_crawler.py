"""個別課題: 武蔵野大学WebサイトのURLとtitleを収集する。"""

from __future__ import annotations

import argparse
import csv
import time
from collections import deque
from pathlib import Path
from urllib.parse import (
    parse_qsl,
    urlencode,
    urldefrag,
    urljoin,
    urlsplit,
    urlunsplit,
)
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup


START_URL = "https://www.musashino-u.ac.jp/"
OUTPUT_PATH = Path(__file__).with_name("sitemap.csv")
USER_AGENT = "s2622037-Scraping-task/1.0 (educational assignment)"
MIN_DELAY_SECONDS = 1.0
MAX_ATTEMPTS = 3
HTML_EXTENSIONS = {"", ".html", ".htm", ".php", ".asp", ".aspx"}
TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "yclid",
    "_ga",
    "_gl",
}


def normalize_url(url: str, base_url: str, target_host: str) -> str | None:
    """同一ドメインの巡回可能なURLを正規化する。"""
    absolute_url = urljoin(base_url, url.strip())
    absolute_url, _fragment = urldefrag(absolute_url)
    parts = urlsplit(absolute_url)

    if parts.scheme not in {"http", "https"} or parts.hostname is None:
        return None
    if parts.hostname.lower() != target_host:
        return None

    path = parts.path or "/"
    suffix = Path(path).suffix.lower()
    if suffix not in HTML_EXTENSIONS:
        return None

    # 同一ページを表す計測用パラメーターを除き、順序を統一する。
    query_items = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMETERS
    ]
    query = urlencode(sorted(query_items), doseq=True)

    # http/httpsの重複を避けるため、対象サイトはhttpsに統一する。
    return urlunsplit(("https", target_host, path, query, ""))


class PoliteCrawler:
    """待機時間とrobots.txtを尊重する、同一ドメイン限定クローラー。"""

    def __init__(self, start_url: str, delay: float, verbose: bool = False) -> None:
        self.start_url = start_url
        self.target_host = (urlsplit(start_url).hostname or "").lower()
        self.delay = max(delay, MIN_DELAY_SECONDS)
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.last_request_at: float | None = None
        self.robots = self._load_robots()

    def _wait(self) -> None:
        """HTTPアクセス間隔が必ずdelay秒以上になるよう待機する。"""
        if self.last_request_at is None:
            wait_seconds = self.delay
        else:
            elapsed = time.monotonic() - self.last_request_at
            wait_seconds = max(0.0, self.delay - elapsed)
        time.sleep(wait_seconds)

    def _get(self, url: str) -> requests.Response:
        self._wait()
        try:
            return self.session.get(url, timeout=30, allow_redirects=True)
        finally:
            self.last_request_at = time.monotonic()

    def _load_robots(self) -> RobotFileParser:
        robots_url = urljoin(self.start_url, "/robots.txt")
        parser = RobotFileParser(robots_url)
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self._get(robots_url)
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                else:
                    # robots.txtが存在しない場合は標準仕様どおり巡回可とする。
                    parser.parse([])
                break
            except requests.RequestException as error:
                print(f"[WARN {attempt}/{MAX_ATTEMPTS}] robots.txt: {error}")
        else:
            parser.parse([])
        return parser

    def crawl(self, max_pages: int = 0) -> dict[str, str]:
        """URLを幅優先で巡回し、URLをkey、titleをvalueとする辞書を返す。"""
        queue = deque([self.start_url])
        queued = {self.start_url}
        finished: set[str] = set()
        attempts: dict[str, int] = {}
        sitemap: dict[str, str] = {}

        while queue and (max_pages <= 0 or len(finished) < max_pages):
            url = queue.popleft()
            if url in finished:
                continue

            if not self.robots.can_fetch(USER_AGENT, url):
                print(f"[SKIP robots.txt] {url}")
                finished.add(url)
                continue

            try:
                response = self._get(url)
                final_url = normalize_url(response.url, url, self.target_host)
                if final_url is None:
                    print(f"[SKIP other domain] {url}")
                    finished.add(url)
                    continue
                response.raise_for_status()
            except requests.RequestException as error:
                status = error.response.status_code if error.response is not None else None
                retryable = status is None or status == 429 or status >= 500
                if not retryable:
                    print(f"[SKIP HTTP {status}] {url}")
                    finished.add(url)
                    continue

                attempts[url] = attempts.get(url, 0) + 1
                if attempts[url] < MAX_ATTEMPTS:
                    print(f"[RETRY {attempts[url]}/{MAX_ATTEMPTS}] {url}: {error}")
                    # 一時障害の回復時間を取るため、キュー末尾で再試行する。
                    queue.append(url)
                else:
                    print(f"[ERROR {MAX_ATTEMPTS}/{MAX_ATTEMPTS}] {url}: {error}")
                    finished.add(url)
                continue

            finished.add(url)
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type:
                print(f"[SKIP non-HTML] {url}")
                continue

            soup = BeautifulSoup(response.content, "html.parser")
            title = soup.title.get_text(" ", strip=True) if soup.title else ""
            sitemap[final_url] = title
            if self.verbose or len(sitemap) <= 5 or len(sitemap) % 50 == 0:
                print(f"[{len(sitemap):>4}] {final_url} | {title}")

            for anchor in soup.find_all("a", href=True):
                next_url = normalize_url(anchor["href"], final_url, self.target_host)
                if next_url and next_url not in finished and next_url not in queued:
                    queue.append(next_url)
                    queued.add(next_url)

        return sitemap


def save_sitemap(sitemap: dict[str, str], output_path: Path) -> None:
    """URLとtitleの辞書をCSVに保存する。"""
    with output_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["url", "title"])
        writer.writerows(sorted(sitemap.items()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-url", default=START_URL)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument(
        "--delay",
        type=float,
        default=MIN_DELAY_SECONDS,
        help="アクセス間隔（最低1.0秒）",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="巡回上限。0は上限なし（動作確認には例: 10）",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="取得した全ページを画面に表示する",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start_url = normalize_url(
        args.start_url,
        args.start_url,
        (urlsplit(args.start_url).hostname or "").lower(),
    )
    if start_url is None:
        raise ValueError("開始URLが正しくありません。")

    crawler = PoliteCrawler(start_url, args.delay, args.verbose)
    sitemap = crawler.crawl(args.max_pages)
    save_sitemap(sitemap, args.output)
    print(f"\n{len(sitemap)}件を {args.output} に保存しました。")


if __name__ == "__main__":
    main()

