from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
)


class TexturePreviewView(QGraphicsView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._image_item = QGraphicsPixmapItem()
        self._scene.addItem(self._image_item)

        self._has_image = False

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

        self.setDragMode(
            QGraphicsView.DragMode.ScrollHandDrag
        )

        self.setBackgroundBrush(
            Qt.GlobalColor.darkGray
        )

    def set_image(self, pixmap: QPixmap) -> None:
        self._image_item.setPixmap(pixmap)
        self._scene.setSceneRect(
            self._image_item.boundingRect()
        )

        self._has_image = not pixmap.isNull()

        if self._has_image:
            self.fit_image_to_window()

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

        minimum_scale = 0.02
        maximum_scale = 30.0

        if minimum_scale <= new_scale <= maximum_scale:
            self.scale(zoom_factor, zoom_factor)