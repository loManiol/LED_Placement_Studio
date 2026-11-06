"""
Interactive QGraphicsView / QGraphicsScene for LED nodes & tiles.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    QTransform,
    QWheelEvent,
)
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QMenu,
)

from core.engine import LEDPad, TileRect


# ---------------------------------------------------------------------------
# LED Node item
# ---------------------------------------------------------------------------

class LEDNode(QGraphicsEllipseItem):
    """Draggable / selectable LED pad visual — drawn at true physical diameter."""

    COLOR_NORMAL = QColor("#89b4fa")
    COLOR_HOVER = QColor("#b4befe")
    COLOR_SELECTED = QColor("#f9e2af")
    COLOR_ON = QColor("#ff3333")
    COLOR_ON_GLOW = QColor("#ff6666")

    def __init__(
        self,
        pad: LEDPad,
        scale: float = 1.0,
        led_dia_mm: float = 5.0,
        parent=None,
    ):
        # scale = scene units per mm → radius matches real LED body size
        self.led_dia_mm = max(0.5, float(led_dia_mm))
        self.radius = (self.led_dia_mm / 2.0) * scale
        r = self.radius
        super().__init__(-r, -r, 2 * r, 2 * r, parent)
        self.pad = pad
        self.scale_factor = scale  # mm → scene units
        self._simulating = False

        self.setPos(pad.x_mm * scale, pad.y_mm * scale)
        self.setBrush(QBrush(self.COLOR_NORMAL))
        self.setPen(QPen(QColor("#1e1e2e"), 1.0))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)
        self.setToolTip(f"LED @ ({pad.x_mm:.1f}, {pad.y_mm:.1f}) mm")

    def set_simulating(self, on: bool):
        self._simulating = on
        if on:
            self.setBrush(QBrush(self.COLOR_ON))
            self.setPen(QPen(QColor("#ffaaaa"), 1.5))
            r = self.radius * 1.15
            self.setRect(-r, -r, 2 * r, 2 * r)
        else:
            self.setBrush(QBrush(self.COLOR_NORMAL))
            self.setPen(QPen(QColor("#1e1e2e"), 1.0))
            r = self.radius
            self.setRect(-r, -r, 2 * r, 2 * r)
        self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            scene = self.scene()
            if scene is not None:
                for v in scene.views():
                    if hasattr(v, "_note_led_moving"):
                        v._note_led_moving()
                        break
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            pos = self.pos()
            self.pad.x_mm = pos.x() / self.scale_factor
            self.pad.y_mm = pos.y() / self.scale_factor
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event):
        if not self._simulating:
            self.setBrush(QBrush(self.COLOR_HOVER))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        if not self._simulating:
            if self.isSelected():
                self.setBrush(QBrush(self.COLOR_SELECTED))
            else:
                self.setBrush(QBrush(self.COLOR_NORMAL))
        super().hoverLeaveEvent(event)

    def paint(self, painter, option, widget=None):
        if self._simulating:
            painter.setBrush(QBrush(QColor(255, 50, 50, 70)))
            painter.setPen(Qt.PenStyle.NoPen)
            r = self.radius * 1.6
            painter.drawEllipse(QPointF(0, 0), r, r)
            self.setBrush(QBrush(self.COLOR_ON))
        elif self.isSelected():
            self.setBrush(QBrush(self.COLOR_SELECTED))
        super().paint(painter, option, widget)


# ---------------------------------------------------------------------------
# Tile rectangle item
# ---------------------------------------------------------------------------

class TileItem(QGraphicsRectItem):
    """Draggable paper tile."""

    def __init__(self, tile: TileRect, scale: float = 1.0, parent=None):
        super().__init__(0, 0, tile.w_mm * scale, tile.h_mm * scale, parent)
        self.tile = tile
        self.scale_factor = scale

        self.setPos(tile.x_mm * scale, tile.y_mm * scale)
        pen = QPen(QColor("#a6e3a1"), 2, Qt.PenStyle.DashLine)
        self.setPen(pen)
        self.setBrush(QBrush(QColor(166, 227, 161, 40)))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(5)
        self.setToolTip(tile.label or "Tile")

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            pos = self.pos()
            self.tile.x_mm = pos.x() / self.scale_factor
            self.tile.y_mm = pos.y() / self.scale_factor
        return super().itemChange(change, value)


# ---------------------------------------------------------------------------
# Canvas View
# ---------------------------------------------------------------------------

class LEDCanvas(QGraphicsView):
    """
    Main interactive view.
    Signals:
        led_count_changed(int)
        status_message(str)
    """

    led_count_changed = pyqtSignal(int)
    status_message = pyqtSignal(str)
    request_add_led = pyqtSignal(float, float)  # x_mm, y_mm

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor("#11111b")))

        self._scale = 2.0  # scene units per mm (for comfortable viewing)
        self._bg_item: Optional[QGraphicsPixmapItem] = None
        self._border_item: Optional[QGraphicsRectItem] = None
        self._nodes: List[LEDNode] = []
        self._tiles: List[TileItem] = []
        self._result = None  # PlacementResult reference
        self._simulating = False
        self._led_dia_mm = 5.0

        # Undo stack
        self._undo_stack: List[List[LEDPad]] = []
        self._redo_stack: List[List[LEDPad]] = []
        self._panning = False
        self._pan_start = None
        self._drag_undo_pushed = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def clear(self):
        self.scene.clear()
        self._bg_item = None
        self._border_item = None
        self._nodes.clear()
        self._tiles.clear()
        self._result = None
        self._simulating = False
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.led_count_changed.emit(0)

    def set_result(self, result, pads: Optional[List[LEDPad]] = None):
        """Load a PlacementResult and plot everything."""
        self.clear()
        self._result = result
        self._led_dia_mm = float(getattr(result, "led_dia_mm", 5.0) or 5.0)
        pads = pads if pads is not None else list(result.pads)

        # Background silhouette
        mask = result.mask
        h, w = mask.shape
        # Make a nice dark-on-light preview
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[mask > 128] = (80, 80, 100, 220)  # soft blue-gray
        rgba[mask <= 128] = (17, 17, 27, 255)  # match canvas bg

        qimg = QImage(
            rgba.data, w, h, w * 4, QImage.Format.Format_RGBA8888
        ).copy()
        pix = QPixmap.fromImage(qimg)

        scene_w = result.final_w_mm * self._scale
        scene_h = result.final_h_mm * self._scale

        self._bg_item = self.scene.addPixmap(pix)
        self._bg_item.setScale(scene_w / w)
        self._bg_item.setZValue(0)

        # Design border (ordered frame around the text bounds)
        margin = 8.0
        self._border_item = QGraphicsRectItem(
            -margin, -margin, scene_w + 2 * margin, scene_h + 2 * margin
        )
        border_pen = QPen(QColor("#585b70"), 2.0)
        border_pen.setCosmetic(True)  # constant pixel width while zooming
        self._border_item.setPen(border_pen)
        self._border_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self._border_item.setZValue(1)
        self.scene.addItem(self._border_item)

        # Large scene so tiles can extend past the design border
        # (edge LEDs stay inside the printed paper, not on the cut line)
        tile_pad = max(scene_w, scene_h) * 0.35 + 80
        self.scene.setSceneRect(
            -tile_pad, -tile_pad, scene_w + 2 * tile_pad, scene_h + 2 * tile_pad
        )

        # LED nodes — drawn at true physical diameter
        for pad in pads:
            node = LEDNode(pad, scale=self._scale, led_dia_mm=self._led_dia_mm)
            self.scene.addItem(node)
            self._nodes.append(node)

        self.led_count_changed.emit(len(self._nodes))
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.status_message.emit(f"Loaded {len(self._nodes)} LEDs")

    def get_current_pads(self) -> List[LEDPad]:
        return [n.pad for n in self._nodes]

    def get_current_tiles(self) -> List[TileRect]:
        return [t.tile for t in self._tiles]

    def set_tiles(self, tiles: List[TileRect]):
        # remove old
        for t in self._tiles:
            self.scene.removeItem(t)
        self._tiles.clear()

        for tile in tiles:
            item = TileItem(tile, scale=self._scale)
            self.scene.addItem(item)
            self._tiles.append(item)

    def add_led_at(self, x_mm: float, y_mm: float):
        self._push_undo()  # snapshot before change
        pad = LEDPad(x_mm, y_mm)
        node = LEDNode(pad, scale=self._scale, led_dia_mm=self._led_dia_mm)
        if self._simulating:
            node.set_simulating(True)
        self.scene.addItem(node)
        self._nodes.append(node)
        self.led_count_changed.emit(len(self._nodes))

    def fit_design(self):
        """Fit the whole design (with border) into the viewport."""
        if self.scene.sceneRect().isEmpty():
            return
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.status_message.emit("View fitted")

    def set_simulate(self, on: bool):
        """Hide text background and light LEDs red, or restore edit view."""
        self._simulating = on
        if self._bg_item is not None:
            self._bg_item.setVisible(not on)
        for node in self._nodes:
            node.set_simulating(on)
        # Dim tiles slightly during simulation so LEDs stand out
        for t in self._tiles:
            t.setOpacity(0.25 if on else 1.0)
        if on:
            self.setBackgroundBrush(QBrush(QColor("#0a0a12")))
        else:
            self.setBackgroundBrush(QBrush(QColor("#11111b")))

    def delete_selected(self):
        to_remove = [n for n in self._nodes if n.isSelected()]
        if not to_remove:
            return
        self._push_undo()
        for n in to_remove:
            self.scene.removeItem(n)
            self._nodes.remove(n)
        self.led_count_changed.emit(len(self._nodes))

    def delete_selected_tiles(self):
        to_remove = [t for t in self._tiles if t.isSelected()]
        for t in to_remove:
            self.scene.removeItem(t)
            self._tiles.remove(t)

    # ------------------------------------------------------------------
    # Undo / Redo
    # ------------------------------------------------------------------
    def _snapshot_pads(self) -> List[LEDPad]:
        return [LEDPad(p.x_mm, p.y_mm, p.tx, p.ty) for p in self.get_current_pads()]

    def _push_undo(self):
        self._undo_stack.append(self._snapshot_pads())
        self._redo_stack.clear()
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)

    def _note_led_moving(self):
        """One undo entry per drag gesture."""
        if not self._drag_undo_pushed:
            self._push_undo()
            self._drag_undo_pushed = True

    def undo(self):
        if not self._undo_stack:
            self.status_message.emit("Nothing to undo")
            return
        self._redo_stack.append(self._snapshot_pads())
        prev = self._undo_stack.pop()
        self._restore_pads(prev)
        self.status_message.emit(f"Undo — {len(prev)} LEDs")

    def redo(self):
        if not self._redo_stack:
            self.status_message.emit("Nothing to redo")
            return
        self._undo_stack.append(self._snapshot_pads())
        nxt = self._redo_stack.pop()
        self._restore_pads(nxt)
        self.status_message.emit(f"Redo — {len(nxt)} LEDs")

    def _restore_pads(self, pads: List[LEDPad]):
        for n in self._nodes:
            self.scene.removeItem(n)
        self._nodes.clear()
        for pad in pads:
            node = LEDNode(pad, scale=self._scale, led_dia_mm=self._led_dia_mm)
            self.scene.addItem(node)
            self._nodes.append(node)
        self.led_count_changed.emit(len(self._nodes))

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        scene_pos = self.mapToScene(event.pos())
        x_mm = scene_pos.x() / self._scale
        y_mm = scene_pos.y() / self._scale

        act_add = menu.addAction("Add LED here")
        act_del = menu.addAction("Delete selected LEDs")
        act_del_tile = menu.addAction("Delete selected Tiles")
        menu.addSeparator()
        act_undo = menu.addAction("Undo")
        act_redo = menu.addAction("Redo")

        chosen = menu.exec(event.globalPos())
        if chosen == act_add:
            self.add_led_at(x_mm, y_mm)
        elif chosen == act_del:
            self.delete_selected()
        elif chosen == act_del_tile:
            self.delete_selected_tiles()
        elif chosen == act_undo:
            self.undo()
        elif chosen == act_redo:
            self.redo()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_undo_pushed = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and self._pan_start is not None:
            delta = event.position().toPoint() - self._pan_start
            self._pan_start = event.position().toPoint()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self._pan_start = None
            self.unsetCursor()
            event.accept()
            return
        self._drag_undo_pushed = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            x_mm = scene_pos.x() / self._scale
            y_mm = scene_pos.y() / self._scale
            self.add_led_at(x_mm, y_mm)
        else:
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)

        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
            self.delete_selected_tiles()
            event.accept()
            return

        if ctrl and key == Qt.Key.Key_Z and not shift:
            self.undo()
            event.accept()
            return
        if ctrl and (key == Qt.Key.Key_Y or (key == Qt.Key.Key_Z and shift)):
            self.redo()
            event.accept()
            return

        super().keyPressEvent(event)
