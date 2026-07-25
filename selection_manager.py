from PySide6.QtCore import QObject, QPointF, Signal
from PySide6.QtGui import QUndoCommand, QUndoStack


def copy_points(points: list[QPointF]) -> list[QPointF]:
    return [QPointF(point) for point in points]


class ChangeSelectionCommand(QUndoCommand):
    def __init__(
        self,
        manager,
        old_points: list[QPointF],
        new_points: list[QPointF],
        description: str,
        first_redo_already_applied: bool = False,
    ) -> None:
        super().__init__(description)

        self.manager = manager
        self.old_points = copy_points(old_points)
        self.new_points = copy_points(new_points)
        self.first_redo_already_applied = first_redo_already_applied
        self.is_first_redo = True

    def undo(self) -> None:
        self.manager._apply_points(self.old_points)

    def redo(self) -> None:
        if (
            self.is_first_redo
            and self.first_redo_already_applied
        ):
            self.is_first_redo = False
            return

        self.is_first_redo = False
        self.manager._apply_points(self.new_points)


class SelectionManager(QObject):
    selection_changed = Signal(list)
    selection_completed = Signal(list)

    MAX_POINTS = 4

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._points: list[QPointF] = []
        self.undo_stack = QUndoStack(self)

    def _apply_points(
        self,
        points: list[QPointF],
    ) -> None:
        was_complete = self.is_complete()

        self._points = copy_points(points)

        current_points = self.get_points()
        self.selection_changed.emit(current_points)

        if self.is_complete() and not was_complete:
            self.selection_completed.emit(current_points)

    def clear(
        self,
        record_undo: bool = True,
    ) -> None:
        if not self._points:
            return

        old_points = self.get_points()

        if record_undo:
            command = ChangeSelectionCommand(
                self,
                old_points,
                [],
                "Clear selection",
            )
            self.undo_stack.push(command)
        else:
            self._apply_points([])

    def reset(self) -> None:
        """
        Clear the selection and its undo history.

        Use this when opening a different image because selections
        from the previous image should not be recoverable.
        """
        self._apply_points([])
        self.undo_stack.clear()

    def add_point(self, point: QPointF) -> bool:
        if self.is_complete():
            return False

        old_points = self.get_points()
        new_points = old_points + [QPointF(point)]

        command = ChangeSelectionCommand(
            self,
            old_points,
            new_points,
            "Add selection point",
        )

        self.undo_stack.push(command)
        return True

    def preview_point_move(
        self,
        index: int,
        point: QPointF,
    ) -> None:
        """
        Update a point during dragging without adding an undo step
        for every mouse-move event.
        """
        if index < 0 or index >= len(self._points):
            return

        self._points[index] = QPointF(point)
        self.selection_changed.emit(self.get_points())

    def commit_point_move(
        self,
        index: int,
        old_point: QPointF,
        new_point: QPointF,
    ) -> None:
        if index < 0 or index >= len(self._points):
            return

        if old_point == new_point:
            return

        old_points = self.get_points()
        new_points = self.get_points()

        old_points[index] = QPointF(old_point)
        new_points[index] = QPointF(new_point)

        command = ChangeSelectionCommand(
            self,
            old_points,
            new_points,
            "Move selection point",
            first_redo_already_applied=True,
        )

        self.undo_stack.push(command)

    def get_points(self) -> list[QPointF]:
        return copy_points(self._points)

    def point_count(self) -> int:
        return len(self._points)

    def is_complete(self) -> bool:
        return len(self._points) == self.MAX_POINTS