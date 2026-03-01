# Zeabur 部署問題修復紀錄

## 日期
2026-03-01

## 問題描述
1. GitHub 推送程式碼後，Zeabur 沒有自動部署
2. 部署後缺少 APScheduler 模組
3. Port 設定錯誤（5000 → 8080）
4. Debug mode 導致部署失敗

---

## 修復步驟

### 1. 新增 APScheduler 依賴
**檔案：** `requirements.txt`
```diff
+ APScheduler>=3.10
```

### 2. 修復 Port 設定
**檔案：** `app.py`
```diff
- if __name__ == '__main__':
-     print("🚀 啟動網頁版儀表板...")
-     print("📍 http://localhost:5000")
-     app.run(host='0.0.0.0', port=5000, debug=True)
+ if __name__ == '__main__':
+     port = int(os.environ.get('PORT', 8080))
+     print("🚀 啟動網頁版儀表板...")
+     print(f"📍 http://localhost:{port}")
+     app.run(host='0.0.0.0', port=port, debug=False)
```

### 3. 修復 Dockerfile
**檔案：** `Dockerfile`
```diff
- EXPOSE 5000
- CMD ["python3", "app.py"]
+ EXPOSE 8080
+ CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "app:app"]
```

### 4. 修復 Zeabur 設定
- Branch 從 `main` 改為 `master`
- 確認 GitHub 連結正確

---

## Git Commit 紀錄
```
6d72392 新增 APScheduler 依賴
80d1473 修復 port 設定為 8080，關閉 debug mode
cc3f693 修復 Dockerfile 使用 gunicorn port 8080
```

---

## 部署網址
- Zeabur: https://stock-web-dashboard.zeabur.app
- Vercel: https://stock-web-dashboard.vercel.app

---

## GitHub Repository
https://github.com/jun20250621-prog/stock-web-dashboard

---

## 注意事項
1. Zeabur 期望 port 為 8080
2. 使用 gunicorn 而非 Flask 內建伺服器
3. 確認 Zeabur GitHub 設定中的 Branch 為 master
4. 開啟 Auto Deploy on Push
