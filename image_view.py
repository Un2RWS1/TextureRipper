from PySide6.QtCore import QPointF, QRect, Qt
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
    QLabel,
)

from edge_snapper import EdgeSnapper
from selection_manager import SelectionManager


class SelectionHandle(QGraphicsEllipseItem):
    def __init__(
        self,
        index: int,
        center: QPointF,
        moved_callback,
        move_started_callback,
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
        self.move_started_callback = move_started_callback
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

        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setZValue(3)

    def mousePressEvent(
        self,
        event: QGraphicsSceneMouseEvent,
    ) -> None:
        self.drag_start_position = QPointF(self.pos())

        if self.move_started_callback is not None:
            self.move_started_callback(
                self.index,
                QPointF(self.pos()),
            )

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
    MAGNIFIER_SIZE = 190
    MAGNIFIER_SOURCE_SIZE = 50
    MAGNIFIER_MARGIN = 16

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.selection_manager = SelectionManager(self)

        self.edge_snapper = EdgeSnapper()
        self._edge_snapping_enabled = False

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
        self._dragging_handle = False

        self.create_magnifier()

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

    def create_magnifier(self) -> None:
        self.magnifier_label = QLabel(self.viewport())

        self.magnifier_label.setFixedSize(
            self.MAGNIFIER_SIZE,
            self.MAGNIFIER_SIZE,
        )
        self.magnifier_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.magnifier_label.setStyleSheet(
            """
            QLabel {
                background-color: #202020;
                border: 3px solid white;
                border-radius: 5px;
            }
            """
        )

        self.magnifier_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        self.magnifier_label.hide()
        self.position_magnifier()

    def position_magnifier(self) -> None:
        viewport_width = self.viewport().width()

        x_position = (
            viewport_width
            - self.MAGNIFIER_SIZE
            - self.MAGNIFIER_MARGIN
        )

        self.magnifier_label.move(
            max(self.MAGNIFIER_MARGIN, x_position),
            self.MAGNIFIER_MARGIN,
        )

    def show_magnifier(
        self,
        scene_position: QPointF,
    ) -> None:
        self._dragging_handle = True
        self.update_magnifier(scene_position)

        self.magnifier_label.show()
        self.magnifier_label.raise_()

    def hide_magnifier(self) -> None:
        self._dragging_handle = False
        self.magnifier_label.hide()

    def update_magnifier(
        self,
        scene_position: QPointF,
    ) -> None:
        source_pixmap = self.get_image()

        if source_pixmap.isNull():
            self.hide_magnifier()
            return

        constrained_position = self.constrain_point_to_image(
            scene_position
        )

        source_size = self.MAGNIFIER_SOURCE_SIZE
        half_source_size = source_size // 2

        center_x = int(round(constrained_position.x()))
        center_y = int(round(constrained_position.y()))

        source_x = center_x - half_source_size
        source_y = center_y - half_source_size

        maximum_x = max(
            0,
            source_pixmap.width() - source_size,
        )
        maximum_y = max(
            0,
            source_pixmap.height() - source_size,
        )

        source_x = max(
            0,
            min(source_x, maximum_x),
        )
        source_y = max(
            0,
            min(source_y, maximum_y),
        )

        source_rectangle = QRect(
            source_x,
            source_y,
            min(source_size, source_pixmap.width()),
            min(source_size, source_pixmap.height()),
        )

        cropped_pixmap = source_pixmap.copy(
            source_rectangle
        )

        if cropped_pixmap.isNull():
            return

        magnified_pixmap = cropped_pixmap.scaled(
            self.MAGNIFIER_SIZE,
            self.MAGNIFIER_SIZE,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )

        self.draw_magnifier_crosshair(
            magnified_pixmap,
            constrained_position,
            source_rectangle,
        )

        self.magnifier_label.setPixmap(
            magnified_pixmap
        )

    def draw_magnifier_crosshair(
        self,
        magnified_pixmap: QPixmap,
        image_position: QPointF,
        source_rectangle: QRect,
    ) -> None:
        crop_width = max(
            source_rectangle.width(),
            1,
        )
        crop_height = max(
            source_rectangle.height(),
            1,
        )

        relative_x = (
            image_position.x()
            - source_rectangle.left()
        )
        relative_y = (
            image_position.y()
            - source_rectangle.top()
        )

        crosshair_x = int(
            round(
                relative_x
                / crop_width
                * self.MAGNIFIER_SIZE
            )
        )
        crosshair_y = int(
            round(
                relative_y
                / crop_height
                * self.MAGNIFIER_SIZE
            )
        )

        crosshair_x = max(
            0,
            min(
                crosshair_x,
                self.MAGNIFIER_SIZE - 1,
            ),
        )
        crosshair_y = max(
            0,
            min(
                crosshair_y,
                self.MAGNIFIER_SIZE - 1,
            ),
        )

        painter = QPainter(magnified_pixmap)

        painter.setPen(
            QPen(QColor(0, 0, 0), 5)
        )
        painter.drawLine(
            crosshair_x,
            0,
            crosshair_x,
            self.MAGNIFIER_SIZE,
        )
        painter.drawLine(
            0,
            crosshair_y,
            self.MAGNIFIER_SIZE,
            crosshair_y,
        )

        painter.setPen(
            QPen(QColor(255, 255, 255), 2)
        )
        painter.drawLine(
            crosshair_x,
            0,
            crosshair_x,
            self.MAGNIFIER_SIZE,
        )
        painter.drawLine(
            0,
            crosshair_y,
            self.MAGNIFIER_SIZE,
            crosshair_y,
        )

        painter.setPen(
            QPen(QColor(255, 80, 80), 2)
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(
            crosshair_x - 7,
            crosshair_y - 7,
            14,
            14,
        )

        painter.end()

    def set_image(self, pixmap: QPixmap) -> None:
        self.hide_magnifier()
        self.set_selection_mode(False)

        self.selection_manager.reset()

        self._image_item.setPixmap(pixmap)
        self.edge_snapper.set_image(pixmap)

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

    def get_selection_points(
        self,
    ) -> list[QPointF]:
        return self.selection_manager.get_points()

    def set_edge_snapping_enabled(
        self,
        enabled: bool,
    ) -> None:
        self._edge_snapping_enabled = enabled

    def edge_snapping_enabled(self) -> bool:
        return self._edge_snapping_enabled

    def get_edge_snap_radius(self) -> int:
        current_scale = self.transform().m11()

        if current_scale <= 0:
            return 12

        radius = int(
            round(14 / current_scale)
        )

        return max(
            3,
            min(radius, 50),
        )

    def apply_edge_snapping(
        self,
        point: QPointF,
    ) -> QPointF:
        constrained_point = self.constrain_point_to_image(
            point
        )

        if not self._edge_snapping_enabled:
            return constrained_point

        snapped_point = self.edge_snapper.snap(
            constrained_point,
            self.get_edge_snap_radius(),
        )

        return self.constrain_point_to_image(
            snapped_point
        )

    def set_selection_mode(
        self,
        enabled: bool,
    ) -> None:
        self._selection_mode = enabled

        if enabled:
            self.setDragMode(
                QGraphicsView.DragMode.NoDrag
            )
            self.setCursor(
                Qt.CursorShape.CrossCursor
            )
        else:
            self.setDragMode(
                QGraphicsView.DragMode.ScrollHandDrag
            )
            self.unsetCursor()

    def clear_selection(self) -> None:
        self.hide_magnifier()
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
        return self._image_item.boundingRect().contains(
            point
        )

    def constrain_point_to_image(
        self,
        point: QPointF,
    ) -> QPointF:
        bounds = self._image_item.boundingRect()

        return QPointF(
            max(
                bounds.left(),
                min(
                    point.x(),
                    bounds.right(),
                ),
            ),
            max(
                bounds.top(),
                min(
                    point.y(),
                    bounds.bottom(),
                ),
            ),
        )

    def handle_move_started(
        self,
        index: int,
        point: QPointF,
    ) -> None:
        snapped_point = self.apply_edge_snapping(
            point
        )

        self.show_magnifier(snapped_point)

    def handle_moved(
        self,
        index: int,
        point: QPointF,
    ) -> None:
        if self._updating_handles:
            return

        constrained_point = self.apply_edge_snapping(
            point
        )

        self.selection_manager.preview_point_move(
            index,
            constrained_point,
        )

        if self._dragging_handle:
            self.update_magnifier(
                constrained_point
            )

    def handle_move_finished(
        self,
        index: int,
        old_point: QPointF,
        new_point: QPointF,
    ) -> None:
        if self._updating_handles:
            return

        constrained_point = self.apply_edge_snapping(
            new_point
        )

        self.selection_manager.commit_point_move(
            index,
            old_point,
            constrained_point,
        )

        self.hide_magnifier()

    def sync_selection_graphics(
        self,
        points: list[QPointF],
    ) -> None:
        self._updating_handles = True

        while (
            len(self._selection_handles)
            > len(points)
        ):
            handle = self._selection_handles.pop()
            self._scene.removeItem(handle)

        while (
            len(self._selection_handles)
            < len(points)
        ):
            index = len(
                self._selection_handles
            )

            handle = SelectionHandle(
                index=index,
                center=points[index],
                moved_callback=self.handle_moved,
                move_started_callback=(
                    self.handle_move_started
                ),
                move_finished_callback=(
                    self.handle_move_finished
                ),
            )

            self._selection_handles.append(handle)
            self._scene.addItem(handle)

        for index, point in enumerate(points):
            self._selection_handles[
                index
            ].setPos(point)

        self._selection_polygon.setPolygon(
            QPolygonF(points)
        )

        self._updating_handles = False

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        if (
            self._selection_mode
            and event.button()
            == Qt.MouseButton.LeftButton
        ):
            scene_position = self.mapToScene(
                event.position().toPoint()
            )

            if not self.point_is_inside_image(
                scene_position
            ):
                return

            selection_point = self.apply_edge_snapping(
                scene_position
            )

            added = self.selection_manager.add_point(
                selection_point
            )

            if (
                added
                and self.selection_manager.is_complete()
            ):
                self.set_selection_mode(False)

            return

        super().mousePressEvent(event)

    def wheelEvent(
        self,
        event: QWheelEvent,
    ) -> None:
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
            self.scale(
                zoom_factor,
                zoom_factor,
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.position_magnifier()