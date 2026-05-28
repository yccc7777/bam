import os
import io
import math
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
        urllib.request.urlretrieve(FONT_URL_REGULAR, FONT_PATH_REGULAR)
    if not os.path.exists(FONT_PATH_BOLD):
        urllib.request.urlretrieve(FONT_URL_BOLD, FONT_PATH_BOLD)

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
    
    WIDTH = 800
    HEIGHT = 500
    
    # Palette (Dark Trading Terminal Theme)
    BG_COLOR = "#0D1117"
    PANEL_BG = "#161B22"
    BORDER_COLOR = "#30363D"
    TEXT_MAIN = "#C9D1D9"
    TEXT_SUB = "#8B949E"
    TEXT_WHITE = "#FFFFFF"
    
    # Fonts
    try:
        f_ticker = ImageFont.truetype(FONT_PATH_BOLD, 52)
        f_price = ImageFont.truetype(FONT_PATH_REGULAR, 40)
        f_signal = ImageFont.truetype(FONT_PATH_BOLD, 48)
        f_huge = ImageFont.truetype(FONT_PATH_BOLD, 80)
        f_h2 = ImageFont.truetype(FONT_PATH_BOLD, 28)
        f_body = ImageFont.truetype(FONT_PATH_REGULAR, 24)
        f_small = ImageFont.truetype(FONT_PATH_REGULAR, 18)
    except:
        f_ticker = f_price = f_signal = f_huge = f_h2 = f_body = f_small = ImageFont.load_default()

    img = Image.new('RGB', (WIDTH, HEIGHT), color=BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    # Determine Signal Colors
    action_text = debate_result.get('final_action', '觀望')
    signal_color = "#D29922" # Yellow
    signal_word = "HOLD"
    if any(k in action_text for k in ["買", "加碼", "多"]):
        signal_color = "#238636" # Green
        signal_word = "BUY"
        if any(k in action_text for k in ["強烈", "積極"]):
            signal_word = "STRONG BUY"
    elif any(k in action_text for k in ["賣", "減碼", "空"]):
        signal_color = "#DA3633" # Red
        signal_word = "SELL"
        if any(k in action_text for k in ["強烈", "積極"]):
            signal_word = "STRONG SELL"

    # --- Header (Ticker, Price, Signal) ---
    draw.text((40, 40), ticker, font=f_ticker, fill=TEXT_MAIN)
    
    bbox_t = draw.textbbox((0,0), ticker, font=f_ticker)
    ticker_w = bbox_t[2] - bbox_t[0]
    draw.text((40 + ticker_w + 20, 50), f"${current_price:.2f}", font=f_price, fill=TEXT_SUB)
    
    # Signal Badge (Right Aligned)
    bbox_s = draw.textbbox((0,0), signal_word, font=f_signal)
    sw = bbox_s[2] - bbox_s[0]
    sh = bbox_s[3] - bbox_s[1]
    bx, by, bw, bh = WIDTH - 40 - sw - 60, 40, sw + 60, sh + 30
    draw.rounded_rectangle([bx, by, bx+bw, by+bh], fill=signal_color, radius=10)
    draw.text((bx + 30, by + 10), signal_word, font=f_signal, fill=TEXT_WHITE)

    # --- Divider ---
    draw.line([(40, 130), (WIDTH - 40, 130)], fill=BORDER_COLOR, width=2)
    
    # --- Middle Section (Win Rate + Fundamentals) ---
    win_rate = predictions.get('1W', 0) * 100
    
    # Win Rate Panel (Left)
    draw.text((40, 160), "1週 AI 預估勝率", font=f_h2, fill=TEXT_SUB)
    draw.text((40, 200), f"{win_rate:.1f}%", font=f_huge, fill=signal_color)
    
    # Other Predictions Panel (Right)
    fx = 420
    draw.rounded_rectangle([fx, 160, WIDTH-40, 340], fill=PANEL_BG, outline=BORDER_COLOR, width=2, radius=12)
    
    draw.text((fx + 20, 180), "2週預期", font=f_small, fill=TEXT_SUB)
    draw.text((fx + 20, 210), f"{predictions.get('2W', 0)*100:.1f}%", font=f_h2, fill=TEXT_MAIN)
    
    draw.text((fx + 180, 180), "3週預期", font=f_small, fill=TEXT_SUB)
    draw.text((fx + 180, 210), f"{predictions.get('3W', 0)*100:.1f}%", font=f_h2, fill=TEXT_MAIN)
    
    draw.text((fx + 20, 260), "1個月預期", font=f_small, fill=TEXT_SUB)
    draw.text((fx + 20, 290), f"{predictions.get('1M', 0)*100:.1f}%", font=f_h2, fill=TEXT_MAIN)
    
    draw.text((fx + 180, 260), "3個月預期", font=f_small, fill=TEXT_SUB)
    draw.text((fx + 180, 290), f"{predictions.get('3M', 0)*100:.1f}%", font=f_h2, fill=TEXT_MAIN)

    # --- Footer Banner (Action Text) ---
    clean_action = action_text.split('。')[0]
    for r in ['📊', '📈', '🔥', '🤖', '🎯', '💡']:
        clean_action = clean_action.replace(r, '')
        
    draw.rounded_rectangle([40, 380, WIDTH-40, 460], fill=PANEL_BG, outline=signal_color, width=2, radius=8)
    
    lines = wrap_text(clean_action.strip(), f_body, WIDTH - 120, draw)
    # Just draw max 2 lines
    text_y = 395
    for i, line in enumerate(lines[:2]):
        draw.text((60, text_y), line, font=f_body, fill=TEXT_WHITE)
        text_y += 30

    # Save to bytes
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.getvalue()
