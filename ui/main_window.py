"""
Main application window for LED Placement Studio.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from core.engine import CoreEngine, LEDPad, PlacementResult, TileRect, get_paper_dims
from ui.canvas import LEDCanvas
from ui.sidebar import Sidebar


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class GenerateWorker(QThread):
    finished_ok = pyqtSignal(object)  # PlacementResult
    failed = pyqtSignal(str)

    def __init__(self, engine: CoreEngine, kwargs: dict):
        super().__init__()
        self.engine = engine
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.engine.generate(**self.kwargs)
            self.finished_ok.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LED Placement Studio")
        self.resize(1400, 900)

        self.engine = CoreEngine()
        self.result: Optional[PlacementResult] = None
        self.worker: Optional[GenerateWorker] = None

        self._build_ui()
        self._connect_signals()
        self._load_stylesheet()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.sidebar = Sidebar()
        splitter.addWidget(self.sidebar)

        # Right side: canvas + thin toolbar label
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)

        self.canvas = LEDCanvas()
        right_layout.addWidget(self.canvas)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 1060])

        root.addWidget(splitter)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.lbl_leds = QLabel("LEDs: 0")
        self.lbl_pitch = QLabel("Pitch: —")
        self.lbl_size = QLabel("Size: —")
        self.status.addPermanentWidget(self.lbl_size)
        self.status.addPermanentWidget(self.lbl_pitch)
        self.status.addPermanentWidget(self.lbl_leds)
        self.status.showMessage("Ready – enter text & click Generate")

        # Menu shortcuts
        undo_act = QAction("Undo", self)
        undo_act.setShortcut(QKeySequence.StandardKey.Undo)
        undo_act.triggered.connect(self.canvas.undo)
        self.addAction(undo_act)

        redo_act = QAction("Redo", self)
        redo_act.setShortcut(QKeySequence.StandardKey.Redo)
        redo_act.triggered.connect(self.canvas.redo)
        self.addAction(redo_act)

    def _connect_signals(self):
        self.sidebar.generate_clicked.connect(self.on_generate)
        self.sidebar.export_clicked.connect(self.on_export)
        self.sidebar.auto_tile_clicked.connect(self.on_auto_tile)
        self.sidebar.add_tile_clicked.connect(self.on_add_tile)
        self.sidebar.clear_tiles_clicked.connect(self.on_clear_tiles)
        self.sidebar.simulate_clicked.connect(self.on_simulate)
        self.sidebar.stop_simulate_clicked.connect(self.on_stop_simulate)

        self.canvas.led_count_changed.connect(self._update_led_count)
        self.canvas.status_message.connect(self.status.showMessage)

    def _load_stylesheet(self):
        qss_path = Path(__file__).resolve().parent.parent / "styles" / "dark.qss"
        if qss_path.is_file():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # Generate
    # ------------------------------------------------------------------
    def on_generate(self):
        text = self.sidebar.get_text()
        if not text:
            QMessageBox.warning(self, "Missing text", "Please enter some text.")
            return

        font_path = self.sidebar.get_font_path()
        font_family = self.sidebar.get_font_family()

        if not font_path and not font_family:
            QMessageBox.warning(
                self,
                "Font required",
                "Please select a system font or browse a .ttf / .otf file.",
            )
            return

        # Update engine parameters from UI
        self.engine.led_dia_mm = self.sidebar.get_led_dia()
        self.engine.pin_spacing_mm = self.sidebar.get_pin_spacing()

        kwargs = dict(
            text=text,
            font_path=font_path,
            font_family=font_family if not font_path else None,
            language_dir=self.sidebar.get_language_dir(),
            desired_width_mm=self.sidebar.get_desired_width(),
            desired_height_mm=self.sidebar.get_desired_height(),
            placement_mode=self.sidebar.get_placement_mode(),
            max_leds=self.sidebar.get_max_leds(),
            pitch_mm=self.sidebar.get_pitch(),
        )

        self.sidebar.btn_generate.setEnabled(False)
        self.status.showMessage("Generating… (this may take a few seconds)")

        self.worker = GenerateWorker(self.engine, kwargs)
        self.worker.finished_ok.connect(self._on_generate_done)
        self.worker.failed.connect(self._on_generate_fail)
        self.worker.start()

    def _on_generate_done(self, result: PlacementResult):
        self.sidebar.btn_generate.setEnabled(True)
        self.result = result
        self.canvas.set_result(result)
        # ensure we leave any previous simulation
        self.canvas.set_simulate(False)
        self.sidebar.btn_simulate.setEnabled(True)
        self.sidebar.btn_stop.setEnabled(False)

        self.lbl_size.setText(
            f"Size: {result.final_w_mm:.0f} × {result.final_h_mm:.0f} mm"
        )
        self.lbl_pitch.setText(f"Pitch: {result.pitch_mm:.2f} mm")
        self.lbl_leds.setText(f"LEDs: {len(result.pads)}")
        self.status.showMessage(
            f"Done – {len(result.pads)} LEDs at ~{result.pitch_mm:.2f} mm pitch"
        )

    def on_simulate(self):
        if not self.result:
            QMessageBox.information(self, "No design", "Generate a placement first.")
            return
        self.canvas.set_simulate(True)
        self.sidebar.btn_simulate.setEnabled(False)
        self.sidebar.btn_stop.setEnabled(True)
        self.status.showMessage("Simulation ON – LEDs lit, text hidden")

    def on_stop_simulate(self):
        self.canvas.set_simulate(False)
        self.sidebar.btn_simulate.setEnabled(True)
        self.sidebar.btn_stop.setEnabled(False)
        self.status.showMessage("Simulation stopped")

    def _on_generate_fail(self, msg: str):
        self.sidebar.btn_generate.setEnabled(True)
        QMessageBox.critical(self, "Generation failed", msg)
        self.status.showMessage("Generation failed")

    def _update_led_count(self, n: int):
        self.lbl_leds.setText(f"LEDs: {n}")
        if self.result:
            target = self.sidebar.get_max_leds()
            if target:
                self.lbl_leds.setText(f"LEDs: {n} / {target}")

    # ------------------------------------------------------------------
    # Tiling
    # ------------------------------------------------------------------
    def on_auto_tile(self):
        if not self.result:
            QMessageBox.information(self, "No design", "Generate a placement first.")
            return
        tiles = self.engine.auto_tiles(
            self.result,
            paper=self.sidebar.get_paper(),
            orientation=self.sidebar.get_orientation(),
            overlap_mm=self.sidebar.get_overlap(),
            smart=self.sidebar.get_smart_tiling(),
        )
        self.canvas.set_tiles(tiles)
        self.status.showMessage(f"Auto-tiled into {len(tiles)} pieces")

    def on_add_tile(self):
        if not self.result:
            QMessageBox.information(self, "No design", "Generate a placement first.")
            return
        w, h = get_paper_dims(
            self.sidebar.get_paper(), self.sidebar.get_orientation()
        )
        # Place new tile near origin (user can drag)
        tile = TileRect(10, 10, w, h, label=f"T{len(self.canvas.get_current_tiles())+1}")
        current = self.canvas.get_current_tiles()
        current.append(tile)
        self.canvas.set_tiles(current)
        self.status.showMessage("Tile added – drag it into position")

    def on_clear_tiles(self):
        self.canvas.set_tiles([])
        self.status.showMessage("Tiles cleared")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def on_export(self):
        if not self.result:
            QMessageBox.information(self, "No design", "Generate a placement first.")
            return

        out_dir = self.sidebar.get_output_dir()
        out_dir.mkdir(parents=True, exist_ok=True)

        pads = self.canvas.get_current_pads()
        tiles = self.canvas.get_current_tiles()

        try:
            # Master JPG
            master_path = out_dir / "FULL_VIEW_Master.jpg"
            self.engine.render_master_jpg(self.result, pads=pads, output_path=master_path)

            # CSV
            csv_path = out_dir / "led_coordinates.csv"
            self.engine.export_csv(pads, csv_path)

            # Tiles (if any)
            tile_paths = []
            if tiles:
                tile_paths = self.engine.export_tiles(
                    self.result,
                    tiles,
                    pads=pads,
                    output_dir=out_dir,
                    paper=self.sidebar.get_paper(),
                    orientation=self.sidebar.get_orientation(),
                )
            else:
                # auto-generate tiles if none present
                auto = self.engine.auto_tiles(
                    self.result,
                    paper=self.sidebar.get_paper(),
                    orientation=self.sidebar.get_orientation(),
                    overlap_mm=self.sidebar.get_overlap(),
                    smart=self.sidebar.get_smart_tiling(),
                )
                tile_paths = self.engine.export_tiles(
                    self.result,
                    auto,
                    pads=pads,
                    output_dir=out_dir,
                    paper=self.sidebar.get_paper(),
                    orientation=self.sidebar.get_orientation(),
                )

            msg = (
                f"Export complete!\n\n"
                f"• Master: {master_path.name}\n"
                f"• CSV: {csv_path.name}\n"
                f"• Tiles: {len(tile_paths)} files in Parts_To_Print/\n\n"
                f"Folder:\n{out_dir}"
            )
            QMessageBox.information(self, "Export successful", msg)
            self.status.showMessage(f"Exported to {out_dir}")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))
