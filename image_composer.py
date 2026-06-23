import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CANVAS = (1080, 1920)
FONT_DIR = Path(__file__).parent / "fonts"

X_START    = int(CANVAS[0] * 0.06)          # 65px — left margin (safe from Instagram chrome)
TEXT_WIDTH = int(CANVAS[0] * 0.55)          # 594px — text wraps before 61% mark
Y_START    = int(CANVAS[1] * 0.10)          # 192px — top margin


def _load_font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        FONT_DIR / filename,
        Path("C:/Windows/Fonts") / filename,
        Path("/usr/share/fonts/truetype/dejavu") / filename,
    ]
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def _wrap_text(
    d: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
) -> list[str]:
    """Word-wrap text to fit within TEXT_WIDTH pixels."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = d.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= TEXT_WIDTH:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_text_block(
    d: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    font_color: tuple,
    shadow_color: tuple,
    start_y: int,
    line_height: int,
) -> int:
    """Draw left-aligned word-wrapped block. Returns y after last line."""
    lines = _wrap_text(d, text, font)
    y = start_y
    for line in lines:
        d.text((X_START + 2, y + 2), line, font=font, fill=shadow_color)
        d.text((X_START, y), line, font=font, fill=font_color)
        y += line_height
    return y


def _draw_qa_overlay(
    d: ImageDraw.ImageDraw,
    quote: str,
    font_color: tuple,
) -> None:
    """Render the Me: / Krishna: dialogue left-aligned from the top-left zone."""
    if font_color[0] > 128:
        shadow_color = (0, 0, 0, 140)
    else:
        shadow_color = (255, 255, 255, 100)

    parts = quote.split("\n", 1)
    me_line      = parts[0].strip() if len(parts) > 0 else ""
    krishna_line = parts[1].strip() if len(parts) > 1 else ""

    is_hindi = bool(re.search(r"[ऀ-ॿ]", quote))
    if is_hindi:
        font_me      = _load_font("NotoSansDevanagari.ttf", 38)
        font_krishna = _load_font("NotoSansDevanagari.ttf", 38)
    else:
        font_me      = _load_font("Lato-Bold.ttf", 38)
        font_krishna = _load_font("PlayfairDisplay-Bold.ttf", 38)

    y = Y_START

    if me_line:
        y = _draw_text_block(d, me_line, font_me, font_color, shadow_color, y, line_height=52)
        y += 28

    if krishna_line:
        _draw_text_block(d, krishna_line, font_krishna, font_color, shadow_color, y, line_height=52)


def make_gradient_bg() -> Image.Image:
    """Neutral dark gradient fallback when no template image is found."""
    img = Image.new("RGB", CANVAS)
    pixels = img.load()
    w, h = CANVAS
    dark  = (12, 12, 20)
    mid   = (55, 55, 85)
    for y in range(h):
        for x in range(w):
            t = x / w * 0.3 + y / h * 0.7
            r = int(dark[0] + (mid[0] - dark[0]) * t)
            g = int(dark[1] + (mid[1] - dark[1]) * t)
            b = int(dark[2] + (mid[2] - dark[2]) * t)
            pixels[x, y] = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
    return img


def compose_card(
    quote: str,
    font_color: tuple,
    bg_image: Image.Image,
) -> Image.Image:
    # Cover-crop to 9:16 without stretching
    src_w, src_h = bg_image.size
    scale = max(CANVAS[0] / src_w, CANVAS[1] / src_h)
    new_w, new_h = int(src_w * scale), int(src_h * scale)
    resized = bg_image.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - CANVAS[0]) // 2
    top  = (new_h - CANVAS[1]) // 2
    canvas = resized.crop((left, top, left + CANVAS[0], top + CANVAS[1])).convert("RGBA")

    d = ImageDraw.Draw(canvas)
    _draw_qa_overlay(d, quote, font_color)

    return canvas.convert("RGB")
