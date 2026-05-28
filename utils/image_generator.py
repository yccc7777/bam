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
        print("Downloading Noto Sans TC Regular...")
        urllib.request.urlretrieve(FONT_URL_REGULAR, FONT_PATH_REGULAR)
    if not os.path.exists(FONT_PATH_BOLD):
        print("Downloading Noto Sans TC Bold...")
        urllib.request.urlretrieve(FONT_URL_BOLD, FONT_PATH_BOLD)

def clean_text(text):
    # Strip emojis to prevent tofu boxes
    replacements = ['📊', '📈', '🔥', '🤖', '👨‍💼', '👨‍💻', '🦅', '🤡', '🎯', '💰', '💡', '🌅', '📰', '👍', '⚠️']
    for r in replacements:
        text = text.replace(r, '')
    return text.strip()

def summarize_text(txt, max_len=30):
    # Take only the first sentence and truncate if still too long
    if not txt: return "無"
    txt = txt.split('。')[0]
    if len(txt) > max_len:
        txt = txt[:max_len] + "..."
    else:
        txt = txt + "。" if not txt.endswith("。") else txt
    return txt

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

def draw_gauge(draw, cx, cy, radius, percentage, font, accent_color, bg_color):
    # Outline arc (0 to 180 degrees mapping to Pillow's 180 to 360)
    # Pillow angle: 0 is 3 o'clock, 90 is 6 o'clock. So top half is 180 to 360.
    bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
    draw.arc(bbox, start=180, end=360, fill="#E0E3E5", width=30)
    
    # Value arc
    end_angle = 180 + (percentage / 100.0) * 180
    draw.arc(bbox, start=180, end=end_angle, fill=accent_color, width=30)
    
    # Tick marks
    for deg in range(180, 361, 18):
        rad = math.radians(deg)
        x_start = cx + (radius - 35) * math.cos(rad)
        y_start = cy + (radius - 35) * math.sin(rad)
        x_end = cx + (radius + 10) * math.cos(rad)
        y_end = cy + (radius + 10) * math.sin(rad)
        draw.line([(x_start, y_start), (x_end, y_end)], fill="#CCCCCC", width=2)
        
    # Percentage text
    pct_str = f"{percentage:.1f}%"
    bbox_t = draw.textbbox((0,0), pct_str, font=font)
    tw = bbox_t[2] - bbox_t[0]
    th = bbox_t[3] - bbox_t[1]
    draw.text((cx - tw/2, cy - th - 5), pct_str, font=font, fill="#2C3E50")

def draw_grid_background(draw, width, height):
    # Light beige/gray background
    grid_color = "#E8EAEB"
    cross_color = "#B0B5B9"
    step = 60
    
    # Draw grid lines
    for x in range(0, width, step):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
    for y in range(0, height, step):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)
        
    # Draw crosshairs
    cross_size = 10
    for x in range(step*2, width, step*4):
        for y in range(step*2, height, step*4):
            draw.line([(x - cross_size, y), (x + cross_size, y)], fill=cross_color, width=1)
            draw.line([(x, y - cross_size), (x, y + cross_size)], fill=cross_color, width=1)

def generate_infographic(ticker: str, current_price: float, fundamentals: dict, predictions: dict, debate_result: dict, news_display: str = "") -> bytes:
    ensure_fonts()
    
    WIDTH = 1200
    HEIGHT = 900
    
    # Palette
    BG_COLOR = "#F4F6F7"
    BORDER_COLOR = "#2C3E50"
    TEXT_MAIN = "#1A1A1A"
    TEXT_SUB = "#5C6A79"
    ACCENT_GREEN = "#1E8449"
    
    img = Image.new('RGB', (WIDTH, HEIGHT), color=BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_grid_background(draw, WIDTH, HEIGHT)
    
    # Fonts
    try:
        f_title = ImageFont.truetype(FONT_PATH_BOLD, 42)
        f_box_title = ImageFont.truetype(FONT_PATH_REGULAR, 24)
        f_h1 = ImageFont.truetype(FONT_PATH_BOLD, 52)
        f_body = ImageFont.truetype(FONT_PATH_REGULAR, 18)
        f_small = ImageFont.truetype(FONT_PATH_REGULAR, 14)
    except:
        f_title = f_box_title = f_h1 = f_body = f_small = ImageFont.load_default()

    margin_x = 60
    margin_y = 60
    
    # --- Title Bar ---
    draw.text((margin_x, margin_y), f"{ticker} 深度評估與交易訊號", font=f_title, fill=TEXT_MAIN)
    draw.text((margin_x, margin_y + 60), "XGBoost + LSTM 雙引擎量化分析報告", font=f_box_title, fill=TEXT_SUB)
    
    # Top Row Layout (3 boxes)
    box_y = margin_y + 120
    box_w = 340
    box_h = 240
    gap = 30
    
    # BOX 1: Target
    bx1 = margin_x
    draw.rectangle([bx1, box_y, bx1 + box_w, box_y + box_h], outline=BORDER_COLOR, width=2)
    draw.text((bx1 + 20, box_y + 20), "監控標的", font=f_box_title, fill=TEXT_SUB)
    draw.text((bx1 + 20, box_y + 70), ticker, font=f_h1, fill=TEXT_MAIN)
    draw.text((bx1 + 20, box_y + 140), f"最新報價  ${current_price:.2f}", font=f_box_title, fill=TEXT_MAIN)
    
    # BOX 2: Win Rate
    bx2 = bx1 + box_w + gap
    draw.rectangle([bx2, box_y, bx2 + box_w, box_y + box_h], outline=BORDER_COLOR, width=2)
    draw.text((bx2 + 20, box_y + 20), "AI 預估上漲機率", font=f_box_title, fill=TEXT_SUB)
    
    # 1W Gauge on the left side
    win_rate = predictions.get('1W', 0) * 100
    gauge_cx = bx2 + 110
    gauge_cy = box_y + 170
    draw_gauge(draw, gauge_cx, gauge_cy, 70, win_rate, f_box_title, ACCENT_GREEN, BG_COLOR)
    draw.text((gauge_cx - 30, gauge_cy + 10), "1週預期", font=f_small, fill=TEXT_SUB)
    
    # Other predictions on the right side
    list_x = bx2 + 200
    list_y = box_y + 70
    preds_to_show = [
        ("2週預期", predictions.get('2W', 0)),
        ("3週預期", predictions.get('3W', 0)),
        ("1個月預期", predictions.get('1M', 0)),
        ("3個月預期", predictions.get('3M', 0)),
    ]
    for lbl, val in preds_to_show:
        draw.text((list_x, list_y), f"{lbl}:", font=f_small, fill=TEXT_SUB)
        draw.text((list_x + 75, list_y - 2), f"{val*100:.1f}%", font=f_body, fill=TEXT_MAIN)
        list_y += 35
    
    # BOX 3: Action
    bx3 = bx2 + box_w + gap
    draw.rectangle([bx3, box_y, bx3 + box_w, box_y + box_h], outline=BORDER_COLOR, width=2)
    draw.text((bx3 + 20, box_y + 20), "行動指引", font=f_box_title, fill=TEXT_SUB)
    
    action_text = summarize_text(clean_text(debate_result.get('final_action', '觀望')), 30)
    # Action Status Box
    btn_w = 260
    btn_h = 60
    btn_x = bx3 + (box_w - btn_w)//2
    btn_y = box_y + 70
    draw.rectangle([btn_x, btn_y, btn_x+btn_w, btn_y+btn_h], fill=ACCENT_GREEN)
    
    # Check if buy or sell for color (naive)
    status = "EXECUTE"
    draw.text((btn_x + 20, btn_y + 12), status, font=f_title, fill="#FFFFFF")
    
    act_lines = wrap_text(action_text, f_body, box_w - 40, draw)
    ay = btn_y + btn_h + 20
    for line in act_lines:
        draw.text((bx3 + 20, ay), line, font=f_body, fill=TEXT_MAIN)
        ay += 25
        
    # --- Middle Row (Fundamentals) ---
    my = box_y + box_h + gap
    draw.rectangle([bx1, my, bx1 + box_w, my + 140], outline=BORDER_COLOR, width=2)
    
    # Grid in fundamental box
    draw.line([(bx1, my+70), (bx1+box_w, my+70)], fill=BORDER_COLOR, width=1)
    draw.line([(bx1+box_w/2, my), (bx1+box_w/2, my+140)], fill=BORDER_COLOR, width=1)
    
    pe = fundamentals.get('PE', 'N/A')
    pb = fundamentals.get('PB', 'N/A')
    eps = fundamentals.get('EPS', 'N/A')
    yoy = fundamentals.get('YOY', 'N/A')
    
    draw.text((bx1 + 10, my + 10), "本益比 (PE)", font=f_small, fill=TEXT_SUB)
    draw.text((bx1 + 10, my + 30), str(pe), font=f_box_title, fill=TEXT_MAIN)
    draw.text((bx1 + box_w/2 + 10, my + 10), "股價淨值比 (PB)", font=f_small, fill=TEXT_SUB)
    draw.text((bx1 + box_w/2 + 10, my + 30), str(pb), font=f_box_title, fill=TEXT_MAIN)
    
    draw.text((bx1 + 10, my + 80), "每股盈餘 (EPS)", font=f_small, fill=TEXT_SUB)
    draw.text((bx1 + 10, my + 100), str(eps), font=f_box_title, fill=TEXT_MAIN)
    draw.text((bx1 + box_w/2 + 10, my + 80), "營收年增率 (YoY)", font=f_small, fill=TEXT_SUB)
    draw.text((bx1 + box_w/2 + 10, my + 100), str(yoy), font=f_box_title, fill=TEXT_MAIN)
    
    # AI Fundament Explanation
    ai_fund_expl = summarize_text(clean_text(debate_result.get('fundamental_explanation', '無')), 45)
    draw.rectangle([bx2, my, bx3+box_w, my + 140], outline=BORDER_COLOR, width=2)
    draw.text((bx2 + 20, my + 15), "AI 基本面解析", font=f_box_title, fill=ACCENT_GREEN)
    
    expl_lines = wrap_text(ai_fund_expl, f_body, (box_w*2 + gap) - 40, draw)
    ey = my + 50
    for line in expl_lines:
        draw.text((bx2 + 20, ey), line, font=f_body, fill=TEXT_MAIN)
        ey += 25
        
    # --- Bottom Row (Four Personas) ---
    by = my + 140 + gap
    draw.rectangle([bx1, by, bx3+box_w, by + 220], outline=BORDER_COLOR, width=2)
    draw.text((bx1 + 20, by + 15), "內部展望與外部籌碼共識", font=f_box_title, fill=TEXT_SUB)
    
    roles = [
        ("經理人 (法說會)", summarize_text(clean_text(debate_result.get('management', '')), 35)),
        ("分析師 (研究報告)", summarize_text(clean_text(debate_result.get('analyst', '')), 35)),
        ("外資 (籌碼面)", summarize_text(clean_text(debate_result.get('foreign', '')), 35)),
        ("散戶 (討論區)", summarize_text(clean_text(debate_result.get('retail', '')), 35))
    ]
    
    # 2x2 grid inside bottom row
    bw2 = (box_w*3 + gap*2) / 2
    draw.line([(bx1, by+120), (bx1+(box_w*3+gap*2), by+120)], fill="#D0D3D4", width=1)
    draw.line([(bx1+bw2, by), (bx1+bw2, by+220)], fill="#D0D3D4", width=1)
    
    positions = [
        (bx1 + 20, by + 50),
        (bx1 + bw2 + 20, by + 50),
        (bx1 + 20, by + 130),
        (bx1 + bw2 + 20, by + 130)
    ]
    
    for idx, (r_title, r_text) in enumerate(roles):
        px, py = positions[idx]
        draw.text((px, py), r_title, font=f_body, fill=ACCENT_GREEN)
        lines = wrap_text(r_text, f_small, bw2 - 40, draw)
        ly = py + 25
        for line in lines:
            draw.text((px, ly), line, font=f_small, fill=TEXT_MAIN)
            ly += 20
            
    # Save to bytes
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.getvalue()
