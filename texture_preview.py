import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QAction,
    QColor,
    QImage,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QToolBar,
    QVBoxLayout,
)

from clone_stamp_view import CloneStampView
from export_settings_dialog import ExportSettingsDialog
from texture_processing import rgba_array_to_qpixmap


def qimage_to_array(
    image: QImage,
) -> np.ndarray:
    converted = image.convertToFormat(
        QImage.Format.Format_RGBA8888
    )

    width = converted.width()
    height = converted.height()
    bytes_per_line = converted.bytesPerLine()

    buffer = converted.bits()

    array = np.frombuffer(
        buffer,
        dtype=np.uint8,
        count=height * bytes_per_line,
    )

    array = array.reshape(
        height,
        bytes_per_line,
    )

    array = array[:, : width * 4]

    return array.reshape(
        height,
        width,
        4,
    ).copy()


def array_to_qimage(
    array: np.ndarray,
) -> QImage:
    contiguous = np.ascontiguousarray(
        array
    )

    height, width, _ = contiguous.shape

    return QImage(
        contiguous.data,
        width,
        height,
        width * 4,
        QImage.Format.Format_RGBA8888,
    ).copy()


def shift_image(
    image: QImage,
    horizontal_shift: int,
    vertical_shift: int,
) -> QImage:
    array = qimage_to_array(
        image
    )

    shifted = np.roll(
        array,
        shift=vertical_shift,
        axis=0,
    )

    shifted = np.roll(
        shifted,
        shift=horizontal_shift,
        axis=1,
    )

    return array_to_qimage(
        shifted
    )


class TexturePreviewDialog(QDialog):
    def __init__(
        self,
        texture_array: np.ndarray,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle(
            "Texture Preview and Seam Editor"
        )
        self.resize(
            1100,
            800,
        )

        self.original_image = (
            rgba_array_to_qpixmap(
                texture_array
            ).toImage().convertToFormat(
                QImage.Format.Format_RGBA8888
            )
        )

        self.offset_enabled = False

        self.preview_view = CloneStampView()
        self.preview_view.set_working_image(
            self.original_image
        )

        self.create_toolbar()

        self.offset_checkbox = QCheckBox(
            "Offset View"
        )
        self.offset_checkbox.toggled.connect(
            self.on_offset_changed
        )

        self.clone_checkbox = QCheckBox(
            "Clone Stamp"
        )
        self.clone_checkbox.setToolTip(
            "Enable clone painting. "
            "Alt + click chooses the source."
        )
        self.clone_checkbox.toggled.connect(
            self.preview_view.set_clone_enabled
        )

        self.brush_size_label = QLabel(
            "Brush: 60 px"
        )

        self.brush_size_slider = QSlider(
            Qt.Orientation.Horizontal
        )
        self.brush_size_slider.setRange(
            5,
            300,
        )
        self.brush_size_slider.setValue(
            60
        )
        self.brush_size_slider.setFixedWidth(
            130
        )
        self.brush_size_slider.valueChanged.connect(
            self.on_brush_size_changed
        )

        self.opacity_label = QLabel(
            "Opacity: 85%"
        )

        self.opacity_slider = QSlider(
            Qt.Orientation.Horizontal
        )
        self.opacity_slider.setRange(
            1,
            100,
        )
        self.opacity_slider.setValue(
            85
        )
        self.opacity_slider.setFixedWidth(
            110
        )
        self.opacity_slider.valueChanged.connect(
            self.on_brush_opacity_changed
        )

        self.instructions_label = QLabel(
            "Clone Stamp: Alt + click a clean source, "
            "then drag over the seam."
        )
        self.instructions_label.setWordWrap(
            True
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

        self.export_button = QPushButton(
            "Export..."
        )
        self.export_button.clicked.connect(
            self.export_texture
        )

        self.close_button = QPushButton(
            "Close"
        )
        self.close_button.clicked.connect(
            self.accept
        )

        edit_controls = QHBoxLayout()
        edit_controls.addWidget(
            self.offset_checkbox
        )
        edit_controls.addWidget(
            self.clone_checkbox
        )
        edit_controls.addWidget(
            self.brush_size_label
        )
        edit_controls.addWidget(
            self.brush_size_slider
        )
        edit_controls.addWidget(
            self.opacity_label
        )
        edit_controls.addWidget(
            self.opacity_slider
        )
        edit_controls.addStretch()
        edit_controls.addWidget(
            self.fit_button
        )
        edit_controls.addWidget(
            self.actual_size_button
        )

        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(
            self.instructions_label,
            1,
        )
        bottom_layout.addWidget(
            self.export_button
        )
        bottom_layout.addWidget(
            self.close_button
        )

        main_layout = QVBoxLayout()
        main_layout.addWidget(
            self.toolbar
        )
        main_layout.addWidget(
            self.preview_view,
            1,
        )
        main_layout.addLayout(
            edit_controls
        )
        main_layout.addLayout(
            bottom_layout
        )

        self.setLayout(
            main_layout
        )

    def create_toolbar(self) -> None:
        self.toolbar = QToolBar(
            "Editor Toolbar"
        )

        undo_action = (
            self.preview_view
            .undo_stack
            .createUndoAction(
                self,
                "Undo Stroke",
            )
        )
        undo_action.setShortcut(
            "Ctrl+Z"
        )

        redo_action = (
            self.preview_view
            .undo_stack
            .createRedoAction(
                self,
                "Redo Stroke",
            )
        )
        redo_action.setShortcut(
            "Ctrl+Shift+Z"
        )

        self.toolbar.addAction(
            undo_action
        )
        self.toolbar.addAction(
            redo_action
        )

    def on_brush_size_changed(
        self,
        size: int,
    ) -> None:
        self.brush_size_label.setText(
            f"Brush: {size} px"
        )

        self.preview_view.set_brush_size(
            size
        )

    def on_brush_opacity_changed(
        self,
        value: int,
    ) -> None:
        self.opacity_label.setText(
            f"Opacity: {value}%"
        )

        self.preview_view.set_brush_opacity(
            value / 100.0
        )

    def on_offset_changed(
        self,
        enabled: bool,
    ) -> None:
        current_image = (
            self.preview_view.working_image()
        )

        width = current_image.width()
        height = current_image.height()

        horizontal_shift = width // 2
        vertical_shift = height // 2

        if enabled:
            shifted = shift_image(
                current_image,
                horizontal_shift,
                vertical_shift,
            )
        else:
            shifted = shift_image(
                current_image,
                -horizontal_shift,
                -vertical_shift,
            )

        self.offset_enabled = enabled

        self.preview_view.set_working_image(
            shifted,
            preserve_view=True,
        )

        # A coordinate remap changes the entire edit state,
        # so clear local stroke history.
        self.preview_view.undo_stack.clear()

    def get_original_orientation_image(
        self,
    ) -> QImage:
        image = self.preview_view.working_image()

        if not self.offset_enabled:
            return image

        return shift_image(
            image,
            -(image.width() // 2),
            -(image.height() // 2),
        )

    def prepare_export_image(
        self,
        settings: dict,
    ) -> QImage:
        image = (
            self.get_original_orientation_image()
            .convertToFormat(
                QImage.Format.Format_RGBA8888
            )
        )

        image = image.scaled(
            settings["width"],
            settings["height"],
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        opacity = settings["opacity"]
        preserve_transparency = (
            settings["preserve_transparency"]
        )

        result = QImage(
            image.size(),
            QImage.Format.Format_RGBA8888,
        )

        if preserve_transparency:
            result.fill(
                Qt.GlobalColor.transparent
            )
        else:
            result.fill(
                QColor(255, 255, 255, 255)
            )

        painter = QPainter(
            result
        )
        painter.setOpacity(
            opacity
        )
        painter.drawImage(
            0,
            0,
            image,
        )
        painter.end()

        if not preserve_transparency:
            flattened = QImage(
                result.size(),
                QImage.Format.Format_RGB888,
            )
            flattened.fill(
                QColor(255, 255, 255)
            )

            painter = QPainter(
                flattened
            )
            painter.drawImage(
                0,
                0,
                result,
            )
            painter.end()

            return flattened

        return result

    def export_texture(self) -> None:
        source_image = (
            self.get_original_orientation_image()
        )

        settings_dialog = ExportSettingsDialog(
            original_width=source_image.width(),
            original_height=source_image.height(),
            parent=self,
        )

        if (
            settings_dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        settings = settings_dialog.settings()

        file_path, selected_filter = (
            QFileDialog.getSaveFileName(
                self,
                "Export Texture",
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

        if not lowercase_path.endswith(
            (
                ".png",
                ".jpg",
                ".jpeg",
                ".bmp",
            )
        ):
            if "JPEG" in selected_filter:
                file_path += ".jpg"
            elif "Bitmap" in selected_filter:
                file_path += ".bmp"
            else:
                file_path += ".png"

        export_image = self.prepare_export_image(
            settings
        )

        if file_path.lower().endswith(
            (".jpg", ".jpeg")
        ):
            # JPEG has no alpha channel.
            export_image = export_image.convertToFormat(
                QImage.Format.Format_RGB888
            )

        saved = export_image.save(
            file_path
        )

        if not saved:
            QMessageBox.warning(
                self,
                "Export Failed",
                "The texture could not be exported.",
            )
            return

        QMessageBox.information(
            self,
            "Texture Exported",
            f"The texture was exported to:\n{file_path}",
        )