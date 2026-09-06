"""Repair text extracted from PDFs that embed the Adobe *Symbol* font.

Such PDFs (CIE papers among them) store Greek letters and maths operators as
Private-Use-Area code points U+F020-U+F0FF -- the Symbol glyph's byte value plus
0xF000. PyMuPDF passes these through unchanged, so ``3.00 x 10^8`` comes out as
``3.00 <U+F0B4> 10^8``.

``normalise`` maps the standard Symbol table back to real Unicode and drops any
remaining PUA code point (usually a fragment of a large bracket) so nothing
mojibake-looking survives into the search index.
"""

from __future__ import annotations

_PUA_LO = 0xF000
_PUA_HI = 0xF0FF

# Adobe Symbol encoding -> Unicode, keyed by (code point - 0xF000).
_SYMBOL: dict[int, str] = {
    0x22: "∀",  # for all
    0x24: "∃",  # there exists
    0x27: "∋",  # contains as member
    0x2D: "−",  # minus
    0x40: "≅",  # approximately equal
    0x41: "Α",
    0x42: "Β",
    0x43: "Χ",
    0x44: "Δ",
    0x45: "Ε",
    0x46: "Φ",
    0x47: "Γ",
    0x48: "Η",
    0x49: "Ι",
    0x4A: "ϑ",
    0x4B: "Κ",
    0x4C: "Λ",
    0x4D: "Μ",
    0x4E: "Ν",
    0x4F: "Ο",
    0x50: "Π",
    0x51: "Θ",
    0x52: "Ρ",
    0x53: "Σ",
    0x54: "Τ",
    0x55: "Υ",
    0x56: "ς",
    0x57: "Ω",
    0x58: "Ξ",
    0x59: "Ψ",
    0x5A: "Ζ",
    0x61: "α",
    0x62: "β",
    0x63: "χ",
    0x64: "δ",
    0x65: "ε",
    0x66: "φ",
    0x67: "γ",
    0x68: "η",
    0x69: "ι",
    0x6A: "ϕ",
    0x6B: "κ",
    0x6C: "λ",
    0x6D: "μ",
    0x6E: "ν",
    0x6F: "ο",
    0x70: "π",
    0x71: "θ",
    0x72: "ρ",
    0x73: "σ",
    0x74: "τ",
    0x75: "υ",
    0x76: "ϖ",
    0x77: "ω",
    0x78: "ξ",
    0x79: "ψ",
    0x7A: "ζ",
    0xA3: "≤",  # <=
    0xA5: "∞",  # infinity
    0xAB: "↔",
    0xAC: "←",
    0xAD: "↑",
    0xAE: "→",
    0xAF: "↓",
    0xB0: "°",  # degree
    0xB1: "±",  # plus-minus
    0xB2: "″",  # double prime
    0xB3: "≥",  # >=
    0xB4: "×",  # multiplication
    0xB5: "∝",  # proportional to
    0xB6: "∂",  # partial differential
    0xB7: "·",  # middle dot
    0xB8: "÷",  # division
    0xB9: "≠",  # not equal
    0xBA: "≡",  # identical to
    0xBB: "≈",  # approximately equal
    0xD6: "√",  # square root
    0xD7: "·",  # dot operator
    0xE5: "∑",  # n-ary summation
    0xF2: "∫",  # integral
}


def normalise(text: str) -> str:
    if all(not (_PUA_LO <= ord(ch) <= _PUA_HI) for ch in text):
        return text
    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if _PUA_LO <= code <= _PUA_HI:
            out.append(_SYMBOL.get(code - _PUA_LO, ""))  # drop unknown PUA glyphs
        else:
            out.append(ch)
    return "".join(out)
