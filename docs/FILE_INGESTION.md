# File Ingestion

Capability-registry pipeline that turns files into normalized **`DocumentBundle`** evidence. Deterministic parsing is a **prerequisite** for LLM reasoning — not a non-LLM fallback for workflow generation.

Related: [PRODUCT_SPEC.md](PRODUCT_SPEC.md) §2.4 · [AI_SAFETY_AND_AGENCY.md](AI_SAFETY_AND_AGENCY.md)

---

## 1. Pipeline

1. **Acquire** — link (default) or copy per user choice.  
2. **Identity & limits** — cryptographic hash; MIME sniff from **content**; size/timestamps/permissions; duplicate detect; enforce archive depth, decompression ratio, page count, duration, memory limits.  
3. **Quarantine** — strip/block executable active content, macros, scripts, remote references, malformed archives from worker execution. **Never execute** imported content.  
4. **Adapt** — route to adapter → `DocumentBundle`.  
5. **Chunk** — structural boundaries (page, section, sheet, scene, function, timestamp), not only token windows.  
6. **Index/embed** — only after redaction/privacy checks; record embedding model + dimensions.  
7. **Hand to planner** — normalized content labeled **untrusted evidence** only; never raw instructions with system privilege.

---

## 2. DocumentBundle contract

Normative fields (schema in [`packages/schemas/ingestion/document-bundle.schema.json`](../packages/schemas/ingestion/document-bundle.schema.json)):

| Field | Description |
|-------|-------------|
| `bundle_id` | UUID |
| `source` | `file_id`, path mode, content hash, MIME, size |
| `metadata` | Title, authors, language, dates, adapter id/version |
| `segments[]` | Ordered text/media segments |
| `structure` | Headings, tables, cells, pages/slides/sheets |
| `images[]` | Refs + OCR/vision results if any |
| `transcripts[]` | Time-coded spans for A/V |
| `locators` | Source coordinates per segment |
| `confidence` | Parser confidence 0–1 |
| `warnings[]` | Partial extract, truncated, password needed, … |
| `errors[]` | Typed failures |
| `security` | Quarantine actions taken |

**Locator examples:** PDF page+bbox; DOCX paragraph id; XLSX sheet!cell; video `t=`; Markdown heading path + block id.

---

## 3. Typed failure modes

| Code | Meaning | User action |
|------|---------|-------------|
| `NeedsPassword` | Encrypted/locked | Provide password |
| `NeedsAdapter` | Unknown/unsupported family | Install pack / convert |
| `Corrupt` | Unreadable structure | Replace file |
| `ResourceLimit` | Bomb/limit exceeded | Adjust limits / split |
| `DrmBlocked` | DRM | Use authorized export |
| `PartialSuccess` | Best-effort with warnings | Review warnings |

Filename alone must never invent a successful semantic extract.

---

## 4. Adapter rollout

### Core text

Markdown, plain text, HTML, XML, JSON, YAML, CSV/TSV, logs, source code, notebooks, email, common subtitles.

### Documents

PDF, DOCX, PPTX, XLSX, RTF, EPUB, OpenDocument; scanned + OCR.

### Media

Images (EXIF/OCR/vision); audio/video (FFmpeg metadata + time-coded transcription); multimodal analysis when model supports it.

### Specialized

Archives; SQLite exports; GIS/CAD/scientific via **restricted** adapters; optional downloadable Apache Tika extension pack for broad metadata/text.

### Unknown binary

Metadata + printable strings only when useful; otherwise stop with `NeedsAdapter`.

---

## 5. Security limits (defaults — tunable)

| Limit | Intent |
|-------|--------|
| Max archive nesting depth | Zip bombs |
| Max decompression ratio / bytes | Zip bombs |
| Max pages / sheets / slides / media duration | DoS |
| Max memory per job | Worker stability |
| Reject active macros/scripts | Code exec |
| Block remote resource fetch during parse | SSRF |

---

## 6. Privacy

- Detect sensitive patterns before embed/cloud send; apply redaction policy.  
- Cloud provider transmission requires consent + preview when policy demands.  
- Bundle retains hashes/locators; may omit raw bytes from logs.

---

## 7. Testing per adapter

Mandatory:

- Golden extraction tests + locator assertions  
- Malformed/adversarial fuzz  
- Resource-limit tests  
- Provenance assertions (`derived_from` readiness)  

Corpus: `tests/corpus` (licensing-safe fixtures only).

---

## 8. Acceptance criteria

- AC-ING-01: Linked source hash unchanged after full intake.  
- AC-ING-02: Planner prompt assembly never concatenates untrusted text outside delimited evidence blocks.  
- AC-ING-03: Zip-bomb fixture triggers `ResourceLimit` within bound.  
- AC-ING-04: Password PDF returns `NeedsPassword`, not hallucinated pages.  
- AC-ING-05: Each v1 adapter has ≥1 golden + ≥1 malformed test.

---

## 9. Optional Apache Tika extension pack (future)

Apache Tika is **not** bundled with the core BrainFlow worker. Broad metadata/text coverage for obscure formats is planned as a **downloadable extension pack**:

| Item | Plan |
|------|------|
| Pack id | `brainflow-pack-tika` (tentative) |
| Delivery | Optional install beside the supervised worker; disabled by default |
| Capability | Register a `tika` adapter behind the same `DocumentBundle` contract |
| Security | Still no exec of macros/scripts; resource limits unchanged; remote fetch blocked |
| Failure | If the pack is absent, unsupported formats continue to return `NeedsAdapter` |

Until that pack ships, prefer first-party adapters in `services/ai-worker/brainflow_worker/intake/adapters/`. Schema: [`packages/schemas/ingestion/document-bundle.schema.json`](../packages/schemas/ingestion/document-bundle.schema.json).

### Adapter coverage (v1 core)

Honest status: **Core** = ships without optional extras. **Optional** = real code path when deps/binaries are present; otherwise typed `NeedsAdapter` / `PartialSuccess` (never silent stub-as-success for OCR/transcription).

| Family | Adapter id | Status |
|--------|------------|--------|
| Markdown | `markdown` | Core |
| Plain text | `plain_text` | Core |
| HTML | `html` | Core (scripts stripped) |
| JSON | `json` | Core |
| YAML | `yaml` | Core (PyYAML) |
| CSV/TSV | `csv` | Core |
| Jupyter notebook | `notebook` | Core (`.ipynb`; cells extracted, **never executed**) |
| PDF (text) | `pdf` | Optional `.[intake]` / pypdf; encrypted → `NeedsPassword` |
| DOCX | `docx` | Optional `.[intake]` / python-docx |
| PPTX | `pptx` | Optional `.[intake]` / python-pptx |
| XLSX | `xlsx` | Optional `.[intake]` / openpyxl |
| OpenDocument (ODT/ODS/ODP) | `opendocument` | Core ZIP+`content.xml` fallback; richer structure via `.[intake]` / odfpy |
| Images | `image` | Metadata core (Pillow for EXIF when installed). **OCR:** real Tesseract path via `.[ocr]` (pytesseract + Tesseract binary) or `set_ocr_hook`; missing → `NeedsAdapter` + `ocr_status=unavailable` (not stub-done) |
| Audio / video | `media` | Metadata via **ffprobe** when FFmpeg is on PATH. **Transcription:** real path via `.[media]` (faster-whisper) or `.[media_whisper]` / `set_transcribe_hook`; missing → `NeedsAdapter` (metadata-only is not claimed as full A/V success) |
| Source code | `code` | Core (never executed) |
| Archives | `archive` | Core (depth/ratio/exec quarantine) |
| Unknown binary | `unknown_binary` | Metadata/printable strings only |
| Apache Tika | `tika` | Future pack — not bundled |

#### Optional extras (worker)

| Extra | Enables |
|-------|---------|
| `brainflow-ai-worker[intake]` | pypdf, python-docx/pptx, openpyxl, Pillow, odfpy |
| `brainflow-ai-worker[ocr]` | Pillow + pytesseract (requires system **Tesseract** binary) |
| `brainflow-ai-worker[media]` | faster-whisper (requires model download on first use; **ffprobe**/FFmpeg for metadata) |
| `brainflow-ai-worker[media_whisper]` | openai-whisper alternate |

Install binaries separately: [Tesseract](https://github.com/tesseract-ocr/tesseract), [FFmpeg](https://ffmpeg.org/) (`ffprobe` on `PATH`).
