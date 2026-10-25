from tts_bakeoff.adapters import cosyvoice2
from tts_bakeoff.adapters.cosyvoice2 import CosyVoice2Adapter


class NewFrontend:  # newer CosyVoice: the frontend loads the reference itself from a path
    def frontend_cross_lingual(self, wav):
        return load_wav(wav, 16000)  # noqa: F821 - only the source text is inspected


class OldFrontend:  # older CosyVoice: the caller passes a 16 kHz tensor
    def frontend_cross_lingual(self, speech):
        return speech


def _model(frontend):
    return type("Model", (), {"frontend": frontend})()


def test_path_is_passed_when_frontend_loads_audio_itself():
    a = CosyVoice2Adapter(prompt_wav="/voices/ref.wav")
    assert a._prompt_arg(_model(NewFrontend())) == "/voices/ref.wav"


def test_tensor_is_loaded_for_older_frontends(monkeypatch):
    monkeypatch.setattr(cosyvoice2, "load_prompt_wav", lambda path, sr: ("tensor", path, sr))
    a = CosyVoice2Adapter(prompt_wav="/voices/ref.wav")
    assert a._prompt_arg(_model(OldFrontend())) == ("tensor", "/voices/ref.wav", 16000)


def test_unknown_frontend_falls_back_to_tensor(monkeypatch):
    monkeypatch.setattr(cosyvoice2, "load_prompt_wav", lambda path, sr: "tensor")
    a = CosyVoice2Adapter(prompt_wav="/voices/ref.wav")
    assert a._prompt_arg(type("Model", (), {})()) == "tensor"
