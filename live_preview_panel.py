from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)

from texture_preview_view import TexturePreviewView


class LivePreviewPanel(QWidget):
    seamless_changed = Signal(bool)
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.original_pixmap = QPixmap()
        self.showing_tiled_preview = False

        self.title_label = QLabel("Live Texture Preview")
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.title_label.setStyleSheet(
            """
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 6px;
            }
            """
        )

        self.preview_view = TexturePreviewView()

        self.placeholder_label = QLabel(
            "Select four corners to generate a preview."
        )
        self.placeholder_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.placeholder_label.setWordWrap(True)

        self.size_label = QLabel("No texture")

        self.seamless_checkbox = QCheckBox("Make Seamless")
        self.seamless_checkbox.setChecked(False)
        self.seamless_checkbox.setToolTip(
            "Blend opposite texture edges. "
            "This modifies the preview and exported texture."
        )
        self.seamless_checkbox.toggled.connect(
            self.seamless_changed.emit
)

        self.tile_button = QPushButton("Show 3 x 3 Tile")
        self.tile_button.setCheckable(True)
        self.tile_button.clicked.connect(
            self.toggle_tiled_preview
        )

        self.fit_button = QPushButton("Fit")
        self.fit_button.clicked.connect(
            self.preview_view.fit_image_to_window
        )

        self.actual_size_button = QPushButton("100%")
        self.actual_size_button.clicked.connect(
            self.preview_view.actual_size
        )

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.size_label)
        controls_layout.addStretch()
        controls_layout.addWidget(self.tile_button)
        controls_layout.addWidget(self.fit_button)
        controls_layout.addWidget(self.actual_size_button)
        controls_layout.addWidget(self.seamless_checkbox)
        controls_layout.addWidget(self.tile_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.title_label)
        main_layout.addWidget(self.placeholder_label)
        main_layout.addWidget(self.preview_view, 1)
        main_layout.addLayout(controls_layout)

        self.setLayout(main_layout)

        self.preview_view.hide()
        self.set_controls_enabled(False)

    def set_controls_enabled(self, enabled: bool) -> None:
        self.tile_button.setEnabled(enabled)
        self.fit_button.setEnabled(enabled)
        self.actual_size_button.setEnabled(enabled)

    def seamless_enabled(self) -> bool:
        return self.seamless_checkbox.isChecked()

    def set_texture(
        self,
        pixmap: QPixmap,
        fit_image: bool = False,
    ) -> None:
        if pixmap.isNull():
            self.clear_texture()
            return

        self.original_pixmap = pixmap

        self.placeholder_label.hide()
        self.preview_view.show()

        preview_pixmap = self.get_current_preview_pixmap()

        self.preview_view.set_image(
            preview_pixmap,
            fit_image=fit_image,
        )

        self.update_size_label()
        self.set_controls_enabled(True)

    def get_current_preview_pixmap(self) -> QPixmap:
        if self.original_pixmap.isNull():
            return QPixmap()

        if self.showing_tiled_preview:
            return self.create_tiled_pixmap(
                self.original_pixmap,
                columns=3,
                rows=3,
            )

        return self.original_pixmap

    def create_tiled_pixmap(
        self,
        source_pixmap: QPixmap,
        columns: int,
        rows: int,
    ) -> QPixmap:
        tile_width = source_pixmap.width()
        tile_height = source_pixmap.height()

        tiled_pixmap = QPixmap(
            tile_width * columns,
            tile_height * rows,
        )

        tiled_pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(tiled_pixmap)

        for row in range(rows):
            for column in range(columns):
                x_position = column * tile_width
                y_position = row * tile_height

                painter.drawPixmap(
                    x_position,
                    y_position,
                    source_pixmap,
                )

        painter.end()

        return tiled_pixmap

    def toggle_tiled_preview(
        self,
        checked: bool,
    ) -> None:
        if self.original_pixmap.isNull():
            return

        self.showing_tiled_preview = checked

        if checked:
            self.tile_button.setText("Show Single")
        else:
            self.tile_button.setText("Show 3 x 3 Tile")

        preview_pixmap = self.get_current_preview_pixmap()

        self.preview_view.set_image(
            preview_pixmap,
            fit_image=True,
        )

        self.update_size_label()

    def update_size_label(self) -> None:
        if self.original_pixmap.isNull():
            self.size_label.setText("No texture")
            return

        width = self.original_pixmap.width()
        height = self.original_pixmap.height()

        if self.showing_tiled_preview:
            self.size_label.setText(
                f"Tile: {width} x {height} pixels | "
                f"Preview: {width * 3} x {height * 3}"
            )
        else:
            self.size_label.setText(
                f"{width} x {height} pixels"
            )

    def clear_texture(self) -> None:
        self.original_pixmap = QPixmap()
        self.showing_tiled_preview = False

        self.tile_button.setChecked(False)
        self.tile_button.setText("Show 3 x 3 Tile")

        self.preview_view.clear_image()
        self.preview_view.hide()

        self.placeholder_label.show()
        self.placeholder_label.setText(
            "Select four corners to generate a preview."
        )

        self.size_label.setText("No texture")
        self.set_controls_enabled(False)

    def show_error(self, message: str) -> None:
        self.original_pixmap = QPixmap()
        self.showing_tiled_preview = False

        self.tile_button.setChecked(False)
        self.tile_button.setText("Show 3 x 3 Tile")

        self.preview_view.clear_image()
        self.preview_view.hide()

        self.placeholder_label.show()
        self.placeholder_label.setText(
            f"Preview unavailable:\n{message}"
        )

        self.size_label.setText("Preview error")
        self.set_controls_enabled(False)

