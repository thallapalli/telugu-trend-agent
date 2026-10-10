"""Render an English life-hack carousel: 5 slides, 1080x1350 JPEG each (Instagram 4:5). Free: Pillow + bundled Noto Sans.

Text may contain **key terms**; they are drawn in the slide's accent colour.
"""
import hashlib
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config

W, H = 1080, 1350
MARGIN = 96

# (top, bottom, accent): dark backgrounds so white text always reads, bright accent for key terms.
THEMES = [
    ((12, 18, 48), (30, 64, 150), (255, 214, 10)),
    ((10, 10, 14), (52, 22, 92), (0, 229, 255)),
    ((8, 40, 52), (14, 98, 110), (255, 150, 90)),
    ((38, 10, 48), (120, 30, 92), (255, 230, 109)),
    ((10, 30, 20), (18, 92, 62), (170, 255, 120)),
]
LABELS = ["QUICK TIP", "THE SETUP", "STEP 1", "STEP 2", "SAVE & SHARE"]
KEYS = ["hook", "problem", "step1", "step2", "cta"]
WHITE = (255, 255, 255)

_FONT_DIRS = [config.ROOT / "fonts", Path("/usr/share/fonts/truetype/noto")]


def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    name = f"NotoSans-{weight}.ttf"
    for d in _FONT_DIRS:
        if (d / name).exists():
            return ImageFont.truetype(str(d / name), size)
    raise FileNotFoundError(f"{name} not found in {_FONT_DIRS}")


def strip_markup(text: str) -> str:
    return text.replace("**", "")


Word = list  # a word is a list of (piece, is_key_term); pieces touch each other with no space between


def _words(text: str) -> list[Word]:
    """Split on whitespace into words, honouring **...** spans. Punctuation glued to a key term
    (like the dot in '**See all settings**.') stays in the same word, so it is drawn with no gap."""
    words: list[Word] = []
    current: Word = []
    key = False
    for part in re.split(r"(\*\*)", text):
        if part == "**":
            key = not key
            continue
        for chunk in re.split(r"(\s+)", part):
            if not chunk:
                continue
            if chunk.isspace():
                if current:
                    words.append(current)
                    current = []
            else:
                current.append((chunk, key))
    if current:
        words.append(current)
    return words


def _word_text(word: Word) -> str:
    return "".join(piece for piece, _ in word)


def _gradient(top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / (H - 1)
        row = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = row
    return img


def _layout(draw: ImageDraw.ImageDraw, words: list[Word], font, max_w: int) -> list[list[Word]]:
    lines: list[list[Word]] = []
    cur: list[Word] = []
    for word in words:
        trial = " ".join(_word_text(w) for w in cur + [word])
        if cur and draw.textlength(trial, font=font) > max_w:
            lines.append(cur)
            cur = [word]
        else:
            cur.append(word)
    if cur:
        lines.append(cur)
    return lines


def _draw_slide(index: int, text: str, theme: tuple, handle: str) -> Image.Image:
    top, bottom, accent = theme
    img = _gradient(top, bottom)
    draw = ImageDraw.Draw(img)
    total = len(KEYS)

    # header: label pill (left) and counter (right)
    label_font, small = _font("Bold", 34), _font("Regular", 36)
    label = LABELS[index]
    lw = draw.textlength(label, font=label_font)
    draw.rounded_rectangle((MARGIN, 96, MARGIN + lw + 56, 96 + 64), radius=32, fill=accent)
    draw.text((MARGIN + 28, 96 + 9), label, font=label_font, fill=(15, 15, 20))
    counter = f"{index + 1}/{total}"
    draw.text((W - MARGIN - draw.textlength(counter, font=small), 104), counter, font=small, fill=(255, 255, 255, 200))

    # body: largest font that fits the safe area
    words = _words(text)
    max_w, area_h = W - 2 * MARGIN, 740
    chosen = None
    for size in range(112, 51, -4):
        font = _font("Bold", size)
        lines = _layout(draw, words, font, max_w)
        line_h = int(size * 1.28)
        if len(lines) * line_h <= area_h:
            chosen = (font, lines, line_h)
            break
    font, lines, line_h = chosen or (font, lines, line_h)
    y = 250 + (area_h - len(lines) * line_h) // 2
    for line in lines:
        line_text = " ".join(_word_text(w) for w in line)
        x = (W - draw.textlength(line_text, font=font)) / 2
        for word in line:
            for piece, key in word:
                draw.text((x, y), piece, font=font, fill=accent if key else WHITE)
                x += draw.textlength(piece, font=font)
            x += draw.textlength(" ", font=font)
        y += line_h

    # footer: handle, progress dots, swipe chevron
    if handle:
        hw = draw.textlength(handle, font=small)
        draw.text(((W - hw) / 2, H - 190), handle, font=small, fill=WHITE)
    dot_y, gap = H - 110, 36
    start = W / 2 - gap * (total - 1) / 2
    for i in range(total):
        r = 9 if i == index else 6
        draw.ellipse((start + i * gap - r, dot_y - r, start + i * gap + r, dot_y + r), fill=accent if i == index else (255, 255, 255))
    if index < total - 1:  # swipe cue in the footer, away from the text
        cx, cy = W - MARGIN, dot_y
        draw.line((cx - 14, cy - 26, cx + 4, cy, cx - 14, cy + 26), fill=accent, width=9, joint="curve")
    return img


def render(slides: dict, post_id: str, out_dir: Path) -> list[Path]:
    """Render the 5 slides and return their paths in order."""
    seed = int(hashlib.sha1(post_id.encode()).hexdigest(), 16)
    theme = THEMES[seed % len(THEMES)]
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, key in enumerate(KEYS):
        img = _draw_slide(i, slides[key], theme, config.IG_HACKS_HANDLE or config.IG_HANDLE)
        path = out_dir / f"{post_id}_{i + 1}.jpg"
        img.save(path, "JPEG", quality=92)  # Instagram accepts JPEG only
        paths.append(path)
    return paths
