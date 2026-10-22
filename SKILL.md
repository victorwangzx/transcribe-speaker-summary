---
name: transcribe-speaker-summary
description: Transcribe audio/video with timestamps, attribute speaker turns with explicit uncertainty, and summarize each speaker. Use for recordings, meeting/interview transcription, 录音转文字、说话人识别与分人总结. Ask for the delivery destination and local file format when unspecified.
metadata:
  version: "2.1.0"
---

# Transcribe Speaker Summary

Turn recordings into an evidence-linked transcript and speaker summary. This skill supplies a portable local transcription route; it does not bundle Python, FFmpeg, model weights, an automatic diarization engine, or cloud credentials.

## 1. Resolve user choices before writing deliverables

Read [references/output-format.md](references/output-format.md) **before asking about delivery or creating final files**. Reuse choices already given; do not ask again.

When missing, ask together:
- Destination: chat only, local files, a specified cloud document, or cloud plus local files?
- For local files: Markdown `.md`, plain text `.txt`, Word `.docx`, or specified combinations? Ask for the directory. If the user says “doc/Word”, clarify whether `.docx` is acceptable; legacy `.doc` is a separate conversion, never a renamed DOCX.
- For cloud: service, exact document/new-document location, and target section. A cloud choice does **not** authorize an extra local delivery, and vice versa.

Explain that local inference needs a working directory for checkpoints and temporary audio even for cloud-only delivery. Confirm an unspecified working directory before creating it, or use an already-authorized task directory. These intermediates are not final files. Never copy the author's private directories into a new user's configuration.

User-provided names and technical terms guide review; they do not prove which voice speaks at each time. Collect language, known speakers and any desired verbatim/editing level if absent and material. Preserve original-language English terms.

## 2. Check environment; install only with informed approval

For first use, a missing dependency, or a different machine, **read [references/setup.md](references/setup.md)**. Run the bundled read-only preflight with the intended Python. Check audio readability, FFmpeg/ffprobe, transcription library and a local model. It neither installs packages nor downloads models.

All example directories are placeholders. **Tell the user to replace them with their own absolute paths** and confirm the resolved paths. Expand `~` to the current user's home; keep paths with spaces quoted. The author's optional existing environment is documented only in setup.md; it is not a universal default.

Before any installation/model download, state what, purpose, disk/network or cost implications, current license/commercial-use conditions and testing/final-use scope; obtain approval unless that exact scope is already authorized. Prefer existing components. No silent package-manager bootstrap, driver upgrades or paid provider fallback. Download permission for model weights is not permission to upload audio.

## 3. Select and execute a route

**Read [references/transcription-workflow.md](references/transcription-workflow.md) before transcription, speaker attribution or recovery.**

- Default when local processing is suitable: bundled `scripts/transcribe_local.py`, a user-approved local CTranslate2 model, CPU/int8, timestamped JSONL and per-chunk checkpoints. `requirements.txt` specifies the tested engine. This route preserves the original and blocks implicit model downloads.
- Existing OpenAI Whisper/another approved engine: reuse if suitable, recording the actual engine and parameters; do not assume `.pt` and CTranslate2 models are interchangeable.
- Automatic diarization: when requested, use bundled `scripts/diarize_local.py` after the separately approved local pyannote setup. It groups voices as 说话人 1/2 and optionally aligns ASR word timestamps; it does not require real-name confirmation. Read the workflow reference for configuration and validation. Do not silently substitute inferred labels when automatic separation was requested. The ASR script alone does **not** diarize.
- Network transcription: only with explicit approval of provider, upload, cost and purpose. Follow the actual provider's current instructions. Do not switch providers on failure without approval.

Start with a short representative sample when the route/model is unvalidated. Check jargon, quiet speech, timestamps and repeated hallucinations before a long run. Do not continually restart a full recording to experiment. Long runs must retain progress and resume only with matching input/model/settings.

## 4. Review and identify human-required steps

Machine transcription, model confidence and context-based correction are not listening verification. Never claim to have listened or performed voice matching when only text was inspected.

Human participation is needed for:
- install/network/cost approvals; account login, credentials and gated-model terms;
- resolving unknown voices to names when evidence is insufficient;
- unclear/overlapping passages, important numbers/names and exact quotations that cannot be confirmed by the available tools;
- choosing output destination/format/path and any genuinely ambiguous overwrite or section replacement.

Ask for the smallest unresolved information while continuing independent work. If the user cannot confirm a passage or identity, retain `[听不清]`, `[重叠发言]`, `[原词存疑：…]` or `说话人待确认`. Do not block an explicitly requested draft, or disguise it as a fully verified transcript. Speaker numbering by question round is not a count of distinct people.

## 5. Summarize, export and verify

Use timestamps for each speaker's substantive summary. Separate proposals, decisions and commitments. A leadership summary is optional when requested; distinguish spoken content, analysis and user-supplied slide text. Do not turn plausible mechanisms or uncertain ASR into facts.

Follow the chosen route in output-format.md. Export only selected formats; `scripts/export_transcript.py` supports `.md`, `.txt` and optional `.docx`. Leave `.doc` conversion and cloud integration to explicitly selected, available tools. Do not invent cloud command syntax or require DingTalk for local transcription.

Before claiming completion:
- verify source duration, processed chunks including empty/silent chunks, timestamp bounds/order, suspicious gaps/repetitions and final coverage;
- review beginning/middle/end **and** speaker changes, key terms/numbers and low-confidence spans; label the actual review level;
- verify chosen files open and contain the beginning/middle/end; render and inspect Word output with available tooling; mark unverified presentation checks as pending;
- for cloud, read the actual destination first, preserve content outside the requested scope, append/insert deliberately, obey connector limits and read back all inserted text and order;
- report destination, actual formats, speaker method and unresolved limits. Do not infer completion from file existence, exit code or cloud success alone.

## Bundled resources

- `README.md`: distribution entry point and version.
- `requirements.txt`: local ASR engine; no installation is automatic.
- `scripts/preflight.py`: read-only dependency/audio/model inspection.
- `scripts/prepare_audio.py`: optional explicit FFmpeg normalization/chunking.
- `scripts/transcribe_local.py`: local-only checkpointed ASR, continuous timestamps.
- `scripts/diarize_local.py`: local community-1 voice grouping and conservative timestamp alignment.
- `scripts/export_transcript.py`: selected text/Word export; no implicit destination.
- `references/setup.md`, `references/transcription-workflow.md`, `references/output-format.md`: mandatory only at the stages specified above.
