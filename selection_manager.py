from PySide6.QtCore import QObject, QPointF, Signal


class SelectionManager(QObject):
    selection_changed = Signal(list)
    selection_completed = Signal(list)

    MAX_POINTS = 4

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._points: list[QPointF] = []

    def clear(self) -> None:
        self._points.clear()
        self.selection_changed.emit([])

    def add_point(self, point: QPointF) -> bool:
        if self.is_complete():
            return False

        self._points.append(QPointF(point))

        points_copy = self.get_points()
        self.selection_changed.emit(points_copy)

        if self.is_complete():
            self.selection_completed.emit(points_copy)

        return True

    def update_point(
        self,
        index: int,
        point: QPointF,
    ) -> None:
        if index < 0 or index >= len(self._points):
            raise IndexError("Selection point index is invalid.")

        self._points[index] = QPointF(point)
        self.selection_changed.emit(self.get_points())

    def get_points(self) -> list[QPointF]:
        return [
            QPointF(point)
            for point in self._points
        ]

    def point_count(self) -> int:
        return len(self._points)

    def is_complete(self) -> bool:
        return len(self._points) == self.MAX_POINTS