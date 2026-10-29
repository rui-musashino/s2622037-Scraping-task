"""練習問題: 阿部寛さんの出演映画タイトルを取得する。"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup


MOVIE_URL = "http://abehiroshi.la.coocan.jp/movie/eiga.htm"
OUTPUT_PATH = Path(__file__).with_name("practice_movies.csv")
USER_AGENT = "Mozilla/5.0 (compatible; s2622037-scraping-practice/1.0)"


def fetch_movie_titles() -> list[str]:
    """映画一覧表の2列目から作品名を取得する。"""
    response = requests.get(
        MOVIE_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()

    # 対象ページはShift_JISで作られているため、文字コードを明示する。
    soup = BeautifulSoup(response.content, "html.parser", from_encoding="shift_jis")
    movie_table = soup.find("table", attrs={"border": "1"})
    if movie_table is None:
        raise RuntimeError("映画一覧の表が見つかりませんでした。")

    titles: list[str] = []
    for row in movie_table.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        text = " ".join(cells[1].stripped_strings)
        text = re.sub(r"\s+", " ", text).strip()
        # 作品名は一覧内で「」に囲まれている。舞台公演など、映画ではない行は除く。
        match = re.search(r"「([^」]+)」", text)
        if match:
            titles.append(match.group(1).strip())
    return titles


def save_titles(titles: list[str], output_path: Path = OUTPUT_PATH) -> None:
    """Excelでも文字化けしにくいUTF-8（BOM付き）のCSVに保存する。"""
    with output_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["title"])
        writer.writerows([title] for title in titles)


def main() -> None:
    titles = fetch_movie_titles()
    save_titles(titles)
    for number, title in enumerate(titles, start=1):
        print(f"{number:>3}: {title}")
    print(f"\n{len(titles)}件を {OUTPUT_PATH.name} に保存しました。")


if __name__ == "__main__":
    main()

