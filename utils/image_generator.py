import os
import io
import urllib.request
from PIL import Image, ImageDraw, ImageFont

# Define paths
FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'fonts')
FONT_PATH_REGULAR = os.path.join(FONT_DIR, 'NotoSansTC-Regular.ttf')
FONT_PATH_BOLD = os.path.join(FONT_DIR, 'NotoSansTC-Bold.ttf')

# Font download URLs (Google Fonts Noto Sans TC)
FONT_URL_REGULAR = "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf"
FONT_URL_BOLD = "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Bold.otf"

def ensure_fonts():
    os.makedirs(FONT_DIR, exist_ok=True)
    if not os.path.exists(FONT_PATH_REGULAR):
        print("Downloading Noto Sans TC Regular...")
        urllib.request.urlretrieve(FONT_URL_REGULAR, FONT_PATH_REGULAR)
    if not os.path.exists(FONT_PATH_BOLD):
        print("Downloading Noto Sans TC Bold...")
        urllib.request.urlretrieve(FONT_URL_BOLD, FONT_PATH_BOLD)

def clean_text_for_pillow(text):
    # Pillow struggles with emojis, so we strip them entirely to keep the layout clean
    replacements = {
        '📊': '', '📈': '', '🔥': '', '🤖': '', '👨‍💼': '', 
        '👨‍💻': '', '🦅': '', '🤡': '', '🎯': '',
        '💰': '', '💡': '', '🌅': '', '📰': '',
        '👍': '', '⚠️': ''
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.strip()

def wrap_text(text, font, max_width, draw):
    lines = []
    paragraphs = text.split('\n')
    for p in paragraphs:
        if not p:
            lines.append("")
            continue
        words = list(p)
        current_line = ""
        for word in words:
            test_line = current_line + word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
    return lines

def generate_infographic(ticker: str, current_price: float, fundamentals: dict, predictions: dict, debate_result: dict, news_display: str = "") -> bytes:
    ensure_fonts()
    
    # Image dimensions
    WIDTH = 800
    HEIGHT = 1200
    MARGIN = 40
    
    # Colors (Dark Theme)
    BG_COLOR = "#121212"
    TEXT_MAIN = "#FFFFFF"
    TEXT_SUB = "#AAAAAA"
    ACCENT_GREEN = "#00E676"
    ACCENT_RED = "#FF3D00"
    PANEL_BG = "#1E1E1E"
    
    img = Image.new('RGB', (WIDTH, HEIGHT), color=BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    try:
        font_title = ImageFont.truetype(FONT_PATH_BOLD, 36)
        font_subtitle = ImageFont.truetype(FONT_PATH_BOLD, 24)
        font_body = ImageFont.truetype(FONT_PATH_REGULAR, 20)
        font_small = ImageFont.truetype(FONT_PATH_REGULAR, 16)
    except Exception as e:
        print(f"Font loading error: {e}")
        font_title = ImageFont.load_default()
        font_subtitle = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_small = ImageFont.load_default()

    y_offset = MARGIN
    
    # --- Title ---
    title_text = f"{ticker} 深度評估報告 (XGBoost + LSTM)"
    title_text = clean_text_for_pillow(title_text)
    draw.text((MARGIN, y_offset), title_text, font=font_title, fill=TEXT_MAIN)
    y_offset += 60
    
    # --- Price ---
    price_text = f"最新收盤價：${current_price:.2f}"
    draw.text((MARGIN, y_offset), clean_text_for_pillow(price_text), font=font_subtitle, fill=ACCENT_GREEN)
    y_offset += 40
    
    # --- Divider ---
    draw.line([(MARGIN, y_offset), (WIDTH - MARGIN, y_offset)], fill=TEXT_SUB, width=1)
    y_offset += 20
    
    # --- Fundamentals Panel ---
    draw.rounded_rectangle([(MARGIN, y_offset), (WIDTH - MARGIN, y_offset + 160)], fill=PANEL_BG, radius=10)
    draw.text((MARGIN + 20, y_offset + 15), clean_text_for_pillow("基本面數據"), font=font_subtitle, fill=TEXT_MAIN)
    fund_str = f"本益比 (PE): {fundamentals.get('PE')}\n股價淨值比 (PB): {fundamentals.get('PB')}\n每股盈餘 (EPS): {fundamentals.get('EPS')}\n營收年增率 (YoY): {fundamentals.get('YOY')}"
    
    # Analysis from AI
    ai_fund_expl = debate_result.get('fundamental_explanation', '無')
    
    draw.text((MARGIN + 20, y_offset + 50), clean_text_for_pillow(fund_str), font=font_body, fill=TEXT_SUB)
    
    # Explain text wrapped
    expl_lines = wrap_text(clean_text_for_pillow(f"AI 解析：{ai_fund_expl}"), font_small, WIDTH - MARGIN*2 - 40, draw)
    expl_y = y_offset + 160 + 10
    for line in expl_lines:
        draw.text((MARGIN, expl_y), line, font=font_small, fill=ACCENT_GREEN)
        expl_y += 25
        
    y_offset = expl_y + 20
    
    # --- Predictions ---
    draw.text((MARGIN, y_offset), clean_text_for_pillow("AI 預估上漲機率"), font=font_subtitle, fill=TEXT_MAIN)
    y_offset += 35
    
    pred_texts = [
        f"1 週預期： {predictions.get('1W', 0)*100:.1f}%",
        f"1 個月預期：{predictions.get('1M', 0)*100:.1f}%",
        f"3 個月預期：{predictions.get('3M', 0)*100:.1f}%"
    ]
    for pt in pred_texts:
        draw.text((MARGIN + 20, y_offset), clean_text_for_pillow(pt), font=font_body, fill=TEXT_SUB)
        y_offset += 30
    y_offset += 10
    
    # --- AI Debate Panel ---
    draw.text((MARGIN, y_offset), clean_text_for_pillow("四大市場參與者實時觀點"), font=font_subtitle, fill=TEXT_MAIN)
    y_offset += 35
    
    roles = [
        ("經理人 (法說會)", debate_result.get('management', '')),
        ("分析師 (研究報告)", debate_result.get('analyst', '')),
        ("外資 (籌碼面)", debate_result.get('foreign', '')),
        ("散戶 (討論區)", debate_result.get('retail', ''))
    ]
    
    for r_title, r_text in roles:
        draw.text((MARGIN, y_offset), clean_text_for_pillow(r_title), font=font_body, fill=ACCENT_GREEN)
        y_offset += 30
        lines = wrap_text(clean_text_for_pillow(r_text), font_body, WIDTH - MARGIN*2, draw)
        for line in lines:
            draw.text((MARGIN + 20, y_offset), line, font=font_body, fill=TEXT_SUB)
            y_offset += 25
        y_offset += 10
        
    # --- Final Action ---
    draw.line([(MARGIN, y_offset), (WIDTH - MARGIN, y_offset)], fill=TEXT_SUB, width=1)
    y_offset += 20
    draw.text((MARGIN, y_offset), clean_text_for_pillow("AI 最終行動建議"), font=font_subtitle, fill=TEXT_MAIN)
    y_offset += 40
    
    final_lines = wrap_text(clean_text_for_pillow(debate_result.get('final_action', '')), font_title, WIDTH - MARGIN*2, draw)
    for line in final_lines:
        draw.text((MARGIN, y_offset), line, font=font_title, fill=ACCENT_RED)
        y_offset += 45
        
    # Crop to actual content height
    final_height = min(y_offset + MARGIN, HEIGHT)
    img = img.crop((0, 0, WIDTH, final_height))
    
    # Save to bytes
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.getvalue()
