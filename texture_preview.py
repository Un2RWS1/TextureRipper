import numpy as np

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
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
        self.texture_pixmap = rgba_array_to_qpixmap(
            texture_array
        )

        self.setWindowTitle("Texture Preview")
        self.resize(900, 700)

        self.preview_view = TexturePreviewView()
        self.preview_view.set_image(
            self.texture_pixmap
        )

        width = self.texture_pixmap.width()
        height = self.texture_pixmap.height()

        self.size_label = QLabel(
            f"Texture size: {width} x {height} pixels"
        )

        self.fit_button = QPushButton("Fit")
        self.fit_button.clicked.connect(
            self.preview_view.fit_image_to_window
        )

        self.actual_size_button = QPushButton("100%")
        self.actual_size_button.clicked.connect(
            self.preview_view.actual_size
        )

        self.save_button = QPushButton("Save Texture")
        self.save_button.clicked.connect(
            self.save_texture
        )

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.size_label)
        controls_layout.addStretch()
        controls_layout.addWidget(self.fit_button)
        controls_layout.addWidget(self.actual_size_button)
        controls_layout.addWidget(self.save_button)
        controls_layout.addWidget(self.close_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.preview_view, 1)
        main_layout.addLayout(controls_layout)

        self.setLayout(main_layout)

    def save_texture(self) -> None:
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

        has_supported_extension = lowercase_path.endswith(
            (".png", ".jpg", ".jpeg", ".bmp")
        )

        if not has_supported_extension:
            if "JPEG" in selected_filter:
                file_path += ".jpg"
            elif "Bitmap" in selected_filter:
                file_path += ".bmp"
            else:
                file_path += ".png"

        saved = self.texture_pixmap.save(file_path)

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