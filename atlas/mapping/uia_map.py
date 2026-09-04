"""UI Automation field mapping.

Builds a ``UiaFieldMap`` that bridges the agent's loop to the exact UI
Automation structure of a native form:

* ``start_control`` - the first editable control the user clicked (anchor).
* ``left_labels``   - static text controls in the LEFT (source) panel.
* ``right_fields``  - editable controls in the RIGHT (form) panel.
* ``upload_button`` - the button that submits/upload the form.
* ``mappings``      - LEFT label -> RIGHT field name pairs (UIA relationships).

The map is written to ``debug/mpf/field_map.json`` and used by the loop to
synthesise scene elements so SourceReader / field discovery / mapping / the
planner never depend on the VLM for exact form geometry.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from dataclasses import field as dc_field
from pathlib import Path
from typing import Any

from atlas.core.logging import logger
from atlas.mapping.mapper import SemanticMapper, normalize_label
from atlas.mapping.member_fields import section_of
from atlas.observe.uia import ScrollContainer, UiaBackend, UiaNode
from atlas.observe.uia import FORM_FIELD_CONTROL_TYPES
from atlas.vision.models import BBox, ElementType

#: Application-chrome / status text that must never be treated as a source
#: record value, no matter where it is found in the UIA tree or OCR output.
#: This is the concrete fix for source-data contamination: real runs have
#: shown strings like "Collapse", "Exit", "[F12] Debug OFF" and section
#: headers ending up as "source labels" purely because a UIA static-text node
#: happened to sit in the left panel. These never come from the record.
NOISE_LABELS_EXACT = {
    "collapse", "expand", "exit", "close", "log", "debug", "f12", "esc",
    "workflow start", "workflow", "click here", "loading", "please wait",
    "record", "ecord", "field", "menu", "toolbar", "status", "console",
}

#: Patterns/values that are commonly seen as FIELD VALUES on the MPF source panel.
KNOWN_VALUE_PATTERNS = (
    "andhra", "arunachal", "assam", "bihar", "chhattisgarh", "goa", "gujarat", 
    "haryana", "himachal", "jharkhand", "karnataka", "kerala", "madhya", "maharashtra",
    "manipur", "meghalaya", "mizoram", "nagaland", "odisha", "punjab", "rajasthan",
    "sikkim", "tamil", "telangana", "tripura", "uttar", "uttarakhand", "bengal",
    "delhi", "chandigarh", "lakshadweep", "puducherry", "ladakh", "jammu",
    "chamar", "turi", "mittal", "kayast", "brahmin", "rajput", "yadav", "gupta",
    "agarwal", "sharma", "singh", "kumar", "devi", "prasad", "das", "pandey",
    "hindu", "muslim", "christian", "sikh", "buddhist", "jain", "parsi",
    "hindi", "bengali", "telugu", "marathi", "tamil", "urdu", "gujarati",
    "kannada", "malayalam", "punjabi", "odia", "assamese", "maithili",
    "never married", "married", "divorced", "widowed", "single", "separated",
    "uttara", "phalguni", "uthram", "palkuni", "rohini", "mrigashira", "ardra",
    "punarvasu", "pushya", "ashlesha", "magha", "purva", "hasta",
    "chitra", "swati", "vishakha", "anuradha", "jyeshtha", "mula", "purvashada",
    "uttarashada", "shravana", "dhanishta", "shatabhisha", "purvabhadra", "uttarabhadra",
    "revati", "ashwini", "bharani", "krittika",
    "simha", "leo", "mesha", "aries", "vrishabha", "taurus", "mithuna", "gemini",
    "karka", "cancer", "kanya", "virgo", "tula", "libra", "vrishchika", "scorpio",
    "dhanu", "sagittarius", "makara", "capricorn", "kumbha", "aquarius", "meena", "pisces",
    "1st pada", "2nd pada", "3rd pada", "4th pada", "1st", "2nd", "3rd", "4th",
    "male", "female", "other", "transgender",
    "own", "rent", "rented", "lease", "ancestral",
    "veg", "vegetarian", "non-veg", "nonveg", "non vegetarian", "eggetarian",
    "no health problems", "healthy", "none", "normal",
    "alive", "passed away", "deceased", "expired",
    "defence", "civil", "services", "salaried", "self-employed", "student", "retired",
    "unemployed", "business", "professional", "housewife",
    "lakh", "crore", "annually", "monthly",
)


def is_likely_value(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    if not t:
        return False
    if re.search(r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}", t):
        return True
    if re.search(r"\d{1,2}:\d{2}:\d{2}", t):
        return True
    if t in KNOWN_VALUE_PATTERNS:
        return True
    if t.endswith(("lakh", "crore", "kg", "cm", "ft", "in", "annually", "monthly")):
        return True
    if re.fullmatch(r"[\d,./: -]+", t):
        return True
    if t == t.lower() and len(t) < 20 and not any(c.isupper() for c in text):
        known_short_labels = {"dob", "pan", "mbi", "rai", "app", "age", "sex", "f", "m"}
        if t not in known_short_labels:
            return True
    return False


def is_noise_or_value_label(text: str) -> bool:
    return is_noise_label(text) or is_likely_value(text)


#: Section headers in the MPF-style form. These group fields; they are never
#: themselves a label/value pair.
NOISE_SECTION_HEADERS = {
    "member basic information",
    "religious and astro information",
    "physical and habits information",
    "family information",
    "education and career information",
    "upload details",
}

#: Instructional / toast / status sentences seen contaminating the source
#: panel in real runs. Matched as substrings (case-insensitive) since OCR/UIA
#: often truncates or pads them.
NOISE_PHRASE_FRAGMENTS = (
    "click the first",
    "left side refreshed",
    "form reset",
    "debug off",
    "debug on",
    "waiting for you to click",
    "anchor accepted",
    "attach mode",
)


def is_noise_label(label: str) -> bool:
    """True if ``label`` is application UI chrome, not a real source field.

    Applied everywhere a candidate (label, value) pair is about to enter a
    ``SourceRecord`` - this is the single choke point that keeps toolbar
    text, section headers, and status/instructional strings out of the data
    pipeline (see NOISE_LABELS_EXACT / NOISE_SECTION_HEADERS /
    NOISE_PHRASE_FRAGMENTS above).
    """
    if not label:
        return True
    norm = re.sub(r"\s+", " ", label).strip().lower()
    if not norm:
        return True
    if norm in NOISE_LABELS_EXACT:
        return True
    if norm in NOISE_SECTION_HEADERS:
        return True
    for frag in NOISE_PHRASE_FRAGMENTS:
        if frag in norm:
            return True
    # Heuristic: real field labels are short noun phrases ("Full Name",
    # "Mother Tongue", "App No"). A long run-on sentence (many words, ending
    # in punctuation typical of a status message) is UI chrome, not a label.
    words = norm.split(" ")
    if len(words) >= 6 and (norm.endswith((".", "!", "…")) or ";" in norm or "—" in label or "-- " in label):
        return True
    return False


UPLOAD_LABELS = ("upload", "submit", "save", "next", "ok", "apply", "create", "register", "done", "finish", "confirm")

#: Strong upload verbs outrank weak confirmation words like "OK"/"Done".
STRONG_UPLOAD_LABELS = {"upload", "submit", "create", "register", "finish", "confirm", "apply"}
WEAK_UPLOAD_LABELS = {"save", "next", "ok", "done", "add"}


@dataclass
class UiaFieldMap:
    """Snapshot of a native form's UIA structure plus its mapping."""

    start_control: UiaNode | None = None
    left_labels: list[UiaNode] = dc_field(default_factory=list)
    right_fields: list[UiaNode] = dc_field(default_factory=list)
    upload_button: UiaNode | None = None
    left_rect: BBox | None = None
    right_rect: BBox | None = None
    scroll_containers: list[ScrollContainer] = dc_field(default_factory=list)
    mappings: list[dict[str, str]] = dc_field(default_factory=list)
    client_origin: tuple[int, int] = (0, 0)
    client_size: tuple[int, int] = (0, 0)

    @property
    def has_form(self) -> bool:
        return bool(self.right_fields)

    @property
    def has_source(self) -> bool:
        return bool(self.left_labels)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_control": self.start_control.to_dict() if self.start_control else None,
            "left_labels": [n.to_dict() for n in self.left_labels],
            "right_fields": [n.to_dict() for n in self.right_fields],
            "upload_button": self.upload_button.to_dict() if self.upload_button else None,
            "left_rect": self.left_rect.to_dict() if self.left_rect else None,
            "right_rect": self.right_rect.to_dict() if self.right_rect else None,
            "scroll_containers": [c.to_dict() for c in self.scroll_containers],
            "mappings": list(self.mappings),
            "client_origin": list(self.client_origin),
            "client_size": list(self.client_size),
        }

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        logger.info("field map saved to {}", path)

    @classmethod
    def load(cls, path: str | Path) -> UiaFieldMap | None:
        path = Path(path)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("field map {} unreadable: {}", path, exc)
            return None
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UiaFieldMap:
        def _node(raw: dict[str, Any] | None) -> UiaNode | None:
            if not raw:
                return None
            return UiaNode(
                name=raw.get("name", ""),
                control_type=raw.get("control_type", ""),
                automation_id=raw.get("automation_id", ""),
                class_name=raw.get("class_name", ""),
                parent=raw.get("parent"),
                handle=raw.get("handle"),
                rect=_rect(raw.get("rect")),
                value=raw.get("value"),
                enabled=raw.get("enabled", True),
                visible=raw.get("visible", True),
                password=raw.get("password", False),
                options=list(raw.get("options") or []),
                type_override=_parse_element_type(raw.get("type_override")),
            )

        def _rect(raw: dict[str, Any] | list[int] | None) -> BBox | None:
            if isinstance(raw, dict):
                return BBox.from_dict(raw)
            if isinstance(raw, (list, tuple)) and len(raw) >= 4:
                return BBox(int(raw[0]), int(raw[1]), int(raw[2]), int(raw[3]))
            return None

        return cls(
            start_control=_node(data.get("start_control")),
            left_labels=[_node(n) for n in data.get("left_labels") or []],
            right_fields=[_node(n) for n in data.get("right_fields") or []],
            upload_button=_node(data.get("upload_button")),
            left_rect=_rect(data.get("left_rect")),
            right_rect=_rect(data.get("right_rect")),
            scroll_containers=[
                ScrollContainer.from_dict(c) for c in (data.get("scroll_containers") or [])
            ],
            mappings=list(data.get("mappings") or []),
            client_origin=tuple(data.get("client_origin") or (0, 0)),
            client_size=tuple(data.get("client_size") or (0, 0)),
        )


class UiaFieldMapBuilder:
    """Builds a :class:`UiaFieldMap` from a window handle + start control."""

    def __init__(
        self,
        backend: UiaBackend | None = None,
        declared_fields: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._backend = backend or UiaBackend.instance()
        self._declared_fields = declared_fields or {}

    def build(self, hwnd: int, start_control: UiaNode | None = None, light: bool = False) -> UiaFieldMap:
        """Build a :class:`UiaFieldMap` from a window handle + start control.

        ``light=True`` is the position-refresh path: it re-reads editable
        fields / buttons / text labels from ONE flat descendants walk but skips
        the independent scroll-container discovery traversal. The loop's scroll
        session is discovered separately (and cached) by the scroller provider,
        so per-scroll refreshes never re-find containers; ``left_rect`` /
        ``left_labels`` stay intact for source reading.
        """
        origin = self._backend.client_origin(hwnd)
        size = self._backend.client_size(hwnd)
        mid_x = origin[0] + size[0] // 2

        # ONE flat UIA walk feeds editable / text / button discovery (they used
        # to each re-walk the full ~260-node tree, tripling the map-build cost).
        # ``descendants`` is the same pywinauto flat walk all three used, so the
        # derived sets are identical to before - only the walk count changes.
        # Backends without ``descendants`` (test fakes) fall back to the old
        # per-method walks via ``nodes=None``.
        _walk = getattr(self._backend, "descendants", None)
        nodes = _walk(hwnd) if callable(_walk) else None
        if nodes is not None:
            editable = self._backend.editable_fields(hwnd, nodes=nodes)
        else:
            editable = self._backend.editable_fields(hwnd)
        # editable_fields already does the recursive fallback internally.
        # FORM-FIELD filter: drop the container-ish editable types (List /
        # ListItem / DataGrid / DataItem / Tree / TreeItem) whenever any genuine
        # leaf widget exists - a popup/table/repeater over-walk is what turned
        # the observed 37-field map into a 2413-field explosion, and leaf fields
        # are all a form fill needs.
        form_fields = [n for n in editable if n.control_type in FORM_FIELD_CONTROL_TYPES]
        if form_fields:
            editable = form_fields
        FORM_FIELD_TYPES = {"Edit", "ComboBox", "List", "ListItem", "DataItem", "TreeItem"}
        right_fields = [
            n for n in editable
            if n.rect is not None 
            and n.rect.center[0] >= mid_x
            and n.control_type in FORM_FIELD_TYPES
        ]
        if not right_fields:
            right_fields = [n for n in editable if n.rect is not None and n.rect.center[0] >= mid_x]
        right_fields = [self._attach_declared(n, hwnd) for n in right_fields]

        # CRITICAL FIX: Associate right fields with their left-side labels
        # The UIA "name" of ComboBoxes/Edits is the CURRENT VALUE, not the label!
        # We must find the label text node to the LEFT of each control.
        if nodes is not None:
            text_nodes_for_labels = self._backend.text_nodes(hwnd, nodes=nodes)
        else:
            text_nodes_for_labels = self._backend.text_nodes(hwnd)
        field_labels = _associate_right_field_labels(right_fields, text_nodes_for_labels)
        # Store the label on each node for later use
        for field in right_fields:
            if field.automation_id in field_labels:
                field.name = field_labels[field.automation_id]

        # NOTE: no scrolling happens here, on purpose. Scrolling below the fold
        # during field-map building is what caused the premature scroll seen
        # immediately after attach. The map is built from whatever the UIA tree
        # exposes; the workflow's reveal pass then scrolls the form per-viewport,
        # gated by can_scroll(), and never before the viewport is complete.

        if nodes is not None:
            text_nodes = self._backend.text_nodes(hwnd, nodes=nodes)
        else:
            text_nodes = self._backend.text_nodes(hwnd)
        # A text node sharing its parent group with an editable right-form field
        # is a FORM LABEL (e.g. "Gender Marital Status", "Religious and Astro
        # Information"), not a source-panel label - even when its x-centre lies
        # left of the window mid-line, because the right column can start well
        # past the source panel. Keeping those out of ``left_labels`` both
        # cleans the source label pool and stops them inflating ``left_rect``
        # into the right form (which leaked the OCR region across the divider).
        right_form_parents = {
            _node_parent_name(n)
            for n in right_fields
            if _node_parent_name(n)
        }
        left_labels = [
            n for n in text_nodes
            if n.rect is not None
            and n.rect.center[0] < mid_x
            and _is_meaningful_label(n.name)
            and not is_likely_value(n.name)  # CRITICAL: reject value-like text as labels
            and _node_parent_name(n) not in right_form_parents
        ]

        if nodes is not None:
            upload_button = self._pick_upload_button(self._backend.buttons(hwnd, nodes=nodes))
        else:
            upload_button = self._pick_upload_button(self._backend.buttons(hwnd))

        # Discover the real scrollable panels (left source list, right entry
        # form) from the UIA hierarchy - the outer window never scrolls.
        # The light refresh path skips this independent traversal: the scroll
        # session is discovered once by the scroller provider and cached, so
        # per-scroll position refreshes never re-walk the tree for containers.
        scroll_containers: list[ScrollContainer] = []
        if not light:
            try:
                client = (origin[0], origin[1], origin[0] + size[0], origin[1] + size[1])
                scroll_containers = self._backend.scroll_containers(hwnd, client)
            except Exception as exc:
                logger.debug("scroll container discovery failed: {}", exc)

        left_rect = _union_rect([n.rect for n in left_labels if n.rect is not None])
        right_rect = _union_rect([n.rect for n in right_fields if n.rect is not None])

        mappings = build_hybrid_mappings(left_labels, right_fields, client_origin=origin)

        field_map = UiaFieldMap(
            start_control=start_control,
            left_labels=left_labels,
            right_fields=right_fields,
            upload_button=upload_button,
            left_rect=left_rect,
            right_rect=right_rect,
            scroll_containers=scroll_containers,
            mappings=mappings,
            client_origin=origin,
            client_size=size,
        )
        logger.info(
            "uia map built: {} left labels, {} right fields, {} scroll containers, upload={}",
            len(left_labels),
            len(right_fields),
            len(scroll_containers),
            bool(upload_button),
        )
        return field_map

    def _attach_declared(self, node: UiaNode, hwnd: int | None = None) -> UiaNode:
        """Attach declared widget options/type by normalized label, if any.

        When the declaration carries no options (Sub Caste / Nakshatra /
        Rashi / Pada and other cascading combos have ``options: []`` in the
        field mapping), fall back to the UIA backend's per-field option cache
        filled by an earlier direct selection - reusing it avoids re-opening
        the dropdown to re-discover the list.
        """
        if not self._declared_fields:
            return node
        declared = self._declared_fields.get(normalize_label(node.name))
        if not declared:
            return node
        options = list(declared.get("options") or [])
        if not options and hwnd is not None and node.rect is not None:
            try:
                cached = self._backend.cached_options(hwnd, node.rect)
            except Exception:
                cached = None
            if cached:
                options = cached
        if options:
            node.options = options
        element_type = _parse_element_type(declared.get("type", ""))
        if element_type is not None:
            node.type_override = element_type
        return node

    @staticmethod
    def _pick_upload_button(buttons: list[UiaNode]) -> UiaNode | None:
        candidates: list[tuple[bool, float, UiaNode]] = []
        for button in buttons:
            label = normalize_label(button.name)
            if not label:
                continue
            strong = any(re.search(rf"\b{re.escape(t)}\b", label) for t in STRONG_UPLOAD_LABELS)
            score = 0.0
            for token in UPLOAD_LABELS:
                if re.search(rf"\b{re.escape(token)}\b", label):
                    score = max(score, len(token) / max(len(label), 1))
            if strong or score > 0:
                candidates.append((strong, score, button))
        if not candidates:
            return None
        # Strong verbs outrank weak ones; ties go to the bottom-most button
        # (form submits usually sit under the fields), then the right-most.
        candidates.sort(
            key=lambda pair: (
                -int(pair[0]),
                -pair[1],
                -(pair[2].rect.top if pair[2].rect else 10**9),
                -(pair[2].rect.left if pair[2].rect else 10**9),
            )
        )
        return candidates[0][2]


#: Geometric row-pairing tolerances for the source (LEFT) panel. Exposed as
#: named constants (rather than buried magic numbers) so a real MPF run that
#: still fails to pair rows can be diagnosed and retuned without touching the
#: pairing logic itself - see PAIRING DIAGNOSTICS below and
#: ``debug/mpf/source_pairs.json``.
SOURCE_ROW_Y_TOLERANCE_PX = 12
SOURCE_ROW_MAX_GAP_PX = 260
SOURCE_ROW_LABEL_MAX_WIDTH_PX = 160


class PairingDiagnostics:
    """Collects why each candidate source row was accepted/rejected during
    :func:`pair_source_pairs`, so a real run that still produces empty values
    can be root-caused from ``debug/mpf/source_pairs.json`` instead of
    guessed at. Never raises; purely additive bookkeeping.
    """

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def reject(self, left: "UiaNode | None", right: "UiaNode | None", reason: str) -> None:
        self.rows.append({
            "accepted": False,
            "label": _clean_label(left.name) if left is not None else None,
            "candidate_value": _clean_label(right.name) if right is not None else None,
            "reason": reason,
        })

    def accept(self, label: str, value: str, source: str) -> None:
        self.rows.append({"accepted": True, "label": label, "value": value, "source": source})

    def to_dict(self) -> dict[str, Any]:
        accepted = [r for r in self.rows if r["accepted"]]
        rejected = [r for r in self.rows if not r["accepted"]]
        return {
            "candidate_rows": len(self.rows),
            "paired_rows": len(accepted),
            "rejected_rows": len(rejected),
            "non_empty_values": sum(1 for r in accepted if r.get("value")),
            "empty_values": sum(1 for r in accepted if not r.get("value")),
            "rows": self.rows,
        }


def parse_multiline_colon_block(text: str) -> list[tuple[str, str]]:
    """Parse a multi-line ``"Label:Value"`` text block into ordered pairs.

    Real MPF renders its LEFT source panel as ONE scrollable text block, not
    as many separate sibling label/value controls - confirmed directly from
    the demonstration recording, e.g.::

        Member Basic Information
        App No:32394824
        MBI Code:MBI1062138570
        Full Name:ABHISHEK ROY
        Genlder:Male
        DOB:13 October 2001
        ...
        Religious and Astro Information
        RAI Code:RAI1093293046
        ...

    Section headers (a line with no colon, e.g. "Member Basic Information")
    are skipped rather than treated as a label. This is now the PRIMARY
    source-parsing strategy (see PairingDiagnostics source="colon_block") -
    the earlier sibling-node geometric row-pairing remains as a fallback for
    layouts that genuinely use separate controls per row.

    Section-aware (FIX #1): the block may also contain ``Project Details``,
    ``Shift Details`` and a live timer/status area that are NEVER record data.
    Only rows inside a member section (Member Basic Information / Religious
    and Astro Information) are kept. When the block contains no member
    section header at all (generic layouts / plain label:value blocks) every
    colon row is kept, preserving the legacy behaviour.
    """
    pairs: list[tuple[str, str]] = []
    lines = [ln.strip() for ln in re.split(r"[\r\n]+", text or "") if ln.strip()]
    section: str | None = None
    saw_member_header = False
    for line in lines:
        if ":" not in line:
            kind = section_of(line)
            if kind == "member":
                section = "member"
                saw_member_header = True
            elif kind == "ignored":
                section = "ignored"
            elif is_likely_value(line):
                continue  # skip value-like lines that have no colon
            continue  # section header, e.g. "Religious and Astro Information"
        if saw_member_header and section != "member":
            continue  # Project Details / Shift Details / timer rows - not data
        label, _, value = line.partition(":")
        label = _clean_label(label)
        value = value.strip()
        if not label or is_noise_label(label):
            continue
        pairs.append((label, value))
    return pairs


def looks_like_colon_block(text: str) -> bool:
    """True if ``text`` contains enough ``"Label:Value"`` lines to be
    confidently parsed as a colon block rather than treated as a single
    plain label (avoids misfiring on an ordinary one-line label like
    ``"District:"`` that merely contains a colon).
    """
    if not text:
        return False
    lines = [ln.strip() for ln in re.split(r"[\r\n]+", text) if ln.strip()]
    colon_lines = sum(1 for ln in lines if ":" in ln and len(ln) < 120)
    return colon_lines >= 3


def pair_source_pairs(
    ocr_lines: list[Any],
    uia_labels: list[UiaNode] | None = None,
    diagnostics: PairingDiagnostics | None = None,
    member_only: bool = False,
) -> list[tuple[str, str]]:
    """Pair OCR text lines from the source panel into (label, value) pairs.

    Strategy, in priority order:

    0. Multi-line "Label:Value" colon-block: confirmed from the real MPF
       recording, the source panel is rendered as ONE scrollable text block
       (not separate sibling controls per row) - see
       ``parse_multiline_colon_block``. This is the PRIMARY strategy.
    1. ``Label: value`` lines straight from OCR.
    2. Geometric pairing of UIA text nodes: used as a fallback for layouts
       that genuinely expose the label and its value as separate sibling
       text nodes on the same row.
    3. UIA static labels fill in any labels still missing (value falls back to
       the OCR remainder of the matching line, or an empty string).

    ``member_only`` (FIX #8/10): when True every surviving pair is gated
    against the member-field schema so Project/Shift/timer/button rows are
    never treated as record data - the concrete fix for "48 paired rows / 9%
    coverage" seen in the real run.
    """
    pairs: dict[str, str] = {}
    ordered: list[str] = []
    colon_block_consumed: set[int] = set()

    for node in uia_labels or []:
        text = node.value or node.name or ""
        if not looks_like_colon_block(text):
            continue
        block_pairs = parse_multiline_colon_block(text)
        if not block_pairs:
            continue
        colon_block_consumed.add(id(node))
        for label, value in block_pairs:
            if label in pairs:
                continue
            pairs[label] = value
            ordered.append(label)
            if diagnostics is not None:
                diagnostics.accept(label, value, source="colon_block")
        # A single source panel is expected; stop after the first block that
        # yields real pairs so a second, unrelated multi-line control (e.g.
        # shift/schedule details) can't overwrite it.
        break

    if len(pairs) >= 3:
        # Confident whole-panel read already done - this is the primary,
        # cheapest, most reliable path (matches the real MPF layout), so
        # skip the OCR/geometric fallback passes entirely.
        return _gate_pairs(pairs, ordered, member_only)

        # --- NEW: OCR row-based pairing ---
    def _group_ocr_by_row(ocr_lines, y_tolerance=12):
        # Group OCR lines by y-coordinate
        rows = []
        line_data = []
        for line in ocr_lines:
            text = getattr(line, "text", "")
            if not text: continue
            bbox = getattr(line, "bbox", None)
            if bbox is None: continue
            center_y = bbox.top + bbox.height / 2
            line_data.append((line, center_y))
        line_data.sort(key=lambda x: x[1])
        for line, center_y in line_data:
            placed = False
            for row in rows:
                row_y = sum(i[1] for i in row) / len(row)
                if abs(center_y - row_y) <= y_tolerance:
                    row.append((line, center_y))
                    placed = True
                    break
            if not placed: rows.append([(line, center_y)])
        return rows

    ocr_rows = _group_ocr_by_row(ocr_lines)
    for row in ocr_rows:
        row.sort(key=lambda x: x[0].bbox.left if x[0].bbox else 0)
        for i in range(len(row) - 1):
            l, r = row[i], row[i+1]
            lt = getattr(l[0], "text", "").strip()
            rt = getattr(r[0], "text", "").strip()
            if not lt or not rt: continue
            lc = _clean_label(lt)
            rc = _clean_label(rt)
            if is_likely_value(lc): continue
            if is_noise_label(lc) or is_noise_label(rc): continue
            if lc == rc: continue
            if lc in pairs: continue
            pairs[lc] = rc
            ordered.append(lc)
            if diagnostics: diagnostics.accept(lc, rc, source="ocr_row")

    # --- ORIGINAL: OCR colon-split fallback ---
    ocr_texts = [getattr(l, "text", "") for l in ocr_lines if getattr(l, "text", "")]
    for t in ocr_texts:
        t = (t or "").strip()
        if not t: continue
        import re
        p = re.split(r"[:：]", t, 1)
        if len(p)==2 and p[0].strip():
            lb = _clean_label(p[0])
            if is_likely_value(lb): continue
            if lb and not is_noise_label(lb) and lb not in pairs and p[1].strip():
                pairs[lb] = p[1].strip()
                ordered.append(lb)
    consumed: set[int] = set(colon_block_consumed)
    if uia_labels:
        rows = _group_same_row(
            [n for n in uia_labels if n.rect is not None], y_tolerance=SOURCE_ROW_Y_TOLERANCE_PX
        )
        for row in rows:
            # Menu/toolbar fragments and duplicate form labels that land on a
            # source row belong to other parent groups; drop them so a row
            # always pairs its true label/value siblings.
            row = _drop_outlier_parents(row)
            row.sort(key=lambda n: (n.rect.left if n.rect else 0, n.rect.top if n.rect else 0))
            i = 0
            while i < len(row) - 1:
                left_node, right_node = row[i], row[i + 1]
                gap = (right_node.rect.left - left_node.rect.right) if left_node.rect and right_node.rect else 0
                label = _clean_label(left_node.name)
                value = _clean_label(right_node.name)
                # Wide nodes are section headers (e.g. "Member Basic
                # Information"), not field labels; never pair them with a value.
                left_wide = left_node.rect is not None and left_node.rect.width > SOURCE_ROW_LABEL_MAX_WIDTH_PX
                if not label:
                    if diagnostics is not None:
                        diagnostics.reject(left_node, right_node, "empty label text")
                    i += 1
                    continue
                if not value:
                    if diagnostics is not None:
                        diagnostics.reject(left_node, right_node, "empty candidate value text")
                    i += 1
                    continue
                if label == value:
                    if diagnostics is not None:
                        diagnostics.reject(left_node, right_node, "label equals candidate value")
                    i += 1
                    continue
                if is_noise_label(label) or is_noise_label(value):
                    if diagnostics is not None:
                        diagnostics.reject(left_node, right_node, "label or value matched noise filter")
                    i += 1
                    continue
                if label in pairs:
                    i += 1
                    continue
                if gap > SOURCE_ROW_MAX_GAP_PX:
                    if diagnostics is not None:
                        diagnostics.reject(left_node, right_node, f"gap {gap}px exceeds {SOURCE_ROW_MAX_GAP_PX}px")
                    i += 1
                    continue
                if left_wide:
                    if diagnostics is not None:
                        diagnostics.reject(left_node, right_node, "label wider than section-header threshold")
                    i += 1
                    continue
                if not _same_parent_group(left_node, right_node):
                    if diagnostics is not None:
                        diagnostics.reject(left_node, right_node, "label/value do not share a parent group")
                    i += 1
                    continue
                pairs[label] = value
                ordered.append(label)
                consumed.add(id(right_node))
                if diagnostics is not None:
                    diagnostics.accept(label, value, source="uia_row_pairing")
                i += 2
                continue

    header_texts = {
        _clean_label(n.name).lower()
        for n in uia_labels or []
        if n.rect is not None and n.rect.width > SOURCE_ROW_LABEL_MAX_WIDTH_PX
    }

    for node in uia_labels or []:
        if id(node) in consumed:
            continue
        label = _clean_label(node.name)
        if not label or label in pairs or is_noise_label(label):
            continue
        remainder = ""
        for text in ocr_texts:
            if text.lower().startswith(label.lower()) and text.lower() not in header_texts:
                remainder = re.sub(r"^[^\w]*", "", text[len(label):]).lstrip(":： \t")
                break
        pairs[label] = remainder
        ordered.append(label)
        if diagnostics is not None:
            diagnostics.accept(
                label, remainder,
                source="ocr_remainder" if remainder else "label_only_no_value_found",
            )

    return _gate_pairs(pairs, ordered, member_only)


def _gate_pairs(
    pairs: dict[str, str],
    ordered: list[str],
    member_only: bool,
) -> list[tuple[str, str]]:
    """Apply the optional member-field gate to the final pair list."""
    if not member_only:
        return [(label, pairs[label]) for label in ordered]
    from atlas.mapping.member_fields import filter_member_pairs

    return filter_member_pairs([(label, pairs[label]) for label in ordered])


def _group_same_row(nodes: list[UiaNode], y_tolerance: int = SOURCE_ROW_Y_TOLERANCE_PX) -> list[list[UiaNode]]:
    """Group nodes whose vertical centres fall within ``y_tolerance`` px."""
    rows: list[list[UiaNode]] = []
    for node in sorted(nodes, key=lambda n: (n.rect.center[1], n.rect.center[0])):
        if node.rect is None:
            continue
        placed = False
        for row in rows:
            row_y = sum(n.rect.center[1] for n in row) / len(row)
            if abs(node.rect.center[1] - row_y) <= y_tolerance:
                row.append(node)
                placed = True
                break
        if not placed:
            rows.append([node])
    return rows


def _build_name_mappings(left_labels: list[UiaNode], right_fields: list[UiaNode]) -> list[dict[str, str]]:
    """Map LEFT source labels onto RIGHT form fields by semantic similarity."""
    mapper = SemanticMapper()
    left_map: dict[str, str] = {}
    for node in left_labels:
        label = _clean_label(node.name)
        if label and label not in left_map:
            left_map[label] = ""
    right_names = []
    for node in right_fields:
        name = _clean_label(node.name)
        if name and name not in right_names:
            right_names.append(name)

    mappings: list[dict[str, str]] = []
    used: set[str] = set()
    for label in left_map:
        best: tuple[float, str] | None = None
        for name in right_names:
            if name in used:
                continue
            canonical_source = mapper.aliases.resolve(label)
            canonical_target = mapper.aliases.resolve(name)
            if canonical_source and canonical_source == canonical_target:
                best = (0.99, name)
                break
            score = _fuzzy(label, name)
            if best is None or score > best[0]:
                best = (score, name)
        if best and best[0] >= 0.55:
            mappings.append({"source": label, "target": best[1], "confidence": round(best[0], 3)})
            used.add(best[1])
    return mappings


def _parent_group_key(node: UiaNode) -> tuple | None:
    """Stable key for a node's parent group, or None when the parent is unknown."""
    parent = getattr(node, "parent", None) or {}
    if not parent:
        return None
    return (parent.get("name"), parent.get("control_type"))


def _row_dominant_group(row: list[UiaNode]) -> tuple | None:
    """Most common parent group in a row, when it holds a strict majority."""
    counts: dict[tuple, int] = {}
    for node in row:
        key = _parent_group_key(node)
        if key is not None:
            counts[key] = counts.get(key, 0) + 1
    if not counts:
        return None
    top_key, top_count = max(counts.items(), key=lambda kv: kv[1])
    if top_count * 2 <= len(row):
        return None
    return top_key


def _drop_outlier_parents(row: list[UiaNode]) -> list[UiaNode]:
    """Drop nodes whose parent group differs from the row's dominant group.

    The source panel renders every field's label and value as sibling text
    nodes under a single parent group. Menu/toolbar fragments (e.g. an OCR
    slice of a tool bar) and duplicate form labels that happen to land on the
    same row belong to other groups and must not take part in geometric
    pairing - otherwise ``State`` would pair with a stray fragment instead of
    ``Tamil Nadu``.
    """
    dominant = _row_dominant_group(row)
    if dominant is None:
        return row
    return [n for n in row if _parent_group_key(n) == dominant]


def _same_parent_group(a: UiaNode, b: UiaNode) -> bool:
    """True when two nodes share a parent group (unknown == unknown)."""
    ka, kb = _parent_group_key(a), _parent_group_key(b)
    if ka is None and kb is None:
        return True
    return ka is not None and ka == kb


def _source_label_nodes(left_labels: list[UiaNode]) -> list[UiaNode]:
    """Return genuine source-panel label nodes, excluding VALUES and headers.

    The source panel renders every record field as a label text node whose
    value is a sibling text node on the same row (same parent group, small
    gap). Those right-side siblings - numeric IDs, codes, dates, names and the
    like - are VALUES, not labels, and must never become mapping candidates.
    Wide nodes are section headers (e.g. "Member Basic Information") and are
    excluded too.
    
    CRITICAL: Only labels from MEMBER sections are valid source fields.
    Labels from "Project Details", "Shift Details", and other ignored sections
    must be excluded even if they geometrically look like label-value pairs.
    """
    candidates = [n for n in left_labels or [] if n.rect is not None]
    if not candidates:
        return []
    rows = _group_same_row(candidates)
    value_ids: set[int] = set()
    for row in rows:
        row = _drop_outlier_parents(row)
        row.sort(key=lambda n: n.rect.left)
        for i in range(len(row) - 1):
            left_node, right_node = row[i], row[i + 1]
            if id(left_node) in value_ids:
                continue
            if left_node.rect.width > 120:
                continue
            gap = right_node.rect.left - left_node.rect.right
            if gap <= 170 and _same_parent_group(left_node, right_node):
                value_ids.add(id(right_node))
    result: list[UiaNode] = []
    for node in left_labels or []:
        if node.rect is None:
            continue
        if id(node) in value_ids:
            continue
        if node.rect.width > 120:
            continue
        # Filter by section: use parent group name to determine section
        parent_name = _node_parent_name(node)
        parent_section = section_of(parent_name)
        if parent_section == "ignored":
            continue  # Skip Project Details, Shift Details, etc.
        if parent_section is None and parent_name:
            # Parent exists but not recognized - likely a UI chrome group
            continue
        result.append(node)
    return result


def build_hybrid_mappings(
    left_labels: list[UiaNode],
    right_fields: list[UiaNode],
    client_origin: tuple[int, int] = (0, 0),
) -> list[dict[str, Any]]:
    """Map each RIGHT form field to its best LEFT/source label (field-first).

    The right fields are authoritative: they carry the form's own UIA names
    (e.g. "Full Name", "Gender", "State"). The left labels come from the
    source panel, where every field renders as a label/value pair of sibling
    text nodes - so a naive left-first pass treated the VALUES as labels and
    cascaded every mapping one field off (``Date Of Birth -> District``,
    ``88616739 -> Gender``, ...). This version:

    * restricts the candidate pool to genuine source labels (right-side values
      and wide section headers are excluded by :func:`_source_label_nodes`);
    * walks the right fields and picks each one's best left label with the
      priority: exact normalized name > known alias > strong fuzzy match;
    * falls back to nearest-right geometry only for fields no label matched.

    Unnamed controls (e.g. the three DOB part-combos) are never mapped.
    """
    source_pool = _source_label_nodes(left_labels)
    if not source_pool or not right_fields:
        return []

    mapper = SemanticMapper()
    used_sources: set[str] = set()
    used_fields: set[int] = set()
    mappings: list[dict[str, Any]] = []

    # Pass 1 - field-first semantic matching.
    for field in right_fields:
        fname = _clean_label(field.name)
        faid = _clean_label(field.automation_id)
        if not fname and not faid:
            continue
        targets = {t for t in (fname, faid) if t}
        best_score = 0.0
        best_source: str | None = None
        best_exact = False
        for node in source_pool:
            source = _clean_label(node.name)
            if not source or source in used_sources:
                continue
            score = 0.0
            is_exact = False
            for target in targets:
                if normalize_label(source) == normalize_label(target):
                    score = max(score, 0.99)
                    is_exact = True
                    continue
                canonical_source = mapper.aliases.resolve(source)
                canonical_target = mapper.aliases.resolve(target)
                if canonical_source and canonical_target and canonical_source == canonical_target:
                    score = max(score, 0.99)
                else:
                    score = max(score, _fuzzy(source, target))
            if score > best_score or (score == best_score and is_exact and not best_exact):
                best_score = score
                best_source = source
                best_exact = is_exact
        if best_score >= 0.55 and best_source:
            mappings.append({
                "source": best_source,
                "target": fname or faid,
                "confidence": round(best_score, 3),
                "method": "semantic",
            })
            used_sources.add(best_source)
            used_fields.add(id(field))

    # Pass 2 - nearest-right geometry for named fields still unmatched.
    for field in right_fields:
        if id(field) in used_fields:
            continue
        fname = _clean_label(field.name)
        faid = _clean_label(field.automation_id)
        if not fname and not faid:
            continue
        if field.rect is None:
            continue
        ox, oy = client_origin
        fx, fy = field.rect.center
        best_dist: float | None = None
        geo_source: str | None = None
        for node in source_pool:
            source = _clean_label(node.name)
            if not source or source in used_sources or node.rect is None:
                continue
            lx, ly = node.rect.center
            if fx <= lx:
                continue
            dist: float = abs(fy - ly) + abs(fx - lx)
            dist += (fy - ly) * 0.01 if (fy - ly) > 0 else 0
            if best_dist is None or dist < best_dist:
                best_dist = dist
                geo_source = source
        if geo_source:
            mappings.append({
                "source": geo_source,
                "target": fname or faid,
                "confidence": 0.82,
                "method": "geometry",
            })
            used_sources.add(geo_source)

    return mappings


def _fuzzy(a: str, b: str) -> float:
    try:
        from rapidfuzz import fuzz

        token = fuzz.token_sort_ratio(a, b) / 100.0
        ratio = fuzz.ratio(a, b) / 100.0
        return max(token, ratio)
    except Exception:
        return 0.0


def _parse_element_type(name: Any) -> ElementType | None:
    try:
        return ElementType(str(name).strip().lower())
    except (ValueError, AttributeError):
        return None


def _clean_label(text: str) -> str:
    text = re.sub(r"[:：\s]+$", "", (text or "")).strip()
    return text



def _associate_right_field_labels(right_fields, text_nodes):
    """Associate each right field with its nearest left label text node.
    
    For each right field (editable control), find the closest text node
    to its LEFT (or same x position on right panel) that shares similar 
    Y position (same row). Returns a dict mapping control automation_id -> label text.
    """
    label_map = {}
    for field in right_fields:
        if field.rect is None:
            continue
        fy = field.rect.center[1]
        fx = field.rect.left
        best_label = None
        best_dist = float("inf")
        for text in text_nodes:
            if text.rect is None:
                continue
            # Must be to the left of or aligned with the field (right panel labels share x)
            # Allow text.rect.right <= fx + 10 to accommodate right-panel labels at same x
            if text.rect.right > fx + 10:
                continue
            # Same row (vertical tolerance)
            ty = text.rect.center[1]
            if abs(ty - fy) > 20:  # 20px vertical tolerance
                continue
            # Horizontal distance (prefer closest - can be 0 for right-panel labels)
            dist = fx - text.rect.right
            if dist < 0:
                dist = 0
            if dist < best_dist:
                # Skip if this looks like a value (not a label)
                if is_likely_value(text.name):
                    continue
                best_label = _clean_label(text.name)
                best_dist = dist
        if best_label:
            label_map[field.automation_id] = best_label
    return label_map

def _node_parent_name(node: UiaNode) -> str:
    """Name of a node's parent group, or ``""`` when unknown.

    Right-form labels and their editable controls share the same parent Group
    (e.g. "Member Basic Information"); source-panel labels live under a
    pure-text group ("Record summary") that owns no editables. ``build`` uses
    this to separate form labels from source labels.
    """
    parent = getattr(node, "parent", None) or {}
    if isinstance(parent, dict):
        return parent.get("name") or ""
    return getattr(parent, "name", "") or ""


def _is_meaningful_label(text: str) -> bool:
    """Filter out OCR noise fragments (single letters, short fragments, etc.)."""
    label = _clean_label(text)
    if not label:
        return False
    # Reject very short fragments (1-2 chars) that are OCR noise.
    if len(label) < 3:
        return False
    # Reject fragments that are just a single letter repeated or punctuation.
    if re.fullmatch(r"[^a-zA-Z0-9]+", label):
        return False
    # Reject fragments that are just a single character repeated (e.g. "aaaa").
    if len(set(label.lower())) == 1:
        return False
    # Reject fragments that are clearly OCR noise like "ile", "ecord", "ools".
    # These are substrings of real words - require at least 2 words or a
    # recognizable word pattern.
    if re.fullmatch(r"[a-z]{2,4}", label.lower()) and not re.search(r"\s", label):
        # Short lowercase-only fragments are likely OCR noise unless they're
        # known field names.
        known_short = {
            "dob", "pan", "mbi", "rai", "mp", "f", "r", "t", "h",
            "app", "age", "sex", "city", "state", "name", "bank",
        }
        if label.lower() not in known_short:
            return False
    return True


def _union_rect(boxes: list[BBox]) -> BBox | None:
    boxes = [b for b in boxes if b is not None and b.width > 0 and b.height > 0]
    if not boxes:
        return None
    left = min(b.left for b in boxes)
    top = min(b.top for b in boxes)
    right = max(b.right for b in boxes)
    bottom = max(b.bottom for b in boxes)
    return BBox(left, top, max(0, right - left), max(0, bottom - top))


__all__ = ["UiaFieldMap", "UiaFieldMapBuilder", "pair_source_pairs", "build_hybrid_mappings", "UPLOAD_LABELS"]
