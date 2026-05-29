import io
import os
import asyncio
import httpx
import base64
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageDraw, ImageFont
from concurrent.futures import ThreadPoolExecutor

# ================= CONFIGURATION =================
INFO_API_URL = "http://203.57.85.58:2035/player-info"
API_KEY = "@yashapis"
# =================================================

# ================= POSITIONS (from your tool) =================
CANVAS_WIDTH = 1850
CANVAS_HEIGHT = 800

POSITIONS = {
    "avatar": {"x": 191, "y": 131, "w": 490, "h": 510, "type": "image"},
    "banner": {"x": 665, "y": 136, "w": 1205, "h": 510, "type": "image"},
    "name_text": {"x": 671, "y": 233, "w": 1165, "h": 215, "type": "text"},
    "guild_text": {"x": 698, "y": 138, "w": 590, "h": 95, "type": "text"},
    "likes_text": {"x": 1558, "y": 516, "w": 220, "h": 65, "type": "text"},
    "level_text": {"x": 230, "y": 702, "w": 105, "h": 80, "type": "text"},
    "uid_text": {"x": 1520, "y": 718, "w": 295, "h": 45, "type": "text"},
    "watermark": {"x": 612, "y": 687, "w": 510, "h": 100, "type": "text"}
}

# ================= STYLE SETTINGS =================
TEXT_COLOR = (255, 215, 0)      # gold
STROKE_COLOR = (0, 0, 0)        # black stroke
WATERMARK_TEXT = "dev:XANAF LEGACY"
# ===================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await client.aclose()
    process_pool.shutdown()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE64 = "aHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L2doL1NoYWhHQ3JlYXRvci9pY29uQG1haW4vUE5H"
info_URL = base64.b64decode(BASE64).decode("utf-8")

FONT_FILE = "arial_unicode_bold.otf"
FONT_CHEROKEE = "NotoSansCherokee.ttf"

client = httpx.AsyncClient(
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=10.0,
    follow_redirects=True
)

process_pool = ThreadPoolExecutor(max_workers=4)

# ================= HELPERS =================
def load_unicode_font(size, font_file=FONT_FILE):
    try:
        font_path = os.path.join(os.path.dirname(__file__), font_file)
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
    except:
        pass
    return ImageFont.load_default()

async def fetch_image_bytes(item_id):
    if not item_id or str(item_id) == "0" or str(item_id) == "None":
        return None
    try:
        resp = await client.get(f"{info_URL}/{item_id}.png")
        if resp.status_code == 200:
            return resp.content
    except:
        pass
    return None

def bytes_to_image(img_bytes):
    if img_bytes:
        return Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    return Image.new("RGBA", (100, 100), (0, 0, 0, 0))

def is_cherokee(c):
    return 0x13A0 <= ord(c) <= 0x13FF or 0xAB70 <= ord(c) <= 0xABBF

def draw_text_with_stroke(draw, x, y, text, font_main, font_alt, stroke_width, text_color, stroke_color):
    if not text:
        return
    cx = x
    for ch in text:
        font = font_alt if is_cherokee(ch) else font_main
        for dx in range(-stroke_width, stroke_width + 1):
            for dy in range(-stroke_width, stroke_width + 1):
                draw.text((cx + dx, y + dy), ch, font=font, fill=stroke_color)
        draw.text((cx, y), ch, font=font, fill=text_color)
        cx += font.getlength(ch)

def wrap_text(text, font, max_width, draw):
    """Text wrap function for long text"""
    if not text:
        return []
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    if current_line:
        lines.append(' '.join(current_line))
    return lines if lines else [text]

# ================= BANNER GENERATION =================
def process_xanaf_banner(data, avatar_bytes, banner_bytes, template_bytes):
    # Load template background (your designed frame)
    template = bytes_to_image(template_bytes)
    
    # Resize template to fixed canvas size
    if template.size != (CANVAS_WIDTH, CANVAS_HEIGHT):
        template = template.resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.LANCZOS)
    
    final = template.copy()
    draw = ImageDraw.Draw(final)
    
    # Extract data
    level = str(data.get("level") or "0")
    name = str(data.get("name") or "Unknown")
    guild = data.get("guild") or ""
    likes = data.get("likes", 0)
    uid = str(data.get("uid") or "")
    
    # Load and paste avatar (circular)
    if avatar_bytes:
        avatar_img = bytes_to_image(avatar_bytes)
        pos = POSITIONS["avatar"]
        avatar_img = avatar_img.resize((pos["w"], pos["h"]), Image.LANCZOS)
        # Make circular avatar
        mask = Image.new("L", (pos["w"], pos["h"]), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, pos["w"], pos["h"]), fill=255)
        final.paste(avatar_img, (pos["x"], pos["y"]), mask)
    
    # Load and paste banner image
    if banner_bytes:
        banner_img = bytes_to_image(banner_bytes)
        pos = POSITIONS["banner"]
        banner_img = banner_img.resize((pos["w"], pos["h"]), Image.LANCZOS)
        final.paste(banner_img, (pos["x"], pos["y"]))
    
    # Fonts
    name_font = load_unicode_font(70)
    name_font_c = load_unicode_font(70, FONT_CHEROKEE)
    guild_font = load_unicode_font(50)
    guild_font_c = load_unicode_font(50, FONT_CHEROKEE)
    likes_font = load_unicode_font(55)
    level_font = load_unicode_font(60)
    uid_font = load_unicode_font(35)
    watermark_font = load_unicode_font(45)
    
    # Draw name
    name_pos = POSITIONS["name_text"]
    wrapped_name = wrap_text(name, name_font, name_pos["w"] - 20, draw)
    name_y = name_pos["y"] + 20
    for line in wrapped_name:
        draw_text_with_stroke(draw, name_pos["x"] + 20, name_y, line, 
                              name_font, name_font_c, 3, TEXT_COLOR, STROKE_COLOR)
        name_y += name_font.size + 5
    
    # Draw guild
    if guild:
        guild_pos = POSITIONS["guild_text"]
        wrapped_guild = wrap_text(guild, guild_font, guild_pos["w"] - 20, draw)
        guild_y = guild_pos["y"] + 15
        for line in wrapped_guild:
            draw_text_with_stroke(draw, guild_pos["x"] + 15, guild_y, line,
                                  guild_font, guild_font_c, 2, TEXT_COLOR, STROKE_COLOR)
            guild_y += guild_font.size + 3
    
    # Draw likes (large number)
    if likes > 0:
        likes_pos = POSITIONS["likes_text"]
        like_text = str(likes)
        bbox = draw.textbbox((0, 0), like_text, font=likes_font)
        text_w = bbox[2] - bbox[0]
        like_x = likes_pos["x"] + (likes_pos["w"] - text_w) // 2
        like_y = likes_pos["y"] + (likes_pos["h"] - likes_font.size) // 2
        draw.text((like_x, like_y), like_text, font=likes_font, fill=TEXT_COLOR)
    
    # Draw level
    level_pos = POSITIONS["level_text"]
    level_text = f"Lv.{level}"
    bbox = draw.textbbox((0, 0), level_text, font=level_font)
    text_w = bbox[2] - bbox[0]
    level_x = level_pos["x"] + (level_pos["w"] - text_w) // 2
    level_y = level_pos["y"] + (level_pos["h"] - level_font.size) // 2
    draw.text((level_x, level_y), level_text, font=level_font, fill=TEXT_COLOR)
    
    # Draw UID
    if uid:
        uid_pos = POSITIONS["uid_text"]
        uid_text = f"UID: {uid}"
        bbox = draw.textbbox((0, 0), uid_text, font=uid_font)
        text_w = bbox[2] - bbox[0]
        uid_x = uid_pos["x"] + (uid_pos["w"] - text_w) // 2
        uid_y = uid_pos["y"] + (uid_pos["h"] - uid_font.size) // 2
        draw.text((uid_x, uid_y), uid_text, font=uid_font, fill=(200, 200, 200))
    
    # Draw watermark
    watermark_pos = POSITIONS["watermark"]
    bbox = draw.textbbox((0, 0), WATERMARK_TEXT, font=watermark_font)
    text_w = bbox[2] - bbox[0]
    wm_x = watermark_pos["x"] + (watermark_pos["w"] - text_w) // 2
    wm_y = watermark_pos["y"] + (watermark_pos["h"] - watermark_font.size) // 2
    draw.text((wm_x, wm_y), WATERMARK_TEXT, font=watermark_font, fill=(255, 215, 0, 200))
    
    out = io.BytesIO()
    final.save(out, "PNG")
    out.seek(0)
    return out

# ================= ENDPOINT =================
@app.get("/")
async def home():
    return {"status": "XANAF LEGACY Banner API", "endpoint": "/xanaf?uid=UID"}

@app.get("/xanaf")
async def get_xanaf_banner(uid: str):
    url = f"{INFO_API_URL}?uid={uid}&key={API_KEY}"
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            raise HTTPException(502, f"Info API returned {resp.status_code}")
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch player info: {str(e)}")
    
    data = resp.json()
    
    basic_info = data.get("basicInfo") or {}
    clan_info = data.get("clanBasicInfo") or {}
    
    name = basic_info.get("nickname")
    level = basic_info.get("level")
    guild = clan_info.get("clanName")
    avatar_id = basic_info.get("headPic")
    banner_id = basic_info.get("bannerId")
    likes = basic_info.get("liked") or 0
    
    if not name:
        raise HTTPException(404, "Account not found or invalid response from info API")
    
    try:
        likes = int(likes)
    except:
        likes = 0
    
    # Fetch images
    avatar, banner = await asyncio.gather(
        fetch_image_bytes(avatar_id),
        fetch_image_bytes(banner_id),
    )
    
    # Use your designed background image
    # IMPORTANT: Save your background as "xanaflegacy.png" in the same folder
    template_path = os.path.join(os.path.dirname(__file__), "xanaflegacy.png")
    if os.path.exists(template_path):
        with open(template_path, "rb") as f:
            template_bytes = f.read()
    else:
        # Fallback: create blank canvas
        template = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (20, 20, 40, 255))
        img_byte_arr = io.BytesIO()
        template.save(img_byte_arr, format="PNG")
        template_bytes = img_byte_arr.getvalue()
    
    player_data = {
        "level": level,
        "name": name,
        "guild": guild,
        "likes": likes,
        "uid": uid
    }
    
    img = await asyncio.get_event_loop().run_in_executor(
        process_pool,
        process_xanaf_banner,
        player_data,
        avatar, banner, template_bytes
    )
    
    return Response(img.getvalue(), media_type="image/png")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)