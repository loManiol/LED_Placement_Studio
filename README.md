# LED Placement Studio

**Version 1.0.0** — Interactive desktop app for placing LED pads along text outlines.

Supports Persian/Arabic (RTL) and Latin scripts, adaptive pitch from a max-LED target, manual editing, simulation, and tiled print export.

## Features

- **Setup → View** two-page flow (no cluttered sidebars)
- System fonts + custom `.ttf` / `.otf`
- **Target LED count** (auto pitch) or **fixed pitch**
- Live LED counter while you edit
- Drag / add / delete pads · undo/redo
- **Simulate** — hide text, light LEDs red
- Auto & manual tiling (A2–A5, B-series)
- Export: master JPG, CSV coordinates, tile JPGs
- Remembers your last settings & window size

## Quick start

### Windows
1. Install [Python 3.10+](https://www.python.org/downloads/) (check “Add to PATH”)
2. Unzip this folder
3. Double-click **`run.cmd`**

### macOS / Linux
```bash
chmod +x run.sh
./run.sh
```

### Manual
```bash
python -m venv venv
# Windows: venv\Scripts\activate
source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
python main.py
```

## Build a standalone app

```bash
# Windows
build_windows.cmd

# macOS / Linux
./build_macos_linux.sh
```

Output lands in `dist/`.

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| Ctrl+Enter | Generate |
| Ctrl+E | Export |
| Ctrl+1 / Ctrl+2 | Setup / View |
| Ctrl+0 | Fit design |
| Space | Toggle simulate |
| Ctrl+Z / Ctrl+Y | Undo / Redo |
| Delete | Remove selection |
| Double-click | Add LED |
| Scroll wheel | Zoom |

## Project layout

```
LED_Placement_Studio/
├── main.py
├── run.cmd / run.sh
├── requirements.txt
├── core/          # engine + settings + version
├── ui/            # setup page, view page, canvas
├── styles/        # dark theme
└── assets/        # app icon
```

## License

MIT — use it in your workshop or product freely.
