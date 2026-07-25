from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class AdjustmentCommand(QUndoCommand):
    """
    Undoable change to one or more texture-adjustment controls.
    """

    def __init__(
        self,
        panel: "AdjustmentsPanel",
        old_state: dict,
        new_state: dict,
        description: str,
        first_redo_already_applied: bool = False,
    ) -> None:
        super().__init__(description)

        self.panel = panel
        self.old_state = deepcopy(old_state)
        self.new_state = deepcopy(new_state)

        self.first_redo_already_applied = (
            first_redo_already_applied
        )
        self.is_first_redo = True

    def undo(self) -> None:
        self.panel.apply_state(
            self.old_state
        )

    def redo(self) -> None:
        if (
            self.is_first_redo
            and self.first_redo_already_applied
        ):
            self.is_first_redo = False
            return

        self.is_first_redo = False

        self.panel.apply_state(
            self.new_state
        )


class AdjustmentSlider(QWidget):
    value_changed = Signal(int)
    interaction_started = Signal()
    interaction_finished = Signal()

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
        self.slider.setRange(
            minimum,
            maximum,
        )
        self.slider.setValue(
            default
        )

        self.value_label = QLabel()
        self.value_label.setMinimumWidth(42)
        self.value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.slider.valueChanged.connect(
            self._on_value_changed
        )
        self.slider.sliderPressed.connect(
            self.interaction_started.emit
        )
        self.slider.sliderReleased.connect(
            self.interaction_finished.emit
        )

        layout = QHBoxLayout()
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        layout.setSpacing(6)

        layout.addWidget(
            self.slider,
            1,
        )
        layout.addWidget(
            self.value_label
        )

        self.setLayout(layout)

        self._update_label(default)

    def _on_value_changed(
        self,
        value: int,
    ) -> None:
        self._update_label(value)
        self.value_changed.emit(value)

    def _update_label(
        self,
        value: int,
    ) -> None:
        self.value_label.setText(
            f"{value}{self.suffix}"
        )

    def value(self) -> int:
        return self.slider.value()

    def set_value(
        self,
        value: int,
    ) -> None:
        self.slider.setValue(value)

    def set_value_silently(
        self,
        value: int,
    ) -> None:
        blocker = QSignalBlocker(
            self.slider
        )

        self.slider.setValue(value)
        self._update_label(value)

        del blocker

    def set_control_enabled(
        self,
        enabled: bool,
    ) -> None:
        self.slider.setEnabled(enabled)
        self.value_label.setEnabled(enabled)


class AdjustmentsPanel(QGroupBox):
    adjustments_changed = Signal()

    DEFAULTS = {
        "lighting_enabled": False,
        "lighting_strength": 65,

        "shadow_enabled": False,
        "shadow_strength": 45,

        "contrast_enabled": False,
        "contrast_strength": 65,

        "color_enabled": False,
        "color_strength": 60,

        "saturation": 100,
    }

    def __init__(
        self,
        undo_stack: QUndoStack,
        parent=None,
    ) -> None:
        super().__init__(
            "Texture Adjustments",
            parent,
        )

        self.undo_stack = undo_stack

        self._applying_state = False
        self._slider_drag_start_state: dict | None = None
        self._last_committed_state: dict = {}

        self.lighting_checkbox = QCheckBox(
            "Normalize Lighting"
        )
        self.lighting_slider = AdjustmentSlider(
            0,
            100,
            self.DEFAULTS["lighting_strength"],
        )
        self.lighting_reset_button = (
            self.create_reset_button(
                "Reset lighting normalization"
            )
        )

        self.shadow_checkbox = QCheckBox(
            "Reduce Shadows"
        )
        self.shadow_slider = AdjustmentSlider(
            0,
            100,
            self.DEFAULTS["shadow_strength"],
        )
        self.shadow_reset_button = (
            self.create_reset_button(
                "Reset shadow reduction"
            )
        )

        self.contrast_checkbox = QCheckBox(
            "Local Contrast"
        )
        self.contrast_slider = AdjustmentSlider(
            0,
            100,
            self.DEFAULTS["contrast_strength"],
        )
        self.contrast_reset_button = (
            self.create_reset_button(
                "Reset local contrast"
            )
        )

        self.color_checkbox = QCheckBox(
            "Auto White Balance"
        )
        self.color_slider = AdjustmentSlider(
            0,
            100,
            self.DEFAULTS["color_strength"],
        )
        self.color_reset_button = (
            self.create_reset_button(
                "Reset white balance"
            )
        )

        self.saturation_label = QLabel(
            "Saturation"
        )
        self.saturation_slider = AdjustmentSlider(
            0,
            200,
            self.DEFAULTS["saturation"],
        )
        self.saturation_reset_button = (
            self.create_reset_button(
                "Reset saturation"
            )
        )

        self.reset_all_button = QPushButton(
            "Reset All Adjustments"
        )

        self._create_layout()
        self._connect_signals()
        self._update_enabled_states()

        self._last_committed_state = (
            self.capture_state()
        )

    def create_reset_button(
        self,
        tooltip: str,
    ) -> QToolButton:
        button = QToolButton()

        reset_icon = self.style().standardIcon(
            QStyle.StandardPixmap.SP_BrowserReload
        )

        button.setIcon(reset_icon)
        button.setToolTip(tooltip)
        button.setAutoRaise(True)
        button.setFixedSize(24, 24)

        return button

    def create_checkbox_header(
        self,
        checkbox: QCheckBox,
        reset_button: QToolButton,
    ) -> QWidget:
        widget = QWidget()

        layout = QHBoxLayout()
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        layout.setSpacing(4)

        layout.addWidget(
            checkbox
        )
        layout.addWidget(
            reset_button
        )
        layout.addStretch()

        widget.setLayout(layout)

        return widget

    def create_label_header(
        self,
        label: QLabel,
        reset_button: QToolButton,
    ) -> QWidget:
        widget = QWidget()

        layout = QHBoxLayout()
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        layout.setSpacing(4)

        layout.addWidget(
            label
        )
        layout.addWidget(
            reset_button
        )
        layout.addStretch()

        widget.setLayout(layout)

        return widget

    def _create_layout(self) -> None:
        main_layout = QVBoxLayout()
        main_layout.setSpacing(5)

        main_layout.addWidget(
            self.create_checkbox_header(
                self.lighting_checkbox,
                self.lighting_reset_button,
            )
        )
        main_layout.addWidget(
            self.lighting_slider
        )

        main_layout.addSpacing(4)

        main_layout.addWidget(
            self.create_checkbox_header(
                self.shadow_checkbox,
                self.shadow_reset_button,
            )
        )
        main_layout.addWidget(
            self.shadow_slider
        )

        main_layout.addSpacing(4)

        main_layout.addWidget(
            self.create_checkbox_header(
                self.contrast_checkbox,
                self.contrast_reset_button,
            )
        )
        main_layout.addWidget(
            self.contrast_slider
        )

        main_layout.addSpacing(4)

        main_layout.addWidget(
            self.create_checkbox_header(
                self.color_checkbox,
                self.color_reset_button,
            )
        )
        main_layout.addWidget(
            self.color_slider
        )

        main_layout.addSpacing(4)

        main_layout.addWidget(
            self.create_label_header(
                self.saturation_label,
                self.saturation_reset_button,
            )
        )
        main_layout.addWidget(
            self.saturation_slider
        )

        main_layout.addSpacing(8)

        main_layout.addWidget(
            self.reset_all_button
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
                self._on_checkbox_changed
            )

        sliders = [
            self.lighting_slider,
            self.shadow_slider,
            self.contrast_slider,
            self.color_slider,
            self.saturation_slider,
        ]

        for slider in sliders:
            slider.interaction_started.connect(
                self._on_slider_interaction_started
            )
            slider.interaction_finished.connect(
                self._on_slider_interaction_finished
            )
            slider.value_changed.connect(
                self._on_slider_value_changed
            )

        self.lighting_reset_button.clicked.connect(
            self.reset_lighting
        )
        self.shadow_reset_button.clicked.connect(
            self.reset_shadows
        )
        self.contrast_reset_button.clicked.connect(
            self.reset_contrast
        )
        self.color_reset_button.clicked.connect(
            self.reset_color
        )
        self.saturation_reset_button.clicked.connect(
            self.reset_saturation
        )

        self.reset_all_button.clicked.connect(
            self.reset_all_adjustments
        )

    def capture_state(self) -> dict:
        return {
            "lighting_enabled":
                self.lighting_checkbox.isChecked(),

            "lighting_strength":
                self.lighting_slider.value(),

            "shadow_enabled":
                self.shadow_checkbox.isChecked(),

            "shadow_strength":
                self.shadow_slider.value(),

            "contrast_enabled":
                self.contrast_checkbox.isChecked(),

            "contrast_strength":
                self.contrast_slider.value(),

            "color_enabled":
                self.color_checkbox.isChecked(),

            "color_strength":
                self.color_slider.value(),

            "saturation":
                self.saturation_slider.value(),
        }

    def apply_state(
        self,
        state: dict,
    ) -> None:
        self._applying_state = True

        checkbox_blockers = [
            QSignalBlocker(
                self.lighting_checkbox
            ),
            QSignalBlocker(
                self.shadow_checkbox
            ),
            QSignalBlocker(
                self.contrast_checkbox
            ),
            QSignalBlocker(
                self.color_checkbox
            ),
        ]

        self.lighting_checkbox.setChecked(
            state["lighting_enabled"]
        )
        self.shadow_checkbox.setChecked(
            state["shadow_enabled"]
        )
        self.contrast_checkbox.setChecked(
            state["contrast_enabled"]
        )
        self.color_checkbox.setChecked(
            state["color_enabled"]
        )

        self.lighting_slider.set_value_silently(
            state["lighting_strength"]
        )
        self.shadow_slider.set_value_silently(
            state["shadow_strength"]
        )
        self.contrast_slider.set_value_silently(
            state["contrast_strength"]
        )
        self.color_slider.set_value_silently(
            state["color_strength"]
        )
        self.saturation_slider.set_value_silently(
            state["saturation"]
        )

        del checkbox_blockers

        self._update_enabled_states()

        self._last_committed_state = deepcopy(
            state
        )

        self._applying_state = False

        self.adjustments_changed.emit()

    def push_state_change(
        self,
        old_state: dict,
        new_state: dict,
        description: str,
        already_applied: bool,
    ) -> None:
        if old_state == new_state:
            self._last_committed_state = deepcopy(
                new_state
            )
            return

        command = AdjustmentCommand(
            panel=self,
            old_state=old_state,
            new_state=new_state,
            description=description,
            first_redo_already_applied=already_applied,
        )

        self.undo_stack.push(command)

        self._last_committed_state = deepcopy(
            new_state
        )

    def _on_checkbox_changed(
        self,
        checked: bool,
    ) -> None:
        if self._applying_state:
            return

        self._update_enabled_states()
        self.adjustments_changed.emit()

        new_state = self.capture_state()

        self.push_state_change(
            old_state=self._last_committed_state,
            new_state=new_state,
            description="Change texture adjustment",
            already_applied=True,
        )

    def _on_slider_interaction_started(
        self,
    ) -> None:
        if self._applying_state:
            return

        self._slider_drag_start_state = (
            self.capture_state()
        )

    def _on_slider_value_changed(
        self,
        value: int,
    ) -> None:
        if self._applying_state:
            return

        # Update the preview continuously while dragging.
        self.adjustments_changed.emit()

        # Keyboard changes and mouse-wheel changes may occur
        # without sliderPressed/sliderReleased.
        if self._slider_drag_start_state is None:
            new_state = self.capture_state()

            self.push_state_change(
                old_state=self._last_committed_state,
                new_state=new_state,
                description="Change texture adjustment",
                already_applied=True,
            )

    def _on_slider_interaction_finished(
        self,
    ) -> None:
        if self._applying_state:
            return

        if self._slider_drag_start_state is None:
            return

        old_state = self._slider_drag_start_state
        new_state = self.capture_state()

        self._slider_drag_start_state = None

        self.push_state_change(
            old_state=old_state,
            new_state=new_state,
            description="Adjust texture slider",
            already_applied=True,
        )

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

    def create_reset_state(
        self,
        keys: list[str],
    ) -> dict:
        new_state = self.capture_state()

        for key in keys:
            new_state[key] = self.DEFAULTS[key]

        return new_state

    def reset_lighting(self) -> None:
        self.push_reset_command(
            keys=[
                "lighting_enabled",
                "lighting_strength",
            ],
            description="Reset lighting normalization",
        )

    def reset_shadows(self) -> None:
        self.push_reset_command(
            keys=[
                "shadow_enabled",
                "shadow_strength",
            ],
            description="Reset shadow reduction",
        )

    def reset_contrast(self) -> None:
        self.push_reset_command(
            keys=[
                "contrast_enabled",
                "contrast_strength",
            ],
            description="Reset local contrast",
        )

    def reset_color(self) -> None:
        self.push_reset_command(
            keys=[
                "color_enabled",
                "color_strength",
            ],
            description="Reset white balance",
        )

    def reset_saturation(self) -> None:
        self.push_reset_command(
            keys=[
                "saturation",
            ],
            description="Reset saturation",
        )

    def reset_all_adjustments(self) -> None:
        old_state = self.capture_state()
        new_state = deepcopy(
            self.DEFAULTS
        )

        self.push_state_change(
            old_state=old_state,
            new_state=new_state,
            description="Reset all texture adjustments",
            already_applied=False,
        )

    def push_reset_command(
        self,
        keys: list[str],
        description: str,
    ) -> None:
        old_state = self.capture_state()
        new_state = self.create_reset_state(
            keys
        )

        self.push_state_change(
            old_state=old_state,
            new_state=new_state,
            description=description,
            already_applied=False,
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