import cv2
import numpy as np

from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QPixmap


class EdgeSnapper:
    def __init__(self) -> None:
        self._edge_map: np.ndarray | None = None

    def clear(self) -> None:
        self._edge_map = None

    def set_image(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            self.clear()
            return

        rgba_image = self._qimage_to_rgba(
            pixmap.toImage()
        )

        grayscale = cv2.cvtColor(
            rgba_image,
            cv2.COLOR_RGBA2GRAY,
        )

        blurred = cv2.GaussianBlur(
            grayscale,
            (5, 5),
            0,
        )

        self._edge_map = cv2.Canny(
            blurred,
            threshold1=60,
            threshold2=140,
        )

    def snap(
        self,
        point: QPointF,
        search_radius: int,
    ) -> QPointF:
        if self._edge_map is None:
            return QPointF(point)

        image_height, image_width = (
            self._edge_map.shape
        )

        center_x = int(round(point.x()))
        center_y = int(round(point.y()))

        left = max(
            0,
            center_x - search_radius,
        )
        right = min(
            image_width,
            center_x + search_radius + 1,
        )
        top = max(
            0,
            center_y - search_radius,
        )
        bottom = min(
            image_height,
            center_y + search_radius + 1,
        )

        edge_region = self._edge_map[
            top:bottom,
            left:right,
        ]

        edge_coordinates = np.argwhere(
            edge_region > 0
        )

        if edge_coordinates.size == 0:
            return QPointF(point)

        absolute_y = (
            edge_coordinates[:, 0] + top
        )
        absolute_x = (
            edge_coordinates[:, 1] + left
        )

        distance_squared = (
            (absolute_x - point.x()) ** 2
            + (absolute_y - point.y()) ** 2
        )

        nearest_index = int(
            np.argmin(distance_squared)
        )

        nearest_x = float(
            absolute_x[nearest_index]
        )
        nearest_y = float(
            absolute_y[nearest_index]
        )

        return QPointF(
            nearest_x,
            nearest_y,
        )

    @staticmethod
    def _qimage_to_rgba(
        image: QImage,
    ) -> np.ndarray:
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
        array = array.reshape(
            height,
            width,
            4,
        )

        return array.copy()