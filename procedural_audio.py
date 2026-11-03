"""Small generated sounds; no downloads or third-party audio assets."""

from array import array
import math
from pathlib import Path
import random
import tempfile
import wave
from panda3d.core import Filename


class ProceduralAudio:
    def __init__(self, loader, enabled=True):
        self.sounds = {}
        self.running = False
        self.directory = None
        if not enabled:
            return
        self.directory = tempfile.TemporaryDirectory(prefix="speedhighway-audio-")
        try:
            for name, frequency, duration in (("engine", 65, 1), ("click", 660, 0.09),
                                               ("crash", 90, 0.3), ("signal", 440, 0.18)):
                samples = array("h")
                noise = random.Random(42)
                for index in range(int(22050 * duration)):
                    envelope = 1 if name == "engine" else 1 - index / (22050 * duration)
                    sample = math.sin(2 * math.pi * frequency * index / 22050)
                    if name == "crash":
                        sample *= noise.uniform(-1, 1)
                    samples.append(int(2400 * envelope * sample))
                path = Path(self.directory.name) / (name + ".wav")
                with wave.open(str(path), "wb") as output:
                    output.setnchannels(1)
                    output.setsampwidth(2)
                    output.setframerate(22050)
                    output.writeframes(samples.tobytes())
                self.sounds[name] = loader.loadSfx(Filename.fromOsSpecific(str(path)).getFullpath())
            self.sounds["engine"].setLoop(True)
        except (OSError, RuntimeError):
            self.sounds.clear()

    def play(self, name, muted=False):
        if not muted and name in self.sounds:
            self.sounds[name].play()

    def update(self, speed, driving, muted):
        engine = self.sounds.get("engine")
        if engine is None:
            return
        audible = driving and not muted
        if audible and not self.running:
            engine.play()
        elif not audible and self.running:
            engine.stop()
        self.running = audible
        engine.setPlayRate(0.7 + speed / 220 * 0.8)
        engine.setVolume(0.08 + speed / 220 * 0.18)

    def close(self):
        for sound in self.sounds.values():
            sound.stop()
        self.sounds.clear()
        if self.directory is not None:
            self.directory.cleanup()
            self.directory = None
