import numpy as np

from assistant.interfaces.audio import Recorder


class FakeStream:
    def __init__(self, callback, chunks, **kwargs):
        self.callback, self.chunks, self.kwargs = callback, chunks, kwargs
        self.closed = False

    def start(self):
        for c in self.chunks:
            self.callback(c.reshape(-1, 1), len(c), None, None)

    def stop(self):
        pass

    def close(self):
        self.closed = True


def make_recorder(chunks):
    made = {}

    def factory(**kwargs):
        made["stream"] = FakeStream(chunks=chunks, **kwargs)
        return made["stream"]
    return Recorder(stream_factory=factory), made


def test_records_16k_mono_float32():
    rec, made = make_recorder([np.ones(8000, np.float32), np.ones(8000, np.float32)])
    rec.start()
    audio = rec.stop()
    assert made["stream"].kwargs["samplerate"] == 16000 and made["stream"].kwargs["channels"] == 1
    assert audio.dtype == np.float32 and len(audio) == 16000
    assert rec.seconds(audio) == 1.0 and made["stream"].closed


def test_empty_recording():
    rec, _ = make_recorder([])
    rec.start()
    assert rec.seconds(rec.stop()) == 0.0
