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
    QGraphicsSceneMouseEvent,
    QGraphicsView,
)

from selection_manager import SelectionManager


class SelectionHandle(QGraphicsEllipseItem):
    def __init__(
        self,
        index: int,
        center: QPointF,
        moved_callback,
        move_finished_callback,
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
        self.move_finished_callback = move_finished_callback
        self.drag_start_position = QPointF(center)

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

    def mousePressEvent(
        self,
        event: QGraphicsSceneMouseEvent,
    ) -> None:
        self.drag_start_position = QPointF(self.pos())
        super().mousePressEvent(event)

    def mouseReleaseEvent(
        self,
        event: QGraphicsSceneMouseEvent,
    ) -> None:
        super().mouseReleaseEvent(event)

        if self.move_finished_callback is not None:
            self.move_finished_callback(
                self.index,
                self.drag_start_position,
                QPointF(self.pos()),
            )

    def itemChange(self, change, value):
        if (
            change
            == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged
        ):
            if self.moved_callback is not None:
                self.moved_callback(
                    self.index,
                    QPointF(self.pos()),
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
        self.set_selection_mode(False)
        self.selection_manager.reset()

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

    def constrain_point_to_image(
        self,
        point: QPointF,
    ) -> QPointF:
        bounds = self._image_item.boundingRect()

        return QPointF(
            max(bounds.left(), min(point.x(), bounds.right())),
            max(bounds.top(), min(point.y(), bounds.bottom())),
        )

    def handle_moved(
        self,
        index: int,
        point: QPointF,
    ) -> None:
        if self._updating_handles:
            return

        constrained_point = self.constrain_point_to_image(
            point
        )

        self.selection_manager.preview_point_move(
            index,
            constrained_point,
        )

    def handle_move_finished(
        self,
        index: int,
        old_point: QPointF,
        new_point: QPointF,
    ) -> None:
        if self._updating_handles:
            return

        constrained_point = self.constrain_point_to_image(
            new_point
        )

        self.selection_manager.commit_point_move(
            index,
            old_point,
            constrained_point,
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
                move_finished_callback=self.handle_move_finished,
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

        zoom_factor = (
            1.25
            if event.angleDelta().y() > 0
            else 1 / 1.25
        )

        current_scale = self.transform().m11()
        new_scale = current_scale * zoom_factor

        if 0.05 <= new_scale <= 20.0:
            self.scale(zoom_factor, zoom_factor)