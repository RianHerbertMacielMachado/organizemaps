#!/usr/bin/env python3
"""
FiveM Map Organizer v1.0.0

GTA V / FiveM Resource Manager
Organize your map files into proper FiveM resources with one click.

Entry point - verifies and installs dependencies before launching the GUI.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys


def ensure_customtkinter() -> None:
    """
    Verify customtkinter is installed, install if absent.

    Uses importlib.util.find_spec to check without importing,
    then pip installs if not found.
    """
    if importlib.util.find_spec('customtkinter') is None:
        print("[FiveM Map Organizer] Installing customtkinter...")
        try:
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', 'customtkinter'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print("[FiveM Map Organizer] customtkinter installed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"[FiveM Map Organizer] Failed to install customtkinter: {e}")
            print("Please install manually: pip install customtkinter")
            sys.exit(1)


def main() -> None:
    """Launch the FiveM Map Organizer application."""
    # Ensure dependencies
    ensure_customtkinter()

    # Import after ensuring dependencies
    from ui.app import FiveMMapOrganizerApp

    # Create and run application
    app = FiveMMapOrganizerApp()
    app.mainloop()


if __name__ == '__main__':
    main()
