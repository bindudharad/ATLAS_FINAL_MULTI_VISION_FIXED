"""MPF Layout Cache - persistent layout caching across runs.

Stores and retrieves the learned MPF form layout so subsequent runs can
reuse field positions, scroll containers, and upload button location
without full UIA rediscovery.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from atlas.mapping.uia_map import UiaFieldMap


@dataclass
class MpfLayout:
    """Cached MPF layout information."""
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    # Window identification
    window_title: str = "MPF Form Filling"
    window_class: str = "WindowsForms10.Window.8.app.0.141b42a_r7_ad1"
    process_name: str = "MPF.exe"
    
    # Layout geometry
    client_origin: tuple[int, int] = (0, 0)
    client_size: tuple[int, int] = (1920, 1080)
    left_rect: dict | None = None
    right_rect: dict | None = None
    
    # Field information (stable identities)
    left_labels: list[dict] = field(default_factory=list)
    right_fields: list[dict] = field(default_factory=list)
    upload_button: dict | None = None
    
    # Scroll containers
    scroll_containers: list[dict] = field(default_factory=list)
    
    # Mapping hints
    mappings: list[dict[str, str]] = field(default_factory=list)
    
    # Validation
    source_field_count: int = 0
    target_field_count: int = 0
    scroll_container_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "window_title": self.window_title,
            "window_class": self.window_class,
            "process_name": self.process_name,
            "client_origin": list(self.client_origin),
            "client_size": list(self.client_size),
            "left_rect": self.left_rect,
            "right_rect": self.right_rect,
            "left_labels": self.left_labels,
            "right_fields": self.right_fields,
            "upload_button": self.upload_button,
            "scroll_containers": self.scroll_containers,
            "mappings": self.mappings,
            "source_field_count": self.source_field_count,
            "target_field_count": self.target_field_count,
            "scroll_container_count": self.scroll_container_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MpfLayout":
        return cls(
            version=data.get("version", 1),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            window_title=data.get("window_title", "MPF Form Filling"),
            window_class=data.get("window_class", "WindowsForms10.Window.8.app.0.141b42a_r7_ad1"),
            process_name=data.get("process_name", "MPF.exe"),
            client_origin=tuple(data.get("client_origin", [0, 0])),
            client_size=tuple(data.get("client_size", [1920, 1080])),
            left_rect=data.get("left_rect"),
            right_rect=data.get("right_rect"),
            left_labels=data.get("left_labels", []),
            right_fields=data.get("right_fields", []),
            upload_button=data.get("upload_button"),
            scroll_containers=data.get("scroll_containers", []),
            mappings=data.get("mappings", []),
            source_field_count=data.get("source_field_count", 0),
            target_field_count=data.get("target_field_count", 0),
            scroll_container_count=data.get("scroll_container_count", 0),
        )

    def is_valid_for(self, window_title: str, window_class: str, process_name: str) -> bool:
        """Check if this layout matches the current window."""
        # Allow case-insensitive substring match for title
        if self.window_title.lower() not in window_title.lower():
            return False
        if self.window_class and self.window_class != window_class:
            return False
        if self.process_name and self.process_name != process_name:
            return False
        return True

    def get_scroll_containers_for_refresh(self) -> list[dict]:
        """Return scroll containers for refresh when UIA returns 0."""
        return self.scroll_containers


class LayoutCache:
    """Manages MPF layout persistence."""
    
    def __init__(self, cache_dir: str | Path = "cache/mpf") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._layout: MpfLayout | None = None
    
    def _get_cache_path(self, window_title: str = "MPF") -> Path:
        safe_title = "".join(c for c in window_title if c.isalnum() or c in "-_ ").strip()
        return self.cache_dir / f"{safe_title}_layout.json"
    
    def save(self, layout: MpfLayout, window_title: str = "MPF") -> None:
        """Save layout to cache."""
        layout.updated_at = time.time()
        path = self._get_cache_path(window_title)
        path.write_text(json.dumps(layout.to_dict(), ensure_ascii=False, indent=2))
        self._layout = layout
        print(f"[LAYOUT_CACHE] Saved layout to {path}")
    
    def load(self, window_title: str = "MPF") -> MpfLayout | None:
        """Load layout from cache if valid."""
        path = self._get_cache_path(window_title)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            layout = MpfLayout.from_dict(data)
            self._layout = layout
            print(f"[LAYOUT_CACHE] Loaded layout from {path} (created {time.ctime(layout.created_at)})")
            return layout
        except Exception as exc:
            print(f"[LAYOUT_CACHE] Failed to load layout: {exc}")
            return None
    
    def update_from_field_map(self, field_map: UiaFieldMap, window_title: str, window_class: str, process_name: str) -> MpfLayout:
        """Create or update layout from a UiaFieldMap."""
        layout = MpfLayout(
            window_title=window_title,
            window_class=window_class,
            process_name=process_name,
            client_origin=field_map.client_origin,
            client_size=field_map.client_size,
            left_rect=field_map.left_rect.to_dict() if field_map.left_rect else None,
            right_rect=field_map.right_rect.to_dict() if field_map.right_rect else None,
            left_labels=[n.to_dict() for n in field_map.left_labels],
            right_fields=[n.to_dict() for n in field_map.right_fields],
            upload_button=field_map.upload_button.to_dict() if field_map.upload_button else None,
            scroll_containers=[c.to_dict() for c in field_map.scroll_containers],
            mappings=list(field_map.mappings),
            source_field_count=len(field_map.left_labels),
            target_field_count=len(field_map.right_fields),
            scroll_container_count=len(field_map.scroll_containers),
        )
        self.save(layout, window_title)
        return layout
    
    def get_cached_scroll_containers(self) -> list[dict]:
        """Get cached scroll containers for fallback."""
        if self._layout:
            return self._layout.scroll_containers
        return []


# Global cache instance
_global_cache: LayoutCache | None = None

def get_layout_cache(cache_dir: str | Path = "cache/mpf") -> LayoutCache:
    global _global_cache
    if _global_cache is None:
        _global_cache = LayoutCache(cache_dir)
    return _global_cache
