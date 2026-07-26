import ctypes
import sys
from pathlib import Path

from PySide6.QtGui import QIcon

import sys
from pathlib import Path

import cv2

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from adjustments_panel import AdjustmentsPanel
from image_view import ImageView
from live_preview_panel import LivePreviewPanel
from texture_adjustments import apply_texture_adjustments
from texture_preview import TexturePreviewDialog
from texture_processing import (
    extract_texture,
    make_texture_seamless,
    rgba_array_to_qpixmap,
)


class TextureRipperWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Texture Ripper")
        self.resize(1500, 900)

        self.current_texture_array = None

        self.image_view = ImageView()

        self.live_preview_panel = LivePreviewPanel()
        self.live_preview_panel.seamless_changed.connect(
            self.on_seamless_changed
        )
        self.live_preview_panel.seamless_strength_changed.connect(
            self.on_seamless_strength_changed
        )

        self.adjustments_panel = AdjustmentsPanel(
            undo_stack=(
                self.image_view
                .selection_manager
                .undo_stack
            )
        )
        self.adjustments_panel.adjustments_changed.connect(
            self.on_adjustments_changed
        )

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(80)
        self.preview_timer.timeout.connect(
            self.update_live_preview
        )

        self.image_view.selection_manager.selection_changed.connect(
            self.on_selection_changed
        )
        self.image_view.selection_manager.selection_completed.connect(
            self.on_selection_completed
        )

        self.open_button = QPushButton(
            "Open Image"
        )
        self.open_button.clicked.connect(
            self.open_image
        )

        self.fit_button = QPushButton(
            "Fit Image"
        )
        self.fit_button.clicked.connect(
            self.image_view.fit_image_to_window
        )

        self.select_button = QPushButton(
            "Select Surface"
        )
        self.select_button.clicked.connect(
            self.start_selection
        )

        self.clear_button = QPushButton(
            "Clear Selection"
        )
        self.clear_button.clicked.connect(
            self.image_view.clear_selection
        )

        self.edge_snap_checkbox = QCheckBox(
            "Edge Snapping"
        )
        self.edge_snap_checkbox.setChecked(False)
        self.edge_snap_checkbox.setToolTip(
            "Snap dragged selection corners "
            "to nearby detected image edges."
        )
        self.edge_snap_checkbox.toggled.connect(
            self.on_edge_snapping_changed
        )

        self.extract_button = QPushButton(
            "Open Full Preview"
        )
        self.extract_button.clicked.connect(
            self.open_full_preview
        )
        self.extract_button.setEnabled(False)

        self.selection_status = QLabel(
            "Selection: 0 / 4 points"
        )

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(
            self.open_button
        )
        controls_layout.addWidget(
            self.fit_button
        )
        controls_layout.addWidget(
            self.select_button
        )
        controls_layout.addWidget(
            self.clear_button
        )
        controls_layout.addWidget(
            self.edge_snap_checkbox
        )
        controls_layout.addWidget(
            self.extract_button
        )
        controls_layout.addStretch()
        controls_layout.addWidget(
            self.selection_status
        )

        editor_widget = QWidget()

        editor_layout = QVBoxLayout()
        editor_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        editor_layout.addWidget(
            self.image_view
        )

        editor_widget.setLayout(
            editor_layout
        )

        right_panel = QWidget()

        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        right_layout.setSpacing(6)

        right_layout.addWidget(
            self.live_preview_panel,
            3,
        )
        right_layout.addWidget(
            self.adjustments_panel,
            2,
        )

        right_panel.setLayout(
            right_layout
        )

        self.main_splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        self.main_splitter.addWidget(
            editor_widget
        )
        self.main_splitter.addWidget(
            right_panel
        )

        self.main_splitter.setStretchFactor(
            0,
            4,
        )
        self.main_splitter.setStretchFactor(
            1,
            1,
        )
        self.main_splitter.setSizes(
            [1100, 400]
        )
        self.main_splitter.setChildrenCollapsible(
            False
        )

        main_layout = QVBoxLayout()
        main_layout.addLayout(
            controls_layout
        )
        main_layout.addWidget(
            self.main_splitter,
            1,
        )

        central_widget = QWidget()
        central_widget.setLayout(
            main_layout
        )

        self.setCentralWidget(
            central_widget
        )

        self.create_menu()
        self.create_toolbar()

        self.statusBar().showMessage(
            "Ready"
        )

    def create_menu(self) -> None:
        file_menu = self.menuBar().addMenu(
            "&File"
        )

        open_action = QAction(
            "&Open Image",
            self,
        )
        open_action.setShortcut(
            "Ctrl+O"
        )
        open_action.triggered.connect(
            self.open_image
        )
        file_menu.addAction(
            open_action
        )

        file_menu.addSeparator()

        exit_action = QAction(
            "E&xit",
            self,
        )
        exit_action.setShortcut(
            "Ctrl+Q"
        )
        exit_action.triggered.connect(
            self.close
        )
        file_menu.addAction(
            exit_action
        )

        edit_menu = self.menuBar().addMenu(
            "&Edit"
        )

        undo_action = (
            self.image_view
            .selection_manager
            .undo_stack
            .createUndoAction(
                self,
                "&Undo",
            )
        )
        undo_action.setShortcut(
            "Ctrl+Z"
        )
        edit_menu.addAction(
            undo_action
        )

        redo_action = (
            self.image_view
            .selection_manager
            .undo_stack
            .createRedoAction(
                self,
                "&Redo",
            )
        )
        redo_action.setShortcut(
            "Ctrl+Shift+Z"
        )
        edit_menu.addAction(
            redo_action
        )

        selection_menu = self.menuBar().addMenu(
            "&Selection"
        )

        select_action = QAction(
            "&Select Surface",
            self,
        )
        select_action.setShortcut(
            "S"
        )
        select_action.triggered.connect(
            self.start_selection
        )
        selection_menu.addAction(
            select_action
        )

        clear_action = QAction(
            "&Clear Selection",
            self,
        )
        clear_action.setShortcut(
            "Escape"
        )
        clear_action.triggered.connect(
            self.image_view.clear_selection
        )
        selection_menu.addAction(
            clear_action
        )

        selection_menu.addSeparator()

        preview_action = QAction(
            "Open &Full Preview",
            self,
        )
        preview_action.setShortcut(
            "Ctrl+E"
        )
        preview_action.triggered.connect(
            self.open_full_preview
        )
        selection_menu.addAction(
            preview_action
        )

        view_menu = self.menuBar().addMenu(
            "&View"
        )

        fit_action = QAction(
            "&Fit Image",
            self,
        )
        fit_action.setShortcut(
            "F"
        )
        fit_action.triggered.connect(
            self.image_view.fit_image_to_window
        )
        view_menu.addAction(
            fit_action
        )

    def create_toolbar(self) -> None:
        toolbar = QToolBar(
            "Main Toolbar"
        )
        toolbar.setMovable(False)

        self.addToolBar(
            toolbar
        )

        open_action = QAction(
            "Open",
            self,
        )
        open_action.triggered.connect(
            self.open_image
        )
        toolbar.addAction(
            open_action
        )

        toolbar.addSeparator()

        undo_action = (
            self.image_view
            .selection_manager
            .undo_stack
            .createUndoAction(
                self,
                "Undo",
            )
        )
        toolbar.addAction(
            undo_action
        )

        redo_action = (
            self.image_view
            .selection_manager
            .undo_stack
            .createRedoAction(
                self,
                "Redo",
            )
        )
        toolbar.addAction(
            redo_action
        )

        toolbar.addSeparator()

        select_action = QAction(
            "Select",
            self,
        )
        select_action.triggered.connect(
            self.start_selection
        )
        toolbar.addAction(
            select_action
        )

        clear_action = QAction(
            "Clear",
            self,
        )
        clear_action.triggered.connect(
            self.image_view.clear_selection
        )
        toolbar.addAction(
            clear_action
        )

        preview_action = QAction(
            "Full Preview",
            self,
        )
        preview_action.triggered.connect(
            self.open_full_preview
        )
        toolbar.addAction(
            preview_action
        )

        fit_action = QAction(
            "Fit",
            self,
        )
        fit_action.triggered.connect(
            self.image_view.fit_image_to_window
        )
        toolbar.addAction(
            fit_action
        )

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

        pixmap = QPixmap(
            file_path
        )

        if pixmap.isNull():
            QMessageBox.warning(
                self,
                "Unable to Open Image",
                "The selected file could not be loaded.",
            )
            return

        self.preview_timer.stop()
        self.current_texture_array = None

        self.live_preview_panel.clear_texture()
        self.image_view.set_image(
            pixmap
        )

        filename = Path(
            file_path
        ).name

        self.statusBar().showMessage(
            f"Opened {filename} - "
            f"{pixmap.width()} x {pixmap.height()} pixels"
        )

    def start_selection(self) -> None:
        if not self.image_view.has_image():
            QMessageBox.information(
                self,
                "No Image",
                "Open an image before selecting a surface.",
            )
            return

        self.preview_timer.stop()
        self.current_texture_array = None
        self.live_preview_panel.clear_texture()

        self.image_view.clear_selection()
        self.image_view.set_selection_mode(
            True
        )

        self.statusBar().showMessage(
            "Click top-left, top-right, "
            "bottom-right, then bottom-left."
        )

    def on_selection_changed(
        self,
        points: list,
    ) -> None:
        point_count = len(points)

        self.selection_status.setText(
            f"Selection: {point_count} / 4 points"
        )

        selection_complete = (
            point_count == 4
        )

        self.extract_button.setEnabled(
            selection_complete
        )

        if point_count == 0:
            self.image_view.set_selection_mode(
                False
            )

            self.preview_timer.stop()
            self.current_texture_array = None
            self.live_preview_panel.clear_texture()

            self.statusBar().showMessage(
                "Selection cleared."
            )

        elif point_count < 4:
            self.image_view.set_selection_mode(
                True
            )

            self.preview_timer.stop()
            self.current_texture_array = None
            self.live_preview_panel.clear_texture()

            self.statusBar().showMessage(
                f"Selection point {point_count} of 4 placed. "
                "Click to place the next point."
            )

        else:
            self.image_view.set_selection_mode(
                False
            )
            self.preview_timer.start()

    def on_selection_completed(
        self,
        points: list,
    ) -> None:
        self.image_view.set_selection_mode(
            False
        )

        self.statusBar().showMessage(
            "Selection complete. Adjust the handles "
            "while watching the live preview."
        )

        self.update_live_preview(
            fit_image=True
        )

    def on_edge_snapping_changed(
        self,
        enabled: bool,
    ) -> None:
        self.image_view.set_edge_snapping_enabled(
            enabled
        )

        self.statusBar().showMessage(
            "Edge snapping enabled."
            if enabled
            else "Edge snapping disabled."
        )

    def on_seamless_changed(
        self,
        enabled: bool,
    ) -> None:
        if len(
            self.image_view.get_selection_points()
        ) == 4:
            self.update_live_preview(
                fit_image=False
            )

        self.statusBar().showMessage(
            "Seamless mode enabled."
            if enabled
            else "Seamless mode disabled."
        )

    def on_seamless_strength_changed(
        self,
        value: int,
    ) -> None:
        if not self.live_preview_panel.seamless_enabled():
            return

        if len(
            self.image_view.get_selection_points()
        ) != 4:
            return

        self.preview_timer.start()

        self.statusBar().showMessage(
            f"Updating seamless blend: {value}%"
        )

    def on_adjustments_changed(self) -> None:
        if len(
            self.image_view.get_selection_points()
        ) != 4:
            return

        self.preview_timer.start()

        self.statusBar().showMessage(
            "Updating texture adjustments..."
        )

    def update_live_preview(
        self,
        fit_image: bool = False,
    ) -> None:
        points = (
            self.image_view
            .get_selection_points()
        )

        if len(points) != 4:
            return

        source_pixmap = (
            self.image_view
            .get_image()
        )

        if source_pixmap.isNull():
            return

        try:
            texture_array = extract_texture(
                source_pixmap.toImage(),
                points,
            )

            adjustment_settings = (
                self.adjustments_panel
                .get_settings()
            )

            texture_array = apply_texture_adjustments(
                texture_array,
                **adjustment_settings,
            )

            if (
                self.live_preview_panel
                .seamless_enabled()
            ):
                texture_array = make_texture_seamless(
                    texture_array,
                    blend_fraction=(
                        self.live_preview_panel
                        .seamless_blend_fraction()
                    ),
                )

            texture_pixmap = rgba_array_to_qpixmap(
                texture_array
            )

        except (ValueError, cv2.error) as error:
            self.current_texture_array = None

            self.live_preview_panel.show_error(
                str(error)
            )
            return

        self.current_texture_array = texture_array

        self.live_preview_panel.set_texture(
            texture_pixmap,
            fit_image=fit_image,
        )

        self.statusBar().showMessage(
            "Texture preview updated."
        )

    def open_full_preview(self) -> None:
        points = (
            self.image_view
            .get_selection_points()
        )

        if len(points) != 4:
            QMessageBox.information(
                self,
                "Incomplete Selection",
                "Select exactly four corners first.",
            )
            return

        self.update_live_preview(
            fit_image=False
        )

        if self.current_texture_array is None:
            QMessageBox.warning(
                self,
                "Preview Unavailable",
                "The texture preview could not be generated.",
            )
            return

        preview_dialog = TexturePreviewDialog(
            self.current_texture_array,
            self,
        )

        preview_dialog.exec()

def resource_path(relative_path: str) -> Path:
    """
    Return the correct resource path while running normally
    or from a PyInstaller bundle.
    """

    return Path(__file__).resolve().parent / relative_path

def main() -> None:
    # Gives Windows a unique identity for the taskbar icon.
    try:
        app_id = "KevinLin.TextureRipper.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            app_id
        )
    except (AttributeError, OSError):
        pass

    app = QApplication(sys.argv)

    icon_path = resource_path(
        "assets/texture_ripper.ico"
    )

    if icon_path.exists():
        app.setWindowIcon(
            QIcon(str(icon_path))
        )

    window = TextureRipperWindow()

    if icon_path.exists():
        window.setWindowIcon(
            QIcon(str(icon_path))
        )

    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()