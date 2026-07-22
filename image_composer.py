import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    from pilmoji import Pilmoji
    _HAS_PILMOJI = True
except ImportError:
    _HAS_PILMOJI = False

CANVAS     = (1080, 1920)
FONT_DIR   = Path(__file__).parent / "fonts"
X_MARGIN   = int(CANVAS[0] * 0.08)
Y_START    = int(CANVAS[1] * 0.20)   # 20% from top
TEXT_WIDTH = int(CANVAS[0] * 0.84)

LINE_H       = 74
STROKE_W     = 4
SHADOW_FILL  = (255, 255, 255, 220)
TEXT_FILL    = (0, 0, 0, 255)

# Broad coverage of the emoji/pictograph blocks so we only reach for the
# (slower, network-backed) emoji renderer when a quote actually needs it.
_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # symbols & pictographs (incl. supplemental / extended)
    "\U00002600-\U000027BF"   # misc symbols + dingbats
    "\U00002300-\U000023FF"   # misc technical (⌚ ⏰ …)
    "\U00002B00-\U00002BFF"   # misc symbols and arrows (⭐ …)
    "\U0001F1E6-\U0001F1FF"   # regional indicators (flags)
    "\U000024C2-\U0001F251"   # enclosed characters
    "]"
)


def _has_emoji(text: str) -> bool:
    return bool(_EMOJI_RE.search(text))


def _load_font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    for p in [FONT_DIR / filename, Path("C:/Windows/Fonts") / filename]:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def _line_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
                pilmoji=None) -> int:
    """Rendered width of a line, accounting for emoji when a Pilmoji ctx is given."""
    if pilmoji is not None:
        return pilmoji.getsize(text, font=font)[0]
    return draw.textbbox((0, 0), text, font=font)[2]


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
               pilmoji=None) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        test = (current + " " + word).strip()
        if _line_width(draw, test, font, pilmoji) <= TEXT_WIDTH:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_plain(canvas: Image.Image, lines: list[str], font: ImageFont.FreeTypeFont,
                y_start: int) -> None:
    """Original renderer: 8-direction white shadow + black text (no emoji glyphs)."""
    draw = ImageDraw.Draw(canvas)
    y = y_start
    for line in lines:
        # white shadow so black text reads on dark backgrounds too
        for dx, dy in [(-3,-3),(3,-3),(-3,3),(3,3),(0,4),(4,0),(-4,0),(0,-4)]:
            draw.text((X_MARGIN + dx, y + dy), line, font=font, fill=SHADOW_FILL)
        draw.text((X_MARGIN, y), line, font=font, fill=TEXT_FILL)
        y += LINE_H


def compose_card(
    quote: str,
    font_color: tuple,
    y_start: int = Y_START,
    **kwargs,
) -> Image.Image:
    """Return a transparent RGBA image with just the text — no background card.

    Emoji in the quote are rendered as color glyphs via Pilmoji. Plain text
    keeps the original 8-direction shadow, so non-emoji cards are unchanged.
    """
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    draw   = ImageDraw.Draw(canvas)

    font = _load_font("Poppins-Bold.ttf", 52)

    if _has_emoji(quote):
        if not _HAS_PILMOJI:
            print("  [card] emoji detected but 'pilmoji' is not installed — "
                  "run `pip install pilmoji` for emoji rendering; drawing plain text")
        else:
            try:
                with Pilmoji(canvas) as pilmoji:
                    lines = _wrap_text(draw, quote, font, pilmoji=pilmoji)
                    y = y_start
                    for line in lines:
                        # stroke gives text the same white halo as the plain path;
                        # emoji are pasted as color images (stroke doesn't apply).
                        pilmoji.text(
                            (X_MARGIN, y), line, font=font, fill=TEXT_FILL,
                            stroke_width=STROKE_W, stroke_fill=SHADOW_FILL,
                        )
                        y += LINE_H
                return canvas
            except Exception as e:
                # Emoji CDN hiccup / render error — never fail the post over it.
                print(f"  [card] emoji render failed ({e}); falling back to plain text")
                canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
                draw   = ImageDraw.Draw(canvas)

    lines = _wrap_text(draw, quote, font)
    _draw_plain(canvas, lines, font, y_start)
    return canvas
