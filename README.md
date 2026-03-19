# 台灣 50 多期預測機器人 (Project Chronos)

**Project Chronos (時鐘神)** 是一個基於機器學習與籌碼動能的台股預測機器人系統，專注於預測「台灣 50 成分股」的未來表現，並透過 Telegram Bot 提供投資者看漲標的排行與個股預測分析。

## 功能與特色
- **多時間窗格預測**：採用機器學習模型 (XGBoost/Random Forest)，預測個股未來 1週、2週、1個月、3個月的預期報酬率。
- **籌碼面輔助**：整合三大法人買賣超資料，輔助過濾籌碼弱勢標的，提升模型準確度。
- **Telegram Bot 介面**：
  - `/top`：獲取預期報酬最高的看漲標的。
  - `/predict <股票代號>`：查詢單一個股的細部預測結果與綜合短評。
- **AI 綜合報告**：利用 Google Gemini API 結合技術面、籌碼面與模型預測，生成人類易讀的綜合評語。

## 系統架構
專案主要分為以下模組：
- `data/`: 爬蟲資料管線 (`yfinance` 獲取日線價量、證交所 API 獲取法人籌碼) 與特徵工程處理。
- `models/`: 機器學習迴歸模型與 LLM 敘述生成模組。
- `strategies/`: 基於預測結果與籌碼條件過濾的選股與買賣號誌邏輯。
- `backtest/`: 包含交易成本在內的歷史回測框架 (2022-2025)。
- `config/`: 參數設定管理。

## 環境建置

1. **複製專案並建立虛擬環境：**
```bash
git clone <Repository_URL>
cd ProjectChronos
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. **設定環境變數：**
請複製 `.env.example` 並更名為 `.env`，填寫對應的 API 金鑰：
```env
TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
GEMINI_API_KEY="your_gemini_api_key"
```

3. **啟動 Bot：**
```bash
python main.py
```

## 版本紀錄 (Changelog)
- **v0.1.0** (In Progress): 專案架構初始化、需求規格討論、資料管線開發。
