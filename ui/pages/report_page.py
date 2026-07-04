"""
FiveM Map Organizer - Report Page.

Displays the last organization report.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import customtkinter as ctk

from utils.helpers import open_file_in_editor


class ReportPage(ctk.CTkFrame):
    """Report page showing the last organization report."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        config: object,
        **kwargs
    ) -> None:
        """
        Initialize ReportPage.

        Args:
            master: Parent widget.
            config: Application configuration object.
        """
        super().__init__(master, fg_color='#1a1a2e', **kwargs)

        self._config = config
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the report page UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=20, pady=(20, 10))

        ctk.CTkLabel(
            header,
            text="Last Report",
            font=ctk.CTkFont(family='Segoe UI', size=18, weight='bold'),
            text_color='#ffffff'
        ).pack(side='left')

        ctk.CTkLabel(
            header,
            text="View the most recent organization report",
            font=ctk.CTkFont(family='Segoe UI', size=10),
            text_color='#888888'
        ).pack(side='left', padx=(15, 0))

        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color='transparent', height=40)
        toolbar.pack(fill='x', padx=20, pady=(0, 10))
        toolbar.pack_propagate(False)

        self._refresh_btn = ctk.CTkButton(
            toolbar,
            text="🔄 Refresh",
            font=ctk.CTkFont(family='Segoe UI', size=10),
            fg_color='#0f3460',
            hover_color='#1a3a5c',
            width=100,
            height=30,
            corner_radius=4,
            command=self.load_report
        )
        self._refresh_btn.pack(side='left', padx=(0, 8))

        self._open_btn = ctk.CTkButton(
            toolbar,
            text="📝 Open in Editor",
            font=ctk.CTkFont(family='Segoe UI', size=10),
            fg_color='#16213e',
            hover_color='#1a3a5c',
            border_color='#444444',
            border_width=1,
            width=130,
            height=30,
            corner_radius=4,
            command=self._open_in_editor
        )
        self._open_btn.pack(side='left')

        # Report text area
        self._textbox = ctk.CTkTextbox(
            self,
            fg_color='#0d1b2a',
            text_color='#ffffff',
            font=ctk.CTkFont(family='Consolas', size=10),
            corner_radius=8,
            border_color='#0f3460',
            border_width=1,
            state='disabled'
        )
        self._textbox.pack(fill='both', expand=True, padx=20, pady=(0, 20))

        # Load initial report
        self.load_report()

    def load_report(self) -> None:
        """Load and display the last report."""
        report_path = self._config.last_report_path

        self._textbox.configure(state='normal')
        self._textbox.delete('1.0', 'end')

        if not report_path or not Path(report_path).exists():
            self._textbox.insert('1.0', "No report found.\n\n"
                                        "Run 'Organize Maps' to generate a report.")
            self._textbox.configure(state='disabled')
            return

        try:
            content = Path(report_path).read_text(encoding='utf-8')
            self._textbox.insert('1.0', content)
        except (OSError, IOError) as e:
            self._textbox.insert('1.0', f"Error reading report: {e}")

        self._textbox.configure(state='disabled')

    def _open_in_editor(self) -> None:
        """Open the report file in system editor."""
        report_path = self._config.last_report_path
        if report_path and Path(report_path).exists():
            open_file_in_editor(Path(report_path))

    def update_accent(self, color: str) -> None:
        """Update accent color."""
        pass
