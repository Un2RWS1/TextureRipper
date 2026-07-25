import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from texture_processing import numpy_to_qpixmap


class TexturePreviewDialog(QDialog):
    def __init__(
        self,
        texture_array: np.ndarray,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.texture_array = texture_array
        self.texture_pixmap = numpy_to_qpixmap(
            texture_array
        )

        self.setWindowTitle("Extracted Texture Preview")
        self.resize(900, 700)

        self.image_label = QLabel()
        self.image_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.image_label.setPixmap(self.texture_pixmap)
        self.image_label.setMinimumSize(
            self.texture_pixmap.size()
        )

        scroll_area = QScrollArea()
        scroll_area.setWidget(self.image_label)
        scroll_area.setWidgetResizable(True)
        scroll_area.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.size_label = QLabel(
            f"Texture size: "
            f"{self.texture_pixmap.width()} x "
            f"{self.texture_pixmap.height()} pixels"
        )

        self.save_button = QPushButton("Save Texture")
        self.save_button.clicked.connect(
            self.save_texture
        )

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.size_label)
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.close_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll_area, 1)
        main_layout.addLayout(button_layout)

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

        if "." not in file_path.split("/")[-1]:
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