# KAY 匿名聊天（Flask 入門版）

## 功能
- 建立帳戶時產生私人 KAY（登入憑證）及公共 KAY（別人用來聯絡你）。
- 私訊：輸入對方公共 KAY 開始對話。
- 建立群組／頻道：各自產生管理用私人 KAY 及加入用公共 KAY。
- 群組／頻道可透過公共 KAY 加入。
- 訊息以 2.5 秒輪詢方式更新；這是簡易 MVP，並非即時 WebSocket。

## 本機執行
需要 Python 3.10+。

```bash
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows:
# .venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

瀏覽 http://127.0.0.1:9008

## KAY 編碼規則
- 私人 KAY：只儲存 SHA-256 雜湊；建立時只顯示一次。遺失後目前版本不能找回。
- 公共 KAY：可分享給別人，供搜尋／開啟私訊或加入群組、頻道。
- 群組／頻道私人 KAY：目前先生成並顯示作為管理憑證；進階版可加入管理員驗證、改名、刪除等功能。

## 上線前必須補強
這是功能原型，不應直接承載敏感或大量真實對話。正式公開前應加入：
- HTTPS、CSRF 防護、登入嘗試限制、訊息發送速率限制。
- 封鎖、檢舉、管理員審核、垃圾訊息防護及使用者安全設定。
- 私人 KAY 更安全的密碼雜湊（例如 Argon2id）及重新產生／撤銷流程。
- PostgreSQL 等外部持久化資料庫、備份與資料刪除機制。
- 權限設計：群組成員管理；頻道可設定只有管理員發文或所有成員發文。

## Vercel 部署提醒
Vercel 可以部署 Flask，但不要把本機 SQLite 檔案當成正式資料庫；Serverless Function 的本機檔案不適合作為跨執行個體的持久資料。正式部署請改用外部 PostgreSQL（例如 Vercel Marketplace 可連接的資料庫），再把資料存取層由 SQLite 改成 PostgreSQL。
