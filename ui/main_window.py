"""
Main application window – two-page flow (Setup → View).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QWidget,
)

from core.engine import CoreEngine, PlacementResult, TileRect, get_paper_dims
from ui.setup_page import SetupPage
from ui.view_page import ViewPage


class GenerateWorker(QThread):
    finished_ok = pyqtSignal(object)
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


class MainWindow(QMainWindow):
    PAGE_SETUP = 0
    PAGE_VIEW = 1

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LED Placement Studio")
        self.resize(1280, 820)

        self.engine = CoreEngine()
        self.result: Optional[PlacementResult] = None
        self.worker: Optional[GenerateWorker] = None
        self._target_leds: Optional[int] = None

        self._build_ui()
        self._connect()
        self._load_stylesheet()

    def _build_ui(self):
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.setup = SetupPage()
        self.view = ViewPage()

        self.stack.addWidget(self.setup)   # index 0
        self.stack.addWidget(self.view)    # index 1
        self.stack.setCurrentIndex(self.PAGE_SETUP)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Welcome – configure your design, then Generate")

        # Global shortcuts for canvas editing
        undo = QAction("Undo", self)
        undo.setShortcut(QKeySequence.StandardKey.Undo)
        undo.triggered.connect(self.view.canvas.undo)
        self.addAction(undo)

        redo = QAction("Redo", self)
        redo.setShortcut(QKeySequence.StandardKey.Redo)
        redo.triggered.connect(self.view.canvas.redo)
        self.addAction(redo)

    def _connect(self):
        self.setup.generate_clicked.connect(self.on_generate)

        self.view.back_clicked.connect(self._go_setup)
        self.view.simulate_clicked.connect(self.on_simulate)
        self.view.stop_simulate_clicked.connect(self.on_stop_simulate)
        self.view.export_clicked.connect(self.on_export)
        self.view.auto_tile_clicked.connect(self.on_auto_tile)
        self.view.add_tile_clicked.connect(self.on_add_tile)
        self.view.clear_tiles_clicked.connect(self.on_clear_tiles)

        self.view.canvas.led_count_changed.connect(self._on_led_count)
        self.view.canvas.status_message.connect(self.view.show_status)
        self.view.canvas.status_message.connect(self.status.showMessage)

    def _load_stylesheet(self):
        qss = Path(__file__).resolve().parent.parent / "styles" / "dark.qss"
        if qss.is_file():
            self.setStyleSheet(qss.read_text(encoding="utf-8"))

    def _go_setup(self):
        # stop simulation if active
        self.view.canvas.set_simulate(False)
        self.view.set_simulating(False)
        self.stack.setCurrentIndex(self.PAGE_SETUP)
        self.status.showMessage("Setup – adjust settings and generate again")

    def _go_view(self):
        self.stack.setCurrentIndex(self.PAGE_VIEW)

    # ------------------------------------------------------------------
    def on_generate(self):
        text = self.setup.get_text()
        if not text:
            QMessageBox.warning(self, "Missing text", "Please enter some text first.")
            return

        font_path = self.setup.get_font_path()
        font_family = self.setup.get_font_family()
        if not font_path and not font_family:
            QMessageBox.warning(self, "Font required", "Select a system font or browse a font file.")
            return

        self.engine.led_dia_mm = self.setup.get_led_dia()
        self.engine.pin_spacing_mm = self.setup.get_pin_spacing()
        self._target_leds = self.setup.get_max_leds()

        kwargs = dict(
            text=text,
            font_path=font_path,
            font_family=font_family if not font_path else None,
            language_dir=self.setup.get_language_dir(),
            desired_width_mm=self.setup.get_desired_width(),
            desired_height_mm=self.setup.get_desired_height(),
            placement_mode=self.setup.get_placement_mode(),
            max_leds=self._target_leds,
            pitch_mm=self.setup.get_pitch(),
            # tighter, more sensible pitch search range
            pitch_min=max(2.5, self.setup.get_led_dia() * 0.9),
            pitch_max=min(40.0, self.setup.get_desired_width() / 5 if self.setup.get_desired_width() > 0 else 40.0),
        )

        self.setup.set_busy(True)
        self.status.showMessage("Placing LEDs… this may take a few seconds")

        self.worker = GenerateWorker(self.engine, kwargs)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_fail)
        self.worker.start()

    def _on_done(self, result: PlacementResult):
        self.setup.set_busy(False)
        self.result = result

        self.view.canvas.set_result(result)
        self.view.canvas.set_simulate(False)
        self.view.set_simulating(False)

        self.view.set_metrics(
            leds=len(result.pads),
            pitch=result.pitch_mm,
            w_mm=result.final_w_mm,
            h_mm=result.final_h_mm,
            target=self._target_leds,
        )

        self._go_view()
        msg = (
            f"Placed {len(result.pads)} LEDs  ·  "
            f"pitch {result.pitch_mm:.2f} mm  ·  "
            f"{result.final_w_mm:.0f}×{result.final_h_mm:.0f} mm"
        )
        self.view.show_status(msg)
        self.status.showMessage(msg)

    def _on_fail(self, msg: str):
        self.setup.set_busy(False)
        QMessageBox.critical(self, "Generation failed", msg)
        self.status.showMessage("Generation failed")

    def _on_led_count(self, n: int):
        self.view.set_led_count(n, self._target_leds)

    # ------------------------------------------------------------------
    def on_simulate(self):
        if not self.result:
            return
        self.view.canvas.set_simulate(True)
        self.view.set_simulating(True)
        self.view.show_status("Simulation ON – text hidden, LEDs lit")
        self.status.showMessage("Simulation ON")

    def on_stop_simulate(self):
        self.view.canvas.set_simulate(False)
        self.view.set_simulating(False)
        self.view.show_status("Simulation stopped – back to edit mode")
        self.status.showMessage("Simulation stopped")

    # ------------------------------------------------------------------
    def on_auto_tile(self):
        if not self.result:
            return
        tiles = self.engine.auto_tiles(
            self.result,
            paper=self.view.get_paper(),
            orientation=self.view.get_orientation(),
            overlap_mm=self.view.get_overlap(),
            smart=self.view.get_smart_tiling(),
        )
        self.view.canvas.set_tiles(tiles)
        self.view.show_status(f"Auto-tiled into {len(tiles)} pieces")

    def on_add_tile(self):
        if not self.result:
            return
        w, h = get_paper_dims(self.view.get_paper(), self.view.get_orientation())
        tile = TileRect(10, 10, w, h, label=f"T{len(self.view.canvas.get_current_tiles()) + 1}")
        current = self.view.canvas.get_current_tiles()
        current.append(tile)
        self.view.canvas.set_tiles(current)
        self.view.show_status("Tile added – drag it into place")

    def on_clear_tiles(self):
        self.view.canvas.set_tiles([])
        self.view.show_status("Tiles cleared")

    # ------------------------------------------------------------------
    def on_export(self):
        if not self.result:
            QMessageBox.information(self, "No design", "Generate a placement first.")
            return

        out_dir = self.setup.get_output_dir()
        out_dir.mkdir(parents=True, exist_ok=True)

        pads = self.view.canvas.get_current_pads()
        tiles = self.view.canvas.get_current_tiles()

        try:
            master_path = out_dir / "FULL_VIEW_Master.jpg"
            self.engine.render_master_jpg(self.result, pads=pads, output_path=master_path)

            csv_path = out_dir / "led_coordinates.csv"
            self.engine.export_csv(pads, csv_path)

            if not tiles:
                tiles = self.engine.auto_tiles(
                    self.result,
                    paper=self.view.get_paper(),
                    orientation=self.view.get_orientation(),
                    overlap_mm=self.view.get_overlap(),
                    smart=self.view.get_smart_tiling(),
                )

            tile_paths = self.engine.export_tiles(
                self.result,
                tiles,
                pads=pads,
                output_dir=out_dir,
                paper=self.view.get_paper(),
                orientation=self.view.get_orientation(),
            )

            QMessageBox.information(
                self,
                "Export successful",
                f"Saved to:\n{out_dir}\n\n"
                f"• Master JPG\n• CSV coordinates\n• {len(tile_paths)} tile pieces",
            )
            self.view.show_status(f"Exported to {out_dir}")
            self.status.showMessage(f"Exported to {out_dir}")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))
