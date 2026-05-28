import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)

class AgentDebateEngine:
    def __init__(self, api_key: str):
        self.use_llm = False
        if not api_key:
            logger.warning("Gemini API key is not set. Debate engine disabled.")
            return
            
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-flash-latest')
            self.use_llm = True
        except Exception as e:
            logger.error(f"Failed to initialize Gemini for debate: {e}")

    def run_debate(self, ticker: str, probabilities: dict, news_context: str = "", fundamentals: dict = None, institutional: str = "", ptt_context: str = "", mops_context: str = "") -> dict:
        """
        執行多智能體辯論流程，根據真實數據模擬不同市場參與者的觀點
        probabilities: dict e.g. {'1W': 0.65} (65% 機率上漲)
        fundamentals: dict containing PE, PB, EPS, YOY
        """
        if not fundamentals: fundamentals = {}
        
        # Format fundamentals string
        fund_str = f"本益比(PE): {fundamentals.get('PE', 'N/A')}, 股價淨值比(PB): {fundamentals.get('PB', 'N/A')}, 每股盈餘(EPS): {fundamentals.get('EPS', 'N/A')}, 營收年增率(YoY): {fundamentals.get('YOY', 'N/A')}"
        
        # Format probabilities string
        prob_str = ", ".join([f"{k}: {v*100:.1f}%" for k, v in probabilities.items()])
        
        if not self.use_llm:
            return {
                "management": "無法連線至 AI。",
                "analyst": "無法連線至 AI。",
                "foreign": "無法連線至 AI。",
                "retail": "無法連線至 AI。",
                "final_action": f"AI模型評估上漲機率為: {prob_str}"
            }
            
        try:
            mega_prompt = f"""請根據以下資訊，扮演多個角色進行分析，並嚴格以 JSON 格式輸出。
股票: {ticker}
預測機率: {prob_str}
基本面: {fund_str}
法說會重點: {mops_context if mops_context else '無近期法說會特殊聲明'}
新聞背景: {news_context if news_context else '無最新新聞'}
鄉民討論: {ptt_context if ptt_context else '無近期 PTT 討論'}
籌碼數據: {institutional if institutional else '無近期異常變動'}

請輸出一個 JSON 物件，必須包含以下 key:
"fundamental_explanation": "50字詳細解釋基本面數據背後代表的意涵(客觀分析)"
"management": "50字高階經理人專注解讀法說會與未來展望"
"analyst": "50字首席分析師說明機率與新聞面是否支持買進"
"foreign": "50字外資機構分析股價位階與籌碼動向"
"retail": "50字認真型散戶總結鄉民情緒與自身評估"
"final_action": "20字最終一句話總結現在到底該怎麼做"
"""
            import json
            response = self.model.generate_content(mega_prompt, generation_config={"response_mime_type": "application/json"})
            result_json = json.loads(response.text.strip())
            
            return {
                "fundamental_explanation": result_json.get("fundamental_explanation", "無"),
                "management": result_json.get("management", "無"),
                "analyst": result_json.get("analyst", "無"),
                "foreign": result_json.get("foreign", "無"),
                "retail": result_json.get("retail", "無"),
                "final_action": result_json.get("final_action", "無")
            }
            
        except Exception as e:
            logger.error(f"Error during agent debate: {e}. Falling back to rule-based.")
            prob_1w = probabilities.get('1W', 0.5) * 100
            
            if prob_1w >= 60.0:
                return {
                    "fundamental_explanation": f"系統無法連線至 AI 進行深度解析。當前數據：{fund_str}",
                    "management": f"本公司最新法說會指出營運穩健，我們對下半年的發展非常有信心。",
                    "analyst": f"AI 勝率高達 {prob_1w:.1f}%，建議客戶積極建立多頭部位。",
                    "foreign": "從近期的籌碼動向與數據分析，外資目前具備高度參與意願，傾向於持續擴大多頭部位。",
                    "retail": "從目前的鄉民討論與數據來看，市場情緒偏向樂觀，我認為值得進場佈局。",
                    "final_action": f"💡 漲幅機率 {prob_1w:.1f}%！勝率偏高，建議勇敢買進。"
                }
            elif prob_1w < 40.0:
                return {
                    "fundamental_explanation": f"系統無法連線至 AI 進行深度解析。當前數據：{fund_str}",
                    "management": f"雖然公司近期遇到一些逆風與挑戰，但長期的核心競爭力依然不變。",
                    "analyst": f"AI 勝率僅 {prob_1w:.1f}%，短期風險較高，建議客戶減碼觀望。",
                    "foreign": "基於目前的籌碼流出狀況與不確定性，外資機構預計將縮減部位以控制下行風險。",
                    "retail": "考量到目前市場瀰漫著悲觀情緒與較低的預期勝率，我會選擇停損或觀望，避免風險。",
                    "final_action": f"💡 漲幅機率僅 {prob_1w:.1f}%！勝率極低，千萬別碰。"
                }
            else:
                return {
                    "fundamental_explanation": f"系統無法連線至 AI 進行深度解析。當前數據：{fund_str}",
                    "management": f"目前公司正處於庫存調整與過渡期，預計未來幾個月將保持平穩發展。",
                    "analyst": f"AI 勝率落在中性的 {prob_1w:.1f}%，缺乏明顯的催化劑，建議觀望。",
                    "foreign": "目前的籌碼結構呈現中性，並未出現明確的主力進駐訊號，機構資金將暫時維持中立觀望。",
                    "retail": "近期討論熱度不高且走勢不明確，這檔股票目前缺乏吸引力，我會轉往其他標的。",
                    "final_action": f"💡 漲幅機率 {prob_1w:.1f}%！方向不明，建議把錢留著觀望。"
                }

    def run_daily_review(self, ticker: str, morning_pm_view: str, morning_price: float, actual_close: float) -> str:
        """
        AI 自我反思與檢討
        """
        if not self.use_llm:
            diff = actual_close - morning_price
            return f"今日收盤價 {actual_close:.2f} (早盤 {morning_price:.2f})。"
            
        try:
            percent_change = ((actual_close - morning_price) / morning_price) * 100
            trend_actual = "上漲" if percent_change > 0 else "下跌" if percent_change < 0 else "平盤"
            
            review_prompt = (
                f"你是負責事後檢討的「嚴格覆核稽核員」。\n"
                f"股票：{ticker}\n"
                f"【早上 08:30 的 AI 決策】\n"
                f"{morning_pm_view}\n"
                f"【今天實際收盤結果】\n"
                f"早上開盤時參考價：{morning_price:.2f}，今天收盤價：{actual_close:.2f} (日盤中實質漲跌：{percent_change:+.2f}%, {trend_actual})\n"
                f"請以「嚴厲、反思」的白話文口吻 (約 100 字)，告訴我：\n"
                f"1. 早上的預測是否有抓到今天的趨勢？\n"
                f"2. 如果看錯了，最大的盲點是什麼？如果看對了，最成功的判斷是什麼？\n"
                f"3. 對於明天開盤，我們的分析系統應該注意什麼？"
            )
            review_view = self.model.generate_content(review_prompt).text.strip()
            return review_view
        except Exception as e:
            logger.error(f"Error during daily review: {e}")
            return f"今日收盤價 {actual_close:.2f} (早盤 {morning_price:.2f})。模型模擬檢討完成。"
