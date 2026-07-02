CUSTOM PRESENTER VOICES
========================

Register a cloned voice from a short reference recording (6-60 seconds, clean audio).

1. Record sample.wav (one speaker, minimal background noise, teaching tone).

2. Register:
   python3 scripts/register_voice.py instructor_jane path/to/sample.wav \
       --label "Jane Instructor" --present-mode lewin

3. Test all engines (edge, chatterbox, xtts, elevenlabs):
   python3 scripts/test_voice_engines.py --sample voices/instructor_jane/sample.wav \
       --voice-id instructor_jane --play

4. Present a course with your voice:
   python3 scripts/present_course.py "output/harvest/courses/.../course.json" \
       --persona instructor_jane --tts-engine clone --with-media

ENGINE SETUP
------------

edge (free, no clone):
  pip install edge-tts

chatterbox (free, MIT, self-hosted clone):
  Run Chatterbox-TTS-Server locally, then:
  export CHATTERBOX_TTS_URL=http://127.0.0.1:8004

xtts (free, platform speech stack):
  export XTTS_TTS_URL=http://127.0.0.1:8100
  (or SPEECH_BASE_URL when the speech gateway exposes /tts/synthesize)

elevenlabs (paid API, premium quality):
  export ELEVENLABS_API_KEY=your_key
  python3 scripts/register_voice.py myvoice sample.wav --elevenlabs

Try engines in order (default):
  export CLONE_TTS_PRIORITY=chatterbox,xtts,elevenlabs,edge

List registered voices:
  python3 scripts/present_course.py --list-voices

Consent: only clone voices you have permission to use.
