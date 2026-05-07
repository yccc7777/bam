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
            # 優先使用 gemini-1.5-flash
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            self.use_llm = True
        except Exception as e:
            logger.error(f"Failed to initialize Gemini for debate: {e}")

    def run_debate(self, ticker: str, predictions: dict, news_context: str = "") -> dict:
        """
        執行多智能體辯論流程，回傳 dict 包含各個 agent 的觀點
        """
        if not self.use_llm:
            return {
                "tech_view": "無法連線至 AI 模型。",
                "fund_view": f"無法連線至 AI 模型。新聞參考：\n{news_context}",
                "risk_view": "無法連線至 AI 模型。",
                "pm_view": "無法給出最終結論。",
                "review_view": "無",
                "final_action": "無"
            }
            
        try:
            pred_str = ", ".join([f"{k}: {v*100:+.2f}%" for k, v in predictions.items()])
            
            # 1. 技術面分析師
            tech_prompt = f"你是「技術面分析師」。\n正在分析股票：{ticker}\nAI 模型預測未來一週報酬率為：{pred_str}\n請用「給股市新手聽的超簡單白話文」(50字以內)，說明現在的股價走勢是強是弱？適合買進還是賣出？"
            tech_view = self.model.generate_content(tech_prompt).text.strip()
            
            # 2. 基本面分析師 (財報分析)
            fund_prompt = f"你是「基本面分析師」。\n正在分析股票：{ticker}\n這是最近的市場新聞：\n{news_context}\n請根據這些新聞與你的知識庫，用「給股市新手聽的超簡單白話文」(50字以內)，說明這家公司最近有什麼利多或利空？未來有沒有前景？"
            fund_view = self.model.generate_content(fund_prompt).text.strip()
            
            # 3. 風險控管員
            risk_prompt = f"你是專門找碴的「風險控管員」。\n正在分析股票：{ticker}\n技術面看：{tech_view}\n基本面看：{fund_view}\n請用「給股市新手聽的超簡單白話文」(50字以內)，用力吐槽上述觀點，指出現在進場可能會遇到什麼倒楣事或風險？"
            risk_view = self.model.generate_content(risk_prompt).text.strip()
            
            # 4. 首席經理人決策 (包含動態資產配置)
            pm_prompt = f"你是發號施令的「首席基金經理人」。\n正在評估股票：{ticker}\n技術面：{tech_view}\n基本面：{fund_view}\n風險：{risk_view}\n請綜合以上觀點，給出最終決策。\n請用「超直白的口吻」回答：\n1. 評級：【強烈買進 / 觀望 / 賣出】(擇一)\n2. 決策理由：綜合評估後的結論 (約 50 字)。\n3. 動態資產配置：建議投入多少資金比例 (0% ~ 100%)，為什麼？"
            pm_view = self.model.generate_content(pm_prompt).text.strip()
            
            # 5. 覆核稽核員 (敗因反思)
            review_prompt = f"你是負責事後諸葛的「覆核稽核員」。\n針對股票：{ticker}，經理人的決策是：\n{pm_view}\n請用白話文推演：如果聽了他的話最後卻賠錢了，最可能發生的 2 個意外是什麼？(50字以內)。"
            review_view = self.model.generate_content(review_prompt).text.strip()
            
            # 6. 最終一句話總結
            final_action_prompt = f"根據首席經理人的決策：\n{pm_view}\n請用「一句超級直白的話 (20字以內)」告訴新手到底該怎麼做（例如：強力買進，拿 30% 的錢去試水溫）。"
            final_action = self.model.generate_content(final_action_prompt).text.strip()
            
            return {
                "tech_view": tech_view,
                "fund_view": fund_view,
                "risk_view": risk_view,
                "pm_view": pm_view,
                "review_view": review_view,
                "final_action": final_action
            }
            
        except Exception as e:
            logger.error(f"Error during agent debate: {e}. Falling back to rule-based simulated debate.")
            
            # Rule-based fallback for Demo purposes if API fails or quota exceeded
            pred_1w = predictions.get('1W', 0) * 100
            
            # Simple summary of news if available
            news_hint = "\n(即時新聞參考：無)"
            if news_context and news_context != "無最新新聞。":
                # Only take the first title to keep it short in fallback
                first_news_title = news_context.split("標題：")[1].split("\n")[0] if "標題：" in news_context else ""
                news_hint = f"\n(即時新聞參考：{first_news_title})"

            if pred_1w >= 2.0:
                tech_mock = f"現在線型看起來超棒，是一波明顯的上漲趨勢！AI 預測下週還會漲 +{pred_1w:.2f}%，現在上車勝率很高喔！"
                fund_mock = f"{ticker} 最近營收表現很好，而且很多大老闆跟外資都在偷偷買進，公司未來賺錢的機會很大。{news_hint}"
                risk_mock = "別高興得太早！現在股價已經漲很多了，小心一買就遇到別人獲利了結倒貨，加上最近美國新聞多，隨時可能大跌。"
                pm_mock = "1. 評級：【強烈買進】\n2. 決策理由：不管從線圖還是公司賺錢能力來看，現在都是難得的好買點！\n3. 動態資產配置：建議拿 30% 的閒錢來買。因為短線有點熱，留點錢等跌了再買。"
                review_mock = "1. 財報其實是騙人的，下個月突然業績爛掉。\n2. 遇到國際大事件，大家恐慌拋售跟著遭殃。"
                final_action_mock = "💡 最終建議：看好會漲！建議拿 30% 的錢勇敢買進。"
            elif pred_1w < 0:
                tech_mock = f"現在線型看起來很糟，趨勢一路往下走。AI 預測下週還會跌 {pred_1w:.2f}%，上面一堆人等著賣，千萬別碰！"
                fund_mock = f"{ticker} 最近生意不好，庫存太多賣不出去，很多專家都下修了這家公司未來的賺錢預期。{news_hint}"
                risk_mock = "現在買根本是接刀子！整個產業都在衰退，外資每天都在狂賣，現在進場只會變成韭菜。"
                pm_mock = "1. 評級：【賣出】\n2. 決策理由：各方面看起來都很慘，完全沒有上漲的理由，趕快逃命要緊。\n3. 動態資產配置：建議配置 0%。風險太高了，乖乖把錢留在身上最安全。"
                review_mock = "1. 公司突然宣布要花大錢買回自己的股票，導致股價飆漲。\n2. 對手公司突然倒閉，訂單全跑過來大賺一波。"
                final_action_mock = "💡 最終建議：千萬別買！一毛錢都不要投進去。"
            else:
                tech_mock = f"現在股價卡在中間不上不下，沒有明顯的方向。AI 預測下週只有微幅波動 +{pred_1w:.2f}%，大家都在觀望。"
                fund_mock = f"{ticker} 表現普普通通，沒有特別好也沒有特別壞。現在是產業淡季，沒什麼賺錢的新消息。{news_hint}"
                risk_mock = "這種死魚盤最怕的就是沒耐心！資金很容易被卡住，如果突然有壞消息，可能連跑都來不及跑。"
                pm_mock = "1. 評級：【觀望】\n2. 決策理由：現在買進的贏面不大，把錢卡在這裡很不划算，建議等方向出來再說。\n3. 動態資產配置：建議配置 5%~10%。真的很想玩的話，只能拿一點點錢玩短線。"
                review_mock = "1. 沒發現主力早就偷偷在買，結果突然連拉好幾根漲停板。\n2. 盤太久沒人要玩，最後大家沒耐心一起殺出大跌。"
                final_action_mock = "💡 最終建議：方向不明，最多只拿 10% 的錢玩玩就好。"

            return {
                "tech_view": tech_mock,
                "fund_view": fund_mock,
                "risk_view": risk_mock,
                "pm_view": pm_mock,
                "review_view": review_mock,
                "final_action": final_action_mock
            }

    def run_daily_review(self, ticker: str, morning_pm_view: str, morning_price: float, actual_close: float) -> str:
        """
        AI 自我反思與檢討
        """
        if not self.use_llm:
            diff = actual_close - morning_price
            return f"今日收盤價 {actual_close:.2f} (早盤 {morning_price:.2f})。模型模擬檢討：若早盤看多且今日上漲，則策略成功；反之則需重新檢視數據。"
            
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
            diff = actual_close - morning_price
            return f"今日收盤價 {actual_close:.2f} (早盤 {morning_price:.2f})。模型模擬檢討：若早盤看多且今日上漲，則策略成功；反之則需重新檢視數據。"
