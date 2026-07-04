"""
FiveM Map Organizer - Utility Helpers Module.

Provides validation, formatting, and OS-specific utility functions.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path


def validate_source_path(path_str: str) -> tuple[bool, str]:
    """
    Validate a source folder path.

    Args:
        path_str: The path string to validate.

    Returns:
        Tuple of (is_valid, error_message). Error message is empty if valid.
    """
    if not path_str or not path_str.strip():
        return False, "Path cannot be empty"

    path = Path(path_str.strip())

    if not path.exists():
        return False, "Path does not exist"

    if not path.is_dir():
        return False, "Path is not a directory"

    try:
        # Check read permissions
        list(path.iterdir())
    except PermissionError:
        return False, "Permission denied"
    except OSError as e:
        return False, f"OS error: {e}"

    return True, ""


def validate_dest_path(path_str: str) -> tuple[bool, str]:
    """
    Validate a destination folder path.
    Destination doesn't need to exist (will be created).

    Args:
        path_str: The path string to validate.

    Returns:
        Tuple of (is_valid, error_message). Error message is empty if valid.
    """
    if not path_str or not path_str.strip():
        return False, "Path cannot be empty"

    path = Path(path_str.strip())

    # Check if parent exists or can be created
    try:
        # If path exists, check it's a directory
        if path.exists() and not path.is_dir():
            return False, "Path exists but is not a directory"

        # Check if we can write to the parent directory
        parent = path.parent
        while not parent.exists():
            parent = parent.parent

        if not os.access(str(parent), os.W_OK):
            return False, "Permission denied to create directory"

    except (PermissionError, OSError) as e:
        return False, f"Cannot access path: {e}"

    return True, ""


def format_duration(seconds: float) -> str:
    """
    Format seconds into HH:MM:SS string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted time string.
    """
    hours = int(seconds) // 3600
    minutes = (int(seconds) % 3600) // 60
    secs = int(seconds) % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_file_count(count: int) -> str:
    """
    Format a file count with plural handling.

    Args:
        count: Number of files.

    Returns:
        Formatted string like "1 file" or "5 files".
    """
    if count == 1:
        return "1 file"
    return f"{count} files"


def open_folder_in_explorer(path: Path) -> bool:
    """
    Open a folder in the system's file explorer.

    Args:
        path: Path to the folder to open.

    Returns:
        True if successfully opened, False otherwise.
    """
    try:
        system = platform.system()
        if system == 'Windows':
            os.startfile(str(path))
        elif system == 'Darwin':
            subprocess.Popen(['open', str(path)])
        else:
            subprocess.Popen(['xdg-open', str(path)])
        return True
    except (OSError, FileNotFoundError):
        return False


def open_file_in_editor(path: Path) -> bool:
    """
    Open a file in the system's default text editor.

    Args:
        path: Path to the file to open.

    Returns:
        True if successfully opened, False otherwise.
    """
    try:
        system = platform.system()
        if system == 'Windows':
            os.startfile(str(path))
        elif system == 'Darwin':
            subprocess.Popen(['open', '-t', str(path)])
        else:
            # Try common editors
            for editor in ['xdg-open', 'gedit', 'kate', 'nano', 'vim']:
                try:
                    subprocess.Popen([editor, str(path)])
                    return True
                except FileNotFoundError:
                    continue
            return False
        return True
    except (OSError, FileNotFoundError):
        return False


def get_config_path() -> Path:
    """
    Get the configuration file path.

    Returns:
        Path to config.json in the app directory.
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        app_dir = Path(sys.executable).parent
    else:
        # Running as script
        app_dir = Path(__file__).parent.parent

    return app_dir / 'config.json'


def copy_to_clipboard(text: str) -> bool:
    """
    Copy text to system clipboard.

    Args:
        text: Text to copy.

    Returns:
        True if successful, False otherwise.
    """
    try:
        system = platform.system()
        if system == 'Windows':
            process = subprocess.Popen(
                ['clip'], stdin=subprocess.PIPE, shell=True
            )
            process.communicate(text.encode('utf-8'))
        elif system == 'Darwin':
            process = subprocess.Popen(
                ['pbcopy'], stdin=subprocess.PIPE
            )
            process.communicate(text.encode('utf-8'))
        else:
            # Try xclip or xsel
            try:
                process = subprocess.Popen(
                    ['xclip', '-selection', 'clipboard'],
                    stdin=subprocess.PIPE
                )
                process.communicate(text.encode('utf-8'))
            except FileNotFoundError:
                process = subprocess.Popen(
                    ['xsel', '--clipboard', '--input'],
                    stdin=subprocess.PIPE
                )
                process.communicate(text.encode('utf-8'))
        return True
    except (OSError, FileNotFoundError, subprocess.SubprocessError):
        return False
