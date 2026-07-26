from __future__ import annotations

import math

import cv2
import numpy as np

from PySide6.QtCore import QPointF, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QImage,
    QMouseEvent,
    QPainter,
    QPainterPath,
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


def qimage_to_rgba_array(image: QImage) -> np.ndarray:
    converted = image.convertToFormat(
        QImage.Format.Format_RGBA8888
    )

    width = converted.width()
    height = converted.height()
    bytes_per_line = converted.bytesPerLine()

    buffer = converted.bits()

    array = np.frombuffer(
        buffer,
        dtype=np.uint8,
        count=height * bytes_per_line,
    )

    array = array.reshape(
        height,
        bytes_per_line,
    )

    array = array[:, : width * 4]

    return array.reshape(
        height,
        width,
        4,
    ).copy()


def rgba_array_to_qimage(array: np.ndarray) -> QImage:
    contiguous = np.ascontiguousarray(array)

    height, width, channels = contiguous.shape

    if channels != 4:
        raise ValueError(
            "Expected an RGBA image array."
        )

    return QImage(
        contiguous.data,
        width,
        height,
        width * 4,
        QImage.Format.Format_RGBA8888,
    ).copy()


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
        self.before_image = before_image.copy()
        self.after_image = after_image.copy()

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
    source_changed = Signal(bool)
    status_message = Signal(str)

    TOOL_PAN = "pan"
    TOOL_CLONE = "clone"
    TOOL_HEAL = "heal"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._image_item = QGraphicsPixmapItem()
        self._scene.addItem(self._image_item)

        self._source_marker = QGraphicsEllipseItem(
            -9,
            -9,
            18,
            18,
        )
        self._source_marker.setPen(
            QPen(
                QColor(80, 220, 255),
                2,
            )
        )
        self._source_marker.setZValue(20)
        self._source_marker.hide()
        self._scene.addItem(
            self._source_marker
        )

        self.undo_stack = QUndoStack(self)

        self._working_image = QImage()
        self._has_image = False

        self._tool = self.TOOL_PAN

        self._source_point: QPointF | None = None
        self._clone_offset = QPointF()

        self._brush_size = 60
        self._brush_opacity = 0.85
        self._brush_hardness = 0.75

        self._painting = False
        self._stroke_before_image = QImage()
        self._stroke_source_image = QImage()
        self._last_stamp_position: QPointF | None = None

        # Used by the healing brush.
        self._healing_source_layer: np.ndarray | None = None
        self._healing_mask: np.ndarray | None = None

        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.setResizeAnchor(
            QGraphicsView.ViewportAnchor.AnchorViewCenter
        )

        self.setBackgroundBrush(
            QColor(45, 45, 45)
        )

        self.set_tool(
            self.TOOL_PAN
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

        self._image_item.setPixmap(
            QPixmap.fromImage(
                self._working_image
            )
        )

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
        self._scene.setSceneRect(
            0,
            0,
            0,
            0,
        )

        self._has_image = False
        self.clear_source()

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

    def set_tool(self, tool: str) -> None:
        valid_tools = {
            self.TOOL_PAN,
            self.TOOL_CLONE,
            self.TOOL_HEAL,
        }

        if tool not in valid_tools:
            raise ValueError(
                f"Unknown editor tool: {tool}"
            )

        self.stop_stroke()
        self._tool = tool

        if tool == self.TOOL_PAN:
            self.setDragMode(
                QGraphicsView.DragMode.ScrollHandDrag
            )
            self.unsetCursor()
        else:
            self.setDragMode(
                QGraphicsView.DragMode.NoDrag
            )
            self.setCursor(
                Qt.CursorShape.CrossCursor
            )

    def current_tool(self) -> str:
        return self._tool

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

    def set_brush_hardness(
        self,
        hardness: float,
    ) -> None:
        self._brush_hardness = max(
            0.05,
            min(float(hardness), 1.0),
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

        self.source_changed.emit(True)
        self.status_message.emit(
            "Repair source selected."
        )

    def clear_source(self) -> None:
        self._source_point = None
        self._source_marker.hide()

        self.source_changed.emit(False)

    def begin_stroke(
        self,
        destination_point: QPointF,
    ) -> None:
        if self._source_point is None:
            self.status_message.emit(
                "Alt + click a clean area to select a source first."
            )
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

        if self._tool == self.TOOL_HEAL:
            shape = (
                self._working_image.height(),
                self._working_image.width(),
                4,
            )

            self._healing_source_layer = np.zeros(
                shape,
                dtype=np.uint8,
            )

            self._healing_mask = np.zeros(
                shape[:2],
                dtype=np.uint8,
            )

        self.paint_interpolated(
            destination_point
        )

    def stop_stroke(self) -> None:
        if not self._painting:
            return

        self._painting = False
        self._last_stamp_position = None

        if self._tool == self.TOOL_HEAL:
            self.finish_healing_stroke()

        self._healing_source_layer = None
        self._healing_mask = None

        if (
            self._stroke_before_image.isNull()
            or self._working_image.isNull()
        ):
            return

        if self.images_are_equal(
            self._stroke_before_image,
            self._working_image,
        ):
            return

        description = (
            "Healing brush stroke"
            if self._tool == self.TOOL_HEAL
            else "Clone stamp stroke"
        )

        command = ImageEditCommand(
            view=self,
            before_image=self._stroke_before_image,
            after_image=self._working_image,
            description=description,
            first_redo_already_applied=True,
        )

        self.undo_stack.push(command)

    @staticmethod
    def images_are_equal(
        first: QImage,
        second: QImage,
    ) -> bool:
        if first.size() != second.size():
            return False

        first_array = qimage_to_rgba_array(
            first
        )
        second_array = qimage_to_rgba_array(
            second
        )

        return np.array_equal(
            first_array,
            second_array,
        )

    def paint_interpolated(
        self,
        current_point: QPointF,
    ) -> None:
        if self._last_stamp_position is None:
            self.apply_brush_stamp(
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
            self._brush_size * 0.15,
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

            self.apply_brush_stamp(
                interpolated
            )

        self._last_stamp_position = QPointF(
            current_point
        )

    def apply_brush_stamp(
        self,
        destination_center: QPointF,
    ) -> None:
        if self._tool == self.TOOL_HEAL:
            self.add_healing_stamp(
                destination_center
            )
        else:
            self.apply_clone_stamp(
                destination_center
            )

    def create_soft_mask(
        self,
        size: int,
    ) -> np.ndarray:
        radius = size / 2.0

        y_values, x_values = np.ogrid[
            :size,
            :size,
        ]

        distance = np.sqrt(
            (x_values - radius + 0.5) ** 2
            + (y_values - radius + 0.5) ** 2
        )

        inner_radius = (
            radius * self._brush_hardness
        )

        mask = np.ones(
            (size, size),
            dtype=np.float32,
        )

        outside = distance >= radius
        fade_region = (
            (distance > inner_radius)
            & (distance < radius)
        )

        mask[outside] = 0.0

        fade_width = max(
            radius - inner_radius,
            0.001,
        )

        mask[fade_region] = (
            radius - distance[fade_region]
        ) / fade_width

        mask *= self._brush_opacity

        return np.clip(
            mask * 255.0,
            0,
            255,
        ).astype(np.uint8)

    def calculate_patch_geometry(
        self,
        destination_center: QPointF,
    ):
        image_width = self._working_image.width()
        image_height = self._working_image.height()

        size = self._brush_size
        half = size // 2

        source_center = (
            destination_center
            + self._clone_offset
        )

        destination_x = (
            int(round(destination_center.x()))
            - half
        )
        destination_y = (
            int(round(destination_center.y()))
            - half
        )

        source_x = (
            int(round(source_center.x()))
            - half
        )
        source_y = (
            int(round(source_center.y()))
            - half
        )

        destination_left = max(
            0,
            destination_x,
        )
        destination_top = max(
            0,
            destination_y,
        )
        destination_right = min(
            image_width,
            destination_x + size,
        )
        destination_bottom = min(
            image_height,
            destination_y + size,
        )

        if (
            destination_right <= destination_left
            or destination_bottom <= destination_top
        ):
            return None

        offset_left = (
            destination_left - destination_x
        )
        offset_top = (
            destination_top - destination_y
        )

        source_left = source_x + offset_left
        source_top = source_y + offset_top

        patch_width = (
            destination_right - destination_left
        )
        patch_height = (
            destination_bottom - destination_top
        )

        source_left = max(
            0,
            min(
                source_left,
                image_width - patch_width,
            ),
        )
        source_top = max(
            0,
            min(
                source_top,
                image_height - patch_height,
            ),
        )

        return {
            "destination_left": destination_left,
            "destination_top": destination_top,
            "source_left": source_left,
            "source_top": source_top,
            "width": patch_width,
            "height": patch_height,
            "mask_left": offset_left,
            "mask_top": offset_top,
        }

    def apply_clone_stamp(
        self,
        destination_center: QPointF,
    ) -> None:
        geometry = self.calculate_patch_geometry(
            destination_center
        )

        if geometry is None:
            return

        source_array = qimage_to_rgba_array(
            self._stroke_source_image
        )
        destination_array = qimage_to_rgba_array(
            self._working_image
        )

        source_patch = source_array[
            geometry["source_top"]:
            geometry["source_top"]
            + geometry["height"],

            geometry["source_left"]:
            geometry["source_left"]
            + geometry["width"],
        ]

        destination_patch = destination_array[
            geometry["destination_top"]:
            geometry["destination_top"]
            + geometry["height"],

            geometry["destination_left"]:
            geometry["destination_left"]
            + geometry["width"],
        ]

        full_mask = self.create_soft_mask(
            self._brush_size
        )

        patch_mask = full_mask[
            geometry["mask_top"]:
            geometry["mask_top"]
            + geometry["height"],

            geometry["mask_left"]:
            geometry["mask_left"]
            + geometry["width"],
        ]

        alpha = (
            patch_mask.astype(np.float32)
            / 255.0
        )[:, :, np.newaxis]

        blended = (
            source_patch.astype(np.float32)
            * alpha
            + destination_patch.astype(np.float32)
            * (1.0 - alpha)
        )

        destination_array[
            geometry["destination_top"]:
            geometry["destination_top"]
            + geometry["height"],

            geometry["destination_left"]:
            geometry["destination_left"]
            + geometry["width"],
        ] = np.clip(
            blended,
            0,
            255,
        ).astype(np.uint8)

        self._working_image = rgba_array_to_qimage(
            destination_array
        )

        self.refresh_pixmap()

    def add_healing_stamp(
        self,
        destination_center: QPointF,
    ) -> None:
        if (
            self._healing_source_layer is None
            or self._healing_mask is None
        ):
            return

        geometry = self.calculate_patch_geometry(
            destination_center
        )

        if geometry is None:
            return

        source_array = qimage_to_rgba_array(
            self._stroke_source_image
        )

        source_patch = source_array[
            geometry["source_top"]:
            geometry["source_top"]
            + geometry["height"],

            geometry["source_left"]:
            geometry["source_left"]
            + geometry["width"],
        ]

        full_mask = self.create_soft_mask(
            self._brush_size
        )

        patch_mask = full_mask[
            geometry["mask_top"]:
            geometry["mask_top"]
            + geometry["height"],

            geometry["mask_left"]:
            geometry["mask_left"]
            + geometry["width"],
        ]

        destination_slice = np.s_[
            geometry["destination_top"]:
            geometry["destination_top"]
            + geometry["height"],

            geometry["destination_left"]:
            geometry["destination_left"]
            + geometry["width"],
        ]

        current_mask = self._healing_mask[
            destination_slice
        ]

        replace_pixels = (
            patch_mask > current_mask
        )

        source_layer_patch = (
            self._healing_source_layer[
                destination_slice
            ]
        )

        source_layer_patch[
            replace_pixels
        ] = source_patch[
            replace_pixels
        ]

        current_mask[
            replace_pixels
        ] = patch_mask[
            replace_pixels
        ]

        # Temporary direct-copy preview while dragging.
        preview_array = qimage_to_rgba_array(
            self._stroke_before_image
        )

        mask_alpha = (
            self._healing_mask.astype(np.float32)
            / 255.0
        )[:, :, np.newaxis]

        preview_array = (
            self._healing_source_layer.astype(np.float32)
            * mask_alpha
            + preview_array.astype(np.float32)
            * (1.0 - mask_alpha)
        )

        self._working_image = rgba_array_to_qimage(
            np.clip(
                preview_array,
                0,
                255,
            ).astype(np.uint8)
        )

        self.refresh_pixmap()

    def finish_healing_stroke(self) -> None:
        if (
            self._healing_source_layer is None
            or self._healing_mask is None
        ):
            return

        nonzero = cv2.findNonZero(
            self._healing_mask
        )

        if nonzero is None:
            return

        x, y, width, height = cv2.boundingRect(
            nonzero
        )

        padding = max(
            4,
            self._brush_size // 4,
        )

        x_start = max(
            0,
            x - padding,
        )
        y_start = max(
            0,
            y - padding,
        )

        x_end = min(
            self._working_image.width(),
            x + width + padding,
        )
        y_end = min(
            self._working_image.height(),
            y + height + padding,
        )

        destination_rgba = qimage_to_rgba_array(
            self._stroke_before_image
        )

        source_rgba = self._healing_source_layer[
            y_start:y_end,
            x_start:x_end,
        ].copy()

        mask = self._healing_mask[
            y_start:y_end,
            x_start:x_end,
        ].copy()

        destination_rgb = cv2.cvtColor(
            destination_rgba,
            cv2.COLOR_RGBA2RGB,
        )

        source_rgb = cv2.cvtColor(
            source_rgba,
            cv2.COLOR_RGBA2RGB,
        )

        # Pixels outside the painted mask need valid source data.
        destination_crop = destination_rgb[
            y_start:y_end,
            x_start:x_end,
        ]

        outside_mask = mask == 0

        source_rgb[
            outside_mask
        ] = destination_crop[
            outside_mask
        ]

        center = (
            x_start + (x_end - x_start) // 2,
            y_start + (y_end - y_start) // 2,
        )

        try:
            healed_rgb = cv2.seamlessClone(
                source_rgb,
                destination_rgb,
                mask,
                center,
                cv2.MIXED_CLONE,
            )
        except cv2.error:
            # Fall back to the temporary blended preview if
            # the selected region is too small or near an edge.
            return

        healed_rgba = cv2.cvtColor(
            healed_rgb,
            cv2.COLOR_RGB2RGBA,
        )

        healed_rgba[:, :, 3] = (
            destination_rgba[:, :, 3]
        )

        self._working_image = rgba_array_to_qimage(
            healed_rgba
        )

        self.refresh_pixmap()

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
            self._tool
            in {
                self.TOOL_CLONE,
                self.TOOL_HEAL,
            }
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