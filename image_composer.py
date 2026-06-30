import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CANVAS     = (1080, 1920)
FONT_DIR   = Path(__file__).parent / "fonts"
X_MARGIN   = int(CANVAS[0] * 0.08)
Y_START    = int(CANVAS[1] * 0.20)   # 20% from top
TEXT_WIDTH = int(CANVAS[0] * 0.84)


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


def compose_card(quote: str, font_color: tuple, **kwargs) -> Image.Image:
    """Return a transparent RGBA image with just the text — no background card."""
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    draw   = ImageDraw.Draw(canvas)

    is_hindi = bool(re.search(r"[ऀ-ॿ]", quote))
    font     = _load_font("NotoSansDevanagari.ttf" if is_hindi else "Poppins-Bold.ttf", 52)

    lines  = _wrap_text(draw, quote, font)
    line_h = 74
    y      = Y_START

    for line in lines:
        # white shadow so black text reads on dark backgrounds too
        for dx, dy in [(-3,-3),(3,-3),(-3,3),(3,3),(0,4),(4,0),(-4,0),(0,-4)]:
            draw.text((X_MARGIN + dx, y + dy), line, font=font, fill=(255, 255, 255, 220))
        draw.text((X_MARGIN, y), line, font=font, fill=(0, 0, 0, 255))
        y += line_h

    return canvas
