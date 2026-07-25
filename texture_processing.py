import math

import cv2
import numpy as np

from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QPixmap


def distance(point_a: QPointF, point_b: QPointF) -> float:
    delta_x = point_b.x() - point_a.x()
    delta_y = point_b.y() - point_a.y()

    return math.hypot(delta_x, delta_y)


def calculate_output_size(
    points: list[QPointF],
) -> tuple[int, int]:
    if len(points) != 4:
        raise ValueError("Exactly four selection points are required.")

    top_left = points[0]
    top_right = points[1]
    bottom_right = points[2]
    bottom_left = points[3]

    top_width = distance(top_left, top_right)
    bottom_width = distance(bottom_left, bottom_right)

    left_height = distance(top_left, bottom_left)
    right_height = distance(top_right, bottom_right)

    output_width = max(
        int(round(top_width)),
        int(round(bottom_width)),
        1,
    )

    output_height = max(
        int(round(left_height)),
        int(round(right_height)),
        1,
    )

    return output_width, output_height


def qimage_to_rgba_array(image: QImage) -> np.ndarray:
    if image.isNull():
        raise ValueError("The source image is empty.")

    converted_image = image.convertToFormat(
        QImage.Format.Format_RGBA8888
    )

    width = converted_image.width()
    height = converted_image.height()
    bytes_per_line = converted_image.bytesPerLine()

    buffer = converted_image.bits()

    image_array = np.frombuffer(
        buffer,
        dtype=np.uint8,
        count=height * bytes_per_line,
    )

    image_array = image_array.reshape(
        height,
        bytes_per_line,
    )

    image_array = image_array[:, : width * 4]
    image_array = image_array.reshape(height, width, 4)

    return image_array.copy()


def extract_texture(
    source_image: QImage,
    points: list[QPointF],
) -> np.ndarray:
    if len(points) != 4:
        raise ValueError(
            "Complete the four-corner selection first."
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

    source_rgba = qimage_to_rgba_array(source_image)

    transformation_matrix = cv2.getPerspectiveTransform(
        source_points,
        destination_points,
    )

    extracted_texture = cv2.warpPerspective(
        source_rgba,
        transformation_matrix,
        (output_width, output_height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )

    return extracted_texture
def make_texture_seamless(
    image_array: np.ndarray,
    blend_fraction: float = 0.10,
) -> np.ndarray:
    """
    Blend opposite edges so the texture tiles more smoothly.

    The source array is not modified.
    """

    if image_array.ndim != 3:
        raise ValueError(
            "The texture must be a color image."
        )

    if not 0.0 < blend_fraction <= 0.5:
        raise ValueError(
            "Blend fraction must be between 0 and 0.5."
        )

    result = image_array.astype(np.float32).copy()

    height, width, _ = result.shape

    horizontal_blend = max(
        1,
        int(round(width * blend_fraction)),
    )
    vertical_blend = max(
        1,
        int(round(height * blend_fraction)),
    )

    original = result.copy()

    # Blend the left and right edges toward their shared average.
    for offset in range(horizontal_blend):
        left_index = offset
        right_index = width - 1 - offset

        strength = 1.0 - (
            offset / max(horizontal_blend - 1, 1)
        )

        left_pixels = original[:, left_index, :]
        right_pixels = original[:, right_index, :]

        average_pixels = (
            left_pixels + right_pixels
        ) * 0.5

        result[:, left_index, :] = (
            left_pixels * (1.0 - strength)
            + average_pixels * strength
        )

        result[:, right_index, :] = (
            right_pixels * (1.0 - strength)
            + average_pixels * strength
        )

    original = result.copy()

    # Blend the top and bottom edges toward their shared average.
    for offset in range(vertical_blend):
        top_index = offset
        bottom_index = height - 1 - offset

        strength = 1.0 - (
            offset / max(vertical_blend - 1, 1)
        )

        top_pixels = original[top_index, :, :]
        bottom_pixels = original[bottom_index, :, :]

        average_pixels = (
            top_pixels + bottom_pixels
        ) * 0.5

        result[top_index, :, :] = (
            top_pixels * (1.0 - strength)
            + average_pixels * strength
        )

        result[bottom_index, :, :] = (
            bottom_pixels * (1.0 - strength)
            + average_pixels * strength
        )

    return np.clip(result, 0, 255).astype(np.uint8)


def rgba_array_to_qpixmap(
    image_array: np.ndarray,
) -> QPixmap:
    if image_array.ndim != 3:
        raise ValueError(
            "The image array must have three dimensions."
        )

    height, width, channel_count = image_array.shape

    if channel_count != 4:
        raise ValueError(
            "The image array must contain four RGBA channels."
        )

    contiguous_array = np.ascontiguousarray(image_array)

    bytes_per_line = width * 4

    qimage = QImage(
        contiguous_array.data,
        width,
        height,
        bytes_per_line,
        QImage.Format.Format_RGBA8888,
    ).copy()

    return QPixmap.fromImage(qimage)