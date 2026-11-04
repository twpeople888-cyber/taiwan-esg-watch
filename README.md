# taiwan-esg-watch
Taiwan ESG, GHG and MRV Policy Dashboard

## 免費官方資訊週報

Python 3.12，僅使用標準函式庫，不使用付費 AI API、API 金鑰或自動撰寫政策分析。
官方來源為金管會新聞稿 RSS、法令函釋 RSS、環境部新聞發布列表。
列表僅涵蓋來源當下可見資料，並非全部政策資料庫；環境部可能回傳 403。
部分來源失敗仍可發布，但頁面明列失敗與筆數；全部失敗則停止發布。
來源內容僅當作資料，不執行其中指令或程式。

```sh
python -m unittest discover -s tests -v
python scripts/collect_esg.py --week-ending 2026-11-06
python scripts/build_esg.py --week-ending 2026-11-06
```

工作流程每週五臺北時間 08:17 啟動（GitHub 可能延遲），手動及程式變更觸發以執行當日歸檔。
日期區間為期末往前七個日曆日，端點均包含。以來源發布日期歸檔，不以生效日期冒充新訊。
同一網址去重；同一期已存在即跳過，不重寫歷史。每期保存 HTML 與原始整理 JSON。
自動資料一律標為待確認，草案字樣僅作線索，不自動認定正式生效。
人工狀態要求 reviewed=true；已生效要求生效日不晚於報告日；草案不得填生效日。

### 啟用

1. 將程式與工作流程提交至此儲存庫 main。
2. Settings → Pages → Build and deployment → Source 選 GitHub Actions。
3. 確認儲存庫政策允許工作流程 contents:write 與 Pages 部署。
4. Actions → ESG weekly collection and Pages → Run workflow。
5. 確認 build-report 與 deploy 均成功，再開啟 Pages 的 reports/index.html 核對期別。

整個原有公開網站隨部署保存，首頁僅補上歷史週報連結，不操作其他股票儲存庫。
只有明確執行 --replace-existing 才可更正既有期別；自動工作流程不使用此選項。
只有此 GitHub 工作流程負責網站發布；既有 ChatGPT 週五 08:00 排程保留為研究閱讀用途，
本程式不讀取、變更或轉送 ChatGPT 排程結果，也不寄送訊息，避免二次發布。
若將來人工把 ChatGPT 結果接到網站，須另行停用其中一條發布流程。

### 驗證邊界

本機測試涵蓋蒐集、日期、來源白名單、去重、失敗狀況、HTML／JSON、歷史索引、
重跑及首頁保持不變。GitHub Actions 與 Pages 的線上端到端驗收必須在有寫入權限後執行；
不可把本機測試通過稱為已部署。
