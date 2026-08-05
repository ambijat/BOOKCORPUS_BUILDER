#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import shutil
import sys
import time
from pathlib import Path

from .paths import AUDIO_DIR, DEBATE_SCRIPT


FALLBACK_TEXT = """
Moderator: Welcome everyone to today’s debate. Our topic: Is geoeconomics truly the key to regional power in the 21st century?

Scholar A (Realist voice): Geoeconomics is fundamentally about relative gains...
"""

VOICE_INDEX = None   # set after listing voices if you want
RATE_FACTOR = 0.95
VOLUME = 1.0

def file_ready(p: Path, min_bytes=1024):
    return p.exists() and p.stat().st_size >= min_bytes

def try_pyttsx3_wav(text: str, wav_path: Path) -> bool:
    try:
        import pyttsx3
        engine = pyttsx3.init()
        if VOICE_INDEX is not None:
            voices = engine.getProperty('voices')
            if 0 <= VOICE_INDEX < len(voices):
                engine.setProperty('voice', voices[VOICE_INDEX].id)
        rate = engine.getProperty('rate')
        engine.setProperty('rate', int(rate * RATE_FACTOR))
        engine.setProperty('volume', float(VOLUME))
        # Always write WAV for Linux/espeak backends
        engine.save_to_file(text, str(wav_path))
        engine.runAndWait()
        # give the filesystem a moment
        time.sleep(0.3)
        return file_ready(wav_path)
    except Exception as e:
        print(f"[pyttsx3] failed: {e}", file=sys.stderr)
        return False

def try_espeak_cli_wav(text: str, wav_path: Path) -> bool:
    # Requires espeak-ng or espeak installed
    tmp = wav_path.parent / "tmp_es_input.txt"
    tmp.write_text(text, encoding="utf-8")
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        print("[espeak] espeak-ng/espeak not found on PATH", file=sys.stderr)
        tmp.unlink(missing_ok=True)
        return False
    import subprocess
    cmd = [exe, "-v", "en", "-s", "170", "-f", str(tmp), "-w", str(wav_path)]
    try:
        subprocess.run(cmd, check=True)
        return file_ready(wav_path)
    except Exception as e:
        print(f"[espeak] failed: {e}", file=sys.stderr)
        return False
    finally:
        tmp.unlink(missing_ok=True)

def maybe_convert_to_mp3(wav_path: Path, mp3_path: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("[info] ffmpeg not installed; keeping WAV only.")
        return False
    import subprocess
    try:
        subprocess.run([ffmpeg, "-y", "-i", str(wav_path), str(mp3_path)], check=True)
        print("[OK] MP3 saved:", mp3_path.resolve())
        return True
    except Exception as e:
        print(f"[ffmpeg] convert failed: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Render the debate script as WAV and, when ffmpeg is available, MP3.")
    parser.add_argument("--script", type=Path, default=DEBATE_SCRIPT, help=f"Input text (default: {DEBATE_SCRIPT})")
    parser.add_argument("--out", type=Path, default=AUDIO_DIR, help=f"Output directory (default: {AUDIO_DIR})")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    debate_text = args.script.read_text(encoding="utf-8") if args.script.exists() else FALLBACK_TEXT
    wav_path = args.out / "debate_cast.wav"
    mp3_path = args.out / "debate_cast.mp3"

    # 1) Try pyttsx3 → WAV
    ok = try_pyttsx3_wav(debate_text, wav_path)
    if not ok:
        print("[warn] pyttsx3 did not produce a WAV; trying espeak-ng CLI...")
        ok = try_espeak_cli_wav(debate_text, wav_path)

    if not ok:
        print("[FAIL] Could not generate audio. Ensure either pyttsx3 works or espeak-ng is installed.", file=sys.stderr)
        sys.exit(1)

    print("[OK] WAV saved:", wav_path.resolve())

    # 2) Optional MP3
    maybe_convert_to_mp3(wav_path, mp3_path)

if __name__ == "__main__":
    main()
