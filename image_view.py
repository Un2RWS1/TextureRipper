from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsView,
)

from selection_manager import SelectionManager


class SelectionHandle(QGraphicsEllipseItem):
    def __init__(
        self,
        index: int,
        center: QPointF,
        moved_callback,
        radius: float = 8.0,
    ) -> None:
        super().__init__(
            -radius,
            -radius,
            radius * 2,
            radius * 2,
        )

        self.index = index
        self.moved_callback = moved_callback

        self.setPos(center)

        self.setBrush(QBrush(QColor(255, 170, 0)))
        self.setPen(QPen(QColor(255, 255, 255), 2))

        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
            True,
        )

        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,
            True,
        )

        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges,
            True,
        )

        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,
            True,
        )

        self.setZValue(3)

    def itemChange(self, change, value):
        if (
            change
            == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged
        ):
            if self.moved_callback is not None:
                self.moved_callback(
                    self.index,
                    self.pos(),
                )

        return super().itemChange(change, value)


class ImageView(QGraphicsView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.selection_manager = SelectionManager(self)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._image_item = QGraphicsPixmapItem()
        self._scene.addItem(self._image_item)

        self._selection_polygon = QGraphicsPolygonItem()
        self._selection_polygon.setPen(
            QPen(QColor(0, 220, 255), 3)
        )
        self._selection_polygon.setBrush(
            QBrush(QColor(0, 220, 255, 45))
        )
        self._selection_polygon.setZValue(2)
        self._scene.addItem(self._selection_polygon)

        self._selection_handles: list[SelectionHandle] = []

        self._has_image = False
        self._selection_mode = False
        self._updating_handles = False

        self.selection_manager.selection_changed.connect(
            self.sync_selection_graphics
        )

        self.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform,
            True,
        )

        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )

        self.setResizeAnchor(
            QGraphicsView.ViewportAnchor.AnchorViewCenter
        )

        self.setBackgroundBrush(QColor(45, 45, 45))

        self.setDragMode(
            QGraphicsView.DragMode.ScrollHandDrag
        )

    def set_image(self, pixmap: QPixmap) -> None:
        self.clear_selection()

        self._image_item.setPixmap(pixmap)
        self._scene.setSceneRect(
            self._image_item.boundingRect()
        )

        self._has_image = not pixmap.isNull()

        if self._has_image:
            self.fit_image_to_window()

    def get_image(self) -> QPixmap:
        return self._image_item.pixmap()

    def has_image(self) -> bool:
        return self._has_image

    def get_selection_points(self) -> list[QPointF]:
        return self.selection_manager.get_points()

    def set_selection_mode(self, enabled: bool) -> None:
        self._selection_mode = enabled

        if enabled:
            self.setDragMode(
                QGraphicsView.DragMode.NoDrag
            )
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setDragMode(
                QGraphicsView.DragMode.ScrollHandDrag
            )
            self.unsetCursor()

    def clear_selection(self) -> None:
        self.set_selection_mode(False)
        self.selection_manager.clear()

    def fit_image_to_window(self) -> None:
        if not self._has_image:
            return

        self.resetTransform()

        self.fitInView(
            self._image_item,
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    def point_is_inside_image(
        self,
        point: QPointF,
    ) -> bool:
        return self._image_item.boundingRect().contains(point)

    def handle_moved(
        self,
        index: int,
        point: QPointF,
    ) -> None:
        if self._updating_handles:
            return

        if not self.point_is_inside_image(point):
            return

        self.selection_manager.update_point(
            index,
            point,
        )

    def sync_selection_graphics(
        self,
        points: list[QPointF],
    ) -> None:
        self._updating_handles = True

        while len(self._selection_handles) > len(points):
            handle = self._selection_handles.pop()
            self._scene.removeItem(handle)

        while len(self._selection_handles) < len(points):
            index = len(self._selection_handles)

            handle = SelectionHandle(
                index=index,
                center=points[index],
                moved_callback=self.handle_moved,
            )

            self._selection_handles.append(handle)
            self._scene.addItem(handle)

        for index, point in enumerate(points):
            self._selection_handles[index].setPos(point)

        self._selection_polygon.setPolygon(
            QPolygonF(points)
        )

        self._updating_handles = False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            self._selection_mode
            and event.button() == Qt.MouseButton.LeftButton
        ):
            scene_position = self.mapToScene(
                event.position().toPoint()
            )

            if not self.point_is_inside_image(scene_position):
                return

            added = self.selection_manager.add_point(
                scene_position
            )

            if added and self.selection_manager.is_complete():
                self.set_selection_mode(False)

            return

        super().mousePressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self._has_image:
            return

        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor

        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor

        current_scale = self.transform().m11()
        new_scale = current_scale * zoom_factor

        minimum_scale = 0.05
        maximum_scale = 20.0

        if minimum_scale <= new_scale <= maximum_scale:
            self.scale(zoom_factor, zoom_factor)