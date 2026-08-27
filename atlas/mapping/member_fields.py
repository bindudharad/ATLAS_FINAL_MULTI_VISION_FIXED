"""Member-field schema: the authoritative "what counts as a source record field".

The real MPF left panel renders ONLY two data sections - "Member Basic
Information" and "Religious and Astro Information" - plus a bunch of UI
chrome that must never become a source field: "Project Details" (Pro No,
S Date, E Date, Total, Minimum, Finish, Balance), "Shift Details"
(Shift/From/To), a live timer ("elapsed"/"progress"/"00"/system
dates) and the Upload button. Prior parsers paired all of it, which is why a
real run produced "48 paired rows" and a 9% mapping coverage that blocked
submit.

This module is the single gate:

* section headers decide which OCR/UIA lines are member data,
* "resolve_member_field" maps a raw label to a canonical member field with
  exact + alias + typo-tolerant matching (labels only, never values),
* "REQUIRED_MEMBER_FIELDS" / "OPTIONAL_MEMBER_FIELDS" drive coverage so
  an absent optional field (e.g. "RAI Code") never blocks a record,
* "filter_member_pairs" drops every pair whose label is not a member field.

Aliases cover the spellings seen in the real recording ("DOB", "Cast",
"SubCast", "Genlder", "SubCaste", "Date Of Birth", ...).
"""

from __future__ import annotations

import re

try:  # rapidfuzz is already a hard dependency (used by atlas.mapping.mapper)
    from rapidfuzz import fuzz
except Exception:  # pragma: no cover - defensive
    fuzz = None  # type: ignore[assignment]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


#: Section headers whose lines ARE member data.
MEMBER_SECTION_HEADERS = frozenset({
    "member basic information",
    "religious and astro information",
    "physical and habits information",
    "family information",
    "education and career information",
})

#: Section headers whose lines are project/shift/timer chrome, never fields.
IGNORED_SECTION_HEADERS = frozenset({
    "project details",
    "shift details",
    "upload details",
    "physical and habits information",
    "family information",
    "education and career information",
})

_MEMBER_SECTION_NORMS = frozenset(_norm(h) for h in MEMBER_SECTION_HEADERS)
_IGNORED_SECTION_NORMS = frozenset(_norm(h) for h in IGNORED_SECTION_HEADERS)

#: Canonical member field names (exact as shown on the MPF panel).
MEMBER_FIELDS = (
    "App No",
    "MBI Code",
    "Full Name",
    "Gender",
    "Date Of Birth",
    "Marital Status",
    "State",
    "District",
    "Taluk",
    "Pincode",
    "House Type",
    "RAI Code",
    "Mother Tongue",
    "Religion",
    "Caste",
    "Sub Caste",
    "Nakshatra",
    "Rashi",
    "Pada",
)

#: Normalized canonical field -> typo-tolerance candidates.
_MEMBER_KEYS = tuple(_norm(key) for key in MEMBER_FIELDS)
_MEMBER_KEYS_TO_CANONICAL = {_norm(key): key for key in MEMBER_FIELDS}
_TYPO_MIN_RATIO = 82

#: Status-bar words the real MPF shows as ALL-LOWERCASE labels.
CHROME_STATUS_LABELS = frozenset({
    "state", "mode", "progress", "elapsed", "upload", "status", "ready", "timer",
})

def section_of(header: str) -> str | None:
    """Return "member" | "ignored" | None for a section header line.
    
    "None" means the line is not a recognised section header at all (a
    field row, an instruction, or unknown chrome).
    """
    norm = _norm(header)
    if norm in _MEMBER_SECTION_NORMS:
        return "member"
    if norm in _IGNORED_SECTION_NORMS:
        return "ignored"
    return None


def resolve_member_field(label: str) -> str | None:
    """Resolve a raw source label to a canonical member field name.

    Exact normalised match first, then the alias dictionary, then typo
    tolerance against the canonical field names. Values are NEVER matched -
    only labels. Returns the canonical name ("Date Of Birth", ...) or
    None when the label is not a member field.
    """
    if not label:
        return None
    # Chrome/status labels (all-lowercase words from the MPF status bar)
    # must never match member fields even if they share a normalized form.
    # e.g. "state" (status bar) != "State" (member field).
    # Check original label (case-sensitive) against chrome labels first.
    if label in CHROME_STATUS_LABELS:
        return None
    norm = _norm(label)
    if not norm:
        return None
    if norm in _MEMBER_KEYS_TO_CANONICAL:
        return _MEMBER_KEYS_TO_CANONICAL[norm]
    canonical = MEMBER_FIELD_ALIASES.get(norm)
    if canonical:
        return canonical
    if fuzz is not None and len(norm) >= 4:
        best, best_ratio = None, 0.0
        for key in _MEMBER_KEYS:
            if len(key) < 3:
                continue
            ratio = fuzz.ratio(norm, key)
            if ratio > best_ratio:
                best, best_ratio = key, ratio
        if best is not None and best_ratio >= _TYPO_MIN_RATIO:
            return _MEMBER_KEYS_TO_CANONICAL[best]
    return None


def is_member_field(label: str) -> bool:
    return resolve_member_field(label) is not None


def filter_member_pairs(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Keep only pairs whose label resolves to a canonical member field.

    This is the concrete fix for "36 left labels -> 48 paired rows -> 9%
    coverage": every Project/Shift/timer/button row ("Pro No", "Shift",
    "Progress", ...) is dropped before it ever reaches the mapper.
    """
    return [(l, v) for l, v in pairs if resolve_member_field(l)]


#: Normalized aliases for member field labels.
MEMBER_FIELD_ALIASES: dict[str, str] = {
    "appno": "App No",
    "applicationno": "App No",
    "applicationnumber": "App No",
    "application": "App No",
    "mbicode": "MBI Code",
    "mbino": "MBI Code",
    "membercode": "MBI Code",
    "fullname": "Full Name",
    "applicantname": "Full Name",
    "name": "Full Name",
    "gender": "Gender",
    "genlder": "Gender",  # real OCR typo on the MPF panel
    "sex": "Gender",
    "dateofbirth": "Date Of Birth",
    "dob": "Date Of Birth",
    "birthdate": "Date Of Birth",
    "birthday": "Date Of Birth",
    "d.o.b": "Date Of Birth",
    "maritalstatus": "Marital Status",
    "state": "State",
    "district": "District",
    "taluk": "Taluk",
    "taluka": "Taluk",
    "pincode": "Pincode",
    "pincodeno": "Pincode",
    "zip": "Pincode",
    "postalcode": "Pincode",
    "housetype": "House Type",
    "typeofhouse": "House Type",
    "raicode": "RAI Code",
    "rai": "RAI Code",
    "mothertongue": "Mother Tongue",
    "mothertoungue": "Mother Tongue",  # common OCR transposition
    "motherlanguage": "Mother Tongue",
    "religion": "Religion",
    "caste": "Caste",
    "cast": "Caste",  # the MPF panel spells it "Cast"
    "subcaste": "Sub Caste",
    "subcast": "Sub Caste",  # the MPF panel spells it "SubCast"
    "subcaste": "Sub Caste",
    "sub-caste": "Sub Caste",
    "nakshatra": "Nakshatra",
    "nakshathra": "Nakshatra",
    "star": "Nakshatra",
    "rashi": "Rashi",
    "rasi": "Rashi",
    "raasi": "Rashi",
    "zodiac": "Rashi",
    "moonsign": "Rashi",
    "pada": "Pada",
    "paada": "Pada",
}

#: Required member fields - missing one of these blocks record coverage.
REQUIRED_MEMBER_FIELDS = frozenset({
    "App No",
    "MBI Code",
    "Full Name",
    "Gender",
    "Date Of Birth",
    "Marital Status",
    "State",
    "District",
    "Taluk",
    "Pincode",
    "House Type",
})

#: Optional member fields - missing these does NOT block coverage.
OPTIONAL_MEMBER_FIELDS = frozenset({
    "RAI Code",
    "Mother Tongue",
    "Religion",
    "Caste",
    "Sub Caste",
    "Nakshatra",
    "Rashi",
    "Pada",
})


__all__ = [
    "section_of",
    "resolve_member_field",
    "is_member_field",
    "filter_member_pairs",
    "MEMBER_FIELD_ALIASES",
    "MEMBER_FIELDS",
    "REQUIRED_MEMBER_FIELDS",
    "OPTIONAL_MEMBER_FIELDS",
    "CHROME_STATUS_LABELS",
]
