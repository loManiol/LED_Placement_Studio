"""
Main application window – two-page flow (Setup → View).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from core.engine import CoreEngine, PlacementResult, TileRect, get_paper_dims
from core.settings import load_geometry, load_setup, save_geometry, save_setup
from core.version import APP_DESCRIPTION, APP_NAME, APP_VERSION, APP_YEAR
from ui.setup_page import SetupPage
from ui.view_page import ViewPage


class GenerateWorker(QThread):
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, engine: CoreEngine, kwargs: dict):
        super().__init__()
        self.engine = engine
        self.kwargs = kwargs

    def run(self):
        try:
            self.progress.emit("Rendering text…")
            result = self.engine.generate(**self.kwargs)
            self.progress.emit("Done")
            self.finished_ok.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        logo_path = Path(__file__).resolve().parent.parent / "assets" / "logo.jpg"
        if logo_path.is_file():
            from PyQt6.QtGui import QPixmap
            pix = QPixmap(str(logo_path)).scaledToWidth(
                360, Qt.TransformationMode.SmoothTransformation
            )
            logo_lbl = QLabel()
            logo_lbl.setPixmap(pix)
            logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(logo_lbl)
        title = QLabel(f"<h2>{APP_NAME}</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        ver = QLabel(f"Version {APP_VERSION}")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver)
        desc = QLabel(APP_DESCRIPTION)
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)
        foot = QLabel(f"© {APP_YEAR} · Built for makers & workshops")
        foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(foot)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class MainWindow(QMainWindow):
    PAGE_SETUP = 0
    PAGE_VIEW = 1

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  ·  v{APP_VERSION}")
        self.resize(1280, 840)

        icon = Path(__file__).resolve().parent.parent / "assets" / "icon.png"
        if icon.is_file():
            self.setWindowIcon(QIcon(str(icon)))

        self.engine = CoreEngine()
        self.result: Optional[PlacementResult] = None
        self.worker: Optional[GenerateWorker] = None
        self._target_leds: Optional[int] = None

        self._build_ui()
        self._build_menu()
        self._connect()
        self._load_stylesheet()

        load_geometry(self)
        load_setup(self.setup)

    def _build_ui(self):
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.setup = SetupPage()
        self.view = ViewPage()

        self.stack.addWidget(self.setup)
        self.stack.addWidget(self.view)
        self.stack.setCurrentIndex(self.PAGE_SETUP)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.progress = QProgressBar()
        self.progress.setMaximumWidth(180)
        self.progress.setMaximumHeight(14)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 0)  # indeterminate
        self.progress.hide()
        self.status.addPermanentWidget(self.progress)

        self.status.showMessage("Welcome — configure your design, then Generate")

    def _build_menu(self):
        menu = self.menuBar()

        file_m = menu.addMenu("&File")
        act_gen = QAction("Generate", self)
        act_gen.setShortcut(QKeySequence("Ctrl+Return"))
        act_gen.triggered.connect(self.on_generate)
        file_m.addAction(act_gen)

        act_export = QAction("Export…", self)
        act_export.setShortcut(QKeySequence("Ctrl+E"))
        act_export.triggered.connect(self.on_export)
        file_m.addAction(act_export)
        file_m.addSeparator()

        act_quit = QAction("Quit", self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        file_m.addAction(act_quit)

        view_m = menu.addMenu("&View")
        act_setup = QAction("Setup page", self)
        act_setup.setShortcut(QKeySequence("Ctrl+1"))
        act_setup.triggered.connect(self._go_setup)
        view_m.addAction(act_setup)

        act_view = QAction("Editor page", self)
        act_view.setShortcut(QKeySequence("Ctrl+2"))
        act_view.triggered.connect(lambda: self._go_view() if self.result else None)
        view_m.addAction(act_view)
        view_m.addSeparator()

        act_fit = QAction("Fit design in view", self)
        act_fit.setShortcut(QKeySequence("Ctrl+0"))
        act_fit.triggered.connect(self.view.canvas.fit_design)
        view_m.addAction(act_fit)

        act_sim = QAction("Simulate LEDs", self)
        act_sim.setShortcut(QKeySequence("Space"))
        act_sim.triggered.connect(self._toggle_simulate)
        view_m.addAction(act_sim)

        edit_m = menu.addMenu("&Edit")
        undo = QAction("Undo", self)
        undo.setShortcut(QKeySequence.StandardKey.Undo)
        undo.triggered.connect(self.view.canvas.undo)
        edit_m.addAction(undo)

        redo = QAction("Redo", self)
        redo.setShortcut(QKeySequence.StandardKey.Redo)
        redo.triggered.connect(self.view.canvas.redo)
        edit_m.addAction(redo)

        help_m = menu.addMenu("&Help")
        act_about = QAction("About…", self)
        act_about.triggered.connect(self._show_about)
        help_m.addAction(act_about)

        act_keys = QAction("Keyboard shortcuts", self)
        act_keys.triggered.connect(self._show_shortcuts)
        help_m.addAction(act_keys)

    def _connect(self):
        self.setup.generate_clicked.connect(self.on_generate)

        self.view.back_clicked.connect(self._go_setup)
        self.view.simulate_clicked.connect(self.on_simulate)
        self.view.stop_simulate_clicked.connect(self.on_stop_simulate)
        self.view.export_clicked.connect(self.on_export)
        self.view.auto_tile_clicked.connect(self.on_auto_tile)
        self.view.add_tile_clicked.connect(self.on_add_tile)
        self.view.clear_tiles_clicked.connect(self.on_clear_tiles)
        self.view.fit_clicked.connect(self.view.canvas.fit_design)

        self.view.canvas.led_count_changed.connect(self._on_led_count)
        self.view.canvas.status_message.connect(self.view.show_status)
        self.view.canvas.status_message.connect(self.status.showMessage)

    def _load_stylesheet(self):
        qss = Path(__file__).resolve().parent.parent / "styles" / "dark.qss"
        if qss.is_file():
            self.setStyleSheet(qss.read_text(encoding="utf-8"))

    def closeEvent(self, event):
        save_setup(self.setup)
        save_geometry(self)
        super().closeEvent(event)

    def _go_setup(self):
        self.view.canvas.set_simulate(False)
        self.view.set_simulating(False)
        self.stack.setCurrentIndex(self.PAGE_SETUP)
        self.status.showMessage("Setup — adjust settings and generate")

    def _go_view(self):
        self.stack.setCurrentIndex(self.PAGE_VIEW)

    def _show_about(self):
        AboutDialog(self).exec()

    def _show_shortcuts(self):
        QMessageBox.information(
            self,
            "Keyboard shortcuts",
            "Ctrl+Enter     Generate\n"
            "Ctrl+E         Export\n"
            "Ctrl+1 / 2     Setup / View page\n"
            "Ctrl+0         Fit design in view\n"
            "Space          Toggle simulate\n"
            "Ctrl+Z / Y     Undo / Redo\n"
            "Delete         Remove selected LEDs or tiles\n"
            "Double-click   Add LED\n"
            "Scroll wheel   Zoom\n"
            "Drag           Move pads / tiles",
        )

    def _toggle_simulate(self):
        if self.stack.currentIndex() != self.PAGE_VIEW or not self.result:
            return
        if self.view.btn_stop.isEnabled():
            self.on_stop_simulate()
        else:
            self.on_simulate()

    # ------------------------------------------------------------------
    def on_generate(self):
        if self.worker and self.worker.isRunning():
            return

        text = self.setup.get_text()
        if not text:
            QMessageBox.warning(self, "Missing text", "Please enter some text first.")
            return

        font_path = self.setup.get_font_path()
        font_family = self.setup.get_font_family()
        if not font_path and not font_family:
            QMessageBox.warning(
                self, "Font required", "Select a system font or browse a font file."
            )
            return

        w = self.setup.get_desired_width()
        h = self.setup.get_desired_height()
        if w <= 0 and h <= 0:
            QMessageBox.warning(
                self, "Size required", "Set a desired width or height (mm)."
            )
            return

        self.engine.led_dia_mm = self.setup.get_led_dia()
        self.engine.pin_spacing_mm = self.setup.get_pin_spacing()
        self._target_leds = self.setup.get_max_leds()

        # Search range for automatic gap (edge-to-edge)
        design_span = w if w > 0 else h
        gap_min = 0.3
        gap_max = min(30.0, max(2.0, design_span / 8.0))

        kwargs = dict(
            text=text,
            font_path=font_path,
            font_family=font_family if not font_path else None,
            language_dir=self.setup.get_language_dir(),
            desired_width_mm=w,
            desired_height_mm=h,
            placement_mode=self.setup.get_placement_mode(),
            max_leds=self._target_leds,
            gap_mm=self.setup.get_gap(),
            gap_min=gap_min,
            gap_max=gap_max,
        )

        save_setup(self.setup)
        self.setup.set_busy(True)
        self.progress.show()
        self.status.showMessage("Placing LEDs…")

        self.worker = GenerateWorker(self.engine, kwargs)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_fail)
        self.worker.progress.connect(self.status.showMessage)
        self.worker.start()

    def _on_done(self, result: PlacementResult):
        self.setup.set_busy(False)
        self.progress.hide()
        self.result = result

        self.view.canvas.set_result(result)
        self.view.canvas.set_simulate(False)
        self.view.set_simulating(False)

        self.view.set_metrics(
            leds=len(result.pads),
            gap=result.gap_mm,
            spacing=result.spacing_mm,
            w_mm=result.final_w_mm,
            h_mm=result.final_h_mm,
            target=self._target_leds,
        )

        self._go_view()
        msg = (
            f"Placed {len(result.pads)} LEDs  ·  "
            f"gap {result.gap_mm:.2f} mm (centres {result.spacing_mm:.2f} mm)  ·  "
            f"{result.final_w_mm:.0f}×{result.final_h_mm:.0f} mm"
        )
        self.view.show_status(msg)
        self.status.showMessage(msg)

    def _on_fail(self, msg: str):
        self.setup.set_busy(False)
        self.progress.hide()
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
        self.view.show_status("Simulation ON — text hidden, LEDs lit")
        self.status.showMessage("Simulation ON")

    def on_stop_simulate(self):
        self.view.canvas.set_simulate(False)
        self.view.set_simulating(False)
        self.view.show_status("Simulation stopped — edit mode")
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
        tile = TileRect(
            10, 10, w, h, label=f"T{len(self.view.canvas.get_current_tiles()) + 1}"
        )
        current = self.view.canvas.get_current_tiles()
        current.append(tile)
        self.view.canvas.set_tiles(current)
        self.view.show_status("Tile added — drag it into place")

    def on_clear_tiles(self):
        self.view.canvas.set_tiles([])
        self.view.show_status("Tiles cleared")

    # ------------------------------------------------------------------
    def on_export(self):
        if not self.result:
            QMessageBox.information(self, "No design", "Generate a placement first.")
            return
        if self.stack.currentIndex() != self.PAGE_VIEW:
            self._go_view()

        out_dir = self.setup.get_output_dir()
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "Output folder", f"Cannot create folder:\n{e}")
            return

        pads = self.view.canvas.get_current_pads()
        tiles = self.view.canvas.get_current_tiles()

        self.progress.show()
        self.status.showMessage("Exporting…")
        QApplication.processEvents()

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

            self.progress.hide()
            QMessageBox.information(
                self,
                "Export successful",
                f"Saved to:\n{out_dir}\n\n"
                f"• {master_path.name}\n"
                f"• {csv_path.name}\n"
                f"• {len(tile_paths)} tile pieces in Parts_To_Print/",
            )
            self.view.show_status(f"Exported to {out_dir}")
            self.status.showMessage(f"Exported to {out_dir}")
        except Exception as e:
            self.progress.hide()
            QMessageBox.critical(self, "Export failed", str(e))
            self.status.showMessage("Export failed")
