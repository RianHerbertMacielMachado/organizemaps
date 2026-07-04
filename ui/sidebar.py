"""
FiveM Map Organizer - Sidebar Widget.

Navigation sidebar with page selection buttons.
"""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk


class Sidebar(ctk.CTkFrame):
    """Navigation sidebar with styled buttons."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_navigate: Callable[[str], None],
        accent_color: str = '#00d4ff',
        **kwargs
    ) -> None:
        """
        Initialize Sidebar.

        Args:
            master: Parent widget.
            on_navigate: Callback when a navigation button is clicked.
            accent_color: Active button accent color.
        """
        super().__init__(master, fg_color='#16213e', width=200, corner_radius=0, **kwargs)
        self.pack_propagate(False)

        self._on_navigate = on_navigate
        self._accent_color = accent_color
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._active_page: str = 'organize'
        self._indicators: dict[str, ctk.CTkFrame] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        """Build sidebar UI."""
        # Logo/title area
        title_frame = ctk.CTkFrame(self, fg_color='transparent', height=60)
        title_frame.pack(fill='x', pady=(15, 20))
        title_frame.pack_propagate(False)

        ctk.CTkLabel(
            title_frame,
            text="🗺️",
            font=ctk.CTkFont(size=24)
        ).pack(side='left', padx=(15, 8))

        title_text = ctk.CTkFrame(title_frame, fg_color='transparent')
        title_text.pack(side='left')

        ctk.CTkLabel(
            title_text,
            text="FiveM Map",
            font=ctk.CTkFont(family='Segoe UI', size=12, weight='bold'),
            text_color='#ffffff'
        ).pack(anchor='w')

        ctk.CTkLabel(
            title_text,
            text="Organizer",
            font=ctk.CTkFont(family='Segoe UI', size=10),
            text_color='#888888'
        ).pack(anchor='w')

        # Navigation buttons
        nav_items = [
            ('organize', '📁', 'Organize Maps'),
            ('preview', '👁', 'Preview Mode'),
            ('settings', '⚙', 'Settings'),
            ('report', '📄', 'View Last Report'),
        ]

        for page_id, icon, label in nav_items:
            self._create_nav_button(page_id, icon, label)

        # Spacer
        spacer = ctk.CTkFrame(self, fg_color='transparent')
        spacer.pack(fill='both', expand=True)

        # Exit button at bottom
        self._create_nav_button('exit', '✕', 'Exit', is_exit=True)

        # Set initial active
        self._set_active('organize')

    def _create_nav_button(self, page_id: str, icon: str, label: str,
                           is_exit: bool = False) -> None:
        """Create a navigation button with indicator."""
        btn_container = ctk.CTkFrame(self, fg_color='transparent', height=40)
        btn_container.pack(fill='x', pady=1)
        btn_container.pack_propagate(False)

        # Left indicator bar
        indicator = ctk.CTkFrame(
            btn_container,
            fg_color='transparent',
            width=3,
            corner_radius=0
        )
        indicator.pack(side='left', fill='y')
        self._indicators[page_id] = indicator

        # Button
        btn = ctk.CTkButton(
            btn_container,
            text=f" {icon}  {label}",
            font=ctk.CTkFont(family='Segoe UI', size=10),
            fg_color='transparent',
            hover_color='#1a3a5c',
            text_color='#ffffff',
            anchor='w',
            height=38,
            corner_radius=0,
            command=lambda pid=page_id: self._on_click(pid)
        )
        btn.pack(side='left', fill='both', expand=True)

        self._buttons[page_id] = btn

    def _on_click(self, page_id: str) -> None:
        """Handle button click."""
        if page_id == 'exit':
            self._on_navigate('exit')
            return

        self._set_active(page_id)
        self._on_navigate(page_id)

    def _set_active(self, page_id: str) -> None:
        """Set the active button state."""
        # Reset all buttons
        for pid, btn in self._buttons.items():
            if pid == 'exit':
                continue
            btn.configure(fg_color='transparent')
            self._indicators[pid].configure(fg_color='transparent')

        # Set active
        if page_id in self._buttons and page_id != 'exit':
            self._active_page = page_id
            self._buttons[page_id].configure(fg_color='#0f3460')
            self._indicators[page_id].configure(fg_color=self._accent_color)

    def update_accent(self, color: str) -> None:
        """Update accent color."""
        self._accent_color = color
        if self._active_page in self._indicators:
            self._indicators[self._active_page].configure(fg_color=color)
