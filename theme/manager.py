from PySide6.QtCore import QObject, Signal

from cad_core import THEMES


class ThemeManager(QObject):
    """Central runtime theme state.

    Widgets subscribe to ``theme_changed`` and repaint themselves from the
    current palette, so switching themes never requires rebuilding the UI tree.
    """

    theme_changed = Signal(str, dict)

    def __init__(self, initial_theme="شب مهندسی", themes=None, parent=None):
        super().__init__(parent)
        self._themes = themes or THEMES
        self._active_name = initial_theme if initial_theme in self._themes else next(iter(self._themes))

    @property
    def names(self):
        return list(self._themes)

    @property
    def active_name(self):
        return self._active_name

    @property
    def active_theme(self):
        return self._themes[self._active_name]

    def set_theme(self, name):
        if name not in self._themes:
            return False
        if name == self._active_name:
            self.theme_changed.emit(self._active_name, self.active_theme)
            return True
        self._active_name = name
        self.theme_changed.emit(self._active_name, self.active_theme)
        return True
