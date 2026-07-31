# ClipMark

A terminal-based Python tool for extracting named WAV clips from long recordings.

## Features

* Play and pause audio
* Scrub forward and backward
* Adjust preview volume
* Mark clip start and end points
* Preview clips before exporting
* Export clips as:

```text
source-name.wav
```

## Windows (plug and play)

1. Install [Python 3](https://www.python.org/downloads/)
   - On the first installer screen, check **Add python.exe to PATH**
2. Download or clone this folder (for example `C:\Users\You\ClipMark`)
3. Double-click **`setup.bat`** once
4. Double-click **`run.bat`** whenever you want to use ClipMark

Or from Command Prompt:

```bat
cd C:\path\to\ClipMark
setup.bat
run.bat
```

Use **Command Prompt** or **Windows Terminal**, not a broken IDE mini-console.

When prompted, paste the full path to a WAV file, for example:

```text
C:\Users\You\Music\recording.wav
```

## Linux / macOS

### Requirements

- Python 3
- A terminal

Python packages:

* numpy
* pyglet
* sounddevice
* soundfile

### Installation

Clone the repository:

```bash
git clone <repository-url>
cd ClipMark
```

Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

On Arch Linux or Manjaro, install the required system libraries with:

```bash
sudo pacman -S --needed portaudio libsndfile
```

### Running

From the project root:

```bash
python3 -m ClipMark
```

Enter the full path to a WAV file when prompted.

Paths may be entered with or without quotation marks.

## Controls

```text
Space       Play/pause
Left/Right  transport controls
Up/Down     playback volume
A           clip start
D           clip end
Enter       preview / continue
E           speak brief status
Shift+E     speak detailed status + mode help
W/S         spoken-voice volume
F1 / F2     status / detail during text entry
Q           Quit
```

Screen-reader note: the curses UI is one screen buffer, so JAWS whole-screen read is limited. Use **E** / **Shift+E** (or **F1** / **F2** while typing names) for spoken, mode-aware status instead of re-reading the whole screen.

After pressing Enter, the selected clip is previewed automatically.

Enter the source and clip name when prompted. The exported filename will use this format:

```text
source-name.wav
```

## License

See the `LICENSE` file.
