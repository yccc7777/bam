import logging
import yfinance as yf
from data.portfolio_db import PortfolioDB

logger = logging.getLogger(__name__)

class PaperBroker:
    def __init__(self, db: PortfolioDB):
        self.db = db

    def get_current_price(self, ticker: str) -> float:
        try:
            stock = yf.Ticker(ticker)
            # 獲取即時價格
            data = stock.history(period="1d")
            if not data.empty:
                return float(data['Close'].iloc[-1])
            return 0.0
        except Exception as e:
            logger.error(f"Error fetching price for {ticker}: {e}")
            return 0.0

    def buy(self, user_id: int, ticker: str, quantity: int) -> dict:
        """
        執行模擬買進
        回傳: {"success": bool, "message": str, "price": float}
        """
        if quantity <= 0:
            return {"success": False, "message": "買進股數必須大於 0"}

        price = self.get_current_price(ticker)
        if price <= 0:
            return {"success": False, "message": f"無法取得 {ticker} 即時報價"}

        cost = price * quantity
        # 假設手續費 0.1425% (不考慮折讓)
        fee = cost * 0.001425
        total_cost = cost + fee

        balance = self.db.get_or_create_user(user_id)
        if balance < total_cost:
            return {"success": False, "message": f"餘額不足！需要 ${total_cost:,.0f}，目前餘額 ${balance:,.0f}"}

        # 更新餘額
        new_balance = balance - total_cost
        self.db.update_balance(user_id, new_balance)

        # 更新持股
        current_qty, current_avg = self.db.get_holding(user_id, ticker)
        new_qty = current_qty + quantity
        # 重新計算平均成本
        new_avg = ((current_qty * current_avg) + total_cost) / new_qty
        self.db.update_holding(user_id, ticker, new_qty, new_avg)

        # 記錄交易
        self.db.record_trade(user_id, ticker, 'BUY', price, quantity)

        return {"success": True, "message": f"成功買進 {quantity} 股 {ticker}！\n成交價: ${price:.2f}\n總花費: ${total_cost:,.0f} (含手續費)\n剩餘可用資金: ${new_balance:,.0f}", "price": price}

    def sell(self, user_id: int, ticker: str, quantity: int) -> dict:
        """
        執行模擬賣出
        回傳: {"success": bool, "message": str, "price": float}
        """
        if quantity <= 0:
            return {"success": False, "message": "賣出股數必須大於 0"}

        current_qty, current_avg = self.db.get_holding(user_id, ticker)
        if current_qty < quantity:
            return {"success": False, "message": f"庫存不足！欲賣出 {quantity} 股，目前持有 {current_qty} 股"}

        price = self.get_current_price(ticker)
        if price <= 0:
            return {"success": False, "message": f"無法取得 {ticker} 即時報價"}

        revenue = price * quantity
        # 假設手續費 0.1425% + 證交稅 0.3%
        fee = revenue * 0.001425
        tax = revenue * 0.003
        total_revenue = revenue - fee - tax

        # 更新餘額
        balance = self.db.get_or_create_user(user_id)
        new_balance = balance + total_revenue
        self.db.update_balance(user_id, new_balance)

        # 更新持股
        new_qty = current_qty - quantity
        self.db.update_holding(user_id, ticker, new_qty, current_avg)

        # 記錄交易
        self.db.record_trade(user_id, ticker, 'SELL', price, quantity)

        # 計算損益
        realized_pnl = (price - current_avg) * quantity - fee - tax

        return {"success": True, "message": f"成功賣出 {quantity} 股 {ticker}！\n成交價: ${price:.2f}\n實收金額: ${total_revenue:,.0f} (扣除稅費)\n已實現損益: ${realized_pnl:,.0f}\n剩餘可用資金: ${new_balance:,.0f}", "price": price}
