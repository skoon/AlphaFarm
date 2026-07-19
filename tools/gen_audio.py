"""One-shot deterministic generator for AlphaFarm's cozy retro-synth audio.

Uses ONLY the Python standard library (wave, math, struct, random) -- no numpy.
Synthesizes 16-bit mono 22050 Hz WAV files into assets/audio/.

Run with:  uv run python tools/gen_audio.py

Every file is regenerated deterministically (fixed RNG seed), so repeated runs
produce byte-identical output. Loopable files (storm_loop, ambient_day,
ambient_night) are built so their first and last samples sit near zero and the
tail crossfades into the head, giving seamless, click-free loops.
"""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 22050
PEAK = 0.7  # hard ceiling on normalized amplitude to keep sounds soft

OUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "audio"

TWO_PI = 2.0 * math.pi


# --------------------------------------------------------------------------- #
# Low-level helpers                                                           #
# --------------------------------------------------------------------------- #
def n_samples(seconds: float) -> int:
    return int(round(seconds * SAMPLE_RATE))


def sine(phase: float) -> float:
    return math.sin(phase)


def triangle(phase: float) -> float:
    """Triangle wave from a phase in radians, range [-1, 1]."""
    t = (phase / TWO_PI) % 1.0
    return 4.0 * abs(t - 0.5) - 1.0


def adsr(i: int, total: int, attack: float, release: float) -> float:
    """Simple attack/decay envelope over sample index i of `total` samples.

    attack/release are fractions of the whole length. Middle sustains at 1.0.
    """
    a = max(1, int(total * attack))
    r = max(1, int(total * release))
    if i < a:
        return i / a
    if i > total - r:
        return max(0.0, (total - i) / r)
    return 1.0


def soft_clip(x: float) -> float:
    """Gentle tanh-ish saturation to avoid harsh peaks, then clamp to PEAK."""
    y = math.tanh(x)
    return max(-PEAK, min(PEAK, y * PEAK))


def normalize(samples: list[float], peak: float = PEAK) -> list[float]:
    m = max((abs(s) for s in samples), default=0.0)
    if m < 1e-9:
        return samples
    scale = peak / m
    return [s * scale for s in samples]


def crossfade_loop(samples: list[float], fade_seconds: float,
                   edge_seconds: float = 0.006) -> list[float]:
    """Make `samples` loop seamlessly.

    Two steps: (1) crossfade the tail into the head so the interior joins
    cleanly, then (2) apply a very short raised-cosine fade at the extreme head
    and tail so the first and last samples sit right at zero. Because both ends
    resolve to ~0, the loop seam is 0 -> 0: continuous and click-free, with only
    a negligible (few-ms) amplitude notch that is inaudible on an ambient pad.
    """
    fade = n_samples(fade_seconds)
    if fade > 0 and fade * 2 < len(samples):
        out = samples[fade:]  # drop the head that we fold into the tail
        n = len(out)
        for k in range(fade):
            # fraction 0 -> just-past-head content, 1 -> original tail
            w = k / fade
            tail = out[n - fade + k]
            head = samples[k]
            out[n - fade + k] = tail * w + head * (1.0 - w)
    else:
        out = list(samples)

    edge = n_samples(edge_seconds)
    n = len(out)
    if edge > 0 and edge * 2 < n:
        for k in range(edge):
            g = 0.5 - 0.5 * math.cos(math.pi * k / edge)  # 0 -> 1 raised cosine
            out[k] *= g
            out[n - 1 - k] *= g
    return out


def write_wav(name: str, samples: list[float]) -> int:
    """Write float samples in [-1, 1] to a 16-bit mono WAV. Returns byte size."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    frames = bytearray()
    for s in samples:
        v = max(-1.0, min(1.0, s))
        frames += struct.pack("<h", int(v * 32767))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(frames))
    return path.stat().st_size


# --------------------------------------------------------------------------- #
# Sound synthesis                                                             #
# --------------------------------------------------------------------------- #
def gen_hoe() -> list[float]:
    """~0.15s low thunk: fast pitch-dropping triangle with a soft body."""
    total = n_samples(0.15)
    out = []
    phase = 0.0
    for i in range(total):
        frac = i / total
        freq = 180.0 - 90.0 * frac  # 180 -> 90 Hz drop
        phase += TWO_PI * freq / SAMPLE_RATE
        env = adsr(i, total, 0.02, 0.6)
        body = 0.7 * triangle(phase) + 0.3 * sine(phase)
        out.append(body * env)
    return normalize(out, 0.65)


def gen_water(rng: random.Random) -> list[float]:
    """~0.25s soft noise-ish squirt: filtered noise riding a rising sine."""
    total = n_samples(0.25)
    out = []
    phase = 0.0
    prev = 0.0
    for i in range(total):
        frac = i / total
        freq = 280.0 + 260.0 * frac  # gentle upward squirt
        phase += TWO_PI * freq / SAMPLE_RATE
        env = adsr(i, total, 0.08, 0.5)
        noise = rng.uniform(-1.0, 1.0)
        prev = 0.82 * prev + 0.18 * noise  # low-pass -> soft
        body = 0.55 * prev + 0.45 * sine(phase)
        out.append(body * env * 0.9)
    return normalize(out, 0.6)


def gen_plant() -> list[float]:
    """~0.15s pop: quick sine blip that pitches upward then fades."""
    total = n_samples(0.15)
    out = []
    phase = 0.0
    for i in range(total):
        frac = i / total
        freq = 420.0 + 380.0 * frac
        phase += TWO_PI * freq / SAMPLE_RATE
        env = adsr(i, total, 0.03, 0.7)
        body = 0.6 * sine(phase) + 0.4 * triangle(phase)
        out.append(body * env)
    return normalize(out, 0.6)


def two_note(freqs, dur, attack=0.02, release=0.4, blend=0.7) -> list[float]:
    """Render a sequence of notes back-to-back with soft envelopes."""
    out = []
    for f in freqs:
        total = n_samples(dur)
        phase = 0.0
        for i in range(total):
            phase += TWO_PI * f / SAMPLE_RATE
            env = adsr(i, total, attack, release)
            body = blend * sine(phase) + (1.0 - blend) * triangle(phase)
            out.append(body * env)
    return out


def gen_harvest() -> list[float]:
    """~0.3s rising two-note chime."""
    out = two_note([523.25, 783.99], dur=0.15, attack=0.03, release=0.5)
    return normalize(out, 0.62)


def gen_credits() -> list[float]:
    """~0.5s pleasant coin arpeggio (major triad + octave)."""
    notes = [523.25, 659.25, 783.99, 1046.50]
    out = two_note(notes, dur=0.125, attack=0.02, release=0.55, blend=0.75)
    return normalize(out, 0.6)


def gen_blip() -> list[float]:
    """~0.08s UI tick: short soft sine."""
    total = n_samples(0.08)
    out = []
    phase = 0.0
    for i in range(total):
        phase += TWO_PI * 880.0 / SAMPLE_RATE
        env = adsr(i, total, 0.08, 0.6)
        out.append(sine(phase) * env)
    return normalize(out, 0.5)


def gen_gift() -> list[float]:
    """~0.4s warm chime: layered thirds with a slow shimmer."""
    total = n_samples(0.4)
    out = []
    p1 = p2 = p3 = 0.0
    for i in range(total):
        p1 += TWO_PI * 440.0 / SAMPLE_RATE
        p2 += TWO_PI * 554.37 / SAMPLE_RATE  # major third
        p3 += TWO_PI * 659.25 / SAMPLE_RATE  # fifth
        env = adsr(i, total, 0.05, 0.55)
        shimmer = 1.0 + 0.04 * sine(TWO_PI * 5.0 * i / SAMPLE_RATE)
        body = (0.45 * sine(p1) + 0.3 * sine(p2) + 0.25 * sine(p3)) * shimmer
        out.append(body * env)
    return normalize(out, 0.6)


def gen_sleep() -> list[float]:
    """~0.8s descending soft tones (a gentle lullaby drop)."""
    notes = [659.25, 523.25, 440.0, 349.23]
    out = two_note(notes, dur=0.2, attack=0.06, release=0.6, blend=0.85)
    return normalize(out, 0.55)


def gen_quest() -> list[float]:
    """~0.9s mysterious rising motif: whole-tone-ish climb with detune."""
    notes = [329.63, 392.0, 466.16, 587.33, 698.46]
    total_per = n_samples(0.18)
    out = []
    for f in notes:
        phase = 0.0
        phase2 = 0.0
        for i in range(total_per):
            phase += TWO_PI * f / SAMPLE_RATE
            phase2 += TWO_PI * (f * 1.006) / SAMPLE_RATE  # subtle detune -> mystery
            env = adsr(i, total_per, 0.08, 0.5)
            body = 0.55 * sine(phase) + 0.45 * triangle(phase2)
            out.append(body * env * 0.9)
    return normalize(out, 0.55)


def gen_storm_loop() -> list[float]:
    """~4s loopable low rumble with slow amplitude wobble.

    Built from a whole number of periods of its slow wobble so start and end
    align, then crossfaded for a click-free seam.
    """
    dur = 4.0
    total = n_samples(dur)
    out = []
    # Two low detuned sines + a slow-moving low partial give a rolling rumble.
    for i in range(total):
        t = i / SAMPLE_RATE
        low = 0.5 * sine(TWO_PI * 55.0 * t) + 0.35 * sine(TWO_PI * 61.0 * t)
        sub = 0.3 * sine(TWO_PI * 41.0 * t)
        # amplitude wobble: whole cycles across the buffer -> loop-friendly
        wobble = 0.6 + 0.4 * (0.5 - 0.5 * math.cos(TWO_PI * 2.0 * i / total))
        out.append(soft_clip((low + sub) * wobble * 0.8))
    out = normalize(out, 0.6)
    return crossfade_loop(out, 0.25)


def gen_ambient_day() -> list[float]:
    """~8s loopable soft alien hum: low sine drone + quiet slow-beating detuned partials."""
    dur = 8.0
    total = n_samples(dur)
    out = []
    for i in range(total):
        t = i / SAMPLE_RATE
        drone = 0.5 * sine(TWO_PI * 110.0 * t)
        # slow-beating detuned partials (very quiet)
        p1 = 0.12 * sine(TWO_PI * 220.5 * t)
        p2 = 0.10 * sine(TWO_PI * 219.3 * t)
        p3 = 0.08 * sine(TWO_PI * 330.6 * t)
        # gentle breathing swell across whole cycles
        swell = 0.75 + 0.25 * (0.5 - 0.5 * math.cos(TWO_PI * 1.0 * i / total))
        out.append((drone + p1 + p2 + p3) * swell * 0.7)
    out = normalize(out, 0.5)
    return crossfade_loop(out, 0.4)


def gen_ambient_night() -> list[float]:
    """~8s loopable darker/softer pad with a hint of shimmer."""
    dur = 8.0
    total = n_samples(dur)
    out = []
    for i in range(total):
        t = i / SAMPLE_RATE
        drone = 0.5 * sine(TWO_PI * 82.41 * t)   # lower, darker
        fifth = 0.18 * sine(TWO_PI * 123.47 * t)
        # faint high shimmer, slow tremolo so it stays soft
        shimmer_amp = 0.05 * (0.5 + 0.5 * sine(TWO_PI * 0.25 * t))
        shimmer = shimmer_amp * sine(TWO_PI * 660.0 * t)
        swell = 0.7 + 0.3 * (0.5 - 0.5 * math.cos(TWO_PI * 1.0 * i / total))
        out.append((drone + fifth + shimmer) * swell * 0.7)
    out = normalize(out, 0.45)
    return crossfade_loop(out, 0.4)


# --------------------------------------------------------------------------- #
# Driver                                                                      #
# --------------------------------------------------------------------------- #
def main() -> None:
    rng = random.Random(1234)  # fixed seed -> deterministic noise
    builders = {
        "hoe.wav": gen_hoe,
        "water.wav": lambda: gen_water(rng),
        "plant.wav": gen_plant,
        "harvest.wav": gen_harvest,
        "credits.wav": gen_credits,
        "blip.wav": gen_blip,
        "gift.wav": gen_gift,
        "sleep.wav": gen_sleep,
        "quest.wav": gen_quest,
        "storm_loop.wav": gen_storm_loop,
        "ambient_day.wav": gen_ambient_day,
        "ambient_night.wav": gen_ambient_night,
    }
    total_bytes = 0
    for name, build in builders.items():
        size = write_wav(name, build())
        total_bytes += size
        print(f"  {name:20s} {size:>8,d} bytes")
    print(f"Wrote {len(builders)} files, {total_bytes:,} bytes total, to {OUT_DIR}")


if __name__ == "__main__":
    main()
