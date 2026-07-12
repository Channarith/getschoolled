---
name: speech-tts
description: How narration audio is produced — natural, cultural neural voices via ElevenLabs, falling back to edge-tts neural, then the on-device browser/mobile voice. Use for Drive Mode / live-class narration, TTS, voice naturalness, ElevenLabs integration, the speech gateway /tts endpoints, or web/mobile audio playback + cancellation. The engine chain and graceful fallback mean narration always plays even with no API key.
---

# Speech / neural TTS

## Engine chain (most natural first)
`ElevenLabs → edge-tts neural → client on-device voice`. Nothing hard-requires a
key: with none set it degrades to edge-tts, then the browser/mobile voice.

## Backend
- ElevenLabs client: `aoep_shared/elevenlabs_tts.py` (stdlib `urllib`;
  `eleven_multilingual_v2`; per-style voice map + `voice_settings`; env overrides
  `ELEVENLABS_VOICE_ID` / `ELEVENLABS_VOICE_<STYLE>`). HTTP is isolated in
  `_http_post` for easy mocking.
- edge-tts neural: `aoep_shared/meeting/natural_tts.py::synthesize_neural`.
- Speech gateway (`services/speech`, pkg `speech_gw`, :8002):
  `POST /tts` and `GET /tts` (GET so mobile expo-av can load a URI) render MP3 via
  the chain, else **501** so the client falls back. `GET /tts/status` reports
  `{available, engine}` so clients probe ONCE instead of per-segment.
- Config: `ELEVENLABS_API_KEY` (secret), `ELEVENLABS_MODEL` (config.py +
  `config/*.env`). Also XTTS/Chatterbox clone backends for custom presenter voices
  (see AGENTS.md).

## Clients
- Web `apps/web/app/lib/tts.ts`: `speakNaturally` probes `serverTtsAvailable()`,
  fetches + plays server MP3 when available, else the best on-device voice
  (`scoreVoice` prefers neural/enhanced voices). `configureServerTts(SPEECH_URL)`
  on mount. **`cancelSpeech()`** stops BOTH browser utterances and server audio —
  Drive Mode routes all its stop/pause/skip through it (don't call
  `speechSynthesis.cancel()` directly, or server audio won't stop).
- Mobile `apps/mobile/src/tts.ts`: `speakNatural` streams server audio via
  `expo-av` (GET /tts URI; long segments fall back), else `expo-speech`.
  `stopSpeech()` stops both; wire it wherever `Speech.stop()` was used.

## Testing
`packages/shared/tests/test_elevenlabs_tts.py` (request shaping, HTTP mocked) +
`services/speech/tests/test_tts_endpoint.py` (chain + 501 + status). Real ElevenLabs
audio needs a live `ELEVENLABS_API_KEY`; verify the wiring via `/tts/status`
flipping to `engine: "elevenlabs"` when the key is set.
