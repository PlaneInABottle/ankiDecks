"""Cross-platform TTS provider (stdlib only).

macOS'ta mevcut davranışı birebir korur:
    say -o tmp.aiff <text> && ffmpeg -y -i tmp.aiff ... tmp.mp3

Linux/CI'da `say` yoksa sırayla dener:
    espeak-ng / espeak -> wav -> ffmpeg -> mp3

Hiçbiri yoksa sessizce None döner; çağıran taraf (anki_tools)
zaten None durumunu "audio failed, alanı koru" diye yönetiyor.
Bu sayede Linux/CI'da script crash olmaz, sadece audiosuz devam eder.

Override: ANKI_TTS=say|espeak-ng|espeak|none
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess


def available_tts_command() -> str | None:
    override = os.environ.get("ANKI_TTS", "").strip()
    if override.lower() == "none":
        return None
    if override:
        return override if shutil.which(override) else None
    if shutil.which("say"):
        return "say"
    for alt in ("espeak-ng", "espeak", "piper"):
        if shutil.which(alt):
            return alt
    return None


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def text_to_mp3_bytes(text: str, work_basename: str = "tts_tmp") -> bytes | None:
    """Synthesize text and return MP3 bytes, or None when unavailable."""
    if not text or not text.strip():
        return None
    engine = available_tts_command()
    if engine is None:
        return None
    temp_wav = f"{work_basename}.aiff" if engine == "say" else f"{work_basename}.wav"
    output_mp3 = f"{work_basename}.mp3"
    try:
        if engine == "say":
            subprocess.run(["say", "-o", temp_wav, text], check=True)
        elif engine in ("espeak-ng", "espeak"):
            subprocess.run([engine, "-w", temp_wav, text], check=True)
        else:
            # Generic fallback: <engine> -o wav? Best-effort, may fail -> None.
            subprocess.run([engine, text, temp_wav], check=True)
        _run(["ffmpeg", "-y", "-i", temp_wav, "-codec:a", "libmp3lame", "-qscale:a", "2", output_mp3])
        with open(output_mp3, "rb") as handle:
            return handle.read()
    except (OSError, subprocess.CalledProcessError):
        return None
    finally:
        for path in (temp_wav, output_mp3):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
    return None


def generate_audio_base64(text: str, filename_core: str = "tts_tmp") -> str | None:
    data = text_to_mp3_bytes(text, work_basename=filename_core)
    if data is None:
        return None
    return base64.b64encode(data).decode("utf-8")
