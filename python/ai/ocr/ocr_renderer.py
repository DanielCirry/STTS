"""
OCR Translation Overlay Renderer.

Renders translated text blocks onto a texture image that covers the original text.
Each detected text block gets an off-white background rectangle with the translated
text drawn on top, sized to fit the bounding box.
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger('stts.ocr.renderer')

# Cache loaded fonts
_font_cache = {}


def _get_font(size: int):
    """Get a PIL font at the given size, with CJK support."""
    if size in _font_cache:
        return _font_cache[size]

    from PIL import ImageFont

    # Try system fonts that support CJK
    font_paths = [
        'C:/Windows/Fonts/msgothic.ttc',   # Japanese
        'C:/Windows/Fonts/malgun.ttf',      # Korean
        'C:/Windows/Fonts/msyh.ttc',        # Chinese
        'C:/Windows/Fonts/arial.ttf',        # Fallback
        'C:/Windows/Fonts/segoeui.ttf',      # Fallback
    ]

    for fp in font_paths:
        if Path(fp).exists():
            try:
                font = ImageFont.truetype(fp, size)
                _font_cache[size] = font
                return font
            except Exception:
                continue

    # Final fallback: default font
    try:
        font = ImageFont.truetype("arial.ttf", size)
    except Exception:
        font = ImageFont.load_default()
    _font_cache[size] = font
    return font


def fit_font_to_box(text: str, box_width: int, box_height: int,
                    min_size: int = 8, max_size: int = 72) -> 'ImageFont':
    """Find the largest font size that fits text within the bounding box."""
    from PIL import ImageFont, ImageDraw, Image

    # Binary search for best font size
    best_font = _get_font(min_size)
    lo, hi = min_size, max_size

    # Create a temporary draw surface for measuring
    tmp_img = Image.new('RGBA', (1, 1))
    tmp_draw = ImageDraw.Draw(tmp_img)

    while lo <= hi:
        mid = (lo + hi) // 2
        font = _get_font(mid)
        bbox = tmp_draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        if tw <= box_width and th <= box_height:
            best_font = font
            lo = mid + 1
        else:
            hi = mid - 1

    return best_font


def render_translation_texture(
    ocr_results: List[Tuple],
    translations: List[str],
    capture_size: Tuple[int, int],
) -> np.ndarray:
    """Render translated text at original bounding box positions.

    Returns RGBA numpy array — transparent everywhere except where
    text was detected. There, off-white boxes with translated text
    cover the original.

    Args:
        ocr_results: List of (bbox, original_text, confidence)
        translations: List of translated strings, same order
        capture_size: (width, height) of the capture region in pixels

    Returns:
        RGBA numpy array of shape (height, width, 4)
    """
    from PIL import Image, ImageDraw

    w, h = capture_size
    # Fully transparent base — only text areas are visible
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    bg_color = (245, 240, 235, 240)   # Off-white, easy on eyes, nearly opaque
    text_color = (30, 30, 30, 255)     # Near-black text

    for (bbox, original, conf), translated in zip(ocr_results, translations):
        # bbox = [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] (corners)
        x_min = int(min(p[0] for p in bbox))
        y_min = int(min(p[1] for p in bbox))
        x_max = int(max(p[0] for p in bbox))
        y_max = int(max(p[1] for p in bbox))

        box_w = x_max - x_min
        box_h = y_max - y_min
        if box_w <= 0 or box_h <= 0:
            continue

        # Background rect covering original text
        padding = 4
        draw.rectangle(
            [x_min - padding, y_min - padding, x_max + padding, y_max + padding],
            fill=bg_color
        )

        # Fit translated text into bounding box
        font = fit_font_to_box(translated, box_w, box_h)
        draw.text((x_min, y_min), translated, font=font, fill=text_color)

    logger.debug(f"[ocr_renderer] Rendered {len(translations)} translated blocks on {w}x{h} texture")
    return np.array(img)
