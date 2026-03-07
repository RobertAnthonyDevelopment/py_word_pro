# PyWord Pro

**PyWord Pro** is a Tkinter-based desktop word processor focused on practical, document-first editing with a clean modular architecture.

![PyWord Pro main window](py_word_pro.png)

## Highlights

- Professional Office-style shell UI:
  - Top strip with quick actions and dirty-state indicator
  - Resizable top toolbar with a `Toolbar` menu to add/remove tools and import/export toolbar layouts
  - Command bar with **Home**, **Insert**, **Review**, and **View** tabs
  - Left navigation panel, center document canvas, optional right inspector, and bottom status strip
- Rich-text controls: font family/size, bold/italic/underline/strike, text color, highlight, alignment, line spacing, bullets, and numbered lists.
- Editing helpers: undo/redo, find/replace, select all, symbols, date/time insertion, and horizontal rule insertion.
- Command Palette (`Ctrl/Cmd+Shift+P`): global searchable action launcher with keyboard-first execution across file, edit, format, insert, review, and view commands.
- Memo Builder: automatically generates polished internal memos, internal documentation, and SOP drafts with optional action-item sections.
- Built-in document templates for:
  - Invoices / estimates / quotes
  - Proposals
  - Basic contracts
  - Client / creative briefs
  - Meeting notes with action items
  - Press kits / one-pagers
  - SOPs / checklists
  - Simple marketing docs (flyer copy, email draft, social post plan)
- Social media templates for LinkedIn posts, Instagram captions, X threads, short-form video scripts, and weekly content calendars.
- Template insertion now applies professional structure styling automatically (H1/H2/H3 headings, bullets/numbered lists, checklist rows, key-value labels, placeholders, callouts, and table-style lines) with selectable visual presets (`Professional Blue`, `Clean Slate`, `Modern Teal`) in the template picker.
- Save your current document as a reusable custom template (`Save Current As Template...`) and load it from the template picker.
- `Action Hub` (Review tab): automatically extracts action items (TODOs, checkboxes, owners, due dates), supports live filtering/search, can auto-toggle completion on source lines, assign owners, set/clear due dates (including natural inputs like `today`, `tomorrow`, `+7d`), add new action lines directly, jump to the next urgent task, and generate actionable dashboard snapshots.
- Dictionary Lookup (`Review -> Dictionary Lookup` and `Ctrl+Shift+D`): define selected/cursor words, show spelling-based suggestions, and save custom dictionary entries that persist across sessions.
- Wikipedia Lookup (`Review -> Wikipedia Lookup`, top `Wiki` button, or `Ctrl+Shift+W`): live topic summaries from the Wikipedia API with source links and one-click summary insertion into the document.
- Fancy to-do export: export Action Hub items as a styled HTML report (with grouped owner sections and metrics) via `Review -> Export Fancy To-Do Report`.
- Brand logo support: set a default logo image once (`View -> Set Default Logo...`) to include in generated templates/memos and fancy to-do report exports.
- Security-first document intake:
  - Enforces file-size limits before parsing
  - Blocks macro-enabled legacy formats (`.docm`, `.xlsm`, `.pptm`, etc.)
  - Validates `.docx` archive structure (zip path safety, expansion limits)
  - Blocks DOCX macro/OLE markers (`vbaProject.bin`, embeddings, OLE object markers)
  - Flags suspicious DDE/external-link indicators in DOCX XML/relationship parts
  - Strict file-signature checks (`.docx` must be real OOXML zip; `.txt` must not be binary-disguised)
  - Security audit trail (`pyword_security_audit.log`) and quarantine of blocked payloads (`pyword_quarantine/`)
  - Audit entries are hash-chained (`previous_hash`/`entry_hash`) for tamper-evident event history
  - Optional advanced scanning hooks: `oletools`, `msoffcrypto-tool`, `yara-python`, `pyclamd`
- File support:
  - Open: `.txt`, `.docx`
  - Save: `.txt`, `.docx`
  - Export: `.pdf`
- Review tools: spell check (`pyspellchecker`) and text-to-speech read-aloud (`pyttsx3`).
- View controls: zoom slider, light/dark mode, paper color, sidebar toggle, focus mode, and developer console toggle.
- Persistent local settings (`pyword_config.json`) for theme, zoom, geometry, recents, and UI preferences (`ui_schema_version: 2`, `release_schema_version: 1`).
- Autosave + crash recovery:
  - Timed local recovery snapshots in `pyword_recovery/`
  - Startup restore prompt after unclean shutdown
  - Session snapshots cleared on clean close

## Quick start

### 1) Requirements

- Python 3.10+
- pip

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

Optional security scanners:

```bash
pip install -r requirements-security.txt
```

Optional security env flags:

- `PYWORD_YARA_RULES=/absolute/path/to/rules.yar` to enable YARA matching
- `PYWORD_CLAMAV_SCAN=1` to enforce ClamAV scanning through `clamd`
- `PYWORD_OLETOOLS_SCAN=0` to disable oletools macro scan hook

Security policy is configurable in `pyword_config.json` under the `security` object:

- `strict_mode`
- `max_input_mb`
- `max_docx_entries`
- `max_docx_uncompressed_mb`
- `max_docx_compression_ratio`
- `block_encrypted_office`
- `require_oletools`, `require_msoffcrypto`, `require_yara_rules`, `require_clamav` (fail-closed controls)
- `quarantine_enabled`, `quarantine_dir`, `audit_log_path`

Recovery policy is configurable in `pyword_config.json` under the `recovery` object:

- `enabled`
- `interval_seconds`
- `max_snapshots`
- `recovery_dir`

### 3) Launch

```bash
python main.py
```

## Supported document workflows

| Action | Formats |
| --- | --- |
| Open | `.txt`, `.docx` |
| Save | `.txt`, `.docx` |
| Export | `.pdf` |

## Project structure

```text
py_word_pro/
├── main.py
├── requirements.txt
├── pyword_config.json
└── src/
    ├── app.py
    ├── config.py
    ├── logic/
    │   ├── file_manager.py
    │   ├── formatting.py
    │   ├── processor.py
    │   ├── syntax.py
    │   └── tools.py
    └── ui/
        ├── contracts.py
        ├── workspace.py
        ├── shell/
        │   ├── editor_shell.py
        │   ├── top_strip.py
        │   ├── command_bar.py
        │   ├── navigation_panel.py
        │   ├── inspector_panel.py
        │   ├── status_strip.py
        │   ├── dev_console.py
        └── theme/
            ├── tokens.py
            └── ttk_styles.py
```

## Notes

- `.docx` import/export preserves a broad set of inline formatting and paragraph alignment where possible.
- PDF export uses `fpdf`/`fpdf2` and writes text content to a PDF document.
- Syntax highlighting and shell components are integrated through a typed command dispatcher (`UiCommandRequest`).

## Development

Run a quick syntax check before committing:

```bash
python -m compileall main.py src
```

## Packaging (macOS)

Build a local macOS app bundle and zip artifact:

```bash
./scripts/build_macos.sh
```

Build thin architecture-specific artifacts by setting `PYWORD_TARGET_ARCH`:

```bash
PYWORD_TARGET_ARCH=arm64 ./scripts/build_macos.sh
PYWORD_TARGET_ARCH=x86_64 ./scripts/build_macos.sh
```

Build a universal macOS artifact when the active Python installation supports `universal2`:

```bash
PYWORD_PYTHON_BIN=/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 \
PYWORD_TARGET_ARCH=universal2 \
PYWORD_BINARY_PACKAGES=PIL,lxml,PyInstaller \
PYWORD_ARTIFACT_SUFFIX=macos-universal \
PYWORD_DIST_ROOT=dist/universal2 \
PYWORD_WORK_ROOT=build/universal2 \
./scripts/build_macos.sh
```

Output artifacts:

- `dist/PyWord Pro.app`
- `dist/PyWord-Pro-macos.zip`

The build script runs a macOS binary-architecture preflight before PyInstaller. If the active Python runtime, compiled extension wheels, or PyInstaller bootloaders do not match the requested target architecture, the build fails early with a concrete error instead of dying late inside PyInstaller.

The GitHub Actions release workflow provisions a dedicated universal2 Python toolchain with `./scripts/setup_macos_universal_python.sh`, installs `delocate`, and then resolves each binary package individually. When a dependency publishes a native `universal2` wheel it is installed directly; when a dependency only publishes split `arm64` and `x86_64` wheels, the bootstrap merges them into a universal wheel before installation.

`requirements-macos-release.txt` contains the non-binary runtime packages for the macOS release job. It intentionally excludes `pymupdf`, which is currently not imported by the app and would otherwise force an additional macOS binary compatibility problem into the release workflow.

## License

Distributed under the MIT License.
