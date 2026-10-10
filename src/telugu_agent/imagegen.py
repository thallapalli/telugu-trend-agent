"""Render a Telugu post as an Instagram-ready JPEG card (1080x1350, 4:5). Free: Pillow + bundled Noto font."""
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features

from . import config

W, H = 1080, 1350
MARGIN = 100

# Dark gradients so white text always has strong contrast.
PALETTES = [
    ((26, 20, 79), (92, 36, 140)),   # indigo -> purple
    ((8, 59, 76), (14, 116, 120)),   # navy -> teal
    ((88, 24, 40), (176, 74, 40)),   # maroon -> burnt orange
    ((17, 64, 44), (36, 120, 78)),   # forest -> green
    ((38, 38, 52), (96, 54, 112)),   # charcoal -> plum
]

_FONT_DIRS = [config.ROOT / "fonts", Path("/usr/share/fonts/truetype/noto")]


def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    name = f"NotoSansTelugu-{weight}.ttf"
    for d in _FONT_DIRS:
        if (d / name).exists():
            return ImageFont.truetype(str(d / name), size, layout_engine=ImageFont.Layout.RAQM)
    raise FileNotFoundError(f"{name} not found in {_FONT_DIRS}")


def _strip_unrenderable(text: str) -> str:
    """Noto Sans Telugu has no emoji; drop them so the card doesn't show tofu boxes."""
    return "".join(
        ch for ch in text
        if ord(ch) <= 0xFFFF and not (0x2600 <= ord(ch) <= 0x27BF) and ord(ch) not in (0xFE0F, 0x200D)
    ).strip()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words, current = paragraph.split(), ""
        for word in words:
            trial = f"{current} {word}".strip()
            if draw.textlength(trial, font=font) <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        lines.append(current)
    return lines


def _gradient(top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / (H - 1)
        row = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = row
    return img


def render(text: str, post_id: str, out_dir: Path) -> Path:
    if not features.check("raqm"):
        raise RuntimeError("Pillow needs libraqm for Telugu shaping (apt install libraqm0 / use a Pillow wheel)")

    seed = int(hashlib.sha1(post_id.encode()).hexdigest(), 16)
    img = _gradient(*PALETTES[seed % len(PALETTES)])
    draw = ImageDraw.Draw(img)
    text = _strip_unrenderable(text)

    # Fit text: largest font size whose wrapped block fits the safe area.
    area_h = H - 2 * 260
    chosen = None
    for size in range(84, 39, -4):
        font = _font("Bold", size)
        lines = _wrap(draw, text, font, W - 2 * MARGIN)
        line_h = int(size * 1.75)  # Telugu glyphs are tall; generous leading
        if len(lines) * line_h <= area_h:
            chosen = (font, lines, line_h)
            break
    font, lines, line_h = chosen or (font, lines, line_h)

    block_h = len(lines) * line_h
    y = (H - block_h) // 2
    draw.rounded_rectangle((W // 2 - 60, y - 70, W // 2 + 60, y - 62), radius=4, fill=(255, 255, 255))
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text(((W - w) / 2, y), line, font=font, fill=(255, 255, 255))
        y += line_h

    if config.IG_HANDLE:
        small = _font("Regular", 38)
        handle = config.IG_HANDLE
        hw = draw.textlength(handle, font=small)
        draw.text(((W - hw) / 2, H - 150), handle, font=small, fill=(255, 255, 255))

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{post_id}.jpg"
    img.save(path, "JPEG", quality=92)  # Instagram accepts JPEG only
    return path
