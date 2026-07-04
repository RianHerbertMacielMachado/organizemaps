"""
FiveM Map Organizer - Main Application Window.

Root CTk application with sidebar navigation and page management.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from ui.pages.organize_page import OrganizePage
from ui.pages.preview_page import PreviewPage
from ui.pages.report_page import ReportPage
from ui.pages.settings_page import SettingsPage
from ui.sidebar import Sidebar
from utils.helpers import get_config_path


@dataclass
class Config:
    """Application configuration with persistence."""

    operation: str = 'copy'
    on_duplicate: str = 'skip'
    include_subfolders: bool = False
    auto_report: bool = True
    accent_color: str = '#00d4ff'
    last_source: str = ''
    last_dest: str = ''
    last_report_path: str = ''

    def save(self, path: Optional[Path] = None) -> None:
        """
        Save configuration to JSON file.

        Args:
            path: Path to save config. Uses default if None.
        """
        if path is None:
            path = get_config_path()

        try:
            path.write_text(
                json.dumps(asdict(self), indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
        except (OSError, IOError):
            pass

    @classmethod
    def load(cls, path: Optional[Path] = None) -> 'Config':
        """
        Load configuration from JSON file.

        Args:
            path: Path to load config from. Uses default if None.

        Returns:
            Config instance with loaded values.
        """
        if path is None:
            path = get_config_path()

        try:
            if path.exists():
                data = json.loads(path.read_text(encoding='utf-8'))
                # Filter only known fields
                known_fields = {f.name for f in cls.__dataclass_fields__.values()}
                filtered = {k: v for k, v in data.items() if k in known_fields}
                return cls(**filtered)
        except (OSError, IOError, json.JSONDecodeError, TypeError):
            pass

        return cls()


class FiveMMapOrganizerApp(ctk.CTk):
    """Main application window for FiveM Map Organizer."""

    def __init__(self) -> None:
        """Initialize the application."""
        super().__init__()

        # Load configuration
        self._config = Config.load()

        # Window setup
        self.title("FiveM Map Organizer v1.0.0")
        self.geometry("1000x650")
        self.minsize(1000, 650)
        self.configure(fg_color='#1a1a2e')

        # Set appearance
        ctk.set_appearance_mode('dark')
        ctk.set_default_color_theme('dark-blue')

        # Build UI
        self._build_ui()

        # Bind keyboard shortcuts
        self.bind('<F5>', self._on_f5)
        self.bind('<Control-s>', self._on_ctrl_s)
        self.bind('<Control-q>', self._on_ctrl_q)

        # Protocol for window close
        self.protocol("WM_DELETE_WINDOW", self._on_exit)

    def _build_ui(self) -> None:
        """Build the main application UI."""
        # Main container
        main_container = ctk.CTkFrame(self, fg_color='#1a1a2e', corner_radius=0)
        main_container.pack(fill='both', expand=True)

        # Sidebar
        self._sidebar = Sidebar(
            main_container,
            on_navigate=self._navigate,
            accent_color=self._config.accent_color
        )
        self._sidebar.pack(side='left', fill='y')

        # Content area
        content_area = ctk.CTkFrame(main_container, fg_color='#1a1a2e', corner_radius=0)
        content_area.pack(side='left', fill='both', expand=True)

        # Pages container
        self._pages_container = ctk.CTkFrame(content_area, fg_color='#1a1a2e', corner_radius=0)
        self._pages_container.pack(fill='both', expand=True)

        # Create pages
        self._pages: dict[str, ctk.CTkFrame] = {}

        self._pages['organize'] = OrganizePage(
            self._pages_container,
            config=self._config,
            on_report_generated=self._on_report_generated
        )

        self._pages['preview'] = PreviewPage(
            self._pages_container,
            config=self._config
        )

        self._pages['settings'] = SettingsPage(
            self._pages_container,
            config=self._config,
            on_accent_change=self._on_accent_change,
            on_save=self._save_config
        )

        self._pages['report'] = ReportPage(
            self._pages_container,
            config=self._config
        )

        # Status bar
        self._status_bar = ctk.CTkFrame(
            content_area,
            fg_color='#0d1b2a',
            height=28,
            corner_radius=0
        )
        self._status_bar.pack(fill='x', side='bottom')
        self._status_bar.pack_propagate(False)

        # Status indicator
        self._status_indicator = ctk.CTkLabel(
            self._status_bar,
            text="● Ready",
            font=ctk.CTkFont(family='Segoe UI', size=8),
            text_color='#00ff88'
        )
        self._status_indicator.pack(side='left', padx=10)

        # File counter
        self._file_counter = ctk.CTkLabel(
            self._status_bar,
            text="",
            font=ctk.CTkFont(family='Segoe UI', size=8),
            text_color='#888888'
        )
        self._file_counter.pack(side='left', expand=True)

        # Shortcuts hint
        ctk.CTkLabel(
            self._status_bar,
            text="F5: Refresh | Ctrl+S: Save",
            font=ctk.CTkFont(family='Segoe UI', size=8),
            text_color='#888888'
        ).pack(side='right', padx=10)

        # Show initial page
        self._current_page: Optional[str] = None
        self._navigate('organize')

    def _navigate(self, page_id: str) -> None:
        """
        Navigate to a page.

        Args:
            page_id: ID of the page to show.
        """
        if page_id == 'exit':
            self._on_exit()
            return

        # Hide current page
        if self._current_page and self._current_page in self._pages:
            self._pages[self._current_page].pack_forget()

        # Show new page
        if page_id in self._pages:
            self._pages[page_id].pack(fill='both', expand=True)
            self._current_page = page_id

            # Refresh report page when navigating to it
            if page_id == 'report':
                self._pages['report'].load_report()

    def _on_accent_change(self, color: str) -> None:
        """Handle accent color change from settings."""
        self._config.accent_color = color
        self._sidebar.update_accent(color)

        for page in self._pages.values():
            if hasattr(page, 'update_accent'):
                page.update_accent(color)

    def _on_report_generated(self, report_path: Path) -> None:
        """Handle new report generation."""
        self._config.last_report_path = str(report_path)
        self._save_config()

    def _save_config(self) -> None:
        """Save configuration to file."""
        self._config.save()

    def _on_f5(self, event=None) -> None:
        """Handle F5 key press - refresh scan."""
        if self._current_page == 'organize':
            self._pages['organize'].refresh_scan()

    def _on_ctrl_s(self, event=None) -> None:
        """Handle Ctrl+S - save config."""
        self._save_config()
        self._status_indicator.configure(text="● Saved", text_color='#00ff88')
        self.after(2000, lambda: self._status_indicator.configure(
            text="● Ready", text_color='#00ff88'
        ))

    def _on_ctrl_q(self, event=None) -> None:
        """Handle Ctrl+Q - quit."""
        self._on_exit()

    def _on_exit(self) -> None:
        """Handle application exit."""
        self._save_config()
        self.quit()
        self.destroy()
