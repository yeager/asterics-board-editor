"""Text-to-speech with Piper (high quality) and espeak-ng (fallback).

Tries Piper first for natural-sounding Swedish and English speech,
falls back to espeak-ng if Piper is not available.

Usage:
    from asterics_board_editor.tts import speak
    speak("Hej!", lang="sv", speed=1.0)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

# Piper voice models
PIPER_VOICES = {
    "sv": [
        ("sv_SE-nst-medium", "Swedish (NST Medium)"),
    ],
    "en": [
        ("en_US-amy-medium", "English (Amy)"),
    ],
}

ESPEAK_VOICES = {"sv": "sv", "en": "en"}

_piper_path: str | None = None
_voice_dir: Path | None = None
_lock = threading.Lock()

# Settings (loaded from app config)
_settings: dict = {
    "engine": "auto",       # "auto", "piper", "espeak"
    "speed": 1.0,           # 0.5 - 2.0
    "pitch": 1.0,           # 0.5 - 2.0 (espeak only)
    "piper_voice_sv": "sv_SE-nst-medium",
    "piper_voice_en": "en_US-amy-medium",
}


def configure(settings: dict):
    """Update TTS settings from app preferences."""
    _settings.update(settings)


def get_settings() -> dict:
    """Get current TTS settings."""
    return dict(_settings)


def _find_piper() -> tuple[str | None, Path | None]:
    """Find piper binary and voice directory."""
    piper = shutil.which("piper")
    if not piper:
        return None, None
    candidates = [
        Path.home() / ".local" / "share" / "piper-voices",
        Path("/usr/share/piper-voices"),
        Path("/usr/local/share/piper-voices"),
    ]
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        candidates.insert(0, Path(xdg) / "piper-voices")
    for d in candidates:
        if d.exists() and any(d.glob("*.onnx")):
            return piper, d
    return piper, None


def _get_piper() -> tuple[str | None, Path | None]:
    global _piper_path, _voice_dir
    with _lock:
        if _piper_path is None:
            _piper_path, _voice_dir = _find_piper()
            if _piper_path is None:
                _piper_path = ""
    return (_piper_path or None), _voice_dir


def get_available_voices(lang: str = "sv") -> list[tuple[str, str]]:
    """Return list of (voice_id, display_name) for given language."""
    voices = []
    _, voice_dir = _get_piper()
    if voice_dir:
        for vid, name in PIPER_VOICES.get(lang, []):
            if (voice_dir / f"{vid}.onnx").exists():
                voices.append((vid, f"Piper: {name}"))
    espeak = shutil.which("espeak-ng") or shutil.which("espeak")
    if espeak:
        voices.append(("espeak", "espeak-ng"))
    return voices


def _play_wav(wav_path: str):
    """Play a WAV file using available player."""
    for player in ["aplay", "paplay", "pw-play", "ffplay"]:
        exe = shutil.which(player)
        if exe:
            args = [exe]
            if player == "ffplay":
                args += ["-nodisp", "-autoexit"]
            args.append(wav_path)
            try:
                subprocess.Popen(args,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                return
            except Exception:
                continue


def speak_piper(text: str, lang: str = "sv") -> bool:
    """Speak using Piper. Returns True if successful."""
    piper, voice_dir = _get_piper()
    if not piper or not voice_dir:
        return False

    voice_key = f"piper_voice_{lang}"
    voice_id = _settings.get(voice_key, PIPER_VOICES.get(lang, [("", "")])[0][0])
    model_path = voice_dir / f"{voice_id}.onnx"
    if not model_path.exists():
        return False

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name

        cmd = [piper, "--model", str(model_path), "--output_file", wav_path]

        # Speed control via length_scale (inverse: lower = faster)
        speed = _settings.get("speed", 1.0)
        if speed != 1.0:
            length_scale = 1.0 / max(0.3, min(3.0, speed))
            cmd += ["--length-scale", f"{length_scale:.2f}"]

        proc = subprocess.run(
            cmd, input=text.encode("utf-8"),
            capture_output=True, timeout=15)

        if proc.returncode == 0 and os.path.exists(wav_path):
            _play_wav(wav_path)
            def cleanup():
                import time; time.sleep(10)
                try: os.unlink(wav_path)
                except OSError: pass
            threading.Thread(target=cleanup, daemon=True).start()
            return True
    except (subprocess.TimeoutExpired, OSError):
        pass
    return False


def speak_espeak(text: str, lang: str = "sv"):
    """Speak using espeak-ng (fallback)."""
    espeak = shutil.which("espeak-ng") or shutil.which("espeak")
    if not espeak:
        return
    voice = ESPEAK_VOICES.get(lang, lang)
    speed = _settings.get("speed", 1.0)
    pitch = _settings.get("pitch", 1.0)
    wpm = int(130 * speed)
    pitch_val = int(50 * pitch)
    try:
        subprocess.Popen(
            [espeak, "-v", voice, "-s", str(wpm), "-p", str(pitch_val), text],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def speak(text: str, lang: str = "sv"):
    """Speak text using best available TTS engine.

    Respects engine preference from settings.
    Runs in background thread.
    """
    def _do_speak():
        engine = _settings.get("engine", "auto")
        if engine == "piper":
            if not speak_piper(text, lang):
                speak_espeak(text, lang)
        elif engine == "espeak":
            speak_espeak(text, lang)
        else:  # auto
            if not speak_piper(text, lang):
                speak_espeak(text, lang)

    threading.Thread(target=_do_speak, daemon=True).start()


def get_tts_info() -> str:
    """Return info about available TTS for debug/about dialog."""
    piper, voice_dir = _get_piper()
    parts = []
    if piper and voice_dir:
        voices = list(voice_dir.glob("*.onnx"))
        parts.append(f"Piper ({len(voices)} voices)")
    espeak = shutil.which("espeak-ng") or shutil.which("espeak")
    if espeak:
        parts.append("espeak-ng")
    engine = _settings.get("engine", "auto")
    speed = _settings.get("speed", 1.0)
    return (", ".join(parts) if parts else "No TTS") + f" [engine={engine}, speed={speed}x]"
