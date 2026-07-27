# Sample Extraction Tool

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

## Requirements

- Python 3
- A terminal
- Linux or macOS

Windows may also work after installing `windows-curses`, but has not yet been fully tested.

Python packages:

* numpy
* pyglet
* sounddevice
* soundfile

## Installation

Clone the repository:

```bash
git clone <repository-url>
cd SampleExtractionTool
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

## Running

```bash
python3 sampleExtracter.py
```

Enter the full path to a WAV file when prompted.

Paths may be entered with or without quotation marks.

## Controls

```text
Space       Play/pause
Left/Right  transport controls
Up/Down     volume
S           clip start
E           clip end
Enter       commit
Q           Quit
```

After pressing Enter, the selected clip is previewed automatically.

Enter the source and clip name when prompted. The exported filename will use this format:

```text
source-name.wav
```

## License

See the `LICENSE` file.
