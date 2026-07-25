from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt


class AdjustmentSlider(QWidget):
    value_changed = Signal(int)

    def __init__(
        self,
        minimum: int,
        maximum: int,
        default: int,
        suffix: str = "%",
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.suffix = suffix

        self.slider = QSlider(
            Qt.Orientation.Horizontal
        )
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(default)

        self.value_label = QLabel()
        self.value_label.setMinimumWidth(42)

        self.slider.valueChanged.connect(
            self._on_value_changed
        )

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.value_label)

        self.setLayout(layout)
        self._update_label(default)

    def _on_value_changed(self, value: int) -> None:
        self._update_label(value)
        self.value_changed.emit(value)

    def _update_label(self, value: int) -> None:
        self.value_label.setText(
            f"{value}{self.suffix}"
        )

    def value(self) -> int:
        return self.slider.value()

    def set_value(self, value: int) -> None:
        self.slider.setValue(value)

    def set_control_enabled(
        self,
        enabled: bool,
    ) -> None:
        self.slider.setEnabled(enabled)
        self.value_label.setEnabled(enabled)


class AdjustmentsPanel(QGroupBox):
    adjustments_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(
            "Texture Adjustments",
            parent,
        )

        self.setCheckable(False)

        self.lighting_checkbox = QCheckBox(
            "Normalize Lighting"
        )
        self.lighting_slider = AdjustmentSlider(
            0,
            100,
            65,
        )

        self.shadow_checkbox = QCheckBox(
            "Reduce Shadows"
        )
        self.shadow_slider = AdjustmentSlider(
            0,
            100,
            45,
        )

        self.contrast_checkbox = QCheckBox(
            "Local Contrast"
        )
        self.contrast_slider = AdjustmentSlider(
            0,
            100,
            65,
        )

        self.color_checkbox = QCheckBox(
            "Auto White Balance"
        )
        self.color_slider = AdjustmentSlider(
            0,
            100,
            60,
        )

        self.saturation_slider = AdjustmentSlider(
            0,
            200,
            100,
        )

        self.reset_button = QPushButton(
            "Reset Adjustments"
        )
        self.reset_button.clicked.connect(
            self.reset_adjustments
        )

        self._create_layout()
        self._connect_signals()
        self._update_enabled_states()

    def _create_layout(self) -> None:
        main_layout = QVBoxLayout()

        main_layout.addWidget(
            self.lighting_checkbox
        )
        main_layout.addWidget(
            self.lighting_slider
        )

        main_layout.addWidget(
            self.shadow_checkbox
        )
        main_layout.addWidget(
            self.shadow_slider
        )

        main_layout.addWidget(
            self.contrast_checkbox
        )
        main_layout.addWidget(
            self.contrast_slider
        )

        main_layout.addWidget(
            self.color_checkbox
        )
        main_layout.addWidget(
            self.color_slider
        )

        saturation_layout = QFormLayout()
        saturation_layout.addRow(
            "Saturation",
            self.saturation_slider,
        )

        main_layout.addLayout(
            saturation_layout
        )
        main_layout.addWidget(
            self.reset_button
        )

        self.setLayout(main_layout)

    def _connect_signals(self) -> None:
        checkboxes = [
            self.lighting_checkbox,
            self.shadow_checkbox,
            self.contrast_checkbox,
            self.color_checkbox,
        ]

        for checkbox in checkboxes:
            checkbox.toggled.connect(
                self._on_adjustment_changed
            )

        sliders = [
            self.lighting_slider,
            self.shadow_slider,
            self.contrast_slider,
            self.color_slider,
            self.saturation_slider,
        ]

        for slider in sliders:
            slider.value_changed.connect(
                self._on_slider_changed
            )

    def _on_adjustment_changed(
        self,
        checked: bool,
    ) -> None:
        self._update_enabled_states()
        self.adjustments_changed.emit()

    def _on_slider_changed(
        self,
        value: int,
    ) -> None:
        self.adjustments_changed.emit()

    def _update_enabled_states(self) -> None:
        self.lighting_slider.set_control_enabled(
            self.lighting_checkbox.isChecked()
        )

        self.shadow_slider.set_control_enabled(
            self.shadow_checkbox.isChecked()
        )

        self.contrast_slider.set_control_enabled(
            self.contrast_checkbox.isChecked()
        )

        self.color_slider.set_control_enabled(
            self.color_checkbox.isChecked()
        )

    def get_settings(self) -> dict:
        return {
            "lighting_enabled":
                self.lighting_checkbox.isChecked(),

            "lighting_strength":
                self.lighting_slider.value() / 100.0,

            "shadow_enabled":
                self.shadow_checkbox.isChecked(),

            "shadow_strength":
                self.shadow_slider.value() / 100.0,

            "contrast_enabled":
                self.contrast_checkbox.isChecked(),

            "contrast_strength":
                self.contrast_slider.value() / 100.0,

            "color_enabled":
                self.color_checkbox.isChecked(),

            "color_strength":
                self.color_slider.value() / 100.0,

            "saturation":
                self.saturation_slider.value() / 100.0,
        }

    def reset_adjustments(self) -> None:
        self.blockSignals(True)

        self.lighting_checkbox.setChecked(False)
        self.shadow_checkbox.setChecked(False)
        self.contrast_checkbox.setChecked(False)
        self.color_checkbox.setChecked(False)

        self.lighting_slider.set_value(65)
        self.shadow_slider.set_value(45)
        self.contrast_slider.set_value(65)
        self.color_slider.set_value(60)
        self.saturation_slider.set_value(100)

        self.blockSignals(False)

        self._update_enabled_states()
        self.adjustments_changed.emit()