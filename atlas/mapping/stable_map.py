"""Stable field identity + last-known-good ``UiaFieldMap`` validation.

Concrete fix for the reported field-map explosion:

    uia map built: 31 left labels, 37 right fields, 5 scroll containers
    uia map built: 31 left labels, 79 right fields, 0 scroll containers
    uia map built: 31 left labels, 634 right fields, 0 scroll containers

Each ``UiaFieldMapBuilder.build()`` (or the assistant's ``refresh()``
closure) is a completely fresh, stateless rebuild - nothing remembered the
previous observation, so a transient UIA over-walk (nested repeater/table
rows, a stale COM enumeration, a partially-rendered popup) could silently
replace a good 37-field map with a corrupt 634-field one and the workflow
would happily keep going against garbage geometry.

This module adds two things:

1. ``stable_field_id`` - a deterministic identity for a ``UiaNode`` so the
   *same* physical control observed on repeated builds (including after a
   scroll, where its on-screen ``rect`` changes) is recognised as ONE field,
   not accumulated as N.
2. ``LastKnownGoodMapGuard`` - validates each freshly-built map against the
   last accepted one before it is allowed to replace it. A candidate is
   rejected (and the previous good map retained) when it looks like a
   spurious over-walk rather than a genuine UI change; scroll-container loss
   (5 -> 0) is patched from the last-known-good map rather than accepted at
   face value, since real MPF scroll containers do not disappear on their
   own.

The guard is deliberately NOT a bare ``if count > 100: reject`` - it
compares growth against the previous observation and cross-checks against
the LEFT (source) panel, which does not change size while the same form is
open, so a right-side explosion with a stable left side is the actual
explosion signature rather than a guess at an absolute ceiling.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from atlas.core.logging import logger

if TYPE_CHECKING:
    from atlas.mapping.uia_map import UiaFieldMap
    from atlas.observe.uia import UiaNode


def normalize_name(name: str | None) -> str:
    """Lowercase, whitespace-collapsed form of a control's name for identity."""
    if not name:
        return ""
    return " ".join(str(name).split()).strip().lower()


def stable_field_id(node: "UiaNode") -> str:
    """Deterministic identity for ``node`` stable across repeated observations
    and across scroll-induced geometry changes.

    Preference order (strongest first):

    1. ``automation_id`` + control_type - the real UIA AutomationId is stable
       for the lifetime of the control even as it scrolls in and out of view.
    2. ``handle`` + control_type - a live HWND-backed control identity.
    3. normalized name + control_type + parent name + document order proxy
       (rounded x-position, which is stable across vertical scrolling even
       though y moves) - used when neither of the above is available (most
       MPF controls, which are UIA-only with no automation id).

    Geometry (``rect``) is intentionally NEVER part of the identity: it is a
    per-viewport property, not part of who the field is (see PHASE 15 /
    viewport-aware field model).
    """
    ctype = (node.control_type or "").strip()
    if getattr(node, "automation_id", ""):
        return f"aid:{ctype}:{node.automation_id}"
    if getattr(node, "handle", None):
        return f"hwnd:{ctype}:{node.handle}"
    parent_name = ""
    parent = getattr(node, "parent", None)
    if isinstance(parent, dict):
        parent_name = normalize_name(parent.get("name"))
    x_bucket = ""
    rect = getattr(node, "rect", None)
    if rect is not None:
        # Bucket the x-origin (not y - y moves under vertical scroll) to a
        # coarse column so two genuinely different fields that happen to
        # share a label do not collide, while the same field's own vertical
        # scroll drift never produces a new identity.
        x_bucket = str(int(rect.x) // 20)
    return f"lbl:{ctype}:{normalize_name(node.name)}:{parent_name}:{x_bucket}"


def duplicate_ratio(nodes: list) -> float:
    """Fraction of ``nodes`` that share a ``stable_field_id`` with an earlier
    node in the same list (0.0 = no duplicates, 1.0 = every node duplicated).
    """
    if not nodes:
        return 0.0
    seen: set[str] = set()
    duplicates = 0
    for node in nodes:
        sid = stable_field_id(node)
        if sid in seen:
            duplicates += 1
        else:
            seen.add(sid)
    return duplicates / len(nodes)


def dedupe_fields(nodes: list) -> list:
    """Collapse ``nodes`` to one entry per ``stable_field_id``, keeping the
    first (reading-order) occurrence. A field observed 50 times stays ONE
    field - see PHASE 14 / field deduplication.
    """
    seen: set[str] = set()
    result = []
    for node in nodes:
        sid = stable_field_id(node)
        if sid in seen:
            continue
        seen.add(sid)
        result.append(node)
    return result


@dataclass(frozen=True)
class MapAnomalyReport:
    """Result of validating one candidate map against the last-known-good one."""

    accepted: bool
    reason: str
    right_before: int
    right_after: int
    left_before: int
    left_after: int
    duplicate_ratio: float
    scroll_before: int
    scroll_after: int
    scroll_patched: bool = False


class LastKnownGoodMapGuard:
    """Validates freshly-built ``UiaFieldMap`` objects against the last one
    accepted, rejecting spurious explosions and patching lost scroll-container
    state instead of blindly trusting every rebuild (PHASE 2 / PHASE 4).

    One guard instance is meant to live for the duration of a single attach
    session (same physical MPF window) - construct a new one per attach, or
    call :meth:`reset` when the target window genuinely changes.
    """

    def __init__(
        self,
        max_growth_ratio: float = 2.5,
        max_absolute_jump: int = 40,
        max_duplicate_ratio: float = 0.15,
        left_label_tolerance: float = 0.25,
    ) -> None:
        self._max_growth_ratio = max_growth_ratio
        self._max_absolute_jump = max_absolute_jump
        self._max_duplicate_ratio = max_duplicate_ratio
        self._left_label_tolerance = left_label_tolerance
        self._last_good: "UiaFieldMap | None" = None
        self.rejections = 0
        self.accepted_count = 0

    def reset(self) -> None:
        """Drop the remembered state (call on a genuine new attach)."""
        self._last_good = None
        self.rejections = 0
        self.accepted_count = 0

    @property
    def last_known_good(self) -> "UiaFieldMap | None":
        return self._last_good

    def seed(self, field_map: "UiaFieldMap | None") -> None:
        """Prime the guard with an already-trusted map (e.g. the attach-time
        build) without running it through validation - it is definitionally
        the first known-good state.
        """
        if field_map is not None:
            self._last_good = field_map

    def evaluate(self, candidate: "UiaFieldMap | None") -> tuple["UiaFieldMap | None", MapAnomalyReport]:
        """Validate ``candidate`` against the last-known-good map.

        Returns ``(map_to_use, report)``. ``map_to_use`` is ``candidate``
        (possibly with deduplicated fields / patched scroll containers) when
        accepted, or the previous last-known-good map when rejected.
        """
        if candidate is None:
            report = MapAnomalyReport(
                accepted=False, reason="candidate is None",
                right_before=len(self._last_good.right_fields) if self._last_good else 0,
                right_after=0,
                left_before=len(self._last_good.left_labels) if self._last_good else 0,
                left_after=0,
                duplicate_ratio=0.0,
                scroll_before=len(self._last_good.scroll_containers) if self._last_good else 0,
                scroll_after=0,
            )
            return self._last_good, report

        # Always dedupe first - a field observed twice in the SAME build is
        # never legitimate growth, it's a walk artifact. dup_ratio and the
        # "raw" (pre-dedup) count are computed BEFORE the replace so a
        # heavily-duplicated build is still recognised as heavily duplicated
        # even after its own fields are collapsed down to one each.
        raw_right_count = len(candidate.right_fields)
        dup_ratio = duplicate_ratio(candidate.right_fields)
        deduped_right = dedupe_fields(candidate.right_fields)
        if len(deduped_right) != raw_right_count:
            candidate = replace(candidate, right_fields=deduped_right)

        if self._last_good is None:
            # First observation this session: nothing to compare against yet,
            # but an internally-duplicated first map is still rejected outright
            # rather than accepted as the new baseline.
            if dup_ratio > self._max_duplicate_ratio and raw_right_count > 5:
                report = MapAnomalyReport(
                    accepted=False,
                    reason=f"initial map has {dup_ratio:.0%} duplicate fields (>{self._max_duplicate_ratio:.0%})",
                    right_before=0, right_after=raw_right_count,
                    left_before=0, left_after=len(candidate.left_labels),
                    duplicate_ratio=dup_ratio,
                    scroll_before=0, scroll_after=len(candidate.scroll_containers),
                )
                self.rejections += 1
                logger.warning("[STABLE_MAP] rejected initial map: {}", report.reason)
                return None, report
            self._last_good = candidate
            self.accepted_count += 1
            report = MapAnomalyReport(
                accepted=True, reason="first observation (seeded)",
                right_before=0, right_after=len(candidate.right_fields),
                left_before=0, left_after=len(candidate.left_labels),
                duplicate_ratio=dup_ratio,
                scroll_before=0, scroll_after=len(candidate.scroll_containers),
            )
            return candidate, report

        prev = self._last_good
        right_before, right_after = len(prev.right_fields), raw_right_count
        left_before, left_after = len(prev.left_labels), len(candidate.left_labels)
        scroll_before, scroll_after = len(prev.scroll_containers), len(candidate.scroll_containers)

        growth_ratio = right_after / max(1, right_before)
        absolute_jump = right_after - right_before
        left_stable = (
            left_before == 0
            or abs(left_after - left_before) / max(1, left_before) <= self._left_label_tolerance
        )

        is_explosion = (
            left_stable
            and (growth_ratio > self._max_growth_ratio or absolute_jump > self._max_absolute_jump)
        )
        is_dup_heavy = dup_ratio > self._max_duplicate_ratio and raw_right_count > right_before

        if is_explosion or is_dup_heavy:
            reason = (
                f"right fields {right_before} -> {right_after} "
                f"(x{growth_ratio:.1f}, left labels stable at ~{left_before}) - "
                f"rejected as spurious over-walk, keeping last-known-good"
                if is_explosion
                else f"candidate has {dup_ratio:.0%} duplicate right fields - rejected"
            )
            self.rejections += 1
            logger.warning(
                "[STABLE_MAP] rejected candidate map: {} left labels, {} right fields "
                "(previous: {} left, {} right) - {}",
                left_after, right_after, left_before, right_before, reason,
            )
            report = MapAnomalyReport(
                accepted=False, reason=reason,
                right_before=right_before, right_after=right_after,
                left_before=left_before, left_after=left_after,
                duplicate_ratio=dup_ratio,
                scroll_before=scroll_before, scroll_after=scroll_after,
            )
            return prev, report

        # Accepted. Scroll containers do not legitimately disappear on their
        # own in the same session; a good map's containers dropping to 0 is
        # patched from the last-known-good state rather than trusted.
        scroll_patched = False
        if scroll_after == 0 and scroll_before > 0:
            candidate = replace(candidate, scroll_containers=list(prev.scroll_containers))
            scroll_patched = True
            logger.info(
                "[STABLE_MAP] scroll containers {} -> 0 on an otherwise-accepted "
                "map; retaining {} last-known-good container(s)",
                scroll_before, scroll_before,
            )

        self._last_good = candidate
        self.accepted_count += 1
        report = MapAnomalyReport(
            accepted=True, reason="within tolerance",
            right_before=right_before, right_after=right_after,
            left_before=left_before, left_after=left_after,
            duplicate_ratio=dup_ratio,
            scroll_before=scroll_before, scroll_after=len(candidate.scroll_containers),
            scroll_patched=scroll_patched,
        )
        return candidate, report
