# LED Placement Studio - Application Architecture & Plan

## 1. Technology Stack
To keep this as a lightweight, single-application package without needing a separate frontend and backend, we will build a native desktop app using Python.

*   **Core GUI Framework:** `PyQt6` (or `PySide6`). It is fast, cross-platform, and we are already using it for the native font rendering.
*   **Interactive Canvas:** `QGraphicsView` and `QGraphicsScene` (built into PyQt6). This allows us to treat the text as a background and every LED pad or Tiling box as a clickable, draggable object.
*   **Image Processing:** `OpenCV` and `NumPy` (already implemented).
*   **Packaging:** `PyInstaller` (to eventually compile the app into a single `.exe` or `.app` file so users don't need to install Python).

## 2. Core Application Modules
The application should be split into distinct modules to keep the code clean and manageable:

1.  **UI/Layout Module:** The left-hand sidebar containing all user inputs (Text, Font Picker, Sizes, Max LEDs, etc.).
2.  **Processing Engine (Worker Thread):** The heavy lifting (OpenCV contour finding, skeletonization). This must run on a background thread so the UI doesn't freeze while calculating.
3.  **Interactive Editor (Canvas):** The central view. Displays the rendered text, dynamically overlays the LEDs as interactive nodes, and overlays the tiling grid.
4.  **Export Engine:** Handles the final generation of CSV, SVG, PDF, and chopped JPG tiles based on the final state of the Canvas.

## 3. Algorithm Tweaks Required
To support your new requirements, our existing logic needs a few upgrades:
*   **Max LED Target:** Currently, the script runs purely on physical *pitch* (distance). To support a "Max LEDs" setting, the algorithm will need to run a fast binary search: guessing a pitch, counting the LEDs, and adjusting the pitch up or down until it hits the user's desired maximum.
*   **Manual Tiling:** Instead of just auto-chopping the image, the user will generate "Tile Objects" (e.g., A4 rectangles) on the canvas. The export engine will crop the final image based on the exact X/Y coordinates of where the user dragged these rectangles.

## 4. Development Roadmap (Step-by-Step)

### Sprint 1: UI Shell & Input Form
*   Create the main window layout (Left panel for controls, Right panel for the preview canvas).
*   Add input widgets: Text box, System Font dropdown selector, Language toggle, Dimensions (Width/Height), Max LED count, and Pitch constraints.
*   Apply a modern stylesheet (QSS) for a sleek, dark-mode or clean light-mode aesthetic.

### Sprint 2: Integration of Core Logic & Headless Rendering
*   Move the existing Python script logic into a separate `CoreEngine` class.
*   Connect the UI "Generate" button to this engine.
*   Take the raw coordinate outputs `(x, y, tx, ty)` and pass them back to the UI instead of immediately saving files.

### Sprint 3: The Interactive LED Canvas
*   Set up the `QGraphicsScene`.
*   Render the text silhouette as the background image.
*   Create a custom `LEDNode` class (inheriting from `QGraphicsEllipseItem`).
*   Plot these nodes using the coordinates from Sprint 2.
*   **Interactivity:** Make nodes `ItemIsMovable` and `ItemIsSelectable`. Add Right-Click context menus to delete nodes. Allow double-clicking on empty spaces on the text to spawn a new LED node.

### Sprint 4: The Tiling Manager
*   Add a "Tiling Mode" toggle.
*   **Auto-Tiling:** Generate draggable bounding boxes (`QGraphicsRectItem`) over the canvas based on selected paper size.
*   **Manual Tiling:** Allow the user to click "Add Tile (A4)", spawn a rectangle, and let them drag it wherever they want. 

### Sprint 5: Export Pipeline
*   Read the *final, edited* positions of all LEDs from the Canvas.
*   Read the *final, edited* positions of all Tile rectangles.
*   Generate the high-res Master JPG.
*   Slice the Master JPG based purely on the Tile rectangles.
*   Generate the SVG/CSV/PDF files.

## 5. Modern Features to Include
*   **Zoom/Pan:** Users can scroll their mouse wheel to zoom into sharp corners and pan around to manually adjust pins.
*   **Live Metrics:** A status bar showing "Current LEDs: 342 / 400" and "Estimated physical pitch: 6.2mm".
*   **Undo/Redo:** Basic stack to undo accidentally deleted LEDs.