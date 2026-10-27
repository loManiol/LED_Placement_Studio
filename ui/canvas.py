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
    """Draggable / selectable LED pad visual."""

    RADIUS = 6.0  # scene units (≈ mm * scale)
    COLOR_NORMAL = QColor("#89b4fa")
    COLOR_HOVER = QColor("#b4befe")
    COLOR_SELECTED = QColor("#f9e2af")
    COLOR_ON = QColor("#ff3333")       # bright red when simulating
    COLOR_ON_GLOW = QColor("#ff6666")

    def __init__(self, pad: LEDPad, scale: float = 1.0, parent=None):
        r = self.RADIUS
        super().__init__(-r, -r, 2 * r, 2 * r, parent)
        self.pad = pad
        self.scale_factor = scale  # mm → scene units
        self._simulating = False

        self.setPos(pad.x_mm * scale, pad.y_mm * scale)
        self.setBrush(QBrush(self.COLOR_NORMAL))
        self.setPen(QPen(QColor("#1e1e2e"), 1.5))
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
            self.setPen(QPen(QColor("#ffaaaa"), 2))
            # slightly larger for “glow”
            r = self.RADIUS * 1.25
            self.setRect(-r, -r, 2 * r, 2 * r)
        else:
            self.setBrush(QBrush(self.COLOR_NORMAL))
            self.setPen(QPen(QColor("#1e1e2e"), 1.5))
            r = self.RADIUS
            self.setRect(-r, -r, 2 * r, 2 * r)
        self.update()

    def itemChange(self, change, value):
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
            # soft outer glow
            painter.setBrush(QBrush(QColor(255, 50, 50, 80)))
            painter.setPen(Qt.PenStyle.NoPen)
            r = self.RADIUS * 2.2
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

        # Undo stack (simple list of pad snapshots)
        self._undo_stack: List[List[LEDPad]] = []
        self._redo_stack: List[List[LEDPad]] = []

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

        # Slightly larger scene so border is fully visible
        self.scene.setSceneRect(
            -margin - 4, -margin - 4, scene_w + 2 * margin + 8, scene_h + 2 * margin + 8
        )

        # LED nodes
        for pad in pads:
            node = LEDNode(pad, scale=self._scale)
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
        pad = LEDPad(x_mm, y_mm)
        node = LEDNode(pad, scale=self._scale)
        if self._simulating:
            node.set_simulating(True)
        self.scene.addItem(node)
        self._nodes.append(node)
        self.led_count_changed.emit(len(self._nodes))
        self._push_undo()

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
    def _push_undo(self):
        snapshot = [LEDPad(p.x_mm, p.y_mm, p.tx, p.ty) for p in self.get_current_pads()]
        self._undo_stack.append(snapshot)
        self._redo_stack.clear()
        if len(self._undo_stack) > 40:
            self._undo_stack.pop(0)

    def undo(self):
        if not self._undo_stack:
            return
        current = [LEDPad(p.x_mm, p.y_mm, p.tx, p.ty) for p in self.get_current_pads()]
        self._redo_stack.append(current)
        prev = self._undo_stack.pop()
        self._restore_pads(prev)

    def redo(self):
        if not self._redo_stack:
            return
        current = [LEDPad(p.x_mm, p.y_mm, p.tx, p.ty) for p in self.get_current_pads()]
        self._undo_stack.append(current)
        nxt = self._redo_stack.pop()
        self._restore_pads(nxt)

    def _restore_pads(self, pads: List[LEDPad]):
        for n in self._nodes:
            self.scene.removeItem(n)
        self._nodes.clear()
        for pad in pads:
            node = LEDNode(pad, scale=self._scale)
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

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            x_mm = scene_pos.x() / self._scale
            y_mm = scene_pos.y() / self._scale
            self.add_led_at(x_mm, y_mm)
        else:
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.delete_selected()
            self.delete_selected_tiles()
        elif event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Z:
                self.undo()
            elif event.key() == Qt.Key.Key_Y:
                self.redo()
        else:
            super().keyPressEvent(event)
