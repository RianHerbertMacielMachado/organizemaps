"""
FiveM Map Organizer - Step Panel Widget.

Reusable step panel with title, number, and content area.
"""

from __future__ import annotations

from typing import Optional

import customtkinter as ctk


class StepPanel(ctk.CTkFrame):
    """A numbered step panel with title and content area."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        step_number: int,
        title: str,
        accent_color: str = '#00d4ff',
        **kwargs
    ) -> None:
        """
        Initialize StepPanel.

        Args:
            master: Parent widget.
            step_number: Step number to display.
            title: Step title text.
            accent_color: Accent color for the title.
        """
        super().__init__(
            master,
            fg_color='#16213e',
            border_color='#0f3460',
            border_width=1,
            corner_radius=8,
            **kwargs
        )

        self._accent_color = accent_color

        # Header with step number and title
        header = ctk.CTkFrame(self, fg_color='transparent', height=36)
        header.pack(fill='x', padx=12, pady=(10, 5))
        header.pack_propagate(False)

        self._title_label = ctk.CTkLabel(
            header,
            text=f"Step {step_number} - {title}",
            font=ctk.CTkFont(family='Segoe UI', size=13, weight='bold'),
            text_color=accent_color,
            anchor='w'
        )
        self._title_label.pack(side='left', fill='x')

        # Content frame
        self.content = ctk.CTkFrame(self, fg_color='transparent')
        self.content.pack(fill='both', expand=True, padx=12, pady=(0, 10))

    def update_accent(self, color: str) -> None:
        """Update the accent color of the title."""
        self._accent_color = color
        self._title_label.configure(text_color=color)
