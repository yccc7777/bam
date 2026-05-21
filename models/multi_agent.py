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
            self.model = genai.GenerativeModel('gemini-2.5-flash')
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
            # 1. 經理人 (法說會視角)
            mgt_prompt = f"你是這家公司({ticker})的「高階經理人」。\n正在法說會上發言。\n這是公司最新的基本面數據：{fund_str}。\n這是我們在公開資訊觀測站(MOPS)上最新公告的法說會重點摘要：\n{mops_context if mops_context else '無近期法說會特殊聲明'}\n請用「給股東聽的自信與專業口吻」(50字以內)，解讀這些數據或法說會內容，並給出未來的展望。"
            management_view = self.model.generate_content(mgt_prompt).text.strip()
            
            # 2. 分析師 (外資/投顧研究報告)
            analyst_prompt = f"你是頂尖投顧的「首席分析師」。\n正在寫({ticker})的研究報告。\nAI 模型(XGBoost+LSTM)預測未來上漲機率為：{prob_str}。\n新聞背景：\n{news_context}\n請用「給客戶看的專業但易懂的分析口吻」(50字以內)，說明現在的機率與新聞面是否支持買進？"
            analyst_view = self.model.generate_content(analyst_prompt).text.strip()
            
            # 3. 外資 (市場主力籌碼)
            foreign_prompt = f"你是操盤百億資金的「專業外資機構經理人」。\n正在盯盤({ticker})。\n目前的真實籌碼數據(證交所三大法人買賣超)：\n{institutional if institutional else '無近期異常變動'}。\n請根據這些真實籌碼數據，用「專業、客觀且嚴謹的機構法人分析口吻」(50字以內)，分析目前的股價位階與籌碼動向，說明機構目前的資金配置傾向（加碼或減碼）？"
            foreign_view = self.model.generate_content(foreign_prompt).text.strip()
            
            # 4. 散戶 (PTT 鄉民)
            retail_prompt = f"你是關注 PTT 股票版(Stock) 討論的「認真型散戶投資人」。\n正在評估股票：{ticker}\n這是最近 PTT 股票版上鄉民的真實推文與討論：\n{ptt_context if ptt_context else '無近期 PTT 討論'}\n經理人說：{management_view}\n分析師說：{analyst_view}\n請閱讀上述 PTT 真實討論後，用「認真且直白、不使用網路酸民梗的散戶分析口吻」(50字以內)，表達你總結了鄉民情緒與自身評估後的心情，你會選擇進場還是觀望？"
            retail_view = self.model.generate_content(retail_prompt).text.strip()
            
            # 5. 最終一句話總結 (評分系統轉換)
            final_action_prompt = f"根據上述四大市場參與者的觀點，以及 AI 給出的勝率：{prob_str}\n請用「一句超級直白的話 (20字以內)」告訴新手現在到底該怎麼做？"
            final_action = self.model.generate_content(final_action_prompt).text.strip()
            
            return {
                "management": management_view,
                "analyst": analyst_view,
                "foreign": foreign_view,
                "retail": retail_view,
                "final_action": final_action
            }
            
        except Exception as e:
            logger.error(f"Error during agent debate: {e}. Falling back to rule-based.")
            prob_1w = probabilities.get('1W', 0.5) * 100
            
            if prob_1w >= 60.0:
                return {
                    "management": f"本公司基本面穩健 ({fund_str})，我們對下半年的營收非常有信心。",
                    "analyst": f"AI 勝率高達 {prob_1w:.1f}%，建議客戶積極建立多頭部位。",
                    "foreign": "從近期的籌碼動向與數據分析，外資目前具備高度參與意願，傾向於持續擴大多頭部位。",
                    "retail": "從目前的鄉民討論與數據來看，市場情緒偏向樂觀，我認為值得進場佈局。",
                    "final_action": f"💡 漲幅機率 {prob_1w:.1f}%！勝率偏高，建議勇敢買進。"
                }
            elif prob_1w < 40.0:
                return {
                    "management": f"雖然近期遇到一些逆風 ({fund_str})，但公司長期核心競爭力不變。",
                    "analyst": f"AI 勝率僅 {prob_1w:.1f}%，短期風險較高，建議客戶減碼觀望。",
                    "foreign": "基於目前的籌碼流出狀況與不確定性，外資機構預計將縮減部位以控制下行風險。",
                    "retail": "考量到目前市場瀰漫著悲觀情緒與較低的預期勝率，我會選擇停損或觀望，避免風險。",
                    "final_action": f"💡 漲幅機率僅 {prob_1w:.1f}%！勝率極低，千萬別碰。"
                }
            else:
                return {
                    "management": f"目前處於庫存調整期 ({fund_str})，未來幾個月將保持平穩。",
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
