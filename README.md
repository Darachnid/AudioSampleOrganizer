# ClipMark

Accessible WAV clip marker. Current preferred implementation: **Rust + egui / AccessKit**.

Mark start/end points in a long recording, preview the selection, name it, and export:

```text
source-name.wav
```

## Why Rust + egui

JAWS and other screen readers need structured UI, not a curses screen dump. egui ships with **AccessKit**, which maps widgets to platform accessibility (UI Automation on Windows, AT-SPI on Linux).

## Rust (recommended)

### Requirements

- Rust stable (`rustup`)
- A C linker / system libs for audio and windowing
  - Linux: `alsa-lib` (and usual X11/Wayland deps)
  - Windows: MSVC Build Tools

### Build & run

```bash
cd clipmark-rs
cargo run --release
```

Binary: `clipmark-rs/target/release/clipmark`

### Controls

```text
Space       Play/pause
Left/Right  tap = ±5s, hold = shuttle seek
Up/Down     playback volume
A           clip start
D           clip end
Enter       preview / continue / export
E           status dialog (brief)
Shift+E     status dialog (detail + mode help)
F1 / F2     status / detail during text entry
Q           Quit
```

Workflow: **Edit → Preview → Source → Name → Final → Export**.

## Other implementations in this repo

| Path | Stack | Notes |
|------|--------|------|
| `clipmark-rs/` | Rust + egui + AccessKit | Preferred for accessibility |
| `src/` | Qt 6 + C++ | Also accessible widgets |
| `ClipMark/` | Python + curses | Legacy prototype |

### Qt / C++ (optional)

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
./build/ClipMark
```

## License

See the `LICENSE` file.
