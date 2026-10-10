"""Render a Telugu post as an Instagram-ready JPEG card (1080x1350, 4:5).
Royal temple aesthetic with Deep Antique Brown, Royal Maroon, and Gold accents.
Uses HarfBuzz (uharfbuzz) + FreeType for 100% native Telugu complex script shaping (vatthulu/conjuncts).
"""
import hashlib
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from . import config

try:
    import freetype
    import uharfbuzz as hb
    _HAS_HARFBUZZ = True
except ImportError:
    _HAS_HARFBUZZ = False

W, H = 1080, 1350
MARGIN = 110

# Royal & temple palettes: deep, rich gradients for authentic heritage contrast
PALETTES = [
    ((34, 18, 12), (68, 38, 22)),   # Deep Antique Brown (teakwood & ancient temple stone)
    ((56, 12, 22), (98, 20, 38)),   # Royal Maroon (imperial dynasty crimson)
    ((26, 20, 16), (58, 42, 30)),   # Deep Temple Bronze & Umber (ancient sanctum)
    ((14, 38, 28), (28, 68, 50)),   # Sacred Temple Moss (temple courtyards & malachite)
    ((20, 16, 36), (44, 32, 66)),   # Royal Antique Indigo (imperial night sky)
]

# Royal Gold and Ivory color palette accents
GOLD_PRIMARY = (226, 178, 74)   # Rich metallic warm gold
GOLD_MUTED   = (186, 144, 58)   # Antique gold for frame hairlines
GOLD_LIGHT   = (255, 223, 133)  # Highlight gold for titles & proverbs
IVORY_WHITE  = (252, 248, 240)  # Warm temple cream for crisp body readability

_FONT_DIRS = [config.ROOT / "fonts", Path("/usr/share/fonts/truetype/noto")]
_FACE_CACHE: dict = {}


def _resolve_font_path(family: str, weight: str) -> Path:
    name = f"{family}-{weight}.ttf" if family else f"NotoSansTelugu-{weight}.ttf"
    for d in _FONT_DIRS:
        p = d / name
        if p.exists():
            return p
    raise FileNotFoundError(f"{name} not found in {_FONT_DIRS}")


def _get_hb_faces(font_path: Path):
    key = str(font_path)
    if key not in _FACE_CACHE:
        ft_face = freetype.Face(key)
        with open(font_path, "rb") as f:
            hb_face = hb.Face(f.read())
        _FACE_CACHE[key] = (ft_face, hb_face)
    return _FACE_CACHE[key]


def _measure_hb_line(text: str, hb_face, size: int) -> float:
    font = hb.Font(hb_face)
    font.scale = (size * 64, size * 64)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    return sum(pos.x_advance for pos in buf.glyph_positions) / 64.0


def _draw_hb_line(
    img: Image.Image,
    text: str,
    font_path: Path,
    size: int,
    color: tuple,
    y: int,
    cx: int = W // 2,
) -> None:
    ft_face, hb_face = _get_hb_faces(font_path)
    ft_face.set_char_size(size * 64)
    font = hb.Font(hb_face)
    font.scale = (size * 64, size * 64)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)

    total_w = sum(pos.x_advance for pos in buf.glyph_positions) / 64.0
    start_x = cx - total_w / 2.0
    x = start_x * 64
    y_scaled = y * 64

    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        ft_face.load_glyph(info.codepoint, freetype.FT_LOAD_RENDER)
        bitmap = ft_face.glyph.bitmap
        bx = int((x + pos.x_offset) / 64) + ft_face.glyph.bitmap_left
        by = int((y_scaled - pos.y_offset) / 64) - ft_face.glyph.bitmap_top
        if bitmap.width > 0 and bitmap.rows > 0:
            mask = Image.frombytes("L", (bitmap.width, bitmap.rows), bytes(bitmap.buffer))
            fill = Image.new("RGB", (bitmap.width, bitmap.rows), color)
            img.paste(fill, (bx, by), mask)
        x += pos.x_advance
        y_scaled += pos.y_advance


def _strip_unrenderable(text: str) -> str:
    """Normalize quotes and drop unrenderable glyphs/emojis."""
    text = text.replace("「", '"').replace("」", '"')
    return "".join(
        ch for ch in text
        if ord(ch) <= 0xFFFF and not (0x2600 <= ord(ch) <= 0x27BF) and ord(ch) not in (0xFE0F, 0x200D)
    ).strip()


def _wrap_lines(text: str, hb_face, size: int, max_w: int) -> list[tuple[str, bool]]:
    wrapped: list[tuple[str, bool]] = []
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    for p_idx, para in enumerate(paragraphs):
        words = para.split()
        cur = ""
        is_title = (p_idx == 0 and (para.startswith('"') or len(paragraphs) > 1))
        for w in words:
            trial = f"{cur} {w}".strip()
            if _measure_hb_line(trial, hb_face, size) <= max_w:
                cur = trial
            else:
                if cur:
                    wrapped.append((cur, is_title))
                cur = w
        if cur:
            wrapped.append((cur, is_title))
    return wrapped


def _gradient(top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / (H - 1)
        row = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = row
    return img


def _draw_diamond(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int = 7, fill: tuple = GOLD_PRIMARY) -> None:
    draw.polygon(
        [(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)],
        fill=fill,
    )


def _draw_royal_divider(draw: ImageDraw.ImageDraw, cx: int, cy: int, width: int = 220, fill: tuple = GOLD_PRIMARY) -> None:
    half = width // 2
    _draw_diamond(draw, cx, cy, size=8, fill=fill)
    draw.line((cx - half, cy, cx - 18, cy), fill=fill, width=2)
    draw.line((cx + 18, cy, cx + half, cy), fill=fill, width=2)
    _draw_diamond(draw, cx - half - 4, cy, size=4, fill=fill)
    _draw_diamond(draw, cx + half + 4, cy, size=4, fill=fill)


def render(text: str, post_id: str, out_dir: Path) -> Path:
    seed = int(hashlib.sha1(post_id.encode()).hexdigest(), 16)
    img = _gradient(*PALETTES[seed % len(PALETTES)])
    draw = ImageDraw.Draw(img)
    text = _strip_unrenderable(text)

    # 1. Royal Double Inset Frame with Corner Ornaments
    draw.rectangle((45, 45, W - 45, H - 45), outline=GOLD_MUTED, width=2)
    draw.rectangle((55, 55, W - 55, H - 55), outline=GOLD_MUTED, width=1)
    for cx, cy in [(45, 45), (W - 45, 45), (45, H - 45), (W - 45, H - 45)]:
        _draw_diamond(draw, cx, cy, size=8, fill=GOLD_PRIMARY)

    telugu_bold_path = _resolve_font_path("NotoSansTelugu", "Bold")
    telugu_reg_path = _resolve_font_path("NotoSansTelugu", "Regular")
    latin_bold_path = _resolve_font_path("NotoSans", "Bold")

    if _HAS_HARFBUZZ:
        # Native HarfBuzz OpenType complex script shaping (flawless Indic conjuncts & vatthulu)
        _, hb_bold = _get_hb_faces(telugu_bold_path)

        # 2. Header Emblem & Brand Badge (Pure Telugu Script)
        _draw_hb_line(img, "తెలుగు లోకల్స్", telugu_bold_path, size=32, color=GOLD_PRIMARY, y=98)
        _draw_hb_line(img, "సంస్కృతి  |  వారసత్వం  |  వైభవం", telugu_reg_path, size=20, color=GOLD_LIGHT, y=140)

        # Header decorative divider
        half = 90
        draw.line((W // 2 - half, 178, W // 2 - 18, 178), fill=GOLD_MUTED, width=2)
        draw.line((W // 2 + 18, 178, W // 2 + half, 178), fill=GOLD_MUTED, width=2)
        _draw_diamond(draw, W // 2, 178, size=8, fill=GOLD_MUTED)

        # 3. Fit Text Block dynamically
        area_h = H - 2 * 270
        max_w = W - 2 * MARGIN
        chosen_size = 46
        chosen_wrapped = []

        for size in range(60, 35, -3):
            wrapped = _wrap_lines(text, hb_bold, size, max_w)
            line_h = int(size * 1.85)
            if len(wrapped) * line_h <= area_h:
                chosen_size = size
                chosen_wrapped = wrapped
                break
        if not chosen_wrapped:
            chosen_wrapped = _wrap_lines(text, hb_bold, 36, max_w)
            chosen_size = 36

        line_h = int(chosen_size * 1.85)
        block_h = len(chosen_wrapped) * line_h
        y = (H - block_h) // 2

        # 4. Accent Divider Above Text
        _draw_royal_divider(draw, W // 2, y - 55, width=240, fill=GOLD_PRIMARY)

        # 5. Render Lines with Visual Hierarchy
        for line_str, is_title in chosen_wrapped:
            col = GOLD_LIGHT if is_title else IVORY_WHITE
            _draw_hb_line(
                img,
                line_str,
                telugu_bold_path,
                size=chosen_size,
                color=col,
                y=y + int(chosen_size * 0.9),
            )
            y += line_h

        # 6. Accent Divider Below Text
        _draw_royal_divider(draw, W // 2, y + 25, width=180, fill=GOLD_MUTED)

        # 7. Footer Divider & Handle (Rendered using Latin font)
        footer_y = H - 145
        draw.line((W // 2 - 100, footer_y - 20, W // 2 + 100, footer_y - 20), fill=GOLD_MUTED, width=1)
        _draw_diamond(draw, W // 2, footer_y - 20, size=5, fill=GOLD_PRIMARY)

        handle = config.IG_HANDLE or "@telugulocals"
        _draw_hb_line(img, handle, latin_bold_path, size=26, color=GOLD_PRIMARY, y=footer_y + 16)
        _draw_diamond(draw, W // 2 - 115, footer_y + 16, size=5, fill=GOLD_PRIMARY)
        _draw_diamond(draw, W // 2 + 115, footer_y + 16, size=5, fill=GOLD_PRIMARY)

    else:
        # Fallback to standard Pillow text rendering if HarfBuzz is unavailable
        font = ImageFont.truetype(str(telugu_bold_path), 44)
        draw.text((W // 2, H // 2), text, font=font, fill=IVORY_WHITE, anchor="mm")

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{post_id}.jpg"
    img.save(path, "JPEG", quality=95)
    return path
