"""Record a few phrases and see which script each STT language setting returns.

    python -m assistant.tools.stt_script_test            # record new clips, then compare
    python -m assistant.tools.stt_script_test --reuse    # compare again using saved clips
    python -m assistant.tools.stt_script_test --local    # also try the offline model

Clips and results are saved under assistant/logs/stt_samples/ (git-ignored).
"""
from __future__ import annotations

import argparse
import json
import time
import wave
from pathlib import Path

import numpy as np

from assistant.core.config import PACKAGE_DIR, load_config
from assistant.core.script import script_of
from assistant.interfaces.stt.base import SAMPLE_RATE, STTError
from assistant.interfaces.stt.groq import to_wav_bytes

SAMPLES_DIR = PACKAGE_DIR / "logs" / "stt_samples"

PHRASES = [
    "chrome kholo",
    "time kya hua hai",
    "Saad ko message bhejo ke main late hoon",
    "Ammi ko bolo ke khana mat banana, main bahar se le aunga",
    "youtube chalao",
    "open calculator",
    "haan",
    "ji",
]


def variants(prompt: str) -> list[tuple[str, str | None, str | None]]:
    return [
        ("auto", None, None),
        ("auto+prompt", None, prompt),
        ("ur", "ur", None),
        ("en", "en", None),
        ("en+prompt", "en", prompt),
    ]


def record_clips() -> list[Path]:
    from assistant.interfaces.audio import Recorder, beep
    from assistant.interfaces.hotkey import PushToTalk

    config = load_config()
    hotkey = config.settings.get("hotkey", "ctrl+alt+space")
    ptt, rec = PushToTalk(hotkey), Recorder()
    ptt.start()
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    try:
        for i, phrase in enumerate(PHRASES, 1):
            while True:
                print(f"\n[{i}/{len(PHRASES)}] Hold {hotkey} and say naturally:  {phrase}")
                ptt.wait_press(); beep("start"); rec.start()
                ptt.wait_release(); audio = rec.stop(); beep("stop")
                secs = len(audio) / SAMPLE_RATE
                if secs >= 0.3:
                    break
                print(f"  too short ({secs:.1f}s), again")
            path = SAMPLES_DIR / f"{i:02d}.wav"
            path.write_bytes(to_wav_bytes(audio))
            print(f"  saved {secs:.1f}s")
            paths.append(path)
    finally:
        ptt.stop()
    return paths


def load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse", action="store_true", help="use clips saved last time")
    parser.add_argument("--local", action="store_true", help="also test the offline model")
    args = parser.parse_args()

    config = load_config()
    prompt = config.settings.get("stt", {}).get("prompt")
    paths = sorted(SAMPLES_DIR.glob("*.wav")) if args.reuse else record_clips()
    if not paths:
        print("No clips found; run without --reuse first.")
        return

    from assistant.interfaces.stt import groq as groq_stt
    providers = [groq_stt.create(config)]
    if args.local:
        from assistant.interfaces.stt import local as local_stt
        providers.append(local_stt.create(config))

    rows = []
    totals: dict[str, dict[str, int]] = {}
    print("\nTranscribing (Groq free tier allows 20 requests a minute, so this paces itself)...")
    for i, path in enumerate(paths):
        audio = load_wav(path)
        phrase = PHRASES[i] if i < len(PHRASES) else path.stem
        print(f"\n#{i + 1} said: {phrase}")
        for provider in providers:
            for label, language, hint in variants(prompt):
                name = f"{provider.name}:{label}"
                start = time.perf_counter()
                try:
                    text = provider.transcribe(audio, language, hint)
                except STTError as e:
                    text = f"<error: {e}>"
                secs = time.perf_counter() - start
                script = script_of(text)
                totals.setdefault(name, {}).setdefault(script, 0)
                totals[name][script] += 1
                rows.append({"clip": path.name, "said": phrase, "variant": name, "text": text,
                             "script": script, "seconds": round(secs, 2)})
                print(f"  {name:18} {secs:4.1f}s  [{script:10}] {text}")
                if provider.name == "groq":
                    time.sleep(3.1)

    print("\nScript per variant (devanagari must be 0):")
    for name, counts in totals.items():
        print(f"  {name:18} " + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    out = SAMPLES_DIR / "results.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
