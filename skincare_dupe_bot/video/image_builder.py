"""Renders vertical (1080x1920) text-card frames with PIL.

Deliberately text-card style rather than product photography: scraping and
redistributing retailer/brand product photos inside monetized video content
raises real copyright/trademark exposure that a text-card design avoids
entirely. This trades visual polish for being safe to actually post.
"""
import textwrap

from PIL import Image, ImageDraw, ImageFont

from skincare_dupe_bot import config
from skincare_dupe_bot.video.script_writer import has_meaningful_savings, savings_pct

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
FONT_BOLD = f"{FONT_DIR}/DejaVuSans-Bold.ttf"
FONT_REGULAR = f"{FONT_DIR}/DejaVuSans.ttf"

PALETTES = {
    "hook": {"bg": (250, 235, 229), "accent": (196, 92, 79), "text": (46, 33, 30)},
    "kbeauty": {"bg": (233, 225, 245), "accent": (110, 79, 165), "text": (35, 27, 51)},
    "dupe": {"bg": (222, 240, 227), "accent": (58, 128, 87), "text": (24, 41, 31)},
    "cta": {"bg": (255, 245, 225), "accent": (196, 140, 30), "text": (51, 40, 12)},
}


def _font(path, size):
    return ImageFont.truetype(path, size)


def _draw_wrapped_text(draw, text, font, fill, max_width, start_y, center_x, line_spacing=1.25):
    avg_char_w = font.getlength("x") or 20
    wrap_width = max(10, int(max_width / avg_char_w))
    lines = []
    for paragraph in text.split("\n"):
        lines.extend(textwrap.wrap(paragraph, width=wrap_width) or [""])

    y = start_y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        line_h = bbox[3] - bbox[1]
        draw.text((center_x - line_w / 2, y), line, font=font, fill=fill)
        y += line_h * line_spacing
    return y


def render_card(kind: str, eyebrow: str, headline: str, subline: str = "", footer: str = "") -> Image.Image:
    palette = PALETTES.get(kind, PALETTES["hook"])
    img = Image.new("RGB", (config.VIDEO_WIDTH, config.VIDEO_HEIGHT), palette["bg"])
    draw = ImageDraw.Draw(img)

    margin = 90
    max_width = config.VIDEO_WIDTH - 2 * margin
    center_x = config.VIDEO_WIDTH / 2

    # accent bar
    draw.rectangle([0, 0, config.VIDEO_WIDTH, 24], fill=palette["accent"])
    draw.rectangle([0, config.VIDEO_HEIGHT - 24, config.VIDEO_WIDTH, config.VIDEO_HEIGHT], fill=palette["accent"])

    y = 260
    if eyebrow:
        eyebrow_font = _font(FONT_BOLD, 46)
        y = _draw_wrapped_text(draw, eyebrow.upper(), eyebrow_font, palette["accent"], max_width, y, center_x)
        y += 40

    headline_font = _font(FONT_BOLD, 78)
    y = _draw_wrapped_text(draw, headline, headline_font, palette["text"], max_width, y, center_x)

    if subline:
        y += 50
        sub_font = _font(FONT_REGULAR, 52)
        y = _draw_wrapped_text(draw, subline, sub_font, palette["text"], max_width, y, center_x)

    if footer:
        footer_font = _font(FONT_BOLD, 44)
        footer_bbox = draw.textbbox((0, 0), footer, font=footer_font)
        footer_w = footer_bbox[2] - footer_bbox[0]
        draw.text(
            (center_x - footer_w / 2, config.VIDEO_HEIGHT - 220),
            footer,
            font=footer_font,
            fill=palette["accent"],
        )

    return img


def build_scene_images(kbeauty, dupe, script) -> list:
    """Returns list of (PIL.Image, kind) for the four fixed scenes."""
    dupe_price = dupe.last_known_price_usd or dupe.typical_price_usd or 0.0
    kb_price = kbeauty.typical_price_usd or 0.0
    show_savings = has_meaningful_savings(kb_price, dupe_price)
    pct = savings_pct(kb_price, dupe_price) if show_savings else 0

    scenes = [
        render_card(
            "hook",
            eyebrow="Dupe alert",
            headline=script.hook,
        ),
        render_card(
            "kbeauty",
            eyebrow=f"K-Beauty {kbeauty.category or ''}".strip(),
            headline=f"{kbeauty.brand}\n{kbeauty.name}",
            subline=f"${kb_price:.2f}" if kb_price else "",
        ),
        render_card(
            "dupe",
            eyebrow=f"{(dupe.retailer or 'Drugstore').title()} dupe",
            headline=f"{dupe.brand}\n{dupe.name}",
            subline=f"${dupe_price:.2f}",
            footer=f"Save ~{pct:.0f}%" if show_savings else "",
        ),
        render_card(
            "cta",
            eyebrow="Before you go",
            headline=script.cta,
            subline=script.hashtags,
        ),
    ]
    return scenes
