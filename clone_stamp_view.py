from __future__ import annotations

import math

import numpy as np

from PySide6.QtCore import QPointF, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QUndoCommand,
    QUndoStack,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
)


def copy_image(image: QImage) -> QImage:
    return image.copy()


class ImageEditCommand(QUndoCommand):
    def __init__(
        self,
        view: "CloneStampView",
        before_image: QImage,
        after_image: QImage,
        description: str,
        first_redo_already_applied: bool = True,
    ) -> None:
        super().__init__(description)

        self.view = view
        self.before_image = copy_image(before_image)
        self.after_image = copy_image(after_image)

        self.first_redo_already_applied = (
            first_redo_already_applied
        )
        self.first_redo = True

    def undo(self) -> None:
        self.view.set_working_image(
            self.before_image,
            preserve_view=True,
        )

    def redo(self) -> None:
        if (
            self.first_redo
            and self.first_redo_already_applied
        ):
            self.first_redo = False
            return

        self.first_redo = False

        self.view.set_working_image(
            self.after_image,
            preserve_view=True,
        )


class CloneStampView(QGraphicsView):
    image_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._image_item = QGraphicsPixmapItem()
        self._scene.addItem(self._image_item)

        self._source_marker = QGraphicsEllipseItem(
            -8,
            -8,
            16,
            16,
        )
        self._source_marker.setPen(
            QPen(
                QColor(80, 220, 255),
                2,
            )
        )
        self._source_marker.setZValue(20)
        self._source_marker.hide()
        self._scene.addItem(self._source_marker)

        self.undo_stack = QUndoStack(self)

        self._working_image = QImage()
        self._has_image = False

        self._clone_enabled = False
        self._source_point: QPointF | None = None
        self._clone_offset = QPointF()

        self._brush_size = 60
        self._brush_opacity = 0.85

        self._painting = False
        self._stroke_before_image = QImage()
        self._stroke_source_image = QImage()
        self._last_stamp_position: QPointF | None = None

        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.setResizeAnchor(
            QGraphicsView.ViewportAnchor.AnchorViewCenter
        )

        self.setDragMode(
            QGraphicsView.DragMode.ScrollHandDrag
        )

        self.setBackgroundBrush(
            QColor(45, 45, 45)
        )

    def set_working_image(
        self,
        image: QImage,
        preserve_view: bool = False,
    ) -> None:
        first_image = not self._has_image

        self._working_image = image.convertToFormat(
            QImage.Format.Format_RGBA8888
        ).copy()

        pixmap = QPixmap.fromImage(
            self._working_image
        )

        self._image_item.setPixmap(pixmap)
        self._scene.setSceneRect(
            self._image_item.boundingRect()
        )

        self._has_image = not image.isNull()

        if self._has_image and (
            first_image or not preserve_view
        ):
            self.fit_image_to_window()

        self.image_changed.emit()

    def working_image(self) -> QImage:
        return self._working_image.copy()

    def clear(self) -> None:
        self._working_image = QImage()
        self._image_item.setPixmap(QPixmap())
        self._scene.setSceneRect(0, 0, 0, 0)

        self._has_image = False
        self._source_point = None
        self._source_marker.hide()

        self.undo_stack.clear()
        self.resetTransform()

    def fit_image_to_window(self) -> None:
        if not self._has_image:
            return

        self.resetTransform()

        self.fitInView(
            self._image_item,
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    def actual_size(self) -> None:
        if not self._has_image:
            return

        self.resetTransform()

    def set_clone_enabled(
        self,
        enabled: bool,
    ) -> None:
        self._clone_enabled = enabled

        if enabled:
            self.setDragMode(
                QGraphicsView.DragMode.NoDrag
            )
            self.setCursor(
                Qt.CursorShape.CrossCursor
            )
        else:
            self.stop_stroke()
            self.setDragMode(
                QGraphicsView.DragMode.ScrollHandDrag
            )
            self.unsetCursor()

    def clone_enabled(self) -> bool:
        return self._clone_enabled

    def set_brush_size(
        self,
        size: int,
    ) -> None:
        self._brush_size = max(
            1,
            int(size),
        )

    def set_brush_opacity(
        self,
        opacity: float,
    ) -> None:
        self._brush_opacity = max(
            0.01,
            min(float(opacity), 1.0),
        )

    def point_inside_image(
        self,
        point: QPointF,
    ) -> bool:
        return self._image_item.boundingRect().contains(
            point
        )

    def choose_source(
        self,
        point: QPointF,
    ) -> None:
        if not self.point_inside_image(point):
            return

        self._source_point = QPointF(point)

        self._source_marker.setPos(
            self._source_point
        )
        self._source_marker.show()

    def begin_stroke(
        self,
        destination_point: QPointF,
    ) -> None:
        if self._source_point is None:
            return

        self._painting = True

        self._stroke_before_image = (
            self._working_image.copy()
        )
        self._stroke_source_image = (
            self._working_image.copy()
        )

        self._clone_offset = (
            self._source_point
            - destination_point
        )

        self._last_stamp_position = None

        self.paint_interpolated(
            destination_point
        )

    def stop_stroke(self) -> None:
        if not self._painting:
            return

        self._painting = False
        self._last_stamp_position = None

        if (
            self._stroke_before_image.isNull()
            or self._working_image.isNull()
        ):
            return

        if (
            self._stroke_before_image
            == self._working_image
        ):
            return

        command = ImageEditCommand(
            view=self,
            before_image=self._stroke_before_image,
            after_image=self._working_image,
            description="Clone stamp stroke",
            first_redo_already_applied=True,
        )

        self.undo_stack.push(command)

    def paint_interpolated(
        self,
        current_point: QPointF,
    ) -> None:
        if self._last_stamp_position is None:
            self.apply_clone_stamp(
                current_point
            )
            self._last_stamp_position = QPointF(
                current_point
            )
            return

        start = self._last_stamp_position
        end = current_point

        delta_x = end.x() - start.x()
        delta_y = end.y() - start.y()

        distance = math.hypot(
            delta_x,
            delta_y,
        )

        spacing = max(
            1.0,
            self._brush_size * 0.18,
        )

        steps = max(
            1,
            int(math.ceil(distance / spacing)),
        )

        for step in range(1, steps + 1):
            fraction = step / steps

            interpolated = QPointF(
                start.x() + delta_x * fraction,
                start.y() + delta_y * fraction,
            )

            self.apply_clone_stamp(
                interpolated
            )

        self._last_stamp_position = QPointF(
            current_point
        )

    def apply_clone_stamp(
        self,
        destination_center: QPointF,
    ) -> None:
        if self._stroke_source_image.isNull():
            return

        radius = self._brush_size // 2

        source_center = (
            destination_center
            + self._clone_offset
        )

        source_rectangle = QRect(
            int(round(source_center.x())) - radius,
            int(round(source_center.y())) - radius,
            self._brush_size,
            self._brush_size,
        )

        destination_rectangle = QRect(
            int(round(destination_center.x())) - radius,
            int(round(destination_center.y())) - radius,
            self._brush_size,
            self._brush_size,
        )

        source_patch = self._stroke_source_image.copy(
            source_rectangle
        )

        if source_patch.isNull():
            return

        painter = QPainter(
            self._working_image
        )

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )

        painter.setOpacity(
            self._brush_opacity
        )

        painter.setClipPath(
            self.create_circular_clip(
                destination_rectangle
            )
        )

        painter.drawImage(
            destination_rectangle,
            source_patch,
        )

        painter.end()

        self.refresh_pixmap()

    def create_circular_clip(
        self,
        rectangle: QRect,
    ):
        from PySide6.QtGui import QPainterPath

        path = QPainterPath()
        path.addEllipse(rectangle)

        return path

    def refresh_pixmap(self) -> None:
        self._image_item.setPixmap(
            QPixmap.fromImage(
                self._working_image
            )
        )

        self.image_changed.emit()

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        if (
            self._clone_enabled
            and event.button()
            == Qt.MouseButton.LeftButton
        ):
            image_point = self.mapToScene(
                event.position().toPoint()
            )

            if not self.point_inside_image(
                image_point
            ):
                return

            if (
                event.modifiers()
                & Qt.KeyboardModifier.AltModifier
            ):
                self.choose_source(
                    image_point
                )
                return

            self.begin_stroke(
                image_point
            )
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        if self._painting:
            image_point = self.mapToScene(
                event.position().toPoint()
            )

            self.paint_interpolated(
                image_point
            )
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        if (
            self._painting
            and event.button()
            == Qt.MouseButton.LeftButton
        ):
            self.stop_stroke()
            return

        super().mouseReleaseEvent(event)

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

        if 0.02 <= new_scale <= 30.0:
            self.scale(
                zoom_factor,
                zoom_factor,
            )