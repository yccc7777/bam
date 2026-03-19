#!/bin/bash

echo "======================================"
echo "    Project Chronos - 自動環境建置腳本"
echo "======================================"

# 1. Check for Xcode Command Line Tools
echo "[1/3] 檢查 Xcode Command Line Tools 狀態..."
if ! xcode-select -p &>/dev/null; then
    echo "⚠️ 尚未安裝 Xcode Command Line Tools！"
    echo "👉 正在為您觸發安裝視窗..."
    xcode-select --install
    echo ""
    echo "=================================================="
    echo "請看您的螢幕畫面，會跳出一個系統對話框。"
    echo "請點擊「安裝 (Install)」，並「同意 (Agree)」條款。"
    echo "安裝過程可能需時幾分鐘，完成後請「再次執行」本腳本！"
    echo "=================================================="
    exit 1
else
    echo "✅ Xcode Command Line Tools 已安裝。"
fi

# 2. Setup Virtual Environment
echo ""
echo "[2/3] 建立 Python 虛擬環境 (venv)..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ 虛擬環境建立成功。"
else
    echo "✅ 虛擬環境 venv 已存在。"
fi

# 3. Install packages
echo ""
echo "[3/3] 啟動虛擬環境並安裝所需套件..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "=================================================="
echo "🎉 所有環境建置完成！"
echo "👉 執行程式前，請確保已將 .env.example 複製為 .env 並填好設定。"
echo "👉 啟動 Bot 指令："
echo "   source venv/bin/activate"
echo "   python main.py"
echo "=================================================="
