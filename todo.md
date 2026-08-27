# Core Foundation (first acceptance pass) — status

Scope agreed with user: TargetField model + merged perception stack + field
ledger + audit gate + engine submit() guard + second complete pass + fix the
0-records-commit bug. Verification: unit tests + real-MPF at milestones.

## Completed
- [x] Inspect codebase (all act/mapping/reason/understanding/core/workflow/
      vision/assistant/entrypoints/tests/docs)
- [x] Analyze the real-MPF video (Screen Recording 2026-08-12 094505.mp4) via
      OCR — root-caused "BATCH COMPLETE: 0 record(s)" (exception swallowed by
      run()) and "flat UIA walk found 0 editable controls" (UIA zero-fallthrough)
- [x] `atlas/understanding/target_field.py` — TargetControlType / FieldSource /
      InteractionStrategy / VerificationStrategy / FieldLedgerState / TargetField
      + control_type_for_uia / interaction_strategy_for / verification_strategy_for
- [x] `atlas/vision/field_cv.py` — InputCandidate + discover_input_candidates
      (OpenCV bordered boxes, dropdown-arrow ink, checkbox squares, _drop_nested),
      associate_label, discover_fields_from_image
- [x] `atlas/observe/perception.py` — PerceptionStack (UIA -> CV/OCR merge),
      from_uia_nodes, merge_fields (IoU>=0.55, label enrichment), order_fields
- [x] `atlas/workflow/ledger.py` — FieldLedger lifecycle + source_map + zero-skip
- [x] `atlas/workflow/audit.py` — RecordAudit / build_audit / [AUDIT] gate
- [x] `atlas/core/logging.py` — perception / entry / audit categories + bound
      loggers (spec requires [PERCEPTION]/[ENTRY]/[AUDIT] sections)
- [x] Wire audit gate into `atlas/workflow/loop.py`:
      _run_record_field_driven builds ledger + audit before submit; submit
      BLOCKED unless AuditStatus.PASS; `_submit_field_driven` runs the engine
      `submit()` guard first; RecordResult.audit populated; audit reasons in
      result.message
- [x] Engine submit() guard: public `submit()` / `allows_submit()` / `audit()` /
      `ledger()` reject upload without a PASS audit (2nd upload protection)
- [x] Second complete pass `_second_complete_pass` — read-only VERIFY of every
      source-backed verified field before submit; drifted fields re-filled
      (bounded, no re-type when correct — verified in isolation, 0.001s)
- [x] Fix 0-records-commit bug in run(): per-record exception -> appended
      RecordResult(success=False) instead of a silent empty batch
- [x] Tests (32 new): test_target_field, test_field_cv, test_perception,
      test_ledger_audit, test_loop_audit + updated test_logging namespace.
      Regression: 426+ tests green (workflow/field_engine/executor/verify/
      mapping/universal/mpf_integration/etc.)

## Discovery-budget phase (ATLAS FINAL RUNTIME FIX — Phases 1-5)
- [x] Phase 1-2: located the hang — `editable_fields` unbounded recursive
      fallback (`inspectable_nodes`, no depth/node/time caps) fired per probed
      HWND in `probe_editable_roots` (handle + every child window), pinning the
      process for 30-90+ s. Call chain: attach_by_title -> _discover_ui_root ->
      best_editable_root -> probe_editable_roots.
- [x] Phase 3: bounded UIA discovery in `atlas/observe/uia.py` —
      `_DiscoveryBudget` (1.5 s wall clock / 1500 nodes / depth 20, shared),
      `walk_descendants`/`inspectable_nodes` respect the budget,
      `editable_fields` does AT MOST ONE bounded recursive retry then logs
      "[DISCOVERY] UIA insufficient" (never re-crawls),
      `_editable_with_rect` dropped the redundant 3rd full walk,
      `probe_editable_roots` shares ONE budget across all child probes and
      stops early with "[DISCOVERY] probe budget exhausted".
- [x] Phase 4: `AttachedTarget` frozen dataclass (hwnd/pid/title/class_name/
      client_rect/process_name/attach_timestamp) recorded on attach
      (`WindowAttacher.attached_target`); `_find_child_with_controls` confined
      to the target's own pid (skips other-process child windows).
- [x] Phase 5: perception fallback wired — `_discover_ui_root` logs "UIA
      insufficient ... falling back to perception (CV/OCR)" instead of
      re-scanning; loop `_perception_fallback_note` runs the merged
      `_perception_stack` (UIA + CV/OCR over the capture) and publishes
      FIELD_DISCOVERED when the UIA field map has no form.
- [x] Tests: test_discovery_budget.py (15 tests) — budget caps, bounded
      recursion, single retry, no double walk, probe-budget exhaustion,
      AttachedTarget lock, pid-guard. Regression green: attach/perception/
      ledger/loop-audit/uia-read/uia-select/uia-scroll/scroller/universal/
      workflow/mapping/controller (300+ tests).

## Notes / findings
- test_uia_flow synthetic field-driven tests hang on the BASELINE (pre-existing
  coverage gate 75% < 95% for Application Number + unbounded _await_record) —
  they are already in .pytest_cache/lastfailed; not a regression from this pass.
- UIA dropdown option lists not exposed (options=0) and whole-window clipboard
  grabs remain open issues for the verification phase (from the video).

## Next
- [ ] Real-MPF acceptance at milestone (run_mpf_test.py): record fills, audit
      PASS, upload commits (was 0 in the video), next record advances; attach
      must now resolve in < 2 s (bounded probe) instead of hanging 30-90 s
- [ ] Phase 6+: connect field engine to the perception fallback fields (feed
      CV/OCR TargetFields into the fill queue when UIA is insufficient)
- [ ] Dashboard side panel: START / PAUSE / RESUME / STOP / START FROM HERE +
      audit counters (RecordAudit visible), upload button state bound to
      allows_submit()
- [ ] State machine required states: DISCOVERING / AUDITING / READY_TO_UPLOAD /
      UPLOADING / SUCCESS / NEEDS_REVIEW
- [ ] [MAPPING] / [ENTRY] log sections, SHIFT+TAB navigation graph for the
      verification strategy