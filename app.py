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

# ================= CONFIG =================
INFO_API_URL = "http://203.57.85.58:2035/player-info"
API_KEY = "@BISHALAPI"

CANVAS_WIDTH = 1850
CANVAS_HEIGHT = 800

TEXT_COLOR = (255, 215, 0)
STROKE_COLOR = (0, 0, 0)
WATERMARK_TEXT = "BY-BISHAL"

# ================= POSITIONS =================
POSITIONS = {
    "avatar": {"x": 191, "y": 131, "w": 490, "h": 510},
    "banner": {"x": 665, "y": 136, "w": 1205, "h": 510},
    "name_text": {"x": 671, "y": 233},
    "guild_text": {"x": 698, "y": 138},
    "likes_text": {"x": 1558, "y": 516},
    "level_text": {"x": 230, "y": 702},
    "uid_text": {"x": 1520, "y": 718},
}

# ================= APP =================
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

client = httpx.AsyncClient(
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=10.0
)

process_pool = ThreadPoolExecutor(max_workers=4)

# ================= HELPERS =================
def load_font(size):
    try:
        return ImageFont.truetype(FONT_FILE, size)
    except:
        return ImageFont.load_default()

async def fetch_image(item_id):
    try:
        r = await client.get(f"{info_URL}/{item_id}.png")
        if r.status_code == 200:
            return r.content
    except:
        return None

def bytes_to_image(data):
    if data:
        return Image.open(io.BytesIO(data)).convert("RGBA")
    return Image.new("RGBA", (100, 100), (0, 0, 0, 0))

# ================= BANNER =================
def create_banner(player, avatar_bytes, banner_bytes, template_bytes):

    template = bytes_to_image(template_bytes).resize(
        (CANVAS_WIDTH, CANVAS_HEIGHT)
    )

    final = template.copy()
    draw = ImageDraw.Draw(final)

    # avatar
    if avatar_bytes:
        avatar = bytes_to_image(avatar_bytes).resize((490, 510))
        final.paste(avatar, (191, 131))

    # banner
    if banner_bytes:
        banner = bytes_to_image(banner_bytes).resize((1205, 510))
        final.paste(banner, (665, 136))

    # fonts
    name_font = load_font(70)
    guild_font = load_font(45)
    normal_font = load_font(40)

    # name
    draw.text(
        (671, 233),
        player["name"],
        font=name_font,
        fill=TEXT_COLOR,
        stroke_width=3,
        stroke_fill=STROKE_COLOR
    )

    # guild
    draw.text(
        (698, 138),
        player["guild"],
        font=guild_font,
        fill=TEXT_COLOR,
        stroke_width=2,
        stroke_fill=STROKE_COLOR
    )

    # likes
    draw.text(
        (1558, 516),
        str(player["likes"]),
        font=normal_font,
        fill=TEXT_COLOR
    )

    # level
    draw.text(
        (230, 702),
        f"Lv.{player['level']}",
        font=normal_font,
        fill=TEXT_COLOR
    )

    # uid
    draw.text(
        (1520, 718),
        f"UID: {player['uid']}",
        font=normal_font,
        fill=(255,255,255)
    )

    # watermark
    draw.text(
        (700, 730),
        WATERMARK_TEXT,
        font=normal_font,
        fill=(255,215,0)
    )

    output = io.BytesIO()
    final.save(output, format="PNG")
    output.seek(0)

    return output

# ================= HOME =================
@app.get("/")
async def home():
    return {
        "status": "online",
        "endpoint": "/bishal?uid=1576195175"
    }

# ================= MAIN ENDPOINT =================
@app.get("/bishal")
async def bishal(uid: str):

    url = f"{INFO_API_URL}?uid={uid}&key={API_KEY}"

    try:
        response = await client.get(url)

        if response.status_code != 200:
            raise HTTPException(404, "Player not found")

        data = response.json()

    except Exception as e:
        raise HTTPException(500, str(e))

    basic = data.get("basicInfo", {})
    clan = data.get("clanBasicInfo", {})

    player = {
        "uid": uid,
        "name": basic.get("nickname", "Unknown"),
        "level": basic.get("level", 0),
        "likes": basic.get("liked", 0),
        "guild": clan.get("clanName", "NO GUILD")
    }

    avatar_id = basic.get("headPic")
    banner_id = basic.get("bannerId")

    avatar, banner = await asyncio.gather(
        fetch_image(avatar_id),
        fetch_image(banner_id)
    )

    template_path = "bishallegacy.png"

    if os.path.exists(template_path):
        with open(template_path, "rb") as f:
            template_bytes = f.read()
    else:
        blank = Image.new("RGBA", (1850, 800), (20,20,20))
        bio = io.BytesIO()
        blank.save(bio, format="PNG")
        template_bytes = bio.getvalue()

    image = await asyncio.get_event_loop().run_in_executor(
        process_pool,
        create_banner,
        player,
        avatar,
        banner,
        template_bytes
    )

    return Response(image.getvalue(), media_type="image/png")

# ================= RUN =================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)