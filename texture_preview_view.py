from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsLineItem,
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

        self._vertical_guide = QGraphicsLineItem()
        self._horizontal_guide = QGraphicsLineItem()

        self._scene.addItem(self._vertical_guide)
        self._scene.addItem(self._horizontal_guide)

        self._vertical_guide.setZValue(10)
        self._horizontal_guide.setZValue(10)

        self._has_image = False
        self._guides_visible = False
        self._guide_opacity = 0.75

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
            QColor(45, 45, 45)
        )

        self.update_guide_style()
        self.update_guide_visibility()

    def set_image(
        self,
        pixmap: QPixmap,
        fit_image: bool = False,
    ) -> None:
        first_image = not self._has_image

        self._image_item.setPixmap(pixmap)

        self._scene.setSceneRect(
            self._image_item.boundingRect()
        )

        self._has_image = not pixmap.isNull()

        self.update_guide_positions()
        self.update_guide_visibility()

        if self._has_image and (
            first_image or fit_image
        ):
            self.fit_image_to_window()

    def clear_image(self) -> None:
        self._image_item.setPixmap(QPixmap())
        self._scene.setSceneRect(0, 0, 0, 0)

        self._has_image = False

        self.resetTransform()
        self.update_guide_visibility()

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

    def set_guides_visible(
        self,
        visible: bool,
    ) -> None:
        self._guides_visible = visible
        self.update_guide_visibility()

    def guides_visible(self) -> bool:
        return self._guides_visible

    def set_guide_opacity(
        self,
        opacity: float,
    ) -> None:
        self._guide_opacity = max(
            0.0,
            min(float(opacity), 1.0),
        )

        self.update_guide_style()

    def update_guide_visibility(self) -> None:
        visible = (
            self._has_image
            and self._guides_visible
        )

        self._vertical_guide.setVisible(visible)
        self._horizontal_guide.setVisible(visible)

    def update_guide_style(self) -> None:
        guide_color = QColor(
            255,
            70,
            70,
        )

        guide_color.setAlphaF(
            self._guide_opacity
        )

        guide_pen = QPen(
            guide_color,
            2,
            Qt.PenStyle.DashLine,
        )

        # Keep the guide visually the same width while zooming.
        guide_pen.setCosmetic(True)

        self._vertical_guide.setPen(guide_pen)
        self._horizontal_guide.setPen(guide_pen)

    def update_guide_positions(self) -> None:
        if not self._has_image:
            return

        width = self._image_item.pixmap().width()
        height = self._image_item.pixmap().height()

        center_x = width / 2.0
        center_y = height / 2.0

        self._vertical_guide.setLine(
            center_x,
            0,
            center_x,
            height,
        )

        self._horizontal_guide.setLine(
            0,
            center_y,
            width,
            center_y,
        )

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