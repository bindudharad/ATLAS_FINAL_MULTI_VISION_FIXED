# ATLAS Data Entry — Reliability Fix (Rework)

## What was actually wrong

I inspected the full project (not just the logs) and traced the "missing
fields" problem to concrete code, not vibes. Summary, most important first:

### 1. The safe execution path existed but was switched off (root cause #1)

`atlas/workflow/loop.py` contains **two** record-processing paths:

- `_run_record` (legacy/"viewport" path): builds one action plan up front
  from the source→target mapping and executes it start to finish, including
  the Submit/Upload click, **with no gate**. It records
  `incomplete_fields` / `unverified_fields` in the result, but only *after*
  submit already happened. This is the path your real runs were using.
- `_run_record_field_driven`: walks an ordered field queue one field at a
  time, has an explicit per-field state machine (`FieldStatus` in
  `atlas/workflow/field_engine.py`), runs a **second completeness pass**
  over anything not `VERIFIED`, and — critically — **blocks Submit** unless
  every source-backed field is `VERIFIED` or `ALREADY_CORRECT`
  (`FieldQueue.blockers()`). This is already exactly the "hard completion
  gate" architecture the reliability spec describes, fully built and
  covered by 43 passing tests in `tests/test_field_engine.py`.

It was gated behind `field_driven: bool = False` in `atlas/config.py`
(env var `WORKFLOW_FIELD_DRIVEN`, default off). **Fixed: now defaults to
`True`.** As defense-in-depth, I also added a submit gate to the legacy
path's `_execute_plan` (`atlas/workflow/loop.py`) so that even if it's ever
hit as a fallback (e.g. no UIA field map available), it will never fire
Submit while any value-bearing action in the record is unverified.

### 2. Source data was contaminated by application UI text

Your logs show strings like `"Collapse"`, `"Exit"`, `"ecord"`,
`"Member Basic Information"`, and
`"Upload completed — left side refreshed with a new random record; form
reset"` showing up as "unmapped source labels" — these are never part of
the record, and their presence inflated the unmapped-label count and
dragged reported source coverage down to 46%, which in turn triggered
repeated (and doomed) `MAPPING_RECOVERY` cycles.

**Fixed:** added `is_noise_label()` in `atlas/mapping/uia_map.py` — a single
choke point with a denylist of UI-chrome words, the known MPF section
headers, and a heuristic for instructional/status sentences. Wired into all
three pairing strategies in `pair_source_pairs` and into
`RecordBuilder.build()` (`atlas/core/record_builder.py`) as a second layer
of defense. Covered by `tests/test_source_contamination.py`.

### 3. UNKNOWN-verified fields (Height, Weight, PHI Code, Rashi, Annual
   Income) were failing to ever resolve

The read-recovery ladder in `atlas/act/verification.py`
(`verify_with_read_recovery`) only inserted a settle delay between recovery
reads when a refocus callback was supplied — and SELECT-type actions
(dropdowns/custom combos) intentionally never get one, since clicking again
could re-open the popup. So a stuck dropdown's recovery reads re-read the
*exact same still-repainting frame* with zero delay, and always got the
same empty/unreadable result. There was also no actual expanded-region
fallback despite a docstring claiming one existed.

**Fixed:**
- A settle delay (growing per attempt) is now inserted before *every*
  recovery read, regardless of whether a refocus callback exists.
- The final recovery attempt now reads a padded/expanded region, to catch
  values that render just outside a custom combo's nominal rect once its
  popup closes and it reflows.
- Bumped `read_recovery_attempts` default from 2 → 3 in
  `atlas/act/executor.py`.

Covered by `tests/test_verification_read_recovery.py`.

## Why this should meaningfully reduce missed fields

With `field_driven=True`, the loop now genuinely follows the
`READ → LOCATE → ENTER → VERIFY → COMPLETE → NEXT` rule your spec describes,
enforced in code (not just log messages), with:

- a two-pass completeness retry after the first sequential walk,
- a hard `queue.blockers()` gate before Submit is ever clicked,
- `FieldStatus.FILLED` (written but UNKNOWN-verified) explicitly **does
  not** satisfy the submit gate — only `VERIFIED`/`ALREADY_CORRECT` do,
- source data cleaned of application-UI noise before it ever reaches the
  mapper, and
- a materially better chance of an UNKNOWN dropdown/text read actually
  resolving to `VERIFIED` instead of getting stuck at `FILLED` forever.

## What I could **not** verify

I do not have a Windows machine or the live MPF desktop application in this
environment, so I could not run the real end-to-end workflow shown in your
videos. Everything above was verified by:

- reading the actual execution path in the code (not guessing from logs),
- the existing automated test suite (~610 tests, run on Linux against
  stubbed `win32api`/`win32con`/`win32gui`/`comtypes` modules — real
  Windows/UIA calls are mocked in these tests, as they were before my
  changes),
- three new/updated test files targeting the exact regressions described
  above.

Two pre-existing tests (`test_pair_source_pairs_geometric_skips_wide_header`,
`test_pair_source_pairs_geometric_wide_header_not_paired_as_label`) were
updated because they previously asserted the *old, buggy* behavior (section
headers kept in the record with an empty value) — the corrected assertion
matches the fix in item #2 above.

Two tests hang indefinitely in this sandbox and were excluded — I confirmed
they hang identically on the **original, unmodified** project too, so they
are a pre-existing environment limitation (they need a real X display /
real Win32 message loop), not a regression:
`test_field_driven_loop_multi_record_reset_detection`,
`test_excel_export_appends_one_row_per_record`.

## Recommended next real-world step

Run this against the actual MPF application for a handful of records with
`debug/` logging on, and check `debug/mpf/field_driven_perf.json` /
`verification_debug.json` for any field that still lands on `FAILED` or
stays `FILLED` after the completeness pass — that will point at whichever
specific control still needs a bespoke read strategy (this project already
has the plumbing for that; see `atlas/act/verify.py`'s `VisionVerifier` /
`UiaValueVerifier`).

## Files changed

- `atlas/config.py` — `field_driven` default → `True`.
- `atlas/workflow/loop.py` — legacy-path submit gate (defense-in-depth);
  import fix.
- `atlas/mapping/uia_map.py` — `is_noise_label()` + wiring into
  `pair_source_pairs`.
- `atlas/core/record_builder.py` — noise filter in `RecordBuilder.build()`.
- `atlas/act/verification.py` — settle delay + padded-region recovery read.
- `atlas/act/executor.py` — `read_recovery_attempts` default 2 → 3.
- `tests/test_source_contamination.py` — new.
- `tests/test_verification_read_recovery.py` — new.
- `tests/test_uia_flow.py` — 2 assertions corrected to match the fix.
