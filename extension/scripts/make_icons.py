"""Generate toolbar icons using only the five approved colors.

Each size is drawn directly (no resampling) so no blended/half-tone colors
can appear in the PNGs.
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "icons"
KYOTO = "#5B5F8D"
MATCHA = "#9BB29E"
TERRACOTTA = "#DA6B51"
VANILLA = "#F1DCBA"
CHARCOAL = "#484149"
PALETTE = {KYOTO, MATCHA, TERRACOTTA, VANILLA, CHARCOAL}


def scaled(value: float, size: int) -> float:
    return value * size / 512


def width(value: float, size: int) -> int:
    return max(1, round(scaled(value, size)))


def box(values: list[float], size: int) -> list[float]:
    return [scaled(value, size) for value in values]


def make(size: int) -> Image.Image:
    image = Image.new("RGB", (size, size), VANILLA)
    draw = ImageDraw.Draw(image)

    # Handle behind the cup.
    draw.arc(
        box([335, 230, 445, 355], size),
        start=270,
        end=90,
        fill=CHARCOAL,
        width=width(18, size),
    )
    draw.rounded_rectangle(
        box([105, 190, 365, 395], size),
        radius=max(1, round(scaled(40, size))),
        fill=KYOTO,
        outline=CHARCOAL,
        width=width(18, size),
    )
    draw.line(
        [scaled(85, size), scaled(415, size), scaled(385, size), scaled(415, size)],
        fill=CHARCOAL,
        width=width(16, size),
    )
    draw.line(
        [scaled(185, size), scaled(150, size), scaled(185, size), scaled(95, size)],
        fill=TERRACOTTA,
        width=width(14, size),
    )
    draw.line(
        [scaled(260, size), scaled(155, size), scaled(260, size), scaled(90, size)],
        fill=MATCHA,
        width=width(14, size),
    )

    pixels = (
        image.get_flattened_data()
        if hasattr(image, "get_flattened_data")
        else image.getdata()
    )
    actual = {f"#{r:02X}{g:02X}{b:02X}" for r, g, b in pixels}
    assert actual <= PALETTE, f"icon {size} uses off-palette colors: {sorted(actual - PALETTE)}"
    return image


OUT.mkdir(parents=True, exist_ok=True)
for dimension in (16, 32, 48, 128):
    make(dimension).save(OUT / f"cup{dimension}.png")
print(f"icons -> {OUT} (5 colors only)")
