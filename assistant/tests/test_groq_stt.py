import io
import os
import wave
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import groq
import httpx
import numpy as np
import pytest

from assistant.interfaces.stt import groq as groq_stt
from assistant.interfaces.stt.base import STTError
from assistant.interfaces.stt.groq import GroqSTT, create, to_wav_bytes


def test_wav_encoding_is_16k_mono_pcm():
    data = to_wav_bytes(np.zeros(8000, dtype=np.float32))
    with wave.open(io.BytesIO(data)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, 16000, 8000)


def test_request_and_text():
    client = MagicMock()
    client.audio.transcriptions.create.return_value = SimpleNamespace(text=" chrome kholo ")
    text = GroqSTT("k", client=client).transcribe(np.zeros(16000, np.float32), "en", "hint")
    assert text == "chrome kholo"
    kw = client.audio.transcriptions.create.call_args.kwargs
    assert kw["model"] == "whisper-large-v3-turbo" and kw["language"] == "en" and kw["prompt"] == "hint"
    assert kw["file"][0].endswith(".wav") and isinstance(kw["file"][1], bytes)


def test_auto_language_omits_param():
    client = MagicMock()
    client.audio.transcriptions.create.return_value = SimpleNamespace(text="x")
    GroqSTT("k", client=client).transcribe(np.zeros(10, np.float32), None, None)
    kw = client.audio.transcriptions.create.call_args.kwargs
    assert "language" not in kw and "prompt" not in kw


def test_rate_limit_becomes_stt_error():
    client = MagicMock()
    req = httpx.Request("POST", "https://api.groq.com")
    client.audio.transcriptions.create.side_effect = groq.RateLimitError(
        "boom", response=httpx.Response(429, request=req), body=None)
    with pytest.raises(STTError, match="rate limited"):
        GroqSTT("k", client=client).transcribe(np.zeros(10, np.float32), "en", None)


def test_create_passes_key_explicitly_and_not_via_environ(config, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    config.secrets = {"GROQ_API_KEY": "gsk-test"}
    with patch.object(groq_stt.groq, "Groq") as cls:
        create(config)
    assert cls.call_args.kwargs["api_key"] == "gsk-test"
    assert "GROQ_API_KEY" not in os.environ


def test_create_without_key_raises_one_sentence(config, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    config.secrets = {}
    with pytest.raises(STTError, match="GROQ_API_KEY"):
        create(config)
