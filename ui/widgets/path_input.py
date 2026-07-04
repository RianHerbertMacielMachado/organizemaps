"""
FiveM Map Organizer - Path Input Widget.

Input field with Browse button and real-time validation.
"""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog
from typing import Callable, Optional

import customtkinter as ctk


class PathInput(ctk.CTkFrame):
    """Path input with folder icon, validation indicator, and browse button."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        placeholder: str = "Select folder...",
        validate_func: Optional[Callable[[str], tuple[bool, str]]] = None,
        on_change: Optional[Callable[[str], None]] = None,
        initial_value: str = '',
        **kwargs
    ) -> None:
        """
        Initialize PathInput.

        Args:
            master: Parent widget.
            placeholder: Placeholder text for empty input.
            validate_func: Validation function returns (is_valid, error_msg).
            on_change: Callback when path value changes.
            initial_value: Initial path value.
        """
        super().__init__(master, fg_color='transparent', height=36, **kwargs)
        self.pack_propagate(False)

        self._validate_func = validate_func
        self._on_change = on_change
        self._debounce_id: Optional[str] = None
        self._is_valid: bool = False

        # Folder icon
        self._icon_label = ctk.CTkLabel(
            self,
            text="📁",
            font=ctk.CTkFont(size=14),
            width=28
        )
        self._icon_label.pack(side='left', padx=(0, 4))

        # Entry field
        self._entry = ctk.CTkEntry(
            self,
            placeholder_text=placeholder,
            fg_color='#0d1b2a',
            border_color='#0f3460',
            text_color='#ffffff',
            placeholder_text_color='#666666',
            font=ctk.CTkFont(family='Segoe UI', size=10),
            height=32,
            corner_radius=4
        )
        self._entry.pack(side='left', fill='x', expand=True, padx=(0, 6))

        if initial_value:
            self._entry.insert(0, initial_value)

        # Validation indicator
        self._status_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=14),
            width=24
        )
        self._status_label.pack(side='left', padx=(0, 6))

        # Browse button
        self._browse_btn = ctk.CTkButton(
            self,
            text="Browse...",
            font=ctk.CTkFont(family='Segoe UI', size=10),
            fg_color='#0f3460',
            hover_color='#1a3a5c',
            width=70,
            height=30,
            corner_radius=4,
            command=self._browse
        )
        self._browse_btn.pack(side='right')

        # Error label (below)
        self._error_frame = ctk.CTkFrame(master, fg_color='transparent', height=18)
        self._error_label = ctk.CTkLabel(
            self._error_frame,
            text="",
            font=ctk.CTkFont(family='Segoe UI', size=9),
            text_color='#ff4444',
            anchor='w'
        )
        self._error_label.pack(side='left', padx=(32, 0))

        # Bind key events for real-time validation
        self._entry.bind('<KeyRelease>', self._on_key_release)

        # Initial validation
        if initial_value:
            self._validate()

    def _browse(self) -> None:
        """Open folder selection dialog."""
        folder = filedialog.askdirectory(
            title="Select Folder",
            initialdir=self.get_path() or None
        )
        if folder:
            self._entry.delete(0, 'end')
            self._entry.insert(0, folder)
            self._validate()

    def _on_key_release(self, event=None) -> None:
        """Handle key release with debounce."""
        if self._debounce_id:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(500, self._validate)

    def _validate(self) -> None:
        """Validate current path value."""
        path_str = self._entry.get().strip()

        if not path_str:
            self._status_label.configure(text="")
            self._error_label.configure(text="")
            self._is_valid = False
            self._error_frame.pack_forget()
            return

        if self._validate_func:
            is_valid, error_msg = self._validate_func(path_str)
            self._is_valid = is_valid

            if is_valid:
                self._status_label.configure(text="✓", text_color='#00ff88')
                self._entry.configure(border_color='#00ff88')
                self._error_label.configure(text="")
                self._error_frame.pack_forget()
            else:
                self._status_label.configure(text="✗", text_color='#ff4444')
                self._entry.configure(border_color='#ff4444')
                self._error_label.configure(text=error_msg)
                self._error_frame.pack(fill='x', pady=(0, 2))
        else:
            self._is_valid = True
            self._status_label.configure(text="✓", text_color='#00ff88')
            self._entry.configure(border_color='#00ff88')

        if self._on_change:
            self._on_change(path_str)

    def get_path(self) -> str:
        """Get current path value."""
        return self._entry.get().strip()

    def set_path(self, path: str) -> None:
        """Set path value programmatically."""
        self._entry.delete(0, 'end')
        self._entry.insert(0, path)
        self._validate()

    def is_valid(self) -> bool:
        """Check if current path is valid."""
        return self._is_valid
