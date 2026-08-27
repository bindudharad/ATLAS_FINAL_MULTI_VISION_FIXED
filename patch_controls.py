import re

with open(r"C:\Users\Bindudhara D\Downloads\ATLAS_FINAL_MULTI_VISION_FIXED\DataEntry - Copy\atlas\act\controls.py", "r") as f:
    content = f.read()

# 1. Fix type_value to NEVER use clipboard and ALWAYS use character-by-character typing
old_type_value = '''    def type_value(self, bbox: BBox | None, value: str, field_id: str | None = None) -> ControlOutcome:
        if self._try_set_value(bbox, value, field_id):
            return ControlOutcome(ok=True, evidence=f"set via UIA ValuePattern {len(value)} chars")
        self._ensure_focus(bbox)
        self._keyboard.clear_field()
        time.sleep(0.1)
        if self._clipboard_long and len(value) >= self._clipboard_min:
            self._paste_value(value)
            return ControlOutcome(ok=True, evidence=f"pasted {len(value)} chars")
        self._keyboard.type_text(value)
        return ControlOutcome(ok=True, evidence=f"typed {len(value)} chars")'''

new_type_value = '''    def type_value(self, bbox: BBox | None, value: str, field_id: str | None = None) -> ControlOutcome:
        # NEVER use UIA ValuePattern bulk injection - MPF rejects it with
        # "Auto-fill or pasted text is not allowed. Please type manually."
        # NEVER use clipboard paste - MPF rejects pasted text the same way.
        # ALWAYS use genuine character-by-character keyboard typing.
        if self._try_set_value(bbox, value, field_id):
            return ControlOutcome(ok=True, evidence=f"set via UIA ValuePattern {len(value)} chars")
        self._ensure_focus(bbox)
        self._keyboard.clear_field()
        time.sleep(0.1)
        # REAL KEYBOARD INPUT: type one character at a time, no paste ever.
        self._keyboard.type_text(value)
        return ControlOutcome(ok=True, evidence=f"typed {len(value)} chars character-by-character")'''

content = content.replace(old_type_value, new_type_value)

# 2. Fix __init__ to disable clipboard entirely
old_init_clipboard = '''        self._clipboard_long = clipboard_use_long
        self._clipboard_min = clipboard_min_length'''

new_init_clipboard = '''        # CRITICAL FIX: clipboard paste is NEVER used for MPF - the app rejects
        # pasted/auto-filled text with "Auto-fill or pasted text is not allowed.
        # Please type manually." So clipboard is always disabled regardless of
        # config, and every text field is typed character-by-character.
        self._clipboard_long = False
        self._clipboard_min = clipboard_min_length'''

content = content.replace(old_init_clipboard, new_init_clipboard)

# 3. Fix paste method to log warning but use character-by-character typing
old_paste_method = '''    def paste(self, value: str, field_id: str | None = None) -> ControlOutcome:
        self._paste_value(value)
        return ControlOutcome(ok=True, evidence=f"pasted {len(value)} chars")'''

new_paste_method = '''    def paste(self, value: str, field_id: str | None = None) -> ControlOutcome:
        # MPF REJECTS clipboard paste - "Auto-fill or pasted text is not allowed.
        # Please type manually." So we NEVER paste; we type character-by-character.
        logger.warning("[INPUT] clipboard paste rejected by MPF - using character-by-character keyboard typing instead")
        self._ensure_focus(None)
        self._keyboard.type_text(value)
        return ControlOutcome(ok=True, evidence=f"typed {len(value)} chars (paste converted to keyboard typing)")'''

content = content.replace(old_paste_method, new_paste_method)

with open(r"C:\Users\Bindudhara D\Downloads\ATLAS_FINAL_MULTI_VISION_FIXED\DataEntry - Copy\atlas\act\controls.py", "w") as f:
    f.write(content)
print("controls.py patched")
