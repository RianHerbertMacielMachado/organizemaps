"""
FiveM Map Organizer - Settings Page.

Application settings with persistence.
"""

from __future__ import annotations

from typing import Optional

import customtkinter as ctk


class SettingsPage(ctk.CTkScrollableFrame):
    """Settings page with operation, duplicate, scan, and theme options."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        config: object,
        on_accent_change: Optional[callable] = None,
        on_save: Optional[callable] = None,
        **kwargs
    ) -> None:
        """
        Initialize SettingsPage.

        Args:
            master: Parent widget.
            config: Application configuration object.
            on_accent_change: Callback when accent color changes.
            on_save: Callback when settings are saved.
        """
        super().__init__(master, fg_color='#1a1a2e', **kwargs)

        self._config = config
        self._on_accent_change = on_accent_change
        self._on_save = on_save

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the settings page UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=20, pady=(20, 15))

        ctk.CTkLabel(
            header,
            text="Settings",
            font=ctk.CTkFont(family='Segoe UI', size=18, weight='bold'),
            text_color='#ffffff'
        ).pack(side='left')

        ctk.CTkLabel(
            header,
            text="Configure application behavior",
            font=ctk.CTkFont(family='Segoe UI', size=10),
            text_color='#888888'
        ).pack(side='left', padx=(15, 0))

        # === Operation Section ===
        self._add_section_header("Operation")

        op_frame = ctk.CTkFrame(self, fg_color='#16213e', corner_radius=8)
        op_frame.pack(fill='x', padx=20, pady=(0, 12))

        ctk.CTkLabel(
            op_frame,
            text="File operation mode:",
            font=ctk.CTkFont(family='Segoe UI', size=10),
            text_color='#cccccc'
        ).pack(anchor='w', padx=15, pady=(10, 5))

        self._operation_var = ctk.StringVar(value=self._config.operation)

        radio_frame = ctk.CTkFrame(op_frame, fg_color='transparent')
        radio_frame.pack(fill='x', padx=15, pady=(0, 10))

        ctk.CTkRadioButton(
            radio_frame,
            text="Copy (keep originals)",
            variable=self._operation_var,
            value='copy',
            font=ctk.CTkFont(family='Segoe UI', size=10),
            fg_color='#00d4ff',
            hover_color='#0099aa'
        ).pack(side='left', padx=(0, 20))

        ctk.CTkRadioButton(
            radio_frame,
            text="Move (delete originals)",
            variable=self._operation_var,
            value='move',
            font=ctk.CTkFont(family='Segoe UI', size=10),
            fg_color='#00d4ff',
            hover_color='#0099aa'
        ).pack(side='left')

        # === Duplicates Section ===
        self._add_section_header("Duplicates")

        dup_frame = ctk.CTkFrame(self, fg_color='#16213e', corner_radius=8)
        dup_frame.pack(fill='x', padx=20, pady=(0, 12))

        ctk.CTkLabel(
            dup_frame,
            text="When a file already exists at destination:",
            font=ctk.CTkFont(family='Segoe UI', size=10),
            text_color='#cccccc'
        ).pack(anchor='w', padx=15, pady=(10, 5))

        self._duplicate_var = ctk.StringVar(value=self._config.on_duplicate)

        ctk.CTkOptionMenu(
            dup_frame,
            variable=self._duplicate_var,
            values=['skip', 'overwrite', 'rename'],
            font=ctk.CTkFont(family='Segoe UI', size=10),
            fg_color='#0d1b2a',
            button_color='#0f3460',
            button_hover_color='#1a3a5c',
            dropdown_fg_color='#16213e',
            dropdown_hover_color='#0f3460',
            width=150
        ).pack(anchor='w', padx=15, pady=(0, 10))

        # === Scan Section ===
        self._add_section_header("Scan")

        scan_frame = ctk.CTkFrame(self, fg_color='#16213e', corner_radius=8)
        scan_frame.pack(fill='x', padx=20, pady=(0, 12))

        self._subfolders_var = ctk.BooleanVar(value=self._config.include_subfolders)

        ctk.CTkCheckBox(
            scan_frame,
            text="Include subfolders (recursive scan)",
            variable=self._subfolders_var,
            font=ctk.CTkFont(family='Segoe UI', size=10),
            fg_color='#00d4ff',
            hover_color='#0099aa',
            checkmark_color='#000000'
        ).pack(anchor='w', padx=15, pady=10)

        # === Reports Section ===
        self._add_section_header("Reports")

        report_frame = ctk.CTkFrame(self, fg_color='#16213e', corner_radius=8)
        report_frame.pack(fill='x', padx=20, pady=(0, 12))

        self._auto_report_var = ctk.BooleanVar(value=self._config.auto_report)

        ctk.CTkCheckBox(
            report_frame,
            text="Generate report automatically after organization",
            variable=self._auto_report_var,
            font=ctk.CTkFont(family='Segoe UI', size=10),
            fg_color='#00d4ff',
            hover_color='#0099aa',
            checkmark_color='#000000'
        ).pack(anchor='w', padx=15, pady=10)

        # === Theme Section ===
        self._add_section_header("Theme")

        theme_frame = ctk.CTkFrame(self, fg_color='#16213e', corner_radius=8)
        theme_frame.pack(fill='x', padx=20, pady=(0, 12))

        ctk.CTkLabel(
            theme_frame,
            text="Accent color:",
            font=ctk.CTkFont(family='Segoe UI', size=10),
            text_color='#cccccc'
        ).pack(anchor='w', padx=15, pady=(10, 5))

        colors_frame = ctk.CTkFrame(theme_frame, fg_color='transparent')
        colors_frame.pack(fill='x', padx=15, pady=(0, 10))

        self._color_buttons: list[ctk.CTkButton] = []
        colors = [
            ('#00d4ff', 'Cyan'),
            ('#00ff88', 'Green'),
            ('#ff00ff', 'Magenta')
        ]

        for color, name in colors:
            btn = ctk.CTkButton(
                colors_frame,
                text=name,
                font=ctk.CTkFont(family='Segoe UI', size=10),
                fg_color=color,
                hover_color=color,
                text_color='#000000',
                width=80,
                height=30,
                corner_radius=4,
                command=lambda c=color: self._set_accent(c)
            )
            btn.pack(side='left', padx=(0, 8))
            self._color_buttons.append(btn)

        # === Action Buttons ===
        btn_frame = ctk.CTkFrame(self, fg_color='transparent')
        btn_frame.pack(fill='x', padx=20, pady=(15, 20))

        ctk.CTkButton(
            btn_frame,
            text="💾 Save Settings",
            font=ctk.CTkFont(family='Segoe UI', size=11, weight='bold'),
            fg_color='#00d4ff',
            hover_color='#00b8d4',
            text_color='#000000',
            width=140,
            height=36,
            corner_radius=6,
            command=self._save_settings
        ).pack(side='left', padx=(0, 10))

        ctk.CTkButton(
            btn_frame,
            text="🔄 Reset Defaults",
            font=ctk.CTkFont(family='Segoe UI', size=10),
            fg_color='#16213e',
            hover_color='#1a3a5c',
            border_color='#444444',
            border_width=1,
            width=130,
            height=36,
            corner_radius=6,
            command=self._reset_defaults
        ).pack(side='left')

        self._save_status = ctk.CTkLabel(
            btn_frame,
            text="",
            font=ctk.CTkFont(family='Segoe UI', size=9),
            text_color='#00ff88'
        )
        self._save_status.pack(side='left', padx=(15, 0))

    def _add_section_header(self, title: str) -> None:
        """Add a section header label."""
        ctk.CTkLabel(
            self,
            text=title.upper(),
            font=ctk.CTkFont(family='Segoe UI', size=9, weight='bold'),
            text_color='#666666'
        ).pack(anchor='w', padx=20, pady=(5, 3))

    def _set_accent(self, color: str) -> None:
        """Set the accent color and notify parent."""
        self._config.accent_color = color
        if self._on_accent_change:
            self._on_accent_change(color)

    def _save_settings(self) -> None:
        """Save current settings to config."""
        self._config.operation = self._operation_var.get()
        self._config.on_duplicate = self._duplicate_var.get()
        self._config.include_subfolders = self._subfolders_var.get()
        self._config.auto_report = self._auto_report_var.get()

        if self._on_save:
            self._on_save()

        self._save_status.configure(text="✓ Settings saved!")
        self.after(3000, lambda: self._save_status.configure(text=""))

    def _reset_defaults(self) -> None:
        """Reset all settings to defaults."""
        self._operation_var.set('copy')
        self._duplicate_var.set('skip')
        self._subfolders_var.set(False)
        self._auto_report_var.set(True)
        self._set_accent('#00d4ff')

        self._config.operation = 'copy'
        self._config.on_duplicate = 'skip'
        self._config.include_subfolders = False
        self._config.auto_report = True
        self._config.accent_color = '#00d4ff'

        if self._on_save:
            self._on_save()

        self._save_status.configure(text="✓ Defaults restored!")
        self.after(3000, lambda: self._save_status.configure(text=""))

    def update_accent(self, color: str) -> None:
        """Update accent color in settings UI."""
        pass
