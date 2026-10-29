# s2622037-Scraping-task

DS Programming（2026年10月21日）のWebスクレイピング課題です。

## セットアップ

```sh
uv sync
```

## 練習問題

阿部寛さんの出演映画ページから、一覧表の映画タイトルを取得します。

```sh
uv run python practice_movies.py
```

結果は画面に表示し、`practice_movies.csv` にも保存します。

## 個別課題

武蔵野大学Webサイトのトップページから同一ドメインのHTMLページを幅優先で巡回し、URLと`title`を辞書型変数に格納してからCSVへ保存します。

```sh
uv run python sitemap_crawler.py
```

結果は`url,title`の2列を持つ`sitemap.csv`に保存します。アクセス前に`robots.txt`を確認し、各HTTPアクセスの間には最低1秒の待機を入れています。一時的な通信失敗、HTTP 429、サーバー側エラー（5xx）が起きたURLは、巡回キューの末尾に戻して最大3回試行します。認証が必要なページやリンク切れなどの4xxは再試行しません。

動作確認だけを行う場合は、巡回ページ数を制限できます。

```sh
uv run python sitemap_crawler.py --max-pages 10
```

取得した全URLとタイトルを実行中にも表示したい場合は、`--verbose`を付けます。

## 注意

- 対象サイトの利用規約・robots.txtを確認して実行してください。
- 待機時間は`--delay`で長くできますが、1秒未満にはなりません。
- 実行時点のWebサイト構成により、結果と所要時間は変わります。

