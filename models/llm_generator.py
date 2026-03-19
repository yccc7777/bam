import google.generativeai as genai
import logging
import os

logger = logging.getLogger(__name__)

class LLMGenerator:
    def __init__(self, api_key: str):
        if not api_key:
            logger.warning("Gemini API key is not set. Will fall back to rule-based generation.")
            self.use_llm = False
        else:
            try:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-pro')
                self.use_llm = True
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
                self.use_llm = False

    def generate_narrative(self, ticker: str, predictions: dict, top_5: bool, institutional_buy: bool) -> str:
        """
        Generate a human-readable summary combining ML predictions and institutional data.
        Falls back to rule-based generation if LLM fails or is unconfigured.
        """
        if self.use_llm:
            try:
                return self._generate_with_gemini(ticker, predictions, top_5, institutional_buy)
            except Exception as e:
                logger.error(f"LLM Generation failed: {e}. Falling back to rules.")
        
        return self._generate_with_rules(ticker, predictions, top_5, institutional_buy)

    def _generate_with_gemini(self, ticker: str, predictions: dict, top_5: bool, institutional_buy: bool) -> str:
        prompt = f"""
        你是台灣股市的資深量化分析師。請用繁體中文，針對股票 {ticker} 寫一段專業、簡潔 (約50字以內) 且易讀的投資建議評語。
        目前 AI 模型的預測數據為：
        - 未來1週預期報酬：{predictions.get('1W', 0) * 100:.2f}%
        - 未來2週預期報酬：{predictions.get('2W', 0) * 100:.2f}%
        - 是否排名全體前五大看漲標的：{'是' if top_5 else '否'}
        - 近3日三大法人籌碼狀態：{'買超(看多)' if institutional_buy else '賣超/無動作(中性或看空)'}
        
        請直接給出綜合評語，不需問候語，並依照上述數據指出這檔股票是否具有強勢動能。
        """
        response = self.model.generate_content(prompt)
        text = response.text.strip()
        return text

    def _generate_with_rules(self, ticker: str, predictions: dict, top_5: bool, institutional_buy: bool) -> str:
        pred_1w = predictions.get('1W', 0) * 100
        
        parts = []
        if pred_1w >= 2.0:
            parts.append(f"未來一週預期報酬達 +{pred_1w:.2f}%，表現強勢。")
        elif pred_1w < 0:
            parts.append(f"未來一週預期報酬為 {pred_1w:.2f}%，具下行風險。")
        else:
            parts.append(f"未來一週預期報酬為 +{pred_1w:.2f}%，處於盤整。")
            
        if institutional_buy:
            parts.append("且三大法人近期呈現連買，籌碼面動能穩健。")
        else:
            parts.append("惟三大法人未顯著買超，建議保守觀望。")
            
        if top_5:
            parts.append("目前為系統精選的前五大飆股潛力標的。")
            
        return " ".join(parts)

    def generate_range_narrative(self, ticker: str, start_date: str, end_date: str, pred_start: float, pred_end: float) -> str:
        """
        Generate a human-readable summary specifically for the requested date range.
        """
        if self.use_llm:
            try:
                prompt = f"""
                你是台灣股市的資深量化分析師。請用繁體中文，針對股票 {ticker} 寫一段專業、簡潔且易讀的投資建議評語 (約50字內)。
                目前 AI 模型預測該股票在您指定的期間表現如下：
                - {start_date} 預期累積報酬率為：{pred_start * 100:.2f}%
                - {end_date} 預期累積報酬率為：{pred_end * 100:.2f}%
                
                請直接給出綜合評語，不需問候語，並指出這段期間（{start_date} 到 {end_date}）該股票的動能趨勢與投資建議。
                """
                response = self.model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                logger.error(f"LLM Generation failed for date range: {e}. Falling back to rules.")
        
        # Rule-based fallback
        trend = "呈現上漲趨勢" if pred_end > pred_start else "呈現下跌趨勢"
        return f"根據模型預測，從 {start_date} 到 {end_date} 股票預期報酬將從 {pred_start*100:.2f}% 變動至 {pred_end*100:.2f}%，整體{trend}，建議投資人謹慎評估進場時機。"
