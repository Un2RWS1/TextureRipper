from pathlib import Path

import numpy as np

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pbr_generation import generate_pbr_maps
from texture_preview_view import TexturePreviewView


def rgba_array_to_pixmap(
    image: np.ndarray,
) -> QPixmap:
    contiguous = np.ascontiguousarray(
        image
    )

    height, width, channels = contiguous.shape

    if channels == 4:
        format_value = QImage.Format.Format_RGBA8888
        bytes_per_line = width * 4

    elif channels == 3:
        format_value = QImage.Format.Format_RGB888
        bytes_per_line = width * 3

    else:
        raise ValueError(
            "Expected an RGB or RGBA image."
        )

    qimage = QImage(
        contiguous.data,
        width,
        height,
        bytes_per_line,
        format_value,
    ).copy()

    return QPixmap.fromImage(
        qimage
    )


class LabeledSlider(QWidget):
    value_changed = Signal(int)

    def __init__(
        self,
        minimum: int,
        maximum: int,
        value: int,
        suffix: str = "",
        parent=None,
    ) -> None:

        super().__init__(parent)

        self.suffix = suffix

        self.slider = QSlider(
            Qt.Orientation.Horizontal
        )
        self.slider.setRange(
            minimum,
            maximum,
        )
        self.slider.setValue(
            value
        )

        self.label = QLabel()
        self.label.setMinimumWidth(
            48
        )

        layout = QHBoxLayout()
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        layout.addWidget(
            self.slider,
            1,
        )
        layout.addWidget(
            self.label
        )

        self.setLayout(
            layout
        )

        self.slider.valueChanged.connect(
            self._on_value_changed
        )

        self._update_label(
            value
        )

    def _on_value_changed(
        self,
        value: int,
    ) -> None:
        self._update_label(
            value
        )
        self.value_changed.emit(
            value
        )

    def _update_label(
        self,
        value: int,
    ) -> None:
        self.label.setText(
            f"{value}{self.suffix}"
        )

    def value(self) -> int:
        return self.slider.value()


class PBRPreviewDialog(QDialog):
    def __init__(
        self,
        source_texture: np.ndarray,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.source_texture = source_texture.copy()
        self.generated_maps: dict[
            str,
            np.ndarray,
        ] = {}

        self.setWindowTitle(
            "PBR Map Generator"
        )
        self.resize(
            1200,
            850,
        )

        self.preview_timer = QTimer(
            self
        )
        self.preview_timer.setSingleShot(
            True
        )
        self.preview_timer.setInterval(
            100
        )
        self.preview_timer.timeout.connect(
            self.regenerate_maps
        )

        self.tab_widget = QTabWidget()

        self.preview_views: dict[
            str,
            TexturePreviewView,
        ] = {}

        for map_name in (
            "Height",
            "Normal",
            "Roughness",
            "AO",
        ):
            view = TexturePreviewView()

            self.preview_views[
                map_name
            ] = view

            self.tab_widget.addTab(
                view,
                map_name,
            )

        controls = self.create_controls()

        self.export_current_button = QPushButton(
            "Export Current Map"
        )
        self.export_current_button.clicked.connect(
            self.export_current_map
        )

        self.export_all_button = QPushButton(
            "Export All Maps"
        )
        self.export_all_button.clicked.connect(
            self.export_all_maps
        )

        self.close_button = QPushButton(
            "Close"
        )
        self.close_button.clicked.connect(
            self.accept
        )

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(
            self.export_current_button
        )
        bottom_layout.addWidget(
            self.export_all_button
        )
        bottom_layout.addWidget(
            self.close_button
        )

        content_layout = QHBoxLayout()
        content_layout.addWidget(
            self.tab_widget,
            1,
        )
        content_layout.addWidget(
            controls
        )

        main_layout = QVBoxLayout()
        main_layout.addLayout(
            content_layout,
            1,
        )
        main_layout.addLayout(
            bottom_layout
        )

        self.setLayout(
            main_layout
        )

        self.regenerate_maps()

    def create_controls(self) -> QWidget:
        controls_widget = QWidget()
        controls_widget.setMaximumWidth(
            340
        )

        height_group = QGroupBox(
            "Height Map"
        )
        height_form = QFormLayout()

        self.height_blur = QSpinBox()
        self.height_blur.setRange(
            1,
            101,
        )
        self.height_blur.setSingleStep(
            2
        )
        self.height_blur.setValue(
            5
        )

        self.height_contrast = LabeledSlider(
            50,
            300,
            125,
            "%",
        )

        self.height_invert = QCheckBox(
            "Invert height"
        )

        height_form.addRow(
            "Blur",
            self.height_blur,
        )
        height_form.addRow(
            "Contrast",
            self.height_contrast,
        )
        height_form.addRow(
            "",
            self.height_invert,
        )

        height_group.setLayout(
            height_form
        )

        normal_group = QGroupBox(
            "Normal Map"
        )
        normal_form = QFormLayout()

        self.normal_strength = LabeledSlider(
            10,
            1000,
            250,
            "%",
        )

        self.normal_blur = QSpinBox()
        self.normal_blur.setRange(
            1,
            31,
        )
        self.normal_blur.setSingleStep(
            2
        )
        self.normal_blur.setValue(
            1
        )

        self.normal_invert_y = QCheckBox(
            "Invert green channel"
        )

        normal_form.addRow(
            "Strength",
            self.normal_strength,
        )
        normal_form.addRow(
            "Blur",
            self.normal_blur,
        )
        normal_form.addRow(
            "",
            self.normal_invert_y,
        )

        normal_group.setLayout(
            normal_form
        )

        roughness_group = QGroupBox(
            "Roughness Map"
        )
        roughness_form = QFormLayout()

        self.roughness_base = LabeledSlider(
            0,
            100,
            60,
            "%",
        )

        self.roughness_detail = LabeledSlider(
            0,
            100,
            45,
            "%",
        )

        self.roughness_blur = QSpinBox()
        self.roughness_blur.setRange(
            3,
            101,
        )
        self.roughness_blur.setSingleStep(
            2
        )
        self.roughness_blur.setValue(
            9
        )

        self.roughness_invert = QCheckBox(
            "Invert roughness"
        )

        roughness_form.addRow(
            "Base",
            self.roughness_base,
        )
        roughness_form.addRow(
            "Detail",
            self.roughness_detail,
        )
        roughness_form.addRow(
            "Radius",
            self.roughness_blur,
        )
        roughness_form.addRow(
            "",
            self.roughness_invert,
        )

        roughness_group.setLayout(
            roughness_form
        )

        ao_group = QGroupBox(
            "Ambient Occlusion"
        )
        ao_form = QFormLayout()

        self.ao_radius = QSpinBox()
        self.ao_radius.setRange(
            3,
            201,
        )
        self.ao_radius.setSingleStep(
            2
        )
        self.ao_radius.setValue(
            25
        )

        self.ao_strength = LabeledSlider(
            0,
            500,
            150,
            "%",
        )

        ao_form.addRow(
            "Radius",
            self.ao_radius,
        )
        ao_form.addRow(
            "Strength",
            self.ao_strength,
        )

        ao_group.setLayout(
            ao_form
        )

        layout = QVBoxLayout()
        layout.addWidget(
            height_group
        )
        layout.addWidget(
            normal_group
        )
        layout.addWidget(
            roughness_group
        )
        layout.addWidget(
            ao_group
        )
        layout.addStretch()

        controls_widget.setLayout(
            layout
        )

        widgets = [
            self.height_blur,
            self.height_contrast.slider,
            self.height_invert,
            self.normal_strength.slider,
            self.normal_blur,
            self.normal_invert_y,
            self.roughness_base.slider,
            self.roughness_detail.slider,
            self.roughness_blur,
            self.roughness_invert,
            self.ao_radius,
            self.ao_strength.slider,
        ]

        for widget in widgets:
            if isinstance(
                widget,
                QCheckBox,
            ):
                widget.toggled.connect(
                    self.schedule_regeneration
                )
            elif isinstance(
                widget,
                QSlider,
            ):
                widget.valueChanged.connect(
                    self.schedule_regeneration
                )
            else:
                widget.valueChanged.connect(
                    self.schedule_regeneration
                )

        return controls_widget

    def schedule_regeneration(self) -> None:
        self.preview_timer.start()

    def regenerate_maps(self) -> None:
        self.generated_maps = generate_pbr_maps(
            self.source_texture,

            height_blur=(
                self.height_blur.value()
            ),
            height_contrast=(
                self.height_contrast.value()
                / 100.0
            ),
            height_invert=(
                self.height_invert.isChecked()
            ),

            normal_strength=(
                self.normal_strength.value()
                / 100.0
            ),
            normal_blur=(
                self.normal_blur.value()
            ),
            normal_invert_y=(
                self.normal_invert_y.isChecked()
            ),

            roughness_base=(
                self.roughness_base.value()
                / 100.0
            ),
            roughness_detail=(
                self.roughness_detail.value()
                / 100.0
            ),
            roughness_blur=(
                self.roughness_blur.value()
            ),
            roughness_invert=(
                self.roughness_invert.isChecked()
            ),

            ao_radius=(
                self.ao_radius.value()
            ),
            ao_strength=(
                self.ao_strength.value()
                / 100.0
            ),
        )

        for map_name, map_array in (
            self.generated_maps.items()
        ):
            self.preview_views[
                map_name
            ].set_image(
                rgba_array_to_pixmap(
                    map_array
                ),
                fit_image=False,
            )

    def current_map_name(self) -> str:
        return self.tab_widget.tabText(
            self.tab_widget.currentIndex()
        )

    def save_map(
        self,
        map_name: str,
        file_path: str,
    ) -> bool:
        map_array = self.generated_maps[
            map_name
        ]

        pixmap = rgba_array_to_pixmap(
            map_array
        )

        return pixmap.save(
            file_path
        )

    def export_current_map(self) -> None:
        map_name = self.current_map_name()

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export {map_name} Map",
            f"texture_{map_name.lower()}.png",
            "PNG Image (*.png)",
        )

        if not file_path:
            return

        if not file_path.lower().endswith(
            ".png"
        ):
            file_path += ".png"

        if not self.save_map(
            map_name,
            file_path,
        ):
            QMessageBox.warning(
                self,
                "Export Failed",
                f"The {map_name} map could not be saved.",
            )

    def export_all_maps(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose PBR Export Folder",
        )

        if not directory:
            return

        output_directory = Path(
            directory
        )

        failed_maps = []

        for map_name in (
            "Height",
            "Normal",
            "Roughness",
            "AO",
        ):
            output_path = (
                output_directory
                / f"texture_{map_name.lower()}.png"
            )

            if not self.save_map(
                map_name,
                str(output_path),
            ):
                failed_maps.append(
                    map_name
                )

        if failed_maps:
            QMessageBox.warning(
                self,
                "Some Exports Failed",
                "Could not export: "
                + ", ".join(failed_maps),
            )
        else:
            QMessageBox.information(
                self,
                "PBR Maps Exported",
                f"All maps were exported to:\n{directory}",
            )