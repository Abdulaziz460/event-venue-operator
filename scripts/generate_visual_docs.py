#!/usr/bin/env python3
"""Generate synthetic visual documents for the Vision RAG demo.

Run:
    uv run python scripts/generate_visual_docs.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


DOCS_DIR = Path(__file__).resolve().parents[1] / "static" / "docs"


def _fonts():
    try:
        return (
            ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 30),
            ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22),
        )
    except OSError:
        return ImageFont.load_default(), ImageFont.load_default()


FONT_BOLD, FONT = _fonts()


def _create_doc(
    title: str,
    rows: list[tuple[str, str, str]],
    filename: str,
    subtitle: str | None = None,
) -> None:
    """Create a simple operational-document image."""
    img = Image.new("RGB", (1200, 850), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 1200, 95], fill="#0f172a")
    draw.text((45, 28), title, font=FONT_BOLD, fill="white")

    y = 125
    if subtitle:
        draw.text((45, y), subtitle, font=FONT, fill="#334155")
        y += 55

    for label, body, color in rows:
        draw.rounded_rectangle(
            [45, y, 1155, y + 92],
            radius=12,
            fill=color,
            outline="#94a3b8",
            width=2,
        )
        draw.text((70, y + 16), label, font=FONT_BOLD, fill="#111827")
        draw.text((300, y + 18), body, font=FONT, fill="#111827")
        y += 112

    img.save(DOCS_DIR / filename, quality=92)


def create_allergen_matrix() -> None:
    _create_doc(
        "Premier Tennis Dining Allergen Matrix",
        [
            ("Baseline Cafe", "Peanut-free yes | Gluten-free yes | Dairy-free limited", "#dbeafe"),
            ("Champions Dining", "Peanut-free yes | Shellfish-free yes | Gluten-free limited", "#dcfce7"),
            ("Premier Club", "Tree nut-free limited | Gluten-free yes | Dairy-free yes", "#ede9fe"),
            ("Food Village", "Peanut-free limited | Best for packaged snacks only", "#fef3c7"),
            ("Garden Pavilion", "Peanut-free yes | Tree nut-free yes | Dairy-free yes", "#ccfbf1"),
        ],
        "allergen_matrix.jpg",
        "Use for dietary routing during rain-delay hospitality moves.",
    )


def create_accessibility_map() -> None:
    _create_doc(
        "Covered and Accessible Routes During Rain Delay",
        [
            ("Main Gate", "Step-free route to Centre Court and information desk", "#dbeafe"),
            ("Centre Court", "Covered route to Court 1 and Premier Club Lounge", "#dcfce7"),
            ("Court 2", "Outdoor exposure risk; redirect before rain starts", "#fee2e2"),
            ("Covered Practice", "Best first-timer redirect for Mikiko", "#fef3c7"),
            ("Champions Lounge", "Best premier redirect for Nina", "#ede9fe"),
        ],
        "accessibility_map.jpg",
        "Covered or step-free paths only.",
    )


def create_hospitality_capacity() -> None:
    _create_doc(
        "Covered Hospitality and Shelter Capacity",
        [
            ("Champions Lounge", "120 seats available | Premier guests prioritized", "#ede9fe"),
            ("Premier Club", "80 seats available | Covered seating", "#dbeafe"),
            ("Covered Practice", "65 spaces | First-timer friendly", "#dcfce7"),
            ("Baseline Cafe", "48 indoor seats | Allergy-aware menu", "#ccfbf1"),
            ("Food Village", "25 covered spaces only | avoid during heavy rain", "#fee2e2"),
        ],
        "height_requirements.jpg",
        "Filename retained for compatibility; content is venue capacity.",
    )


def create_weather_response() -> None:
    _create_doc(
        "Rain Delay Response Protocol",
        [
            ("90 min out", "Detect rain forecast; retrieve weather and routing memories", "#dbeafe"),
            ("Mikiko", "Send one clear route to Covered Practice Court", "#dcfce7"),
            ("Nina", "Protect covered seat and Champions Dining window", "#ede9fe"),
            ("30 min out", "Move outdoor-court guests toward covered zones", "#fef3c7"),
            ("After action", "Write accepted routing and booking outcomes back to memory", "#ccfbf1"),
        ],
        "weather_response.jpg",
    )


def create_evacuation_zones() -> None:
    _create_doc(
        "Premier Tennis Evacuation and Shelter Zones",
        [
            ("Zone A", "Centre Court -> North Gate", "#dbeafe"),
            ("Zone B", "Court 1 and Court 2 -> East Gate", "#dcfce7"),
            ("Zone C", "Food Village -> South Gate", "#fef3c7"),
            ("Zone D", "Hospitality suites -> West Gate", "#ede9fe"),
            ("Zone E", "Practice courts -> Main Gate", "#ccfbf1"),
        ],
        "evacuation_zones.jpg",
        "For lightning risk, shelter first; evacuate by nearest signed gate if instructed.",
    )


def main() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    create_allergen_matrix()
    create_accessibility_map()
    create_hospitality_capacity()
    create_weather_response()
    create_evacuation_zones()
    print("Generated visual documents in static/docs")


if __name__ == "__main__":
    main()
