"""
FiveM Map Organizer - Preview Mode Page.

Shows a tree preview of how files would be organized.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from core.scanner import MapResource, scan_folder
from utils.helpers import validate_source_path


class PreviewPage(ctk.CTkFrame):
    """Preview page showing the tree structure of organized resources."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        config: object,
        **kwargs
    ) -> None:
        """
        Initialize PreviewPage.

        Args:
            master: Parent widget.
            config: Application configuration object.
        """
        super().__init__(master, fg_color='#1a1a2e', **kwargs)

        self._config = config
        self._resources: list[MapResource] = []
        self._unclassified: list[Path] = []

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the preview page UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=20, pady=(20, 10))

        ctk.CTkLabel(
            header,
            text="Preview Mode",
            font=ctk.CTkFont(family='Segoe UI', size=18, weight='bold'),
            text_color='#ffffff'
        ).pack(side='left')

        ctk.CTkLabel(
            header,
            text="Preview the folder structure before organizing",
            font=ctk.CTkFont(family='Segoe UI', size=10),
            text_color='#888888'
        ).pack(side='left', padx=(15, 0))

        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color='transparent', height=40)
        toolbar.pack(fill='x', padx=20, pady=(0, 10))
        toolbar.pack_propagate(False)

        self._preview_btn = ctk.CTkButton(
            toolbar,
            text="🔍 Generate Preview",
            font=ctk.CTkFont(family='Segoe UI', size=10),
            fg_color='#0f3460',
            hover_color='#1a3a5c',
            width=140,
            height=30,
            corner_radius=4,
            command=self._generate_preview
        )
        self._preview_btn.pack(side='left', padx=(0, 8))

        self._export_btn = ctk.CTkButton(
            toolbar,
            text="📄 Export as .txt",
            font=ctk.CTkFont(family='Segoe UI', size=10),
            fg_color='#16213e',
            hover_color='#1a3a5c',
            border_color='#444444',
            border_width=1,
            width=120,
            height=30,
            corner_radius=4,
            command=self._export_preview
        )
        self._export_btn.pack(side='left')

        self._status_label = ctk.CTkLabel(
            toolbar,
            text="",
            font=ctk.CTkFont(family='Segoe UI', size=9),
            text_color='#888888'
        )
        self._status_label.pack(side='right')

        # Tree preview area
        self._tree_frame = ctk.CTkScrollableFrame(
            self,
            fg_color='#0d1b2a',
            corner_radius=8
        )
        self._tree_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))

        # Initial message
        self._placeholder = ctk.CTkLabel(
            self._tree_frame,
            text="Click 'Generate Preview' to scan and display the folder structure.\n"
                 "Make sure a valid source path is set in the Organize Maps page.",
            font=ctk.CTkFont(family='Segoe UI', size=11),
            text_color='#666666',
            justify='center'
        )
        self._placeholder.pack(expand=True, pady=50)

    def _generate_preview(self) -> None:
        """Generate and display the preview tree."""
        source_path = self._config.last_source

        if not source_path:
            self._status_label.configure(text="No source path set", text_color='#ff4444')
            return

        valid, err = validate_source_path(source_path)
        if not valid:
            self._status_label.configure(text=f"Source: {err}", text_color='#ff4444')
            return

        self._status_label.configure(text="Scanning...", text_color='#ffaa00')
        self._preview_btn.configure(state='disabled')

        def _scan_thread():
            try:
                resources, unclassified = scan_folder(
                    Path(source_path),
                    include_subfolders=self._config.include_subfolders
                )
                self.after(0, lambda: self._display_tree(resources, unclassified))
            except Exception as e:
                self.after(0, lambda: self._status_label.configure(
                    text=f"Error: {str(e)}", text_color='#ff4444'
                ))
                self.after(0, lambda: self._preview_btn.configure(state='normal'))

        threading.Thread(target=_scan_thread, daemon=True).start()

    def _display_tree(self, resources: list[MapResource], unclassified: list[Path]) -> None:
        """Display the tree structure in the preview area."""
        self._resources = resources
        self._unclassified = unclassified
        self._preview_btn.configure(state='normal')
        self._status_label.configure(
            text=f"{len(resources)} resources, {len(unclassified)} unclassified",
            text_color='#00ff88'
        )

        # Clear existing content
        for widget in self._tree_frame.winfo_children():
            widget.destroy()

        if not resources and not unclassified:
            ctk.CTkLabel(
                self._tree_frame,
                text="No files found in source folder.",
                font=ctk.CTkFont(family='Segoe UI', size=11),
                text_color='#666666'
            ).pack(pady=20)
            return

        # Build tree display
        for resource in resources:
            self._add_resource_tree(resource)

        # Unclassified
        if unclassified:
            self._add_separator()
            self._add_tree_line("📁 _nao_classificados/", 0, '#ff4444')
            for f in unclassified:
                self._add_tree_line(f"    📄 {f.name}", 1, '#888888')

    def _add_resource_tree(self, resource: MapResource) -> None:
        """Add a resource tree to the display."""
        # Method color
        method_colors = {'YMF': '#00d4ff', 'XML': '#00ff88', 'NAME': '#888888'}
        method_color = method_colors.get(resource.method, '#888888')

        # Resource folder header
        header_frame = ctk.CTkFrame(self._tree_frame, fg_color='transparent', height=24)
        header_frame.pack(fill='x', pady=(6, 0))
        header_frame.pack_propagate(False)

        ctk.CTkLabel(
            header_frame,
            text=f"📁 {resource.name}/",
            font=ctk.CTkFont(family='Consolas', size=10, weight='bold'),
            text_color='#ffffff',
            anchor='w'
        ).pack(side='left')

        ctk.CTkLabel(
            header_frame,
            text=f"[{resource.method}]",
            font=ctk.CTkFont(family='Consolas', size=9),
            text_color=method_color,
            anchor='w'
        ).pack(side='left', padx=(8, 0))

        # fxmanifest.lua
        self._add_tree_line("    📄 fxmanifest.lua", 1, '#00ff88')

        # Meta files in root
        for f in resource.meta_files:
            self._add_tree_line(f"    📄 {f.name}", 1, '#ffaa00')

        # Scripts folder
        if resource.script_files:
            self._add_tree_line("    📁 scripts/", 1, '#ffffff')
            for f in resource.script_files:
                self._add_tree_line(f"        📄 {f.name}", 2, '#888888')

        # Stream folder
        if resource.stream_files:
            self._add_tree_line("    📁 stream/", 1, '#ffffff')
            for f in resource.stream_files:
                self._add_tree_line(f"        📄 {f.name}", 2, '#888888')

    def _add_tree_line(self, text: str, indent: int, color: str) -> None:
        """Add a single line to the tree display."""
        label = ctk.CTkLabel(
            self._tree_frame,
            text=text,
            font=ctk.CTkFont(family='Consolas', size=10),
            text_color=color,
            anchor='w'
        )
        label.pack(fill='x', padx=(indent * 4, 0))

    def _add_separator(self) -> None:
        """Add a visual separator."""
        sep = ctk.CTkFrame(self._tree_frame, fg_color='#333333', height=1)
        sep.pack(fill='x', pady=8)

    def _export_preview(self) -> None:
        """Export the preview tree as a .txt file."""
        from tkinter import filedialog

        if not self._resources and not self._unclassified:
            self._status_label.configure(text="Nothing to export", text_color='#ffaa00')
            return

        filepath = filedialog.asksaveasfilename(
            title="Export Preview",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile="preview_tree.txt"
        )

        if not filepath:
            return

        lines: list[str] = []
        lines.append("FiveM Map Organizer - Preview Tree")
        lines.append("=" * 50)
        lines.append("")

        for resource in self._resources:
            lines.append(f"[{resource.method}] {resource.name}/")
            lines.append(f"├── fxmanifest.lua")

            for f in resource.meta_files:
                lines.append(f"├── {f.name}")

            if resource.script_files:
                lines.append(f"├── scripts/")
                for f in resource.script_files:
                    lines.append(f"│   └── {f.name}")

            if resource.stream_files:
                lines.append(f"└── stream/")
                for i, f in enumerate(resource.stream_files):
                    prefix = "│   ├──" if i < len(resource.stream_files) - 1 else "│   └──"
                    lines.append(f"    {prefix} {f.name}")

            lines.append("")

        if self._unclassified:
            lines.append("_nao_classificados/")
            for f in self._unclassified:
                lines.append(f"└── {f.name}")

        Path(filepath).write_text('\n'.join(lines), encoding='utf-8')
        self._status_label.configure(text=f"Exported to {filepath}", text_color='#00ff88')

    def update_accent(self, color: str) -> None:
        """Update accent color."""
        pass
