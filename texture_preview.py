import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from texture_preview_view import TexturePreviewView
from texture_processing import rgba_array_to_qpixmap


class TexturePreviewDialog(QDialog):
    def __init__(
        self,
        texture_array: np.ndarray,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.texture_array = texture_array

        # This is always the real texture used for saving.
        self.original_pixmap = rgba_array_to_qpixmap(
            texture_array
        )

        self.offset_enabled = False

        self.setWindowTitle(
            "Texture Preview"
        )
        self.resize(
            1000,
            750,
        )

        self.preview_view = TexturePreviewView()
        self.preview_view.set_image(
            self.original_pixmap,
            fit_image=True,
        )

        width = self.original_pixmap.width()
        height = self.original_pixmap.height()

        self.size_label = QLabel(
            f"Texture size: {width} x {height} pixels"
        )

        self.offset_checkbox = QCheckBox(
            "Offset View"
        )
        self.offset_checkbox.setToolTip(
            "Shift the texture by half its width and height "
            "so the outer edges meet in the center."
        )
        self.offset_checkbox.toggled.connect(
            self.on_offset_changed
        )

        self.guides_checkbox = QCheckBox(
            "Show Seam Guides"
        )
        self.guides_checkbox.setChecked(True)
        self.guides_checkbox.setEnabled(False)
        self.guides_checkbox.toggled.connect(
            self.preview_view.set_guides_visible
        )

        self.guide_opacity_label = QLabel(
            "Guide opacity: 75%"
        )

        self.guide_opacity_slider = QSlider(
            Qt.Orientation.Horizontal
        )
        self.guide_opacity_slider.setRange(
            0,
            100,
        )
        self.guide_opacity_slider.setValue(
            75
        )
        self.guide_opacity_slider.setFixedWidth(
            110
        )
        self.guide_opacity_slider.setEnabled(
            False
        )
        self.guide_opacity_slider.valueChanged.connect(
            self.on_guide_opacity_changed
        )

        self.fit_button = QPushButton(
            "Fit"
        )
        self.fit_button.clicked.connect(
            self.preview_view.fit_image_to_window
        )

        self.actual_size_button = QPushButton(
            "100%"
        )
        self.actual_size_button.clicked.connect(
            self.preview_view.actual_size
        )

        self.save_button = QPushButton(
            "Save Texture"
        )
        self.save_button.clicked.connect(
            self.save_texture
        )

        self.close_button = QPushButton(
            "Close"
        )
        self.close_button.clicked.connect(
            self.accept
        )

        display_controls_layout = QHBoxLayout()
        display_controls_layout.addWidget(
            self.offset_checkbox
        )
        display_controls_layout.addWidget(
            self.guides_checkbox
        )
        display_controls_layout.addWidget(
            self.guide_opacity_label
        )
        display_controls_layout.addWidget(
            self.guide_opacity_slider
        )
        display_controls_layout.addStretch()
        display_controls_layout.addWidget(
            self.fit_button
        )
        display_controls_layout.addWidget(
            self.actual_size_button
        )

        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(
            self.size_label
        )
        bottom_layout.addStretch()
        bottom_layout.addWidget(
            self.save_button
        )
        bottom_layout.addWidget(
            self.close_button
        )

        main_layout = QVBoxLayout()
        main_layout.addWidget(
            self.preview_view,
            1,
        )
        main_layout.addLayout(
            display_controls_layout
        )
        main_layout.addLayout(
            bottom_layout
        )

        self.setLayout(
            main_layout
        )

    def create_offset_pixmap(
        self,
        source_pixmap: QPixmap,
    ) -> QPixmap:
        """
        Shift the texture horizontally and vertically by half.

        This moves the original outer boundaries into the center.
        """

        if source_pixmap.isNull():
            return QPixmap()

        width = source_pixmap.width()
        height = source_pixmap.height()

        horizontal_shift = width // 2
        vertical_shift = height // 2

        offset_pixmap = QPixmap(
            width,
            height,
        )
        offset_pixmap.fill(
            Qt.GlobalColor.transparent
        )

        painter = QPainter(
            offset_pixmap
        )

        # Draw four wrapped copies of the source texture.
        painter.drawPixmap(
            -horizontal_shift,
            -vertical_shift,
            source_pixmap,
        )

        painter.drawPixmap(
            width - horizontal_shift,
            -vertical_shift,
            source_pixmap,
        )

        painter.drawPixmap(
            -horizontal_shift,
            height - vertical_shift,
            source_pixmap,
        )

        painter.drawPixmap(
            width - horizontal_shift,
            height - vertical_shift,
            source_pixmap,
        )

        painter.end()

        return offset_pixmap

    def on_offset_changed(
        self,
        enabled: bool,
    ) -> None:
        self.offset_enabled = enabled

        self.guides_checkbox.setEnabled(
            enabled
        )
        self.guide_opacity_slider.setEnabled(
            enabled
        )
        self.guide_opacity_label.setEnabled(
            enabled
        )

        if enabled:
            display_pixmap = self.create_offset_pixmap(
                self.original_pixmap
            )

            self.preview_view.set_image(
                display_pixmap,
                fit_image=True,
            )

            self.preview_view.set_guides_visible(
                self.guides_checkbox.isChecked()
            )

            self.setWindowTitle(
                "Texture Preview - Offset Seam View"
            )

        else:
            self.preview_view.set_guides_visible(
                False
            )

            self.preview_view.set_image(
                self.original_pixmap,
                fit_image=True,
            )

            self.setWindowTitle(
                "Texture Preview"
            )

    def on_guide_opacity_changed(
        self,
        value: int,
    ) -> None:
        self.guide_opacity_label.setText(
            f"Guide opacity: {value}%"
        )

        self.preview_view.set_guide_opacity(
            value / 100.0
        )

    def save_texture(self) -> None:
        """
        Save the original, correctly oriented texture.

        Offset mode is only a diagnostic display mode.
        """

        file_path, selected_filter = (
            QFileDialog.getSaveFileName(
                self,
                "Save Texture",
                "extracted_texture.png",
                (
                    "PNG Image (*.png);;"
                    "JPEG Image (*.jpg *.jpeg);;"
                    "Bitmap Image (*.bmp)"
                ),
            )
        )

        if not file_path:
            return

        lowercase_path = file_path.lower()

        has_supported_extension = (
            lowercase_path.endswith(
                (
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".bmp",
                )
            )
        )

        if not has_supported_extension:
            if "JPEG" in selected_filter:
                file_path += ".jpg"
            elif "Bitmap" in selected_filter:
                file_path += ".bmp"
            else:
                file_path += ".png"

        saved = self.original_pixmap.save(
            file_path
        )

        if not saved:
            QMessageBox.warning(
                self,
                "Save Failed",
                "The texture could not be saved.",
            )
            return

        QMessageBox.information(
            self,
            "Texture Saved",
            f"The texture was saved to:\n{file_path}",
        )