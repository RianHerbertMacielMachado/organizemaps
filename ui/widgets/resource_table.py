"""
FiveM Map Organizer - Resource Table Widget.

Styled Treeview table for displaying scan results.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

import customtkinter as ctk

from core.scanner import MapResource


class ResourceTable(ctk.CTkFrame):
    """Styled Treeview table for resource scan results."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        accent_color: str = '#00d4ff',
        **kwargs
    ) -> None:
        """
        Initialize ResourceTable.

        Args:
            master: Parent widget.
            accent_color: Accent color for highlights.
        """
        super().__init__(master, fg_color='#0d1b2a', corner_radius=6, **kwargs)

        self._accent_color = accent_color

        # Style configuration
        style = ttk.Style()
        style.theme_use('default')

        style.configure(
            'Resource.Treeview',
            background='#0d1b2a',
            foreground='#ffffff',
            fieldbackground='#0d1b2a',
            borderwidth=0,
            font=('Segoe UI', 9),
            rowheight=28
        )
        style.configure(
            'Resource.Treeview.Heading',
            background='#16213e',
            foreground='#888888',
            font=('Segoe UI', 9, 'bold'),
            borderwidth=0,
            relief='flat'
        )
        style.map(
            'Resource.Treeview',
            background=[('selected', '#0f3460')],
            foreground=[('selected', '#ffffff')]
        )
        style.map(
            'Resource.Treeview.Heading',
            background=[('active', '#1a3a5c')]
        )

        # Treeview widget
        columns = ('files', 'type', 'status', 'method')
        self._tree = ttk.Treeview(
            self,
            columns=columns,
            show='headings',
            style='Resource.Treeview',
            selectmode='browse'
        )

        # Column configuration
        self._tree.heading('files', text='Files', anchor='center')
        self._tree.heading('type', text='Type', anchor='w')
        self._tree.heading('status', text='Status', anchor='w')
        self._tree.heading('method', text='Method', anchor='center')

        self._tree.column('files', width=60, minwidth=50, anchor='center')
        self._tree.column('type', width=120, minwidth=80, anchor='w')
        self._tree.column('status', width=100, minwidth=80, anchor='w')
        self._tree.column('method', width=70, minwidth=50, anchor='center')

        # Add resource name as first column (tree column)
        self._tree['show'] = ('headings', 'tree')
        self._tree.heading('#0', text='Resource Name', anchor='w')
        self._tree.column('#0', width=250, minwidth=150, anchor='w')

        # Scrollbar
        scrollbar = ttk.Scrollbar(
            self,
            orient='vertical',
            command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=scrollbar.set)

        # Style scrollbar
        style.configure(
            'Vertical.TScrollbar',
            background='#16213e',
            troughcolor='#0d1b2a',
            borderwidth=0,
            arrowsize=0
        )

        # Pack
        self._tree.pack(side='left', fill='both', expand=True, padx=(4, 0), pady=4)
        scrollbar.pack(side='right', fill='y', padx=(0, 4), pady=4)

        # Tags for alternating row colors
        self._tree.tag_configure('even', background='#0d1b2a')
        self._tree.tag_configure('odd', background='#111827')
        self._tree.tag_configure('ready', foreground='#00ff88')
        self._tree.tag_configure('check', foreground='#ffaa00')
        self._tree.tag_configure('no_stream', foreground='#ff4444')

    def clear(self) -> None:
        """Remove all items from the table."""
        for item in self._tree.get_children():
            self._tree.delete(item)

    def populate(self, resources: list[MapResource]) -> None:
        """
        Populate table with resource data.

        Args:
            resources: List of MapResource objects to display.
        """
        self.clear()

        for idx, resource in enumerate(resources):
            # Count total files
            total_files = (
                len(resource.stream_files) +
                len(resource.meta_files) +
                len(resource.script_files)
            )

            # Get file types
            extensions: set[str] = set()
            for f in resource.stream_files:
                extensions.add(f.suffix.lower())
            for f in resource.meta_files:
                extensions.add(f.suffix.lower())
            type_str = ' '.join(sorted(extensions))

            # Status display
            if resource.status == 'ready':
                status_str = '✓ Ready'
                status_tag = 'ready'
            elif resource.status == 'meta_only':
                status_str = '⚠ Check'
                status_tag = 'check'
            else:
                status_str = '✗ No Stream'
                status_tag = 'no_stream'

            # Row alternation tag
            row_tag = 'even' if idx % 2 == 0 else 'odd'

            self._tree.insert(
                '',
                'end',
                text=resource.name,
                values=(total_files, type_str, status_str, resource.method),
                tags=(row_tag, status_tag)
            )

    def get_selected(self) -> Optional[str]:
        """Get name of selected resource."""
        selection = self._tree.selection()
        if selection:
            return self._tree.item(selection[0])['text']
        return None
