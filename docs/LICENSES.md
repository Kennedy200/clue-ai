# Dependency licences

Checked from each project's published licence; verify before commercial redistribution.

| Dependency | Licence | Commercial use |
|---|---|---|
| FastAPI, Starlette, Uvicorn, Pydantic, SQLAlchemy, Alembic, httpx, argon2-cffi, cryptography | MIT / BSD / Apache-2.0 | Yes |
| faster-whisper, CTranslate2 | MIT | Yes |
| OpenAI Whisper model weights (downloaded on first use) | MIT | Yes |
| kokoro-onnx | MIT | Yes |
| Kokoro-82M voice model | Apache-2.0 | Yes |
| onnxruntime | MIT | Yes |
| **espeak-ng** (pulled in by kokoro-onnx for phonemes) | **GPL-3.0** | **Flag:** we call it as a separate library at runtime and do not redistribute it, but if you ship a bundled product, get legal advice or swap the phonemiser |
| Pillow | HPND | Yes |
| numpy | BSD | Yes |
| Next.js, React, Tailwind CSS | MIT | Yes |
| **FFmpeg** (installed by the user, not bundled) | LGPL or **GPL** depending on the build; the recommended "full" build includes GPL parts (libx264) | Using it to render your own videos is fine. Do not redistribute the binary inside a product without checking its licence |
| Fonts: Space Grotesk, Inter, JetBrains Mono (Google Fonts) | SIL OFL 1.1 | Yes |

Wikimedia Commons images keep their own per-file licence; Clue AI records author and licence and skips NC and ND files.
AI images from Pollinations are AI-generated; check their current terms before commercial use.
