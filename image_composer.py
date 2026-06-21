from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CANVAS = (1080, 1920)   # 9:16 portrait — Instagram Reels
FONT_DIR = Path(__file__).parent / "fonts"

DEFAULT_ACCENT = (255, 255, 255)

MOOD_COLORS: dict[int, tuple] = {
    1: (99,  102, 241),   # purple  — quiet exhaustion
    2: (245, 158,  11),   # amber   — bittersweet time
    3: (244,  63,  94),   # rose    — soft isolation
    4: (14,  165, 233),   # sky     — acceptance / letting go
}


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


def _draw_quote(d: ImageDraw.ImageDraw, quote: str, accent: tuple) -> None:
    font = _load_font("CaveatBold.ttf", 80)
    words = quote.split()
    lines = [" ".join(words[i:i+3]) for i in range(0, len(words), 3)]

    line_h = 95
    start_y = int(CANVAS[1] * 0.18)

    for line in lines:
        bbox = d.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (CANVAS[0] - tw) // 2
        # Multi-layer shadow for depth
        d.text((x + 5, start_y + 5), line, font=font, fill=(0, 0, 0, 220))
        d.text((x + 3, start_y + 3), line, font=font, fill=(0, 0, 0, 160))
        # Pure white text
        d.text((x, start_y), line, font=font, fill=(255, 255, 255))
        start_y += line_h



def make_gradient_bg(mood_number: int = 1) -> Image.Image:
    """Fallback gradient if no template image is found."""
    accent = MOOD_COLORS.get(mood_number, DEFAULT_ACCENT)
    img = Image.new("RGB", CANVAS)
    pixels = img.load()
    w, h = CANVAS
    dark = (12, 12, 20)
    for y in range(h):
        for x in range(w):
            t = (x / w * 0.4 + y / h * 0.6)
            r = int(dark[0] + (accent[0] - dark[0]) * t * 0.6)
            g = int(dark[1] + (accent[1] - dark[1]) * t * 0.6)
            b = int(dark[2] + (accent[2] - dark[2]) * t * 0.6)
            pixels[x, y] = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
    return img


def compose_card(
    quote: str,
    mood_number: int,
    bg_image: Image.Image,
) -> Image.Image:
    accent = MOOD_COLORS.get(mood_number, DEFAULT_ACCENT)

    # Cover + centre-crop to preserve aspect ratio (no stretch)
    src_w, src_h = bg_image.size
    scale = max(CANVAS[0] / src_w, CANVAS[1] / src_h)
    new_w, new_h = int(src_w * scale), int(src_h * scale)
    resized = bg_image.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - CANVAS[0]) // 2
    top  = (new_h - CANVAS[1]) // 2
    canvas = resized.crop((left, top, left + CANVAS[0], top + CANVAS[1])).convert("RGBA")

    d = ImageDraw.Draw(canvas)
    _draw_quote(d, quote, accent)

    return canvas.convert("RGB")
