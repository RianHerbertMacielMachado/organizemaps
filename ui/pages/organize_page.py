"""
FiveM Map Organizer - Organize Maps Page.

Main page with 5-step organization workflow.
"""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from core.organizer import organize_resources
from core.scanner import MapResource, scan_folder
from ui.widgets.path_input import PathInput
from ui.widgets.progress_bar import ProgressBar
from ui.widgets.resource_table import ResourceTable
from ui.widgets.step_panel import StepPanel
from utils.helpers import (
    open_folder_in_explorer,
    validate_dest_path,
    validate_source_path,
)


class OrganizePage(ctk.CTkScrollableFrame):
    """Main organize maps page with 5-step workflow."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        config: object,
        on_report_generated: Optional[callable] = None,
        **kwargs
    ) -> None:
        """
        Initialize OrganizePage.

        Args:
            master: Parent widget.
            config: Application configuration object.
            on_report_generated: Callback when a report is generated.
        """
        super().__init__(master, fg_color='#1a1a2e', **kwargs)

        self._config = config
        self._on_report_generated = on_report_generated
        self._resources: list[MapResource] = []
        self._unclassified: list[Path] = []
        self._progress_queue: queue.Queue = queue.Queue()
        self._is_processing: bool = False

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the complete page UI."""
        # Page header
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=20, pady=(15, 10))

        ctk.CTkLabel(
            header,
            text="FiveM Map Organizer",
            font=ctk.CTkFont(family='Segoe UI', size=22, weight='bold'),
            text_color='#ffffff'
        ).pack(side='left')

        version_badge = ctk.CTkLabel(
            header,
            text="v1.0.0",
            font=ctk.CTkFont(family='Segoe UI', size=9),
            fg_color='#0f3460',
            corner_radius=10,
            text_color='#00d4ff',
            width=50,
            height=20
        )
        version_badge.pack(side='left', padx=(10, 0))

        ctk.CTkLabel(
            header,
            text="Organize your map files into proper FiveM resources with one click",
            font=ctk.CTkFont(family='Segoe UI', size=10),
            text_color='#888888'
        ).pack(side='left', padx=(15, 0))

        # === Step 1: Source & Destination ===
        self._step1 = StepPanel(self, 1, "Source & Destination")
        self._step1.pack(fill='x', padx=20, pady=(5, 8))

        # Source path input
        self._source_input = PathInput(
            self._step1.content,
            placeholder="Select raw maps folder...",
            validate_func=validate_source_path,
            initial_value=self._config.last_source
        )
        self._source_input.pack(fill='x', pady=(5, 4))

        # Destination path input
        self._dest_input = PathInput(
            self._step1.content,
            placeholder="Select or create destination folder...",
            validate_func=validate_dest_path,
            initial_value=self._config.last_dest
        )
        self._dest_input.pack(fill='x', pady=(4, 5))

        # === Step 2: Scan Results ===
        self._step2 = StepPanel(self, 2, "Scan Results")
        self._step2.pack(fill='x', padx=20, pady=(0, 8))

        self._resource_table = ResourceTable(
            self._step2.content,
            accent_color=self._config.accent_color
        )
        self._resource_table.pack(fill='both', expand=True, pady=5)
        self._resource_table.configure(height=150)

        # === Step 3: Summary ===
        self._step3 = StepPanel(self, 3, "Summary")
        self._step3.pack(fill='x', padx=20, pady=(0, 8))

        cards_frame = ctk.CTkFrame(self._step3.content, fg_color='transparent')
        cards_frame.pack(fill='x', pady=5)
        cards_frame.columnconfigure((0, 1, 2), weight=1)

        # Files card
        self._files_card = self._create_summary_card(
            cards_frame, "📄", "Files", "0"
        )
        self._files_card.grid(row=0, column=0, padx=(0, 5), sticky='nsew')

        # Resources card
        self._resources_card = self._create_summary_card(
            cards_frame, "📦", "Resources", "0"
        )
        self._resources_card.grid(row=0, column=1, padx=5, sticky='nsew')

        # Unclassified card
        self._unclassified_card = self._create_summary_card(
            cards_frame, "❓", "Unclassified", "0"
        )
        self._unclassified_card.grid(row=0, column=2, padx=(5, 0), sticky='nsew')

        # === Step 4: Progress ===
        self._step4 = StepPanel(self, 4, "Progress")
        self._step4.pack(fill='x', padx=20, pady=(0, 8))

        self._progress_bar = ProgressBar(
            self._step4.content,
            accent_color=self._config.accent_color
        )
        self._progress_bar.pack(fill='x', pady=(5, 8))

        # Organize button
        self._organize_btn = ctk.CTkButton(
            self._step4.content,
            text="Organize Maps",
            font=ctk.CTkFont(family='Segoe UI', size=12, weight='bold'),
            fg_color='#00d4ff',
            hover_color='#00b8d4',
            text_color='#000000',
            width=200,
            height=38,
            corner_radius=6,
            command=self._start_organize
        )
        self._organize_btn.pack(pady=(0, 5))

        # === Step 5: Success ===
        self._step5 = StepPanel(self, 5, "Success")
        self._step5.pack(fill='x', padx=20, pady=(0, 15))

        self._success_frame = ctk.CTkFrame(
            self._step5.content,
            fg_color='#0a2a1a',
            border_color='#00ff88',
            border_width=1,
            corner_radius=6
        )
        self._success_frame.pack(fill='x', pady=5)

        self._success_label = ctk.CTkLabel(
            self._success_frame,
            text="Awaiting organization...",
            font=ctk.CTkFont(family='Segoe UI', size=11),
            text_color='#888888'
        )
        self._success_label.pack(pady=10)

        # Success buttons (hidden initially)
        self._success_btns = ctk.CTkFrame(self._success_frame, fg_color='transparent')

        self._open_folder_btn = ctk.CTkButton(
            self._success_btns,
            text="📁 Open Folder",
            font=ctk.CTkFont(family='Segoe UI', size=10),
            fg_color='#0f3460',
            hover_color='#1a3a5c',
            width=120,
            height=30,
            corner_radius=4,
            command=self._open_dest_folder
        )
        self._open_folder_btn.pack(side='left', padx=(0, 8))

        self._copy_report_btn = ctk.CTkButton(
            self._success_btns,
            text="📋 Copy Report",
            font=ctk.CTkFont(family='Segoe UI', size=10),
            fg_color='#16213e',
            hover_color='#1a3a5c',
            border_color='#444444',
            border_width=1,
            width=120,
            height=30,
            corner_radius=4,
            command=self._copy_report
        )
        self._copy_report_btn.pack(side='left', padx=(0, 8))

        self._done_btn = ctk.CTkButton(
            self._success_btns,
            text="✓ Done",
            font=ctk.CTkFont(family='Segoe UI', size=10),
            fg_color='#1a3a1a',
            hover_color='#2a4a2a',
            border_color='#00ff88',
            border_width=1,
            width=100,
            height=30,
            corner_radius=4,
            command=self._on_done
        )
        self._done_btn.pack(side='left')

    def _create_summary_card(
        self, parent: ctk.CTkFrame, icon: str, label: str, value: str
    ) -> ctk.CTkFrame:
        """Create a summary card widget."""
        card = ctk.CTkFrame(parent, fg_color='#0f3460', corner_radius=8, height=70)
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color='transparent')
        inner.pack(expand=True)

        # Icon and value on same line
        top_row = ctk.CTkFrame(inner, fg_color='transparent')
        top_row.pack()

        ctk.CTkLabel(
            top_row,
            text=icon,
            font=ctk.CTkFont(size=16)
        ).pack(side='left', padx=(0, 6))

        value_label = ctk.CTkLabel(
            top_row,
            text=value,
            font=ctk.CTkFont(family='Segoe UI', size=22, weight='bold'),
            text_color='#00d4ff'
        )
        value_label.pack(side='left')

        # Store reference for updating
        card._value_label = value_label

        ctk.CTkLabel(
            inner,
            text=label,
            font=ctk.CTkFont(family='Segoe UI', size=9),
            text_color='#888888'
        ).pack()

        return card

    def _update_summary(self) -> None:
        """Update summary cards with current data."""
        total_files = sum(
            len(r.stream_files) + len(r.meta_files) + len(r.script_files)
            for r in self._resources
        ) + len(self._unclassified)

        self._files_card._value_label.configure(text=str(total_files))
        self._resources_card._value_label.configure(text=str(len(self._resources)))
        self._unclassified_card._value_label.configure(text=str(len(self._unclassified)))

    def _start_organize(self) -> None:
        """Start the organization workflow."""
        if self._is_processing:
            return

        source_path = self._source_input.get_path()
        dest_path = self._dest_input.get_path()

        # Validate paths
        src_valid, src_err = validate_source_path(source_path)
        if not src_valid:
            self._show_error(f"Source path error: {src_err}")
            return

        dst_valid, dst_err = validate_dest_path(dest_path)
        if not dst_valid:
            self._show_error(f"Destination path error: {dst_err}")
            return

        # Save paths to config
        self._config.last_source = source_path
        self._config.last_dest = dest_path

        self._is_processing = True
        self._organize_btn.configure(state='disabled')
        self._progress_bar.start()
        self._progress_bar.set_status("Scanning files...")

        # Run scan + organize in background thread
        thread = threading.Thread(
            target=self._worker_thread,
            args=(Path(source_path), Path(dest_path)),
            daemon=True
        )
        thread.start()

        # Start polling progress queue
        self._poll_progress()

    def _worker_thread(self, source: Path, destination: Path) -> None:
        """Background worker for scan and organize operations."""
        try:
            # Phase 1: Scan
            def scan_progress(current: int, total: int, msg: str) -> None:
                progress = current / total * 0.5  # Scan is 50% of total
                self._progress_queue.put(('progress', progress, f"Scanning: {msg}"))

            resources, unclassified = scan_folder(
                source,
                include_subfolders=self._config.include_subfolders,
                progress_callback=scan_progress
            )

            self._progress_queue.put(('scan_complete', resources, unclassified))

            # Phase 2: Organize
            def org_progress(current: int, total: int, msg: str) -> None:
                progress = 0.5 + (current / total * 0.5)  # Organize is other 50%
                self._progress_queue.put(('progress', progress, msg))

            result = organize_resources(
                resources=resources,
                unclassified=unclassified,
                destination=destination,
                operation=self._config.operation,
                on_duplicate=self._config.on_duplicate,
                auto_report=self._config.auto_report,
                progress_callback=org_progress
            )

            self._progress_queue.put(('complete', result))

        except PermissionError:
            self._progress_queue.put(('error', "Permission denied. Run as administrator."))
        except OSError as e:
            if e.errno == 28:
                self._progress_queue.put(('error', "Disk full. Free up space."))
            else:
                self._progress_queue.put(('error', f"OS error: {e}"))
        except Exception as e:
            self._progress_queue.put(('error', f"Unexpected error: {str(e)}"))

    def _poll_progress(self) -> None:
        """Poll progress queue and update UI."""
        try:
            while True:
                msg = self._progress_queue.get_nowait()

                if msg[0] == 'progress':
                    _, value, status = msg
                    self._progress_bar.set_progress(value, status)

                elif msg[0] == 'scan_complete':
                    _, resources, unclassified = msg
                    self._resources = resources
                    self._unclassified = unclassified
                    self._resource_table.populate(resources)
                    self._update_summary()

                elif msg[0] == 'complete':
                    result = msg[1]
                    self._on_organize_complete(result)
                    return

                elif msg[0] == 'error':
                    self._on_organize_error(msg[1])
                    return

        except queue.Empty:
            pass

        if self._is_processing:
            self.after(100, self._poll_progress)

    def _on_organize_complete(self, result: dict) -> None:
        """Handle successful organization completion."""
        self._is_processing = False
        self._progress_bar.stop()
        self._progress_bar.set_progress(1.0, "Organization complete!")
        self._organize_btn.configure(state='normal')

        # Update success panel
        self._success_label.configure(
            text="✓ Organization complete!",
            text_color='#00ff88'
        )
        self._success_btns.pack(pady=(0, 10))

        # Store report path
        if result.get('report_path'):
            self._config.last_report_path = str(result['report_path'])
            if self._on_report_generated:
                self._on_report_generated(result['report_path'])

    def _on_organize_error(self, error_msg: str) -> None:
        """Handle organization error."""
        self._is_processing = False
        self._progress_bar.stop()
        self._progress_bar.set_status(f"Error: {error_msg}")
        self._organize_btn.configure(state='normal')
        self._show_error(error_msg)

    def _show_error(self, message: str) -> None:
        """Show error dialog."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Error")
        dialog.geometry("400x180")
        dialog.configure(fg_color='#2a0000')
        dialog.resizable(False, False)
        dialog.grab_set()

        # Center on parent
        dialog.transient(self.winfo_toplevel())

        ctk.CTkLabel(
            dialog,
            text="🚫 Error",
            font=ctk.CTkFont(family='Segoe UI', size=16, weight='bold'),
            text_color='#ff4444'
        ).pack(pady=(20, 10))

        ctk.CTkLabel(
            dialog,
            text=message,
            font=ctk.CTkFont(family='Segoe UI', size=11),
            text_color='#ffffff',
            wraplength=350
        ).pack(padx=20, pady=(0, 15))

        ctk.CTkButton(
            dialog,
            text="OK",
            fg_color='#ff4444',
            hover_color='#cc3333',
            width=80,
            command=dialog.destroy
        ).pack()

    def _open_dest_folder(self) -> None:
        """Open destination folder in explorer."""
        dest = self._dest_input.get_path()
        if dest:
            open_folder_in_explorer(Path(dest))

    def _copy_report(self) -> None:
        """Copy report content to clipboard."""
        from utils.helpers import copy_to_clipboard

        report_path = self._config.last_report_path
        if report_path and Path(report_path).exists():
            content = Path(report_path).read_text(encoding='utf-8')
            copy_to_clipboard(content)

    def _on_done(self) -> None:
        """Reset to initial state."""
        self._resources = []
        self._unclassified = []
        self._resource_table.clear()
        self._progress_bar.reset()
        self._success_label.configure(
            text="Awaiting organization...",
            text_color='#888888'
        )
        self._success_btns.pack_forget()
        self._update_summary()

    def refresh_scan(self) -> None:
        """Re-scan the source folder (F5 shortcut)."""
        source_path = self._source_input.get_path()
        if not source_path:
            return

        src_valid, _ = validate_source_path(source_path)
        if not src_valid:
            return

        # Quick scan in thread
        self._progress_bar.set_status("Re-scanning...")

        def _scan_thread():
            try:
                resources, unclassified = scan_folder(
                    Path(source_path),
                    include_subfolders=self._config.include_subfolders
                )
                self._progress_queue.put(('scan_complete', resources, unclassified))
                self._progress_queue.put(('progress', 0.0, "Scan complete. Ready."))
            except Exception as e:
                self._progress_queue.put(('error', str(e)))

        self._is_processing = True
        threading.Thread(target=_scan_thread, daemon=True).start()
        self._poll_progress()
        self._is_processing = False

    def update_accent(self, color: str) -> None:
        """Update accent color throughout the page."""
        self._step1.update_accent(color)
        self._step2.update_accent(color)
        self._step3.update_accent(color)
        self._step4.update_accent(color)
        self._step5.update_accent(color)
        self._progress_bar.update_accent(color)
        self._organize_btn.configure(fg_color=color)
        self._files_card._value_label.configure(text_color=color)
        self._resources_card._value_label.configure(text_color=color)
        self._unclassified_card._value_label.configure(text_color=color)
