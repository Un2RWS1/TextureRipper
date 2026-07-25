from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)


class ExportSettingsDialog(QDialog):
    def __init__(
        self,
        original_width: int,
        original_height: int,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.original_width = original_width
        self.original_height = original_height

        self.aspect_ratio = (
            original_width / original_height
            if original_height > 0
            else 1.0
        )

        self._updating_dimensions = False

        self.setWindowTitle(
            "Export Settings"
        )

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(
            [
                "Original",
                "50%",
                "1024 px maximum",
                "2048 px maximum",
                "4096 px maximum",
                "Custom",
            ]
        )
        self.preset_combo.currentTextChanged.connect(
            self.apply_preset
        )

        self.width_spinbox = QSpinBox()
        self.width_spinbox.setRange(
            1,
            16384,
        )
        self.width_spinbox.setValue(
            original_width
        )

        self.height_spinbox = QSpinBox()
        self.height_spinbox.setRange(
            1,
            16384,
        )
        self.height_spinbox.setValue(
            original_height
        )

        self.lock_aspect_checkbox = QCheckBox(
            "Lock aspect ratio"
        )
        self.lock_aspect_checkbox.setChecked(
            True
        )

        self.preserve_transparency_checkbox = QCheckBox(
            "Preserve transparency"
        )
        self.preserve_transparency_checkbox.setChecked(
            True
        )

        self.opacity_slider = QSlider(
            Qt.Orientation.Horizontal
        )
        self.opacity_slider.setRange(
            0,
            100,
        )
        self.opacity_slider.setValue(
            100
        )

        self.opacity_label = QLabel(
            "100%"
        )

        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(
            self.opacity_slider,
            1,
        )
        opacity_layout.addWidget(
            self.opacity_label
        )

        form_layout = QFormLayout()
        form_layout.addRow(
            "Preset",
            self.preset_combo,
        )
        form_layout.addRow(
            "Width",
            self.width_spinbox,
        )
        form_layout.addRow(
            "Height",
            self.height_spinbox,
        )
        form_layout.addRow(
            "",
            self.lock_aspect_checkbox,
        )
        form_layout.addRow(
            "Export opacity",
            opacity_layout,
        )
        form_layout.addRow(
            "",
            self.preserve_transparency_checkbox,
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(
            self.accept
        )
        buttons.rejected.connect(
            self.reject
        )

        layout = QVBoxLayout()
        layout.addLayout(
            form_layout
        )
        layout.addWidget(
            buttons
        )

        self.setLayout(layout)

        self.width_spinbox.valueChanged.connect(
            self.on_width_changed
        )
        self.height_spinbox.valueChanged.connect(
            self.on_height_changed
        )
        self.opacity_slider.valueChanged.connect(
            self.on_opacity_changed
        )

    def on_width_changed(
        self,
        width: int,
    ) -> None:
        if self._updating_dimensions:
            return

        self.preset_combo.setCurrentText(
            "Custom"
        )

        if not self.lock_aspect_checkbox.isChecked():
            return

        self._updating_dimensions = True

        height = max(
            1,
            int(round(width / self.aspect_ratio)),
        )

        self.height_spinbox.setValue(
            height
        )

        self._updating_dimensions = False

    def on_height_changed(
        self,
        height: int,
    ) -> None:
        if self._updating_dimensions:
            return

        self.preset_combo.setCurrentText(
            "Custom"
        )

        if not self.lock_aspect_checkbox.isChecked():
            return

        self._updating_dimensions = True

        width = max(
            1,
            int(round(height * self.aspect_ratio)),
        )

        self.width_spinbox.setValue(
            width
        )

        self._updating_dimensions = False

    def on_opacity_changed(
        self,
        value: int,
    ) -> None:
        self.opacity_label.setText(
            f"{value}%"
        )

    def apply_preset(
        self,
        preset: str,
    ) -> None:
        if preset == "Custom":
            return

        if preset == "Original":
            width = self.original_width
            height = self.original_height

        elif preset == "50%":
            width = max(
                1,
                self.original_width // 2,
            )
            height = max(
                1,
                self.original_height // 2,
            )

        else:
            maximum_dimension = int(
                preset.split()[0]
            )

            scale = min(
                1.0,
                maximum_dimension
                / max(
                    self.original_width,
                    self.original_height,
                ),
            )

            width = max(
                1,
                int(round(
                    self.original_width * scale
                )),
            )

            height = max(
                1,
                int(round(
                    self.original_height * scale
                )),
            )

        self._updating_dimensions = True

        self.width_spinbox.setValue(
            width
        )
        self.height_spinbox.setValue(
            height
        )

        self._updating_dimensions = False

    def settings(self) -> dict:
        return {
            "width": self.width_spinbox.value(),
            "height": self.height_spinbox.value(),
            "opacity": (
                self.opacity_slider.value()
                / 100.0
            ),
            "preserve_transparency": (
                self.preserve_transparency_checkbox
                .isChecked()
            ),
        }