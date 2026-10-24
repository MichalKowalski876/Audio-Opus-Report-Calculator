from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6 import QtCore, QtGui, QtWidgets

from GUI.style.theme_manager import ThemeManager


TutorialTarget = QtWidgets.QWidget | tuple[QtWidgets.QWidget, ...]


@dataclass(frozen=True)
class TutorialStep:
    target: TutorialTarget
    title: str
    text: str
    prepare: Callable[[], None] | None = None

    def targets(self) -> tuple[QtWidgets.QWidget, ...]:
        if isinstance(self.target, QtWidgets.QWidget):
            return (self.target,)
        return tuple(self.target)


class _TutorialHalo(QtWidgets.QWidget):
    """Subtelna, pulsująca obwódka wokół aktualnego elementu."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )
        self._phase = 0
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._animate)

    def showEvent(self, event):
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def _animate(self):
        self._phase = (self._phase + 1) % 40
        self.update()

    def paintEvent(self, event):
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        accent = QtGui.QColor(ThemeManager.get_current_accent())
        distance = abs(self._phase - 20) / 20
        glow_alpha = int(38 + (1 - distance) * 42)
        border_alpha = int(145 + (1 - distance) * 70)
        frame = self.rect().adjusted(6, 6, -6, -6)

        glow = QtGui.QColor(accent)
        glow.setAlpha(glow_alpha)
        painter.setPen(QtGui.QPen(glow, 9))
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(frame, 9, 9)

        border = QtGui.QColor(accent)
        border.setAlpha(border_alpha)
        painter.setPen(QtGui.QPen(border, 2))
        painter.drawRoundedRect(frame, 8, 8)


class _TutorialBubble(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tutorialBubble")
        self._expanded = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(5)

        self.step_label = QtWidgets.QLabel()
        self.step_label.setObjectName("tutorialStep")
        self.step_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.step_label)

        self.title_label = QtWidgets.QLabel()
        self.title_label.setObjectName("tutorialTitle")
        layout.addWidget(self.title_label)

        self.text_label = QtWidgets.QLabel()
        self.text_label.setObjectName("tutorialText")
        self.text_label.setWordWrap(True)
        self.text_label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        layout.addWidget(self.text_label)

    def set_step(self, index: int, total: int, step: TutorialStep):
        self._apply_theme()
        self.step_label.setText(f"Krok {index + 1}/{total}")
        self.title_label.setText(step.title)
        self.text_label.setText(step.text)
        self.set_expanded(False)

    def set_expanded(self, expanded: bool):
        self._expanded = bool(expanded)
        self.title_label.setVisible(self._expanded)
        self.text_label.setVisible(self._expanded)
        self.setFixedWidth(210 if self._expanded else 82)
        self.adjustSize()

    def _apply_theme(self):
        dark = ThemeManager.get_current_theme() == "dark"
        background = "#292929" if dark else "#ffffff"
        foreground = "#f3f3f3" if dark else "#202020"
        muted = "#b8b8b8" if dark else "#666666"
        accent = ThemeManager.get_current_accent()
        self.setStyleSheet(
            f"""
            QFrame#tutorialBubble {{
                background: {background};
                border: 1px solid {accent};
                border-radius: 9px;
            }}
            QLabel {{
                color: {foreground};
                background: transparent;
                border: none;
            }}
            QLabel#tutorialStep {{
                color: {accent};
                font-size: 10px;
                font-weight: 600;
            }}
            QLabel#tutorialTitle {{
                font-size: 13px;
                font-weight: 700;
            }}
            QLabel#tutorialText {{
                color: {muted};
                font-size: 11px;
            }}
            """
        )


class GuidedTutorial(QtCore.QObject):
    """Oprowadza po wskazanych elementach bez blokowania ich obsługi."""

    active_changed = QtCore.Signal(bool)
    step_changed = QtCore.Signal(int, int)

    def __init__(
        self,
        host: QtWidgets.QWidget,
        steps: list[TutorialStep] | None = None,
        parent=None,
    ):
        super().__init__(parent or host)
        self.host = host
        self.steps = list(steps or [])
        self._active = False
        self._index = -1
        self._watched_targets: tuple[QtWidgets.QWidget, ...] = ()
        self._displayed_target_groups: tuple[
            tuple[QtWidgets.QWidget, ...], ...
        ] = ()
        self._show_all_steps = False

        self.halos = [_TutorialHalo(host)]
        # Zachowana nazwa dla kodu i testów korzystających z jednego celu.
        self.halo = self.halos[0]
        self.bubbles = [_TutorialBubble(host)]
        self.bubble = self.bubbles[0]
        self._hide_overlays()
        self.host.installEventFilter(self)

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def current_index(self) -> int:
        return self._index

    @property
    def current_targets(self) -> tuple[QtWidgets.QWidget, ...]:
        if not self._active or not (0 <= self._index < len(self.steps)):
            return ()
        return self.steps[self._index].targets()

    @property
    def current_target(self) -> QtWidgets.QWidget | None:
        targets = self.current_targets
        return targets[0] if targets else None

    def set_steps(
        self,
        steps: list[TutorialStep],
        index: int = 0,
        show_all: bool = False,
    ):
        """Podmienia sekwencję dla widoku i ustawia sposób jej prezentacji."""
        self.steps = list(steps)
        self._show_all_steps = bool(show_all)
        if not self._active:
            self._index = -1
            return
        if not self.steps:
            self.pause()
            return
        normalized_index = max(0, min(index, len(self.steps) - 1))
        if self._show_all_steps:
            self._show_steps_together(normalized_index)
        else:
            self._show_step(normalized_index)

    def start(self, index: int = 0):
        if not self._active:
            self._active = True
            self.active_changed.emit(True)
        if not self.steps:
            self.pause()
            return
        normalized_index = max(0, min(index, len(self.steps) - 1))
        if self._show_all_steps:
            self._show_steps_together(normalized_index)
        else:
            self._show_step(normalized_index)

    def stop(self):
        self._unwatch_targets()
        self._hide_overlays()
        self._index = -1
        if self._active:
            self._active = False
            self.active_changed.emit(False)

    def pause(self):
        """Chowa oznaczenia na widoku bez wyłączania całego tutoriala."""
        self._unwatch_targets()
        self._hide_overlays()
        self._index = -1

    def next(self):
        if (
            not self._active
            or self._show_all_steps
            or self._index >= len(self.steps) - 1
        ):
            return
        self._show_step(self._index + 1)

    def previous(self):
        if self._active and not self._show_all_steps and self._index > 0:
            self._show_step(self._index - 1)

    def show_step(self, index: int):
        if not self._active or not self.steps:
            return
        normalized_index = max(0, min(index, len(self.steps) - 1))
        if self._show_all_steps:
            self._show_steps_together(normalized_index)
        else:
            self._show_step(normalized_index)

    def _ensure_halos(self, count: int):
        while len(self.halos) < count:
            self.halos.append(_TutorialHalo(self.host))

    def _ensure_bubbles(self, count: int):
        while len(self.bubbles) < count:
            self.bubbles.append(_TutorialBubble(self.host))

    def _unwatch_targets(self):
        for target in self._watched_targets:
            target.removeEventFilter(self)
        self._watched_targets = ()
        self._displayed_target_groups = ()

    def _hide_overlays(self):
        for halo in self.halos:
            halo.hide()
        for bubble in self.bubbles:
            bubble.hide()

    def _watch_groups(
        self,
        groups: tuple[tuple[QtWidgets.QWidget, ...], ...],
    ):
        self._displayed_target_groups = groups
        unique_targets = tuple(dict.fromkeys(
            target for group in groups for target in group
        ))
        self._watched_targets = unique_targets
        for target in self._watched_targets:
            target.installEventFilter(self)

    def _show_step(self, index: int):
        self._unwatch_targets()
        self._hide_overlays()

        self._index = index
        step = self.steps[index]
        if step.prepare is not None:
            step.prepare()

        self._watch_groups((step.targets(),))
        self._ensure_halos(len(self._watched_targets))
        self._ensure_bubbles(1)
        self.bubbles[0].set_step(index, len(self.steps), step)
        self.step_changed.emit(index, len(self.steps))
        QtCore.QTimer.singleShot(0, self._position_overlays)

    def _show_steps_together(self, index: int):
        self._unwatch_targets()
        self._hide_overlays()
        self._index = index

        for step in self.steps:
            if step.prepare is not None:
                step.prepare()
        groups = tuple(step.targets() for step in self.steps)
        self._watch_groups(groups)
        self._ensure_halos(sum(len(group) for group in groups))
        self._ensure_bubbles(len(self.steps))
        for step_index, step in enumerate(self.steps):
            self.bubbles[step_index].set_step(
                step_index,
                len(self.steps),
                step,
            )
        self.step_changed.emit(index, len(self.steps))
        QtCore.QTimer.singleShot(0, self._position_overlays)

    def eventFilter(self, watched, event):
        if self._active and (
            watched is self.host or watched in self._watched_targets
        ):
            if watched in self._watched_targets:
                expanded = event.type() in {
                    QtCore.QEvent.Type.Enter,
                    QtCore.QEvent.Type.HoverEnter,
                }
                collapsed = event.type() in {
                    QtCore.QEvent.Type.Leave,
                    QtCore.QEvent.Type.HoverLeave,
                }
                if expanded or collapsed:
                    for group_index, targets in enumerate(
                        self._displayed_target_groups
                    ):
                        if watched in targets:
                            self.bubbles[group_index].set_expanded(expanded)
                    QtCore.QTimer.singleShot(0, self._position_overlays)
            if event.type() in {
                QtCore.QEvent.Type.Move,
                QtCore.QEvent.Type.Resize,
                QtCore.QEvent.Type.Show,
                QtCore.QEvent.Type.Hide,
                QtCore.QEvent.Type.LayoutRequest,
            }:
                QtCore.QTimer.singleShot(0, self._position_overlays)
        return super().eventFilter(watched, event)

    def _visible_target_rects(
        self,
        targets: tuple[QtWidgets.QWidget, ...],
    ) -> list[QtCore.QRect]:
        rects = []
        for target in targets:
            if not target.isVisibleTo(self.host):
                continue
            top_left = target.mapTo(self.host, QtCore.QPoint(0, 0))
            rects.append(QtCore.QRect(top_left, target.size()))
        return rects

    @staticmethod
    def _combined_rect(rects: list[QtCore.QRect]) -> QtCore.QRect:
        combined = QtCore.QRect(rects[0])
        for rect in rects[1:]:
            combined = combined.united(rect)
        return combined

    @staticmethod
    def _bubble_position(
        target_rect: QtCore.QRect,
        bubble_size: QtCore.QSize,
        available: QtCore.QRect,
        occupied: list[QtCore.QRect],
    ) -> QtCore.QPoint:
        gap = 14
        candidates = (
            QtCore.QPoint(
                target_rect.center().x() - bubble_size.width() // 2,
                target_rect.bottom() + gap,
            ),
            QtCore.QPoint(
                target_rect.center().x() - bubble_size.width() // 2,
                target_rect.top() - bubble_size.height() - gap,
            ),
            QtCore.QPoint(
                target_rect.left() - bubble_size.width() - gap,
                target_rect.center().y() - bubble_size.height() // 2,
            ),
            QtCore.QPoint(
                target_rect.right() + gap,
                target_rect.center().y() - bubble_size.height() // 2,
            ),
        )
        position = candidates[0]
        for candidate in candidates:
            candidate_rect = QtCore.QRect(candidate, bubble_size)
            if (
                available.contains(candidate_rect)
                and not any(candidate_rect.intersects(rect) for rect in occupied)
            ):
                position = candidate
                break

        maximum_x = max(available.left(), available.right() - bubble_size.width() + 1)
        maximum_y = max(available.top(), available.bottom() - bubble_size.height() + 1)
        position.setX(min(max(position.x(), available.left()), maximum_x))
        position.setY(min(max(position.y(), available.top()), maximum_y))
        return position

    def _position_overlays(self):
        if not self._active:
            return
        rect_groups = [
            self._visible_target_rects(targets)
            for targets in self._displayed_target_groups
        ]
        if not any(rect_groups):
            self._hide_overlays()
            return

        visible_rects = [rect for group in rect_groups for rect in group]
        self._ensure_halos(len(visible_rects))
        for index, halo in enumerate(self.halos):
            if index >= len(visible_rects):
                halo.hide()
                continue
            halo.setGeometry(visible_rects[index].adjusted(-12, -12, 12, 12))
            halo.show()
            halo.raise_()

        available = self.host.rect().adjusted(10, 10, -10, -10)
        occupied: list[QtCore.QRect] = []
        for group_index, target_rects in enumerate(rect_groups):
            bubble = self.bubbles[group_index]
            if not target_rects:
                bubble.hide()
                continue
            bubble.show()
            bubble.adjustSize()
            position = self._bubble_position(
                self._combined_rect(target_rects),
                bubble.size(),
                available,
                occupied,
            )
            bubble.move(position)
            occupied.append(QtCore.QRect(position, bubble.size()))

        for bubble in self.bubbles[len(rect_groups):]:
            bubble.hide()
        for halo in self.halos:
            if halo.isVisible():
                halo.raise_()
        for bubble in self.bubbles:
            if bubble.isVisible():
                bubble.raise_()
