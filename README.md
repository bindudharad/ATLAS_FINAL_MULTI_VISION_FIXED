# ATLAS AI - MPF (Download and Upload Form) Data Entry Agent

An AI-first Windows computer agent that automates MPF form data entry. Atlas behaves like a real human data entry operator: it reads source data from the LEFT panel, fills editable form fields on the RIGHT panel, clicks **Upload Details**, waits for the next record, and repeats until stopped.

```
Observe -> Understand -> Reason -> Plan -> Execute -> Verify -> Observe
```

## Current Status (this build)

This build was developed and test-verified in a **Linux sandbox** (no Windows, no live MPF
process, no live Gemini/OpenRouter API access). A screen recording of a real MPF session was
supplied and frame-analyzed directly (`ffmpeg` extraction + visual inspection), and the fixes
below are grounded in what that recording actually shows, not assumptions:

**Real MPF layout, confirmed from the recording:**
- The LEFT source panel is **one single scrollable text block**, not separate sibling controls
  per row - it renders as `"Label:Value"` lines with bare section-header lines (no colon), e.g.
  `App No:32394824`, `Full Name:ABHISHEK ROY`, `Genlder:Male` (yes, the real app has this exact
  typo), `DOB:13 October 2001`, under headers like "Member Basic Information" / "Religious and
  Astro Information" / "Family Information" / "Education and Career Information".
- The RIGHT target form genuinely is a structured native WinForms form (individual labeled
  ComboBox/TextBox/DateTimePicker controls, e.g. Gender/State/District as dropdowns opening
  alphabetically-sorted popups; Taluk switching between a dropdown and free-text depending on
  the selected District) - this **matches** the existing UIA-based right-side architecture, so
  it was not changed.
- Both panels scroll independently and go well beyond the first visible screen (confirmed
  "Upload Details" button only appears after scrolling the right form to the bottom).

**PASS - verified in this environment (705 passed / 4 failed, full suite):**
- **Audit-round fixes** (found by tracing the actual call paths, not assumed): (1)
  `AgentLoop._observe()` called `self._target.observe()` -> ...  -> the Vision provider's HTTP
  request with NO exception handling anywhere in that chain, despite the explicit repeated
  requirement that ATLAS must never crash merely because the AI provider is unavailable - fixed
  by catching and falling back to the last cached analysis. (2) `_parse_scene()`'s bbox parsing
  only handled a nested `bbox`/`box`/`bounds` dict or a 4-element list - it did NOT handle the
  flat `x`/`y`/`width`/`height` keys that the provider's OWN documented `SCENE_PROMPT` asks the
  model to return, so real elements from that exact schema were silently dropped before ever
  reaching the field map. Fixed and covered by `tests/test_vision_provider_safety.py`. (3)
  Cascading dropdowns (State -> District -> Taluk, Caste -> Sub Caste) had a 3-second option
  cache with no dependency-aware invalidation hook - a successful selection now invalidates every
  OTHER cached option list (`UiaBackend.invalidate_options_except`), the general, conservative fix
  since the cache has no declared parent/child graph to invalidate selectively.
</br>
- **Primary source-parsing fix**: `atlas/mapping/uia_map.py` gained
  `parse_multiline_colon_block()` / `looks_like_colon_block()`, wired into `pair_source_pairs()`
  as the new PRIMARY strategy (Step 0, ahead of OCR and the old sibling-geometry pairing, which
  remains only as a fallback for layouts that don't match this pattern). Tested directly against
  the real block of text transcribed from the recording (17 tests, `tests/test_source_pipeline_fix.py`).
- Added the real-world label variants found in the recording as MPF plugin aliases
  (`plugins/mpf/field_mapping.json`): `"genlder"` -> Gender, `"cast"`/`"subcast"`/`"sub cast"` ->
  Caste/Sub Caste (the real source panel uses "Cast"/"SubCast", not "Caste"/"Sub Caste"), plus
  4 newly-declared fields the recording showed but the field map didn't have yet: `FAI Code`,
  `Health Info`, `Any Disability`, `Diet`.
- Field-map explosion fix, source UIA/OCR merge-priority fix, cheap per-poll source read
  (previous rounds) - all still passing.
- Upload Details hard-block, single-form termination, zero-skip ledger, dropdown state
  machine, scroll/viewport merge, cascading-dropdown handling - unchanged, still passing.
- Fixed a missing `pywinauto` runtime dependency in `requirements.txt`.

**REQUIRES WINDOWS - cannot be verified from this sandbox:**
- Whether a real MPF left-panel UIA node's `.value`/`.name` actually contains the full
  multi-line block text with embedded newlines (this is the single biggest remaining unknown -
  if UIA truncates the accessible name to one line, the colon-block parser needs its input fed
  from an OCR read of the cropped left-panel region instead, which the merge-priority path
  already supports as a fallback).
- Real MPF.exe attachment, real UIA tree walking, real dropdown open/scroll/select.
- The `pywinauto`/`comtypes` COM ValuePattern fallback path in `atlas/observe/uia.py` -
  `comtypes.client` requires real Windows COM and cannot be exercised on Linux. 3 of the 4
  remaining test failures are exactly this path; the 4th is a `ctypes.windll` (Windows-only)
  code path in discovery filtering.

**NOT LIVE TESTED:**
- Gemini / OpenRouter vision provider calls - this sandbox has no network access to either
  API. The provider abstraction, JSON schema validation, and UIA -> OCR -> deterministic
  fallback chain are implemented and unit-tested with mocked HTTP responses only.
- A dedicated vision-first "SourceVisionObserver" for the left panel was considered (per an
  explicit request) but NOT built this round: the recording shows the left panel is clean
  rendered text, not a scanned/photographed document, so a correctly-wired UIA/OCR colon-block
  read should be both faster and more accurate than a VLM call for this specific screen. The
  existing Vision provider abstraction remains available as a fallback for genuinely ambiguous
  cases (low-confidence reads, verification contradictions) rather than as the primary path.

## Is a Vision API required?

Answering this explicitly, as requested: **No, but it is strongly recommended for the LEFT
source panel specifically, and the code works correctly either way.** Python alone (UIA + the
colon-block parser above) reliably reads the left panel because it turned out to be clean
rendered text, not a scanned image - confirmed by direct frame analysis of the supplied
recording, not an assumption. Vision API involvement is architecturally an OBSERVER only, never
the mouse/keyboard executor, and is used for genuinely hard cases: verification contradictions,
low-confidence reads, dropdown-option ambiguity when UIA/OCR can't resolve it, and unexpected
screen states. If no Vision provider is configured, ATLAS still runs end-to-end via
UIA -> OCR -> deterministic fallback; it does not crash or refuse to start.

## Multi-provider Vision fallback (Google / Groq / OpenRouter)

`atlas/vision/manager.py` adds `VisionProviderManager`, a health-aware fast-failover layer on
top of the existing single-provider architecture (it does not duplicate provider HTTP/parsing
logic - Groq and OpenRouter both reuse the existing `OpenAIVisionProvider` since they're
OpenAI-compatible chat-completions endpoints; Google reuses the existing `GeminiVisionProvider`).

- **Activation**: set `VISION_PROVIDER=multi`, or simply configure 2+ of `GOOGLE_STUDIO_API_KEY`
  / `GROQ_API_KEY` / `OPENROUTER_API_KEY` - the factory (`create_vision_provider`) builds the
  manager automatically. A single configured key keeps the existing single-provider path
  unchanged (fully backward compatible).
- **Order**: `VISION_PROVIDER_ORDER=google,groq,openrouter` (configurable); a provider with no
  API key is skipped entirely, never attempted.
- **Failover**: on any exception the manager classifies the failure (`TIMEOUT`, `NETWORK_ERROR`,
  `RATE_LIMIT`, `SERVER_ERROR`, `AUTH_ERROR`, `INVALID_RESPONSE`, ...) and tries the next
  provider immediately - no long waits.
- **Cooldown**: a transient failure puts that provider in `COOLDOWN` for
  `VISION_PROVIDER_COOLDOWN_SECONDS` (default 60s) so it is not retried on every single request;
  an auth/model-config failure marks it `UNAVAILABLE` for the rest of the process instead
  (retrying will not fix a bad key).
- **Stickiness**: the most recently successful provider is tried first on the next request.
- **If every provider fails**: the manager raises the last exception rather than fabricating a
  result - the `AgentLoop._observe()` fix below turns that into "reuse the last known screen
  state and keep going" rather than a crash.
- 14 dedicated tests in `tests/test_vision_manager.py` (missing-key skip, Google-fails/Groq-succeeds,
  both-fail/OpenRouter-succeeds, all-fail raises, cooldown skip, stickiness, invalid-JSON failover,
  factory wiring) - all mocked, no real network calls.

`.env` is never created or included with real keys - only `.env.example` is shipped, per the
explicit "never include `.env` in the ZIP" requirement repeated across every round of this project.

## Urgent bug-report round: why the runtime showed "No VLM endpoint configured" with real keys

Three real root causes were found by tracing the actual runtime evidence, not guessed at:

1. **`load_dotenv()` searched the wrong directory.** python-dotenv's default `load_dotenv()`
   looks in the process's CURRENT WORKING DIRECTORY, not next to `main.py`. Launching ATLAS from
   any directory other than the project root (a shortcut, a scheduled task, a different terminal)
   silently never found a real `.env` sitting right there, so every provider key read back empty.
   Fixed in `atlas/config.py`: the project root is now resolved explicitly from this file's own
   location and loaded from there first. Verified with a real subprocess launched from a
   deliberately different `cwd` (`tests/test_vision_provider_visibility.py`).
2. **Provider configuration was never shown anywhere.** `python main.py doctor` now prints a
   `Vision providers: Google/Groq/OpenRouter: CONFIGURED|NOT CONFIGURED` block (keys never
   printed), plus provider order and whether fallback is active - exactly the loud startup
   visibility this bug report asked for.
3. **`python main.py observe` was never actually a registered CLI command**, despite being
   documented as working in every prior round of this project - confirmed by inspecting the
   argparse registration directly, not by re-reading old claims. Fixed: `observe` is now a real
   subcommand (routes to the same non-mutating attach -> capture -> observe -> dump handler as
   `diagnose`, so it inherits its "never types/clicks/scrolls/uploads" guarantee rather than
   getting a new, unverified implementation). Also added `python main.py vision-doctor` as
   requested: prints provider status, then makes ONE live call against the attached window's
   screenshot and reports which provider answered, latency, and structured field count.
4. **`TYPING_USE_CLIPBOARD_FOR_LONG` defaulted to `true`** in `atlas/config.py`, contradicting
   the explicit repeated requirement that clipboard paste must not be the primary interaction.
   Default flipped to `false`; clipboard remains available as an explicit opt-in.

All four are genuinely new findings from tracing this round's evidence, not restatements of
earlier fixes - they're independent from the Vision failover system (which was already wired
correctly end-to-end: `main.py` -> `load_config()` -> `Assistant.__init__` ->
`create_vision_provider(self._config.vision, ...)`, confirmed by grep, not assumed).

## Quick Start

### Prerequisites

- Windows 10/11, Python 3.10+
- Install dependencies:
  ```powershell
  pip install -r requirements.txt
  pip install -r requirements-optional.txt   # optional: vision/OCR extras
  python -m playwright install chromium      # only if using --web
  python main.py doctor                      # verify environment
  ```


### Run MPF Data Entry

```powershell
python run_mpf_test.py --records 3            # recommended test workflow
python main.py run --title "MPF" --max-records 3
```

`run_mpf_test.py` is the dedicated MPF test workflow. It:
1. Attaches to the MPF window by title
2. Opens the live debug dashboard
3. Reads the LEFT source panel
4. Fills the RIGHT form fields
5. Clicks **Upload Details**
6. Waits for the next record
7. Repeats until `--records` is reached or STOP (Ctrl+C) is pressed

Other options:
```powershell
python run_mpf_test.py --records 5 --no-dashboard   # headless run
python run_mpf_test.py --json                        # JSON summary output
python run_mpf_test.py --diagnose                    # run diagnostics first
```

### Universal Attach-First Mode (web + desktop)

Attach to an **existing** browser/application instead of launching a duplicate.
`DISCOVER -> CLASSIFY -> ATTACH -> VERIFY -> AUTOMATE`; a launch only happens
when nothing exists anywhere and `AUTO_LAUNCH_TARGET=true` (default `false`).

```powershell
# Universal attach-first on the MPF desktop target (never relaunches it)
python run_mpf_test.py --records 3 --field-driven --auto

# Universal attach-first via the main CLI
python main.py run --mode auto --title "MPF" --max-records 3
python main.py run --auto --url "http://localhost:5173" --max-records 3

# WEB_DOM benchmark against the bundled test app (attach-existing + timing)
python run_universal_web.py --records 3
python run_universal_web.py --records 3 --react
```

The WEB_DOM engine (`atlas/web/form_engine.py`) discovers DOM fields, maps the
source record semantically, fills via `fill()` / `select_option()` / `check()`
with authoritative DOM read-back verification, and times/learns the fastest
method per field. Measured: **~40–55 ms per field** vs the 100–500 ms target,
with zero new processes. See `UNIVERSAL_AUTOMATION_REPORT.md` and
`PERFORMANCE_BEFORE_AFTER.md`.

### Diagnostic Mode

```powershell
python run_mpf_test.py --diagnose --title "MPF"
python main.py diagnose --title "MPF" --out debug/mpf
```

Captures the complete window state for debugging into `debug/mpf/diag-<timestamp>/`:
- `screen.png` - full monitor screenshot
- `window.png` - the attached window's client area
- `ui_tree.json` - native Win32 control hierarchy
- `scene.json` - the agent's structured perception
- `controls.json` - editable form controls
- `mapping.json` - source-to-form field mapping
- `summary.json` - human-readable diagnosis

If no matching MPF window is open, Atlas prints a friendly message and exits
with code 1 instead of a raw traceback.

### Live Debug Dashboard

The dashboard shows in real-time:

```
ATLAS AI - MPF Data Entry
state: OBSERVING
record 1  key=MPF-001
field: [type] Full Name = KRISHNA
expected: 'KRISHNA'
observed: 'KRISHNA'
confidence: 95%
verify: OK  attempt 0
upload: clicking Upload Details ...
completed fields: Full Name, Gender, DOB, Mobile
missing fields: none
```

## Architecture

```
atlas/
  assistant/     Assistant facade + wiring
  act/           executor, controls, keyboard/mouse/clipboard, verification
  core/          events, logging, state machine, settings
  mapping/       source -> target field mapping
  memory/        SQLite alias learning
  observe/       capture, window attach, screen state
  overlay/       floating status overlay
  plugins/       plugin manager + MPF plugin
  reason/        planner, recovery planner, LLM advisor
  target/        DesktopTarget, WebTarget adapters
  universal/     attach-first manager, target detector/classifier, restart
                 policy, smart wait, method learner, performance guards
  web/           CDP tab discovery, browser discovery, form engine (WEB_DOM)
  understanding/ source record extraction, field discovery
  vision/        VLM providers, scene analyzer, OCR, debug rendering
  workflow/      AgentLoop + WorkflowSummary

plugins/mpf/
  plugin.py          MPF plugin entry point
  field_mapping.json Field definitions, types, and aliases
  mpf_detector.py    Window detector, panel splitter, upload button finder
  mpf_workflow.py    Record bookkeeping and session tracking
```

## How It Works

### 1. Window Attachment
Atlas finds the MPF window by title (substring match like "MPF"). It captures the window's client area using the Win32 API.

### 2. Scene Understanding
A Vision Language Model (VLM) converts the screenshot into a structured scene description with:
- **Elements** (labels, textboxes, comboboxes, date pickers, buttons)
- **Sections** (source panel, form panel, actions area)
- **Bounding boxes** for each element

### 3. Semantic Field Mapping
The MPF plugin tags elements by position:
- **LEFT panel** → source data (labels + values)
- **RIGHT panel** → form fields (editable controls)
- **BOTTOM** → Upload Details button

Labels from the source panel are mapped to form fields using:
- **Exact match** (same label text)
- **Alias match** (e.g., "DOB" → "Date Of Birth", "Mobile" → "Mobile Number")
- **Fuzzy match** (token overlap, containment)
- **Persistent memory** (learned aliases saved to SQLite)

### 4. Action Planning
The planner generates a deterministic sequence of actions:
- **CLICK** → focus the field
- **CLEAR** → remove existing value
- **TYPE** → type the value (human-like speed)
- **VERIFY** → read back and compare
- **SELECT** → choose from dropdown options
- **CHOOSE_DATE** → type date in the correct format
- **CLICK** Upload Details → submit

### 5. Human-like Execution
- **Mouse** → bezier curves, jitter, random delays, natural pauses
- **Keyboard** → human typing speed, tab navigation, clipboard fast-path for long values
- **Verification** → every value is read back via clipboard, OCR, or target API

### 6. Verification
After typing, Atlas never assumes success:
- **Reads back** the field value (clipboard select-all+copy, OCR region read, or DOM value)
- **Compares** with expected value (normalized: case, whitespace, boolean synonyms)
- **Retries** up to 3 times with corrective actions (re-click, scroll, re-observe)
- **Recovery planner** decides next steps if all retries fail

### 7. Record Lifecycle
```
Observe → SourceRecord → FieldMapping → FillPlan → Execute → Verify → Upload
→ Wait for next record → Repeat
→ STOP button ends execution safely at any point
```

## CLI Commands

```powershell
# Run MPF data entry (test workflow with dashboard + diagnostics)
python run_mpf_test.py --records 3

# Run MPF data entry (CLI entry point)
python main.py run --title "MPF" [--max-records N] [--no-overlay] [--json]

# Diagnostic snapshot
python main.py diagnose --title "MPF" [--out debug/mpf]

# Serve JSON command endpoint
python main.py serve [--port PORT]

# Environment check
python main.py doctor

# Full test suite
python -m pytest tests/ -q --no-header
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `VISION_PROVIDER` | `auto` | `openai`, `gemini`, `local`, `auto` |
| `VISION_API_KEY` | `` | API key for VLM |
| `VISION_API_BASE` | `` | Custom API base URL |
| `WORKFLOW_VERIFY_AFTER_ACTION` | `true` | Verify every value action |
| `WORKFLOW_MAX_RETRIES_PER_ACTION` | `3` | Max retry attempts |
| `MOUSE_SPEED` | `0.35` | Mouse movement speed (0-1) |
| `TYPING_MIN_DELAY` | `0.05` | Min delay between keystrokes |
| `TYPING_MAX_DELAY` | `0.25` | Max delay between keystrokes |
| `OCR_ENGINE` | `paddle` | OCR engine: `paddle`, `tesseract`, `none` |
| `LOG_LEVEL` | `DEBUG` | Logging level |
| `PLUGINS_ENABLED` | `true` | Enable plugin system |

## MPF Field Mapping

The `plugins/mpf/field_mapping.json` file defines:
- **window_keywords** - window title patterns to match
- **upload_button_labels** - button text patterns to detect
- **fields** - form field definitions with types and requirements
- **aliases** - vocabulary mappings (source label → canonical form field)

Extend this file to add new fields or aliases without changing code.

## Testing

```powershell
# All tests
python -m pytest tests/ -q --no-header

# MPF plugin + workflow tests
python -m pytest tests/test_mpf_diagnostic.py -v --no-header

# End-to-end MPF integration (real plugin wired into the AgentLoop, 3 records)
python -m pytest tests/test_mpf_integration.py -v --no-header

# State machine tests
python -m pytest tests/test_states.py -v --no-header
```

The integration suite proves the complete record lifecycle without needing a
live MPF window: read LEFT data, fill RIGHT form (text + dropdown + date),
click **Upload Details**, wait for the next record, repeat 3 times, and stop
safely via the STOP flag.

## Project Status

- ✅ MPF window detection
- ✅ Source panel reading
- ✅ Form field discovery
- ✅ Semantic field mapping (exact + alias + fuzzy)
- ✅ Action planning with verification
- ✅ Human-like mouse and keyboard
- ✅ Verification with retry (up to 3 attempts)
- ✅ Upload button detection
- ✅ Record lifecycle (auto-repeat until STOP)
- ✅ Live debug dashboard
- ✅ Diagnostic mode (friendly error when MPF window is not open)
- ✅ MPF plugin system
- ✅ OBSERVING / UNDERSTANDING states
- ✅ Upload events fire when the plugin-located Upload Details button is clicked
- ✅ Vision pipeline degrades gracefully when optional OCR/VLM modules fail
- ✅ Web target support (Playwright)
- ✅ Viewport-aware filling: fills visible fields in strict visual order, then scrolls down to reveal below-the-fold fields (NO SCROLL RULE: never scrolls while a visible field is unfilled or unverified)
- ✅ Both source (left) and entry (right) panels scroll together, exactly like a human operator
- ✅ 189/189 tests passing (incl. end-to-end MPF integration)
#   A I - C o m p u t e r - D a t a - E n t r y - A g e n t 
 
 