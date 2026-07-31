"""Speak ClipMark status text for screen-reader workflows."""

import shutil
import subprocess
import sys
import threading


class SpeechOutput:
    """
    Non-blocking status speech via the host TTS engine.

    Windows uses System.Speech (SAPI). Linux tries espeak-ng, espeak, or
    spd-say. If no engine is available, speak() still updates callers via
    status_message without raising.
    """

    def __init__(self, volume_percent=80):
        self.volume_percent = self._bounded_percent(volume_percent)
        self.engine = self._detect_engine()
        self._lock = threading.Lock()
        self._process = None
        self.status_message = self._engine_status()

    @staticmethod
    def _bounded_percent(value):
        return max(0, min(int(value), 100))

    def _detect_engine(self):
        if sys.platform == "win32":
            return "sapi"

        for command in ("espeak-ng", "espeak", "spd-say"):
            if shutil.which(command):
                return command

        return None

    def _engine_status(self):
        if self.engine == "sapi":
            return f"Voice ready (SAPI) at {self.volume_percent}%."

        if self.engine:
            return (
                f"Voice ready ({self.engine}) "
                f"at {self.volume_percent}%."
            )

        return (
            "Voice unavailable. Install espeak-ng on Linux, "
            "or use Windows SAPI. Status still updates on screen."
        )

    def set_volume_percent(self, percent):
        """Set spoken-voice volume from 0 through 100."""

        self.volume_percent = self._bounded_percent(percent)
        self.status_message = (
            f"Voice volume {self.volume_percent}%."
        )
        return self.volume_percent

    def change_volume(self, direction):
        """Step voice volume up (1) or down (-1)."""

        step = 10 if self.volume_percent >= 20 else 5
        return self.set_volume_percent(
            self.volume_percent + (step * direction)
        )

    def stop(self):
        """Stop any in-progress spoken announcement."""

        with self._lock:
            if self._process is not None:
                try:
                    self._process.terminate()
                except OSError:
                    pass
                self._process = None

    def speak(self, text, interrupt=True):
        """Speak text without blocking the UI loop."""

        cleaned = " ".join(str(text).split())
        if not cleaned:
            return

        if interrupt:
            self.stop()

        if self.engine is None:
            self.status_message = cleaned
            return

        thread = threading.Thread(
            target=self._speak_blocking,
            args=(cleaned,),
            name="clipmark-speech",
            daemon=True,
        )
        thread.start()

    def _speak_blocking(self, text):
        try:
            if self.engine == "sapi":
                self._speak_sapi(text)
            else:
                self._speak_command(text)
        except (OSError, subprocess.SubprocessError):
            self.status_message = (
                "Voice failed. Status is on screen."
            )

    def _speak_sapi(self, text):
        volume = self.volume_percent
        escaped = (
            text.replace("`", "``")
            .replace('"', '`"')
            .replace("'", "''")
        )

        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$speak.Volume = {volume}; "
            f"$speak.Speak(\"{escaped}\")"
        )

        with self._lock:
            self._process = subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    script,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            process = self._process

        process.wait()

        with self._lock:
            if self._process is process:
                self._process = None

    def _speak_command(self, text):
        volume = self.volume_percent

        if self.engine in ("espeak-ng", "espeak"):
            # espeak -a is 0..200
            amplitude = max(0, min(volume * 2, 200))
            command = [
                self.engine,
                "-a",
                str(amplitude),
                text,
            ]
        else:
            # spd-say -i is -100..100
            intensity = max(-100, min(volume - 100, 100))
            command = [
                self.engine,
                "-i",
                str(intensity),
                text,
            ]

        with self._lock:
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            process = self._process

        process.wait()

        with self._lock:
            if self._process is process:
                self._process = None
