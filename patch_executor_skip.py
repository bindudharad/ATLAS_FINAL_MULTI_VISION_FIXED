import re

with open(r"C:\Users\Bindudhara D\Downloads\ATLAS_FINAL_MULTI_VISION_FIXED\DataEntry - Copy\atlas\act\executor.py", "r") as f:
    content = f.read()

# 1. Make _check_already_correct more robust - check normalized values
old_check = '''    def _check_already_correct(self, action: Action) -> ActionResult | None:
        """Return an ALREADY_CORRECT result when the field already holds the
        target value (no-op detection), else None.

        Only called for verifiable value actions when ``noop_detect`` is on.
        A pre-write MATCH means the write can be skipped entirely - this is
        the Sub Caste / Nakshatra "reset" case where the value never actually
        changed. Reported as ``ACTION_SUCCESS_VERIFICATION_ALREADY_CORRECT``
        (verified, so it never counts as UNKNOWN and never re-fills).
        """
        with Timer() as pre_timer:
            vresult = self._verify(action)
        self._record_stage(action, "noop", pre_timer.elapsed)
        if not vresult.is_match:
            return None
        result = ActionResult('''

new_check = '''    def _check_already_correct(self, action: Action) -> ActionResult | None:
        """Return an ALREADY_CORRECT result when the field already holds the
        target value (no-op detection), else None.

        Only called for verifiable value actions when ``noop_detect`` is on.
        A pre-write MATCH means the write can be skipped entirely - this is
        the critical prefilled-skip case (e.g. App No already = 31549796),
        where we MUST NOTHING: no click, no typing, no clearing, no paste.
        Reported as ``ACTION_SUCCESS_VERIFICATION_ALREADY_CORRECT``
        (verified, so it never counts as UNKNOWN and never re-fills).
        """
        with Timer() as pre_timer:
            vresult = self._verify(action)
        self._record_stage(action, "noop", pre_timer.elapsed)
        if not vresult.is_match:
            return None
        # CRITICAL: log the skip so the user sees it was skipped, not written
        logger.info(
            "[SKIP] {} already populated with {!r} - no action taken",
            action.field_id or action.reason,
            action.value,
        )
        result = ActionResult('''

content = content.replace(old_check, new_check)

with open(r"C:\Users\Bindudhara D\Downloads\ATLAS_FINAL_MULTI_VISION_FIXED\DataEntry - Copy\atlas\act\executor.py", "w") as f:
    f.write(content)
print("executor.py patched")
