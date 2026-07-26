import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QImage,
    QPainter,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSlider,
    QToolBar,
    QVBoxLayout,
)

from clone_stamp_view import (
    CloneStampView,
    qimage_to_rgba_array,
    rgba_array_to_qimage,
)
from export_settings_dialog import ExportSettingsDialog
from pbr_preview_dialog import PBRPreviewDialog
from texture_processing import rgba_array_to_qpixmap


def shift_image(
    image: QImage,
    horizontal_shift: int,
    vertical_shift: int,
) -> QImage:
    """
    Wrap an image horizontally and vertically.

    Positive values shift pixels right and down. Pixels that move past
    an edge wrap around to the opposite side.
    """

    array = qimage_to_rgba_array(image)

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

    return rgba_array_to_qimage(shifted)


class TexturePreviewDialog(QDialog):
    def __init__(
        self,
        texture_array: np.ndarray,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle(
            "Texture Preview and Seam Repair"
        )
        self.resize(
            1200,
            850,
        )

        self.original_image = (
            rgba_array_to_qpixmap(texture_array)
            .toImage()
            .convertToFormat(
                QImage.Format.Format_RGBA8888
            )
        )

        self.offset_enabled = False

        self.preview_view = CloneStampView()

        self.preview_view.set_working_image(
            self.original_image
        )

        self.preview_view.status_message.connect(
            self.on_editor_status
        )

        self.create_toolbar()
        self.create_tool_controls()
        self.create_brush_controls()
        self.create_bottom_controls()

        self.create_layout()

        self.on_tool_changed()

    def create_toolbar(self) -> None:
        self.toolbar = QToolBar(
            "Editor Toolbar"
        )

        self.toolbar.setMovable(False)

        undo_action = (
            self.preview_view
            .undo_stack
            .createUndoAction(
                self,
                "Undo Repair",
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
                "Redo Repair",
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

    def create_tool_controls(self) -> None:
        self.pan_radio = QRadioButton(
            "Pan"
        )

        self.clone_radio = QRadioButton(
            "Clone"
        )

        self.heal_radio = QRadioButton(
            "Heal"
        )

        self.pan_radio.setChecked(
            True
        )

        self.tool_group = QButtonGroup(
            self
        )

        self.tool_group.setExclusive(
            True
        )

        self.tool_group.addButton(
            self.pan_radio
        )

        self.tool_group.addButton(
            self.clone_radio
        )

        self.tool_group.addButton(
            self.heal_radio
        )

        self.pan_radio.toggled.connect(
            self.on_tool_changed
        )

        self.clone_radio.toggled.connect(
            self.on_tool_changed
        )

        self.heal_radio.toggled.connect(
            self.on_tool_changed
        )

        self.offset_checkbox = QCheckBox(
            "Offset View"
        )

        self.offset_checkbox.setToolTip(
            "Shift the outer texture edges into the center "
            "so they can be repaired."
        )

        self.offset_checkbox.toggled.connect(
            self.on_offset_changed
        )

        self.seam_guides_checkbox = QCheckBox(
            "Seam Guides"
        )

        self.seam_guides_checkbox.setChecked(
            True
        )

        self.seam_guides_checkbox.setToolTip(
            "Show guides where the offset seams meet."
        )

        # Seam-guide drawing is not yet implemented in CloneStampView.
        # The checkbox is kept here so the control is ready when guide
        # overlays are added.
        self.seam_guides_checkbox.setEnabled(
            False
        )

    def create_brush_controls(self) -> None:
        self.brush_size_label = QLabel(
            "Size: 60 px"
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
            110
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
            95
        )

        self.opacity_slider.valueChanged.connect(
            self.on_brush_opacity_changed
        )

        self.hardness_label = QLabel(
            "Hardness: 75%"
        )

        self.hardness_slider = QSlider(
            Qt.Orientation.Horizontal
        )

        self.hardness_slider.setRange(
            5,
            100,
        )

        self.hardness_slider.setValue(
            75
        )

        self.hardness_slider.setFixedWidth(
            95
        )

        self.hardness_slider.valueChanged.connect(
            self.on_brush_hardness_changed
        )

        self.preview_view.set_brush_size(
            self.brush_size_slider.value()
        )

        self.preview_view.set_brush_opacity(
            self.opacity_slider.value() / 100.0
        )

        self.preview_view.set_brush_hardness(
            self.hardness_slider.value() / 100.0
        )

    def create_bottom_controls(self) -> None:
        self.clear_source_button = QPushButton(
            "Clear Source"
        )

        self.clear_source_button.clicked.connect(
            self.preview_view.clear_source
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

        self.instructions_label = QLabel(
            "Choose Clone or Heal. Alt + click a clean "
            "source area, then paint over the seam."
        )

        self.instructions_label.setWordWrap(
            True
        )

        self.pbr_button = QPushButton(
            "Generate PBR Maps"
        )

        self.pbr_button.clicked.connect(
            self.open_pbr_generator
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

    def create_layout(self) -> None:
        controls_layout = QHBoxLayout()

        controls_layout.addWidget(
            self.pan_radio
        )

        controls_layout.addWidget(
            self.clone_radio
        )

        controls_layout.addWidget(
            self.heal_radio
        )

        controls_layout.addSpacing(
            12
        )

        controls_layout.addWidget(
            self.offset_checkbox
        )

        controls_layout.addWidget(
            self.seam_guides_checkbox
        )

        controls_layout.addSpacing(
            12
        )

        controls_layout.addWidget(
            self.brush_size_label
        )

        controls_layout.addWidget(
            self.brush_size_slider
        )

        controls_layout.addWidget(
            self.opacity_label
        )

        controls_layout.addWidget(
            self.opacity_slider
        )

        controls_layout.addWidget(
            self.hardness_label
        )

        controls_layout.addWidget(
            self.hardness_slider
        )

        controls_layout.addStretch()

        controls_layout.addWidget(
            self.clear_source_button
        )

        controls_layout.addWidget(
            self.fit_button
        )

        controls_layout.addWidget(
            self.actual_size_button
        )

        bottom_layout = QHBoxLayout()

        bottom_layout.addWidget(
            self.instructions_label,
            1,
        )

        bottom_layout.addWidget(
            self.pbr_button
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
            controls_layout
        )

        main_layout.addLayout(
            bottom_layout
        )

        self.setLayout(
            main_layout
        )

    def on_editor_status(
        self,
        message: str,
    ) -> None:
        self.instructions_label.setText(
            message
        )

    def on_tool_changed(self) -> None:
        if self.pan_radio.isChecked():
            tool = CloneStampView.TOOL_PAN

        elif self.clone_radio.isChecked():
            tool = CloneStampView.TOOL_CLONE

        else:
            tool = CloneStampView.TOOL_HEAL

        self.preview_view.set_tool(
            tool
        )

        brush_controls_enabled = (
            tool != CloneStampView.TOOL_PAN
        )

        self.brush_size_label.setEnabled(
            brush_controls_enabled
        )

        self.brush_size_slider.setEnabled(
            brush_controls_enabled
        )

        self.opacity_label.setEnabled(
            brush_controls_enabled
        )

        self.opacity_slider.setEnabled(
            brush_controls_enabled
        )

        self.hardness_label.setEnabled(
            brush_controls_enabled
        )

        self.hardness_slider.setEnabled(
            brush_controls_enabled
        )

        self.clear_source_button.setEnabled(
            brush_controls_enabled
        )

        if tool == CloneStampView.TOOL_PAN:
            self.instructions_label.setText(
                "Pan mode: drag to move around the texture. "
                "Use the mouse wheel to zoom."
            )

        elif tool == CloneStampView.TOOL_CLONE:
            self.instructions_label.setText(
                "Clone: Alt + click a clean source area, "
                "then paint exact copied pixels over the seam."
            )

        else:
            self.instructions_label.setText(
                "Heal: Alt + click a similar source area, "
                "then paint over the seam. The repair blends "
                "after the mouse is released."
            )

    def on_brush_size_changed(
        self,
        size: int,
    ) -> None:
        self.brush_size_label.setText(
            f"Size: {size} px"
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

    def on_brush_hardness_changed(
        self,
        value: int,
    ) -> None:
        self.hardness_label.setText(
            f"Hardness: {value}%"
        )

        self.preview_view.set_brush_hardness(
            value / 100.0
        )

    def on_offset_changed(
        self,
        enabled: bool,
    ) -> None:
        current_image = (
            self.preview_view.working_image()
        )

        if current_image.isNull():
            return

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

        self.preview_view.clear_source()

        # Existing brush commands use coordinates from the previous
        # orientation. Clear the local history after remapping.
        self.preview_view.undo_stack.clear()

        if enabled:
            self.setWindowTitle(
                "Texture Preview and Seam Repair - Offset View"
            )

            self.instructions_label.setText(
                "Offset view enabled. Repair the horizontal "
                "and vertical seams crossing through the center."
            )

        else:
            self.setWindowTitle(
                "Texture Preview and Seam Repair"
            )

            self.instructions_label.setText(
                "Offset view disabled. The texture is shown "
                "in its original orientation."
            )

    def get_original_orientation_image(
        self,
    ) -> QImage:
        image = (
            self.preview_view.working_image()
        )

        if image.isNull():
            return QImage()

        if not self.offset_enabled:
            return image

        return shift_image(
            image,
            -(image.width() // 2),
            -(image.height() // 2),
        )

    def open_pbr_generator(self) -> None:
        repaired_image = (
            self.get_original_orientation_image()
        )

        if repaired_image.isNull():
            QMessageBox.warning(
                self,
                "PBR Generator",
                "There is no texture available.",
            )
            return

        texture_array = qimage_to_rgba_array(
            repaired_image
        )

        dialog = PBRPreviewDialog(
            texture_array,
            self,
        )

        dialog.exec()

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

        if preserve_transparency:
            result = QImage(
                image.size(),
                QImage.Format.Format_RGBA8888,
            )

            result.fill(
                Qt.GlobalColor.transparent
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

            return result

        result = QImage(
            image.size(),
            QImage.Format.Format_RGB888,
        )

        result.fill(
            QColor(
                255,
                255,
                255,
            )
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

        return result

    def export_texture(self) -> None:
        source_image = (
            self.get_original_orientation_image()
        )

        if source_image.isNull():
            QMessageBox.warning(
                self,
                "Export Texture",
                "There is no texture available to export.",
            )
            return

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

        settings = (
            settings_dialog.settings()
        )

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

        lowercase_path = (
            file_path.lower()
        )

        supported_extensions = (
            ".png",
            ".jpg",
            ".jpeg",
            ".bmp",
        )

        if not lowercase_path.endswith(
            supported_extensions
        ):
            if "JPEG" in selected_filter:
                file_path += ".jpg"

            elif "Bitmap" in selected_filter:
                file_path += ".bmp"

            else:
                file_path += ".png"

        export_image = (
            self.prepare_export_image(
                settings
            )
        )

        if file_path.lower().endswith(
            (
                ".jpg",
                ".jpeg",
            )
        ):
            export_image = (
                export_image.convertToFormat(
                    QImage.Format.Format_RGB888
                )
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
            (
                "The texture was exported to:\n"
                f"{file_path}"
            ),
        )