# LED Placement Studio

Interactive desktop application for placing LED pads along text outlines (supports Persian/Arabic RTL and Latin LTR). Built with PyQt6 + OpenCV.

## Features

- **Native system font rendering** (including complex scripts via Qt)
- **Max LED count** targeting via adaptive pitch binary search
- **Interactive canvas**: move, add, delete LED nodes
- **Auto & Manual tiling** (A2–A5, B2–B5, custom)
- **Live metrics**: current LED count, estimated pitch
- **Export**: Master JPG, Tile JPGs, CSV coordinates, optional SVG/PDF
- **Zoom / Pan**, Undo/Redo, modern dark UI

## Project Structure

```
LED_Placement_Studio/
├── main.py                 # Entry point
├── requirements.txt
├── README.md
├── core/
│   ├── __init__.py
│   └── engine.py           # Core processing (render, place, tile)
├── ui/
│   ├── __init__.py
│   ├── main_window.py      # Main window + layout
│   ├── sidebar.py          # Left control panel
│   ├── canvas.py           # QGraphicsView interactive editor
│   └── styles.py           # QSS theme
├── styles/
│   └── dark.qss            # Stylesheet
└── assets/                 # Icons, etc. (optional)
```

## Installation

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Packaging (optional)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "LED Placement Studio" main.py
```

## Development Roadmap (Status)

| Sprint | Description                        | Status   |
|--------|------------------------------------|----------|
| 1      | UI Shell & Input Form              | Done     |
| 2      | CoreEngine integration             | Done     |
| 3      | Interactive LED Canvas             | Done     |
| 4      | Tiling Manager (auto + manual)     | Done     |
| 5      | Export Pipeline                    | Done     |

## License

MIT – feel free to modify for your workshop / production needs.
