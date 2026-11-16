from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from assistant.interfaces.stt.base import STTError
from assistant.interfaces.stt.local import LocalSTT, create


def test_transcribes_with_language_and_prompt():
    model = MagicMock()
    model.transcribe.return_value = ([SimpleNamespace(text=" chrome "), SimpleNamespace(text="kholo ")], None)
    text = LocalSTT(model=model).transcribe(np.zeros(16000, np.float32), "en", "hint")
    assert text == "chrome kholo"
    kw = model.transcribe.call_args.kwargs
    assert kw["language"] == "en" and kw["initial_prompt"] == "hint" and kw["vad_filter"] is False


def test_model_load_failure_is_one_sentence():
    with patch("faster_whisper.WhisperModel", side_effect=OSError("DLL blocked")):
        with pytest.raises(STTError, match="Offline transcription"):
            LocalSTT().transcribe(np.zeros(10, np.float32), None, None)


def test_settings(config):
    config.settings["stt"] = {"local": {"model": "base", "compute_type": "int8"}}
    stt = create(config)
    assert stt.model_size == "base" and stt.compute_type == "int8"
