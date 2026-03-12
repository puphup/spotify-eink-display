"""
Display service — builds PIL images for the e-ink screen.

Font install on Raspberry Pi for full multilingual support (Thai, CJK, Arabic, etc.):
  sudo apt install fonts-noto fonts-noto-cjk fonts-thai-tlwg
"""

import io
import requests
from PIL import Image, ImageDraw, ImageFont
import config


# ---------------------------------------------------------------------------
# Script detection + per-script font loading
# ---------------------------------------------------------------------------

def _detect_script(text: str) -> str:
    """Return the dominant non-Latin script found in the text, or 'latin'."""
    for ch in text:
        cp = ord(ch)
        if 0x0E00 <= cp <= 0x0E7F:
            return "thai"
        if (0x3040 <= cp <= 0x30FF or   # Hiragana / Katakana
                0x4E00 <= cp <= 0x9FFF or   # CJK Unified Ideographs
                0xF900 <= cp <= 0xFAFF or   # CJK Compatibility
                0x3400 <= cp <= 0x4DBF):    # CJK Extension A
            return "cjk"
        if 0x0600 <= cp <= 0x06FF:
            return "arabic"
        if 0x0400 <= cp <= 0x04FF:
            return "cyrillic"
    return "latin"


def _load_font(size: int, bold: bool = False, text: str = "") -> ImageFont.ImageFont:
    """
    Pick the best font for the given text's script.
    PIL has no built-in font fallback — we must select the right file per script.
    """
    script = _detect_script(text)

    b = "-Bold" if bold else "-Regular"

    if script == "thai":
        candidates = [
            # Raspberry Pi
            f"/usr/share/fonts/truetype/noto/NotoSansThai{b}.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
            "/usr/share/fonts/truetype/thai-tlwg/Loma.ttf",
            "/usr/share/fonts/truetype/thai-tlwg/Garuda.ttf",
            "/usr/share/fonts/truetype/thai-tlwg/Waree.ttf",
            # macOS
            "/System/Library/Fonts/Thonburi.ttf",
            "/Library/Fonts/Thonburi.ttf",
        ]
    elif script == "cjk":
        candidates = [
            # Raspberry Pi
            f"/usr/share/fonts/opentype/noto/NotoSansCJK{b.lower()}.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
            # macOS
            "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/PingFang.ttc",
        ]
    else:
        # Latin, Cyrillic, Arabic, etc. — Noto Sans has broad coverage
        candidates = [
            f"/usr/share/fonts/truetype/noto/NotoSans{b}.ttf",
            f"/usr/share/fonts/opentype/noto/NotoSans{b}.otf",
            f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
            "/System/Library/Fonts/HelveticaNeue.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
        ]

    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _download_image(url: str) -> Image.Image | None:
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        return None


def _cover_crop(image: Image.Image, width: int, height: int) -> Image.Image:
    """Scale image to fill (width × height), crop center. No blur."""
    src_w, src_h = image.size
    scale = max(width / src_w, height / src_h)
    new_w, new_h = int(src_w * scale), int(src_h * scale)
    image = image.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    return image.crop((left, top, left + width, top + height))


def _draw_single_line(draw: ImageDraw.ImageDraw, text: str, font,
                      x: int, y: int, max_width: int, fill, shadow=None) -> int:
    """Draw text on a single line, truncating with '…' if too wide. Returns new y."""
    ellipsis = "…"
    while text and draw.textbbox((0, 0), text + ellipsis, font=font)[2] > max_width:
        text = text[:-1]
    if draw.textbbox((0, 0), text, font=font)[2] > max_width:
        text = text + ellipsis
    if shadow:
        draw.text((x + 1, y + 2), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)
    return y + draw.textbbox((0, 0), text, font=font)[3] + 6


def _draw_wrapped(draw: ImageDraw.ImageDraw, text: str, font,
                  x: int, y: int, max_width: int, fill, shadow=None) -> int:
    """Word-wrap and draw text. Returns new y after last line."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        w = draw.textbbox((0, 0), test, font=font)[2]
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    for line in lines:
        if shadow:
            draw.text((x + 1, y + 2), line, font=font, fill=shadow)
        draw.text((x, y), line, font=font, fill=fill)
        line_h = draw.textbbox((0, 0), line, font=font)[3]
        y += line_h + 6
    return y


def _bottom_overlay(width: int, overlay_height: int) -> Image.Image:
    """Solid dark overlay with a short fade at the top edge."""
    img = Image.new("RGBA", (width, overlay_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    fade_px = 40  # how many pixels to fade in from transparent
    for y in range(overlay_height):
        if y < fade_px:
            alpha = int(200 * (y / fade_px) ** 1.5)
        else:
            alpha = 200
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
    return img


# ---------------------------------------------------------------------------
# Main image builders
# ---------------------------------------------------------------------------

def build_display_image(track: dict) -> Image.Image:
    """
    Portrait layout (480 × 800):
    - Album art fills full screen, sharp (no blur)
    - Bottom 20% (~160px) has a dark overlay with track info
    - "NOW PLAYING" pill top-left of the overlay
    """
    width, height = config.EINK_WIDTH, config.EINK_HEIGHT   # 480 × 800
    overlay_height = int(height * 0.20)                      # 160px
    overlay_y = height - overlay_height                      # 640px

    # --- Base: sharp full-bleed album art ---
    art = _download_image(track.get("album_art_url") or "") if track.get("album_art_url") else None
    if art:
        canvas = _cover_crop(art, width, height).convert("RGBA")
    else:
        canvas = Image.new("RGBA", (width, height), (20, 20, 20, 255))

    # --- Bottom overlay (20%) ---
    overlay = _bottom_overlay(width, overlay_height)
    canvas.paste(overlay, (0, overlay_y), overlay)

    draw = ImageDraw.Draw(canvas)

    pad_x = 20
    text_width = width - pad_x * 2
    shadow = (0, 0, 0, 180)

    # --- NOW PLAYING pill ---
    font_pill = _load_font(12, bold=True)
    pill_label = "NOW PLAYING"
    pill_bbox = draw.textbbox((0, 0), pill_label, font=font_pill)
    pw, ph = pill_bbox[2], pill_bbox[3]
    ppx, ppy = pad_x, overlay_y + 12
    ppw, pph = 10, 5
    draw.rounded_rectangle(
        [ppx, ppy, ppx + pw + ppw * 2, ppy + ph + pph * 2],
        radius=16,
        fill=(30, 215, 96, 230),  # Spotify green
    )
    draw.text((ppx + ppw, ppy + pph), pill_label, font=font_pill, fill=(0, 0, 0))

    # --- Track info — load fonts matched to each text's script ---
    title = track.get("title", "Unknown")
    artist = track.get("artist", "")
    font_title = _load_font(34, bold=True, text=title)
    font_artist = _load_font(22, text=artist)

    text_y = overlay_y + 14 + ph + pph * 2 + 8  # below the pill

    text_y = _draw_single_line(
        draw, title,
        font_title, pad_x, text_y, text_width,
        fill=(255, 255, 255), shadow=shadow,
    )
    _draw_wrapped(
        draw, artist,
        font_artist, pad_x, text_y, text_width,
        fill=(200, 200, 200), shadow=shadow,
    )

    return canvas.convert("RGB")


def build_idle_image() -> Image.Image:
    width, height = config.EINK_WIDTH, config.EINK_HEIGHT
    canvas = Image.new("RGB", (width, height), (12, 12, 12))
    draw = ImageDraw.Draw(canvas)

    font = _load_font(36, bold=True)
    font_sub = _load_font(22)

    text = "Nothing Playing"
    tw = draw.textbbox((0, 0), text, font=font)[2]
    draw.text(((width - tw) // 2, height // 2 - 50), text, font=font, fill=(220, 220, 220))

    sub = "Scan QR to request a song"
    sw = draw.textbbox((0, 0), sub, font=font_sub)[2]
    draw.text(((width - sw) // 2, height // 2 + 20), sub, font=font_sub, fill=(90, 90, 90))

    return canvas
