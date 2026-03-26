# タスク管理 (TODO)

## キャプティブポータル実装

- [x] `main.py`: `DNSServer` の有効化 (インポート、初期化、start)。
- [x] `web.py`: `handle_client` メソッド内にキャプティブポータル用のリダイレクトロジックを追加。
  - Host ヘッダーチェックの実装。
  - 特定パス (`/generate_204` 等) のリダイレクト実装。
- [x] 動作確認: 実機 (iPhone, Android, PC) で Wi-Fi 接続時に自動的にページが開くか確認。

## Markdown 対応

- [x] ライブラリ導入: `marked.js` を `www/lib/` に配置。
- [x] フロントエンド実装 (`index.js`): 対象項目の表示処理を Markdown パーサー経由に変更。
  - 職務経歴 (`job_description`)
  - ポートレイト (`portrait_summary`)
  - 志望動機 (`usr_siboudouki`)
  - 趣味 (`usr_hobby`)
  - 特技 (`usr_skill`)

## 管理画面認証

- [x] `secrets.py.sample` に管理用パスワード設定を追加。
- [x] `web.py` に `/admin/login` `/admin/logout` とセッション認証を追加。
- [x] `/admin/*` と管理用 API の未認証アクセスを遮断。
- [x] `www/` にログイン画面と未認証時の導線を追加。
- [ ] 実機でログイン、未認証拒否、ログアウトを確認。
