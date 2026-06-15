from PySide6.QtCore import QObject, Signal


class UnitManager(QObject):
    """Stores CAD geometry in meters and formats values in the active unit."""

    unit_changed = Signal(str)

    FACTORS = {
        "m": 1.0,
        "cm": 100.0,
        "mm": 1000.0,
    }

    def __init__(self, initial_unit="m", parent=None):
        super().__init__(parent)
        self._active_unit = initial_unit if initial_unit in self.FACTORS else "m"

    @property
    def units(self):
        return list(self.FACTORS)

    @property
    def active_unit(self):
        return self._active_unit

    def set_unit(self, unit):
        if unit not in self.FACTORS:
            return False
        if unit == self._active_unit:
            self.unit_changed.emit(self._active_unit)
            return True
        self._active_unit = unit
        self.unit_changed.emit(self._active_unit)
        return True

    def to_base_length(self, value):
        return value / self.FACTORS[self._active_unit]

    def length(self, meters):
        return meters * self.FACTORS[self._active_unit]

    def area(self, square_meters):
        factor = self.FACTORS[self._active_unit]
        return square_meters * factor * factor

    def format_length(self, meters, precision=2):
        return f"{self.length(meters):.{precision}f} {self._active_unit}"

    def format_area(self, square_meters, precision=2):
        return f"{self.area(square_meters):.{precision}f} {self._active_unit}²"
