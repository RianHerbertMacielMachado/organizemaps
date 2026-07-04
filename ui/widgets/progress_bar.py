"""
FiveM Map Organizer - Progress Bar Widget.

Custom progress bar with percentage, spinner, and timer.
"""

from __future__ import annotations

import math
import time
from typing import Optional

import customtkinter as ctk


class ProgressBar(ctk.CTkFrame):
    """Custom progress bar with percentage display, spinner, and timer."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        accent_color: str = '#00d4ff',
        **kwargs
    ) -> None:
        """
        Initialize ProgressBar.

        Args:
            master: Parent widget.
            accent_color: Color for the progress fill.
        """
        super().__init__(master, fg_color='transparent', **kwargs)

        self._accent_color = accent_color
        self._progress: float = 0.0
        self._is_running: bool = False
        self._start_time: float = 0.0
        self._spinner_angle: float = 0.0
        self._animation_id: Optional[str] = None

        # Top row: spinner + progress bar + percentage
        top_frame = ctk.CTkFrame(self, fg_color='transparent', height=40)
        top_frame.pack(fill='x', pady=(0, 6))
        top_frame.pack_propagate(False)

        # Spinner canvas
        self._spinner_canvas = ctk.CTkCanvas(
            top_frame,
            width=30,
            height=30,
            bg='#16213e',
            highlightthickness=0
        )
        self._spinner_canvas.pack(side='left', padx=(0, 10))

        # Progress bar container
        bar_frame = ctk.CTkFrame(top_frame, fg_color='#0d1b2a', height=26, corner_radius=13)
        bar_frame.pack(side='left', fill='x', expand=True, padx=(0, 10))
        bar_frame.pack_propagate(False)

        # Progress fill (using canvas for smooth rendering)
        self._bar_canvas = ctk.CTkCanvas(
            bar_frame,
            height=22,
            bg='#0d1b2a',
            highlightthickness=0
        )
        self._bar_canvas.pack(fill='both', expand=True, padx=2, pady=2)

        # Percentage label
        self._percent_label = ctk.CTkLabel(
            top_frame,
            text="0%",
            font=ctk.CTkFont(family='Segoe UI', size=12, weight='bold'),
            text_color=accent_color,
            width=45
        )
        self._percent_label.pack(side='right')

        # Bottom row: status label + timer
        bottom_frame = ctk.CTkFrame(self, fg_color='transparent', height=20)
        bottom_frame.pack(fill='x')
        bottom_frame.pack_propagate(False)

        self._status_label = ctk.CTkLabel(
            bottom_frame,
            text="Ready",
            font=ctk.CTkFont(family='Segoe UI', size=9),
            text_color='#888888',
            anchor='w'
        )
        self._status_label.pack(side='left')

        self._timer_label = ctk.CTkLabel(
            bottom_frame,
            text="00:00:00",
            font=ctk.CTkFont(family='Segoe UI', size=9),
            text_color='#888888',
            anchor='e'
        )
        self._timer_label.pack(side='right')

        # Draw initial state
        self._bar_canvas.bind('<Configure>', self._draw_bar)

    def _draw_bar(self, event=None) -> None:
        """Draw the progress bar fill."""
        self._bar_canvas.delete('all')
        width = self._bar_canvas.winfo_width()
        height = self._bar_canvas.winfo_height()

        if width <= 1:
            return

        # Background
        self._bar_canvas.create_rectangle(
            0, 0, width, height,
            fill='#0d1b2a', outline=''
        )

        # Fill
        fill_width = int(width * self._progress)
        if fill_width > 0:
            self._bar_canvas.create_rectangle(
                0, 0, fill_width, height,
                fill=self._accent_color, outline=''
            )

            # Percentage text centered on bar
            percent_text = f"{int(self._progress * 100)}%"
            self._bar_canvas.create_text(
                fill_width // 2, height // 2,
                text=percent_text,
                fill='#000000',
                font=('Segoe UI', 9, 'bold')
            )

    def _draw_spinner(self) -> None:
        """Draw the animated spinner."""
        self._spinner_canvas.delete('all')
        cx, cy, r = 15, 15, 10

        # Draw arc
        start = self._spinner_angle
        self._spinner_canvas.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            start=start, extent=270,
            outline=self._accent_color, width=2,
            style='arc'
        )

    def _animate(self) -> None:
        """Animation loop for spinner and timer."""
        if not self._is_running:
            return

        # Update spinner
        self._spinner_angle = (self._spinner_angle + 10) % 360
        self._draw_spinner()

        # Update timer
        elapsed = time.time() - self._start_time
        hours = int(elapsed) // 3600
        minutes = (int(elapsed) % 3600) // 60
        seconds = int(elapsed) % 60
        self._timer_label.configure(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")

        self._animation_id = self.after(50, self._animate)

    def start(self) -> None:
        """Start the progress animation and timer."""
        self._is_running = True
        self._start_time = time.time()
        self._progress = 0.0
        self._draw_bar()
        self._animate()

    def stop(self) -> None:
        """Stop the progress animation."""
        self._is_running = False
        if self._animation_id:
            self.after_cancel(self._animation_id)
            self._animation_id = None

    def set_progress(self, value: float, status: str = "") -> None:
        """
        Set progress value.

        Args:
            value: Progress value between 0.0 and 1.0.
            status: Optional status message.
        """
        self._progress = max(0.0, min(1.0, value))
        self._percent_label.configure(text=f"{int(self._progress * 100)}%")
        self._draw_bar()

        if status:
            self._status_label.configure(text=status)

    def set_status(self, text: str) -> None:
        """Set status label text."""
        self._status_label.configure(text=text)

    def reset(self) -> None:
        """Reset progress bar to initial state."""
        self.stop()
        self._progress = 0.0
        self._percent_label.configure(text="0%")
        self._status_label.configure(text="Ready")
        self._timer_label.configure(text="00:00:00")
        self._draw_bar()
        self._spinner_canvas.delete('all')

    def update_accent(self, color: str) -> None:
        """Update accent color."""
        self._accent_color = color
        self._percent_label.configure(text_color=color)
        self._draw_bar()
