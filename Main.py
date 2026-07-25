import sys
from pathlib import Path

import cv2

from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from image_view import ImageView
from texture_preview import TexturePreviewDialog
from texture_processing import extract_texture


class TextureRipperWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Texture Ripper")
        self.resize(1200, 800)

        self.image_view = ImageView()

        self.image_view.selection_manager.selection_changed.connect(
            self.on_selection_changed
        )

        self.image_view.selection_manager.selection_completed.connect(
            self.on_selection_completed
        )

        self.open_button = QPushButton("Open Image")
        self.open_button.clicked.connect(self.open_image)

        self.fit_button = QPushButton("Fit Image")
        self.fit_button.clicked.connect(
            self.image_view.fit_image_to_window
        )

        self.select_button = QPushButton("Select Surface")
        self.select_button.clicked.connect(
            self.start_selection
        )

        self.clear_button = QPushButton("Clear Selection")
        self.clear_button.clicked.connect(
            self.image_view.clear_selection
        )

        self.extract_button = QPushButton("Extract Texture")
        self.extract_button.clicked.connect(
            self.extract_selected_texture
        )
        self.extract_button.setEnabled(False)

        self.selection_status = QLabel(
            "Selection: 0 / 4 points"
        )

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.open_button)
        controls_layout.addWidget(self.fit_button)
        controls_layout.addWidget(self.select_button)
        controls_layout.addWidget(self.clear_button)
        controls_layout.addWidget(self.extract_button)
        controls_layout.addStretch()
        controls_layout.addWidget(self.selection_status)

        main_layout = QVBoxLayout()
        main_layout.addLayout(controls_layout)
        main_layout.addWidget(self.image_view, 1)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)

        self.setCentralWidget(central_widget)

        self.create_menu()
        self.create_toolbar()

        self.statusBar().showMessage("Ready")

    def create_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        open_action = QAction("&Open Image", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_image)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        selection_menu = self.menuBar().addMenu(
            "&Selection"
        )

        select_action = QAction(
            "&Select Surface",
            self,
        )
        select_action.setShortcut("S")
        select_action.triggered.connect(
            self.start_selection
        )
        selection_menu.addAction(select_action)

        clear_action = QAction(
            "&Clear Selection",
            self,
        )
        clear_action.setShortcut("Escape")
        clear_action.triggered.connect(
            self.image_view.clear_selection
        )
        selection_menu.addAction(clear_action)

        selection_menu.addSeparator()

        extract_action = QAction(
            "&Extract Texture",
            self,
        )
        extract_action.setShortcut("Ctrl+E")
        extract_action.triggered.connect(
            self.extract_selected_texture
        )
        selection_menu.addAction(extract_action)

        view_menu = self.menuBar().addMenu("&View")

        fit_action = QAction("&Fit Image", self)
        fit_action.setShortcut("F")
        fit_action.triggered.connect(
            self.image_view.fit_image_to_window
        )
        view_menu.addAction(fit_action)

    def create_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)

        self.addToolBar(toolbar)

        open_action = QAction("Open", self)
        open_action.triggered.connect(self.open_image)
        toolbar.addAction(open_action)

        select_action = QAction("Select", self)
        select_action.triggered.connect(
            self.start_selection
        )
        toolbar.addAction(select_action)

        clear_action = QAction("Clear", self)
        clear_action.triggered.connect(
            self.image_view.clear_selection
        )
        toolbar.addAction(clear_action)

        extract_action = QAction("Extract", self)
        extract_action.triggered.connect(
            self.extract_selected_texture
        )
        toolbar.addAction(extract_action)

        fit_action = QAction("Fit", self)
        fit_action.triggered.connect(
            self.image_view.fit_image_to_window
        )
        toolbar.addAction(fit_action)

    def open_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Image",
            "",
            (
                "Image Files "
                "(*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff);;"
                "All Files (*)"
            ),
        )

        if not file_path:
            return

        pixmap = QPixmap(file_path)

        if pixmap.isNull():
            QMessageBox.warning(
                self,
                "Unable to Open Image",
                "The selected file could not be loaded.",
            )
            return

        self.image_view.set_image(pixmap)

        filename = Path(file_path).name
        width = pixmap.width()
        height = pixmap.height()

        self.statusBar().showMessage(
            f"Opened {filename} - {width} x {height} pixels"
        )

    def start_selection(self) -> None:
        if not self.image_view.has_image():
            QMessageBox.information(
                self,
                "No Image",
                "Open an image before selecting a surface.",
            )
            return

        self.image_view.clear_selection()
        self.image_view.set_selection_mode(True)

        self.statusBar().showMessage(
            "Click top-left, top-right, "
            "bottom-right, then bottom-left."
        )

    def on_selection_changed(self, points: list) -> None:
        point_count = len(points)

        self.selection_status.setText(
            f"Selection: {point_count} / 4 points"
        )

        self.extract_button.setEnabled(
            point_count == 4
        )

        if point_count == 0:
            self.statusBar().showMessage(
                "Selection cleared."
            )

        elif point_count < 4:
            self.statusBar().showMessage(
                f"Selection point {point_count} of 4 placed."
            )

    def on_selection_completed(self, points: list) -> None:
        self.statusBar().showMessage(
            "Selection complete. Adjust the handles, "
            "then click Extract Texture."
        )

    def extract_selected_texture(self) -> None:
        points = self.image_view.get_selection_points()

        if len(points) != 4:
            QMessageBox.information(
                self,
                "Incomplete Selection",
                "Select exactly four corners first.",
            )
            return

        source_pixmap = self.image_view.get_image()

        if source_pixmap.isNull():
            QMessageBox.warning(
                self,
                "No Image",
                "There is no image to extract from.",
            )
            return

        try:
            texture_array = extract_texture(
                source_pixmap.toImage(),
                points,
            )

        except (ValueError, cv2.error) as error:
            QMessageBox.critical(
                self,
                "Extraction Failed",
                str(error),
            )
            return

        preview_dialog = TexturePreviewDialog(
            texture_array,
            self,
        )

        preview_dialog.exec()


def main() -> None:
    app = QApplication(sys.argv)

    window = TextureRipperWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()