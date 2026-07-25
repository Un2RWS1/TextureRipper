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

        # Main image canvas
        self.image_view = ImageView()
        self.image_view.selection_changed.connect(
            self.on_selection_changed
        )

        # Open image button
        self.open_button = QPushButton("Open Image")
        self.open_button.clicked.connect(self.open_image)

        # Fit image button
        self.fit_button = QPushButton("Fit Image")
        self.fit_button.clicked.connect(
            self.image_view.fit_image_to_window
        )

        # Start four-corner selection
        self.select_button = QPushButton("Select Surface")
        self.select_button.clicked.connect(
            self.start_selection
        )

        # Remove the current selection
        self.clear_button = QPushButton("Clear Selection")
        self.clear_button.clicked.connect(
            self.image_view.clear_selection
        )

        # Extract and flatten the selected surface
        self.extract_button = QPushButton("Extract Texture")
        self.extract_button.clicked.connect(
            self.extract_selected_texture
        )

        # Extraction is unavailable until four points exist.
        self.extract_button.setEnabled(False)

        # Shows the number of selected corners
        self.selection_status = QLabel(
            "Selection: 0 / 4 points"
        )

        # Top row of controls
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.open_button)
        controls_layout.addWidget(self.fit_button)
        controls_layout.addWidget(self.select_button)
        controls_layout.addWidget(self.clear_button)
        controls_layout.addWidget(self.extract_button)
        controls_layout.addStretch()
        controls_layout.addWidget(self.selection_status)

        # Main application layout
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
        """Create the menus at the top of the window."""

        # File menu
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

        # Selection menu
        selection_menu = self.menuBar().addMenu("&Selection")

        start_selection_action = QAction(
            "&Select Surface",
            self,
        )
        start_selection_action.setShortcut("S")
        start_selection_action.triggered.connect(
            self.start_selection
        )
        selection_menu.addAction(start_selection_action)

        clear_selection_action = QAction(
            "&Clear Selection",
            self,
        )
        clear_selection_action.setShortcut("Escape")
        clear_selection_action.triggered.connect(
            self.image_view.clear_selection
        )
        selection_menu.addAction(clear_selection_action)

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

        # View menu
        view_menu = self.menuBar().addMenu("&View")

        fit_action = QAction("&Fit Image", self)
        fit_action.setShortcut("F")
        fit_action.triggered.connect(
            self.image_view.fit_image_to_window
        )
        view_menu.addAction(fit_action)

    def create_toolbar(self) -> None:
        """Create the shortcut toolbar."""

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
        """Open an image from the computer."""

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

        # The user pressed Cancel.
        if not file_path:
            return

        pixmap = QPixmap(file_path)

        if pixmap.isNull():
            QMessageBox.warning(
                self,
                "Unable to Open Image",
                "The selected file could not be loaded as an image.",
            )
            return

        self.image_view.set_image(pixmap)

        filename = Path(file_path).name
        width = pixmap.width()
        height = pixmap.height()

        self.statusBar().showMessage(
            f"Opened {filename} — {width} × {height} pixels"
        )

    def start_selection(self) -> None:
        """Begin a new four-corner surface selection."""

        if not self.image_view.has_image():
            QMessageBox.information(
                self,
                "No Image",
                "Open an image before selecting a surface.",
            )
            return

        # Starting a new selection removes the old selection.
        self.image_view.clear_selection()
        self.image_view.set_selection_mode(True)

        self.statusBar().showMessage(
            "Click four corners in order: "
            "top-left, top-right, bottom-right, bottom-left."
        )

    def on_selection_changed(self, points: list) -> None:
        """Update the interface whenever selection points change."""

        point_count = len(points)

        self.selection_status.setText(
            f"Selection: {point_count} / 4 points"
        )

        # Only enable extraction when four corners have been placed.
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

        else:
            self.statusBar().showMessage(
                "Selection complete. Drag the handles to adjust it, "
                "then click Extract Texture."
            )

    def extract_selected_texture(self) -> None:
        """Flatten the four-corner selection into a rectangle."""

        points = self.image_view.get_selection_points()

        if len(points) != 4:
            QMessageBox.information(
                self,
                "Incomplete Selection",
                "Select exactly four corners before extracting.",
            )
            return

        pixmap = self.image_view.get_image()

        if pixmap.isNull():
            QMessageBox.warning(
                self,
                "No Image",
                "There is no image to extract from.",
            )
            return

        try:
            texture_array = extract_texture(
                pixmap.toImage(),
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