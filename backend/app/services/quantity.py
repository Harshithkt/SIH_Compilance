"""Parsing and normalising the net quantity declaration.

Several provisions turn on the declared quantity rather than on its presence:

  - Rule 7(2) with Table I — the minimum height of numerals depends on whether the net
    quantity is up to 200 g/ml, 200-500 g/ml, or above 500 g/ml.
  - Rule 13(2) and 13(3) — quantities below one kilogram must be expressed in grams,
    at or above one kilogram in kilograms, and so on for length and volume.
  - Rule 26(a) — packages of ten gram or ten millilitre or less are exempt altogether,
    and packages from 10-20 g/ml need only price and quantity.
  - Rule 3(a) — Chapter II does not apply above 25 kg / 25 litre.

So the quantity has to be read as a number and a unit, not just matched as text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# unit -> (dimension, multiplier to the base unit: gram, millilitre, centimetre, count)
UNITS: dict[str, tuple[str, float]] = {
    "mg": ("mass", 0.001),
    "g": ("mass", 1.0),
    "gm": ("mass", 1.0),
    "gms": ("mass", 1.0),
    "gram": ("mass", 1.0),
    "grams": ("mass", 1.0),
    "kg": ("mass", 1000.0),
    "kgs": ("mass", 1000.0),
    "kilogram": ("mass", 1000.0),
    "ml": ("volume", 1.0),
    "millilitre": ("volume", 1.0),
    "milliliter": ("volume", 1.0),
    "cl": ("volume", 10.0),
    "l": ("volume", 1000.0),
    "ltr": ("volume", 1000.0),
    "litre": ("volume", 1000.0),
    "liter": ("volume", 1000.0),
    "litres": ("volume", 1000.0),
    "mm": ("length", 0.1),
    "cm": ("length", 1.0),
    "m": ("length", 100.0),
    "metre": ("length", 100.0),
    "meter": ("length", 100.0),
    "n": ("number", 1.0),
    "u": ("number", 1.0),
}

# Rule 13(4): these counting words may not be used on a package at all.
FORBIDDEN_COUNT_WORDS = ("dozen", "score", "gross", "great gross")

# Rule 12(6): expressions that create an exaggerated or inadequate impression of quantity.
FORBIDDEN_QUANTITY_QUALIFIERS = ("minimum", "not less than", "about", "approx", "approximately")

QUANTITY_PATTERN = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>" + "|".join(sorted(UNITS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


@dataclass
class Quantity:
    value: float
    unit: str
    dimension: str  # mass | volume | length | number
    base_value: float  # in gram / millilitre / centimetre / count

    @property
    def is_weight_or_volume(self) -> bool:
        return self.dimension in ("mass", "volume")


def parse(declaration: str | None) -> Quantity | None:
    if not declaration:
        return None
    match = QUANTITY_PATTERN.search(declaration)
    if not match:
        return None

    unit = match.group("unit").lower()
    dimension, multiplier = UNITS[unit]
    try:
        value = float(match.group("value").replace(",", "."))
    except ValueError:
        return None

    return Quantity(
        value=value, unit=unit, dimension=dimension, base_value=value * multiplier
    )


def correct_unit_form(quantity: Quantity) -> tuple[bool, str]:
    """Rule 13(2) and 13(3): which unit the quantity should have been expressed in.

    Below one kilogram the unit is the gram; at or above, the kilogram. Below one litre
    the millilitre; at or above, the litre. Below one metre the centimetre.
    """
    unit = quantity.unit.lower()

    if quantity.dimension == "mass":
        if quantity.base_value < 1000:
            ok = unit in ("g", "gm", "gms", "gram", "grams", "mg")
            return ok, "grams (Rule 13(2)(a): below one kilogram the unit is the gram)"
        ok = unit in ("kg", "kgs", "kilogram")
        return ok, "kilograms (Rule 13(3)(a): at or above one kilogram the unit is the kilogram)"

    if quantity.dimension == "volume":
        if quantity.base_value < 1000:
            ok = unit in ("ml", "millilitre", "milliliter", "cl")
            return ok, "millilitres (Rule 13(2)(f): below one litre the unit is the millilitre)"
        ok = unit in ("l", "ltr", "litre", "liter", "litres")
        return ok, "litres (Rule 13(3)(e): at or above one litre the unit is the litre)"

    if quantity.dimension == "length":
        if quantity.base_value < 100:
            ok = unit in ("cm", "mm")
            return ok, "centimetres (Rule 13(2)(b): below one metre the unit is the centimetre)"
        ok = unit in ("m", "metre", "meter")
        return ok, "metres (Rule 13(3)(b): at or above one metre the unit is the metre)"

    return True, ""


def minimum_numeral_height_mm(quantity: Quantity | None, blown_or_embossed: bool = False) -> float | None:
    """Rule 7(2) with the Second Schedule's Table I, for quantities by weight or volume.

    | net quantity        | normal | blown/formed/moulded/embossed/perforated |
    | up to 200 g/ml      |  1 mm  |  2 mm |
    | 200 up to 500 g/ml  |  2 mm  |  4 mm |
    | above 500 g/ml      |  4 mm  |  6 mm |
    """
    if quantity is None or not quantity.is_weight_or_volume:
        return None

    if quantity.base_value <= 200:
        return 2.0 if blown_or_embossed else 1.0
    if quantity.base_value <= 500:
        return 4.0 if blown_or_embossed else 2.0
    return 6.0 if blown_or_embossed else 4.0


def exemption(quantity: Quantity | None) -> str | None:
    """Rule 26(a) and Rule 3(a): whether the package falls outside these provisions.

    Returns 'exempt' (nothing required), 'price_and_quantity_only' (the 10-20 g/ml
    proviso), 'out_of_scope' (above 25 kg/litre, Rule 3(a)), or None.
    """
    if quantity is None or not quantity.is_weight_or_volume:
        return None

    if quantity.base_value <= 10:
        return "exempt"
    if quantity.base_value <= 20:
        return "price_and_quantity_only"
    if quantity.base_value > 25000:
        return "out_of_scope"
    return None
