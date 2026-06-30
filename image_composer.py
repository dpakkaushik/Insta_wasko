import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CANVAS   = (1080, 1920)
FONT_DIR = Path(__file__).parent / "fonts"

X_MARGIN   = int(CANVAS[0] * 0.08)   # left & right padding
Y_START    = int(CANVAS[1] * 0.35)   # start text at 35% down
TEXT_WIDTH = int(CANVAS[0] * 0.84)   # usable text width


def _load_font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    for p in [FONT_DIR / filename, Path("C:/Windows/Fonts") / filename]:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        test = (current + " " + word).strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= TEXT_WIDTH:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def make_gradient_bg() -> Image.Image:
    img    = Image.new("RGB", CANVAS)
    pixels = img.load()
    w, h   = CANVAS
    dark, mid = (12, 12, 20), (55, 55, 85)
    for y in range(h):
        for x in range(w):
            t = x / w * 0.3 + y / h * 0.7
            pixels[x, y] = tuple(
                max(0, min(255, int(dark[i] + (mid[i] - dark[i]) * t))) for i in range(3)
            )
    return img


def compose_card(quote: str, font_color: tuple, bg_image: Image.Image) -> Image.Image:
    # Cover-crop bg to 9:16
    src_w, src_h = bg_image.size
    scale  = max(CANVAS[0] / src_w, CANVAS[1] / src_h)
    new_w, new_h = int(src_w * scale), int(src_h * scale)
    resized = bg_image.resize((new_w, new_h), Image.LANCZOS)
    left    = (new_w - CANVAS[0]) // 2
    top     = (new_h - CANVAS[1]) // 2
    canvas  = resized.crop((left, top, left + CANVAS[0], top + CANVAS[1])).convert("RGBA")

    draw   = ImageDraw.Draw(canvas)
    is_hindi = bool(re.search(r"[ऀ-ॿ]", quote))
    font   = _load_font("NotoSansDevanagari.ttf" if is_hindi else "Lato-Bold.ttf", 48)
    shadow = (0, 0, 0, 160) if font_color[0] > 128 else (255, 255, 255, 80)

    lines = _wrap_text(draw, quote, font)
    line_h = 68
    total_h = len(lines) * line_h
    y = (CANVAS[1] - total_h) // 2  # vertically center the text block

    for line in lines:
        draw.text((X_MARGIN + 2, y + 2), line, font=font, fill=shadow)
        draw.text((X_MARGIN, y),     line, font=font, fill=font_color)
        y += line_h

    return canvas.convert("RGB")
