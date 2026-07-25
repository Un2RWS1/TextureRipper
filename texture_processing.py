import math

import cv2
import numpy as np
from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QPixmap


def point_distance(point_a: QPointF, point_b: QPointF) -> float:
    delta_x = point_b.x() - point_a.x()
    delta_y = point_b.y() - point_a.y()

    return math.hypot(delta_x, delta_y)


def calculate_output_size(
    points: list[QPointF],
) -> tuple[int, int]:
    if len(points) != 4:
        raise ValueError("Exactly four points are required.")

    top_left, top_right, bottom_right, bottom_left = points

    top_width = point_distance(top_left, top_right)
    bottom_width = point_distance(bottom_left, bottom_right)

    left_height = point_distance(top_left, bottom_left)
    right_height = point_distance(top_right, bottom_right)

    output_width = int(round(max(top_width, bottom_width)))
    output_height = int(round(max(left_height, right_height)))

    output_width = max(output_width, 1)
    output_height = max(output_height, 1)

    return output_width, output_height


def qimage_to_numpy(image: QImage) -> np.ndarray:
    converted_image = image.convertToFormat(
        QImage.Format.Format_RGBA8888
    )

    width = converted_image.width()
    height = converted_image.height()
    bytes_per_line = converted_image.bytesPerLine()

    pointer = converted_image.bits()

    array = np.frombuffer(
        pointer,
        dtype=np.uint8,
        count=height * bytes_per_line,
    )

    array = array.reshape(
        height,
        bytes_per_line,
    )

    array = array[:, : width * 4]
    array = array.reshape(height, width, 4)

    return array.copy()


def numpy_to_qpixmap(image_array: np.ndarray) -> QPixmap:
    if image_array.ndim != 3:
        raise ValueError("Expected a color image array.")

    height, width, channel_count = image_array.shape

    if channel_count == 3:
        rgb_image = cv2.cvtColor(
            image_array,
            cv2.COLOR_BGR2RGB,
        )

        bytes_per_line = width * 3

        qimage = QImage(
            rgb_image.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_RGB888,
        ).copy()

    elif channel_count == 4:
        rgba_image = cv2.cvtColor(
            image_array,
            cv2.COLOR_BGRA2RGBA,
        )

        bytes_per_line = width * 4

        qimage = QImage(
            rgba_image.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_RGBA8888,
        ).copy()

    else:
        raise ValueError(
            f"Unsupported channel count: {channel_count}"
        )

    return QPixmap.fromImage(qimage)


def extract_texture(
    source_image: QImage,
    points: list[QPointF],
) -> np.ndarray:
    if source_image.isNull():
        raise ValueError("The source image is empty.")

    if len(points) != 4:
        raise ValueError(
            "A four-point selection is required."
        )

    output_width, output_height = calculate_output_size(
        points
    )

    source_points = np.array(
        [
            [points[0].x(), points[0].y()],
            [points[1].x(), points[1].y()],
            [points[2].x(), points[2].y()],
            [points[3].x(), points[3].y()],
        ],
        dtype=np.float32,
    )

    destination_points = np.array(
        [
            [0, 0],
            [output_width - 1, 0],
            [output_width - 1, output_height - 1],
            [0, output_height - 1],
        ],
        dtype=np.float32,
    )

    source_rgba = qimage_to_numpy(source_image)

    source_bgra = cv2.cvtColor(
        source_rgba,
        cv2.COLOR_RGBA2BGRA,
    )

    transform_matrix = cv2.getPerspectiveTransform(
        source_points,
        destination_points,
    )

    extracted_texture = cv2.warpPerspective(
        source_bgra,
        transform_matrix,
        (output_width, output_height),
        flags=cv2.INTER_CUBIC,
    )

    return extracted_texture