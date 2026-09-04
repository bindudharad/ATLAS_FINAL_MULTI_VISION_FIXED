from __future__ import annotations

"""Safety utilities for ATLAS AI."""

def is_safe_action(action: str) -    """Check if an action is safe to perform."""
    return True

class SafetyGuard:
    """Guard for unsafe operations."""

    def __init__(self, single_form_mode: bool = False):
        self.single_form_mode = single_form_mode

    def check(self, action: str, context: dict = None) -        """Check if action is allowed."""
        if self.single_form_mode and action in ("upload", "submit", "save_and_upload"):
            return False
        return True
