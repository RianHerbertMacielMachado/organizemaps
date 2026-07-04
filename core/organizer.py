"""
FiveM Map Organizer - Organizer Module.

Handles the actual file organization: creating folder structure,
copying/moving files, and generating reports.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.manifest import write_manifest
from core.scanner import MapResource


def _handle_duplicate(src: Path, dest: Path, mode: str) -> Path:
    """
    Handle duplicate file at destination.

    Args:
        src: Source file path.
        dest: Destination file path.
        mode: 'skip', 'overwrite', or 'rename'.

    Returns:
        Final destination path (may be renamed).
    """
    if not dest.exists():
        return dest

    if mode == 'skip':
        return dest  # Will skip copy
    elif mode == 'overwrite':
        return dest
    elif mode == 'rename':
        stem = dest.stem
        suffix = dest.suffix
        parent = dest.parent
        counter = 1
        while dest.exists():
            dest = parent / f"{stem}_{counter}{suffix}"
            counter += 1
        return dest

    return dest


def organize_resources(
    resources: list[MapResource],
    unclassified: list[Path],
    destination: Path,
    operation: str = 'copy',
    on_duplicate: str = 'skip',
    auto_report: bool = True,
    progress_callback: Optional[callable] = None
) -> dict[str, object]:
    """
    Organize all resources into proper FiveM folder structure.

    Creates the following structure for each resource:
        resource_name/
        ├── fxmanifest.lua
        ├── *.meta (meta files in root)
        ├── scripts/ (if .lua files exist)
        │   └── *.lua
        └── stream/ (all stream files)
            └── *.ymap, *.ytyp, etc.

    Args:
        resources: List of MapResource objects to organize.
        unclassified: List of unclassified file paths.
        destination: Destination root folder.
        operation: 'copy' or 'move'.
        on_duplicate: 'skip', 'overwrite', or 'rename'.
        auto_report: Whether to generate a report file.
        progress_callback: Optional callback(current, total, message).

    Returns:
        Dict with report data: {
            'total_files': int,
            'resources_created': int,
            'unclassified_count': int,
            'errors': list[str],
            'report_path': Optional[Path],
            'duration_seconds': float
        }
    """
    start_time = datetime.now()
    errors: list[str] = []
    total_items = len(resources) + (1 if unclassified else 0)
    current_item = 0

    # Ensure destination exists
    destination.mkdir(parents=True, exist_ok=True)

    # Process each resource
    for resource in resources:
        current_item += 1
        if progress_callback:
            progress_callback(
                current_item, total_items,
                f"Organizing {resource.name}..."
            )

        resource_dir = destination / resource.name
        resource_dir.mkdir(parents=True, exist_ok=True)

        # Create stream/ directory
        stream_dir = resource_dir / 'stream'
        stream_dir.mkdir(exist_ok=True)

        # Copy/move stream files
        for src_file in resource.stream_files:
            dest_file = stream_dir / src_file.name
            dest_file = _handle_duplicate(src_file, dest_file, on_duplicate)

            try:
                if on_duplicate == 'skip' and (stream_dir / src_file.name).exists():
                    continue
                if operation == 'copy':
                    shutil.copy2(src_file, dest_file)
                else:
                    shutil.move(str(src_file), str(dest_file))
            except (OSError, shutil.Error) as e:
                errors.append(f"Error with {src_file.name}: {str(e)}")

        # Copy/move meta files to resource root
        for src_file in resource.meta_files:
            dest_file = resource_dir / src_file.name
            dest_file = _handle_duplicate(src_file, dest_file, on_duplicate)

            try:
                if on_duplicate == 'skip' and (resource_dir / src_file.name).exists():
                    continue
                if operation == 'copy':
                    shutil.copy2(src_file, dest_file)
                else:
                    shutil.move(str(src_file), str(dest_file))
            except (OSError, shutil.Error) as e:
                errors.append(f"Error with {src_file.name}: {str(e)}")

        # Copy/move script files to scripts/ directory
        if resource.script_files:
            scripts_dir = resource_dir / 'scripts'
            scripts_dir.mkdir(exist_ok=True)

            for src_file in resource.script_files:
                dest_file = scripts_dir / src_file.name
                dest_file = _handle_duplicate(src_file, dest_file, on_duplicate)

                try:
                    if on_duplicate == 'skip' and (scripts_dir / src_file.name).exists():
                        continue
                    if operation == 'copy':
                        shutil.copy2(src_file, dest_file)
                    else:
                        shutil.move(str(src_file), str(dest_file))
                except (OSError, shutil.Error) as e:
                    errors.append(f"Error with {src_file.name}: {str(e)}")

        # Generate fxmanifest.lua
        try:
            write_manifest(resource, resource_dir)
        except (OSError, IOError) as e:
            errors.append(f"Error writing manifest for {resource.name}: {str(e)}")

    # Process unclassified files
    if unclassified:
        current_item += 1
        if progress_callback:
            progress_callback(current_item, total_items, "Moving unclassified files...")

        unclassified_dir = destination / '_nao_classificados'
        unclassified_dir.mkdir(exist_ok=True)

        for src_file in unclassified:
            dest_file = unclassified_dir / src_file.name
            dest_file = _handle_duplicate(src_file, dest_file, on_duplicate)

            try:
                if on_duplicate == 'skip' and (unclassified_dir / src_file.name).exists():
                    continue
                if operation == 'copy':
                    shutil.copy2(src_file, dest_file)
                else:
                    shutil.move(str(src_file), str(dest_file))
            except (OSError, shutil.Error) as e:
                errors.append(f"Error with {src_file.name}: {str(e)}")

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Generate report
    report_path: Optional[Path] = None
    if auto_report:
        report_path = _generate_report(
            resources, unclassified, destination,
            operation, start_time, duration, errors
        )

    return {
        'total_files': sum(
            len(r.stream_files) + len(r.meta_files) + len(r.script_files)
            for r in resources
        ) + len(unclassified),
        'resources_created': len(resources),
        'unclassified_count': len(unclassified),
        'errors': errors,
        'report_path': report_path,
        'duration_seconds': duration
    }


def _generate_report(
    resources: list[MapResource],
    unclassified: list[Path],
    destination: Path,
    operation: str,
    start_time: datetime,
    duration: float,
    errors: list[str]
) -> Path:
    """
    Generate an organization report file.

    Args:
        resources: List of organized resources.
        unclassified: List of unclassified files.
        destination: Destination folder.
        operation: Operation type used.
        start_time: When organization started.
        duration: Duration in seconds.
        errors: List of error messages.

    Returns:
        Path to the generated report file.
    """
    timestamp = start_time.strftime('%Y%m%d_%H%M%S')
    report_name = f"_relatorio_{timestamp}.txt"
    report_path = destination / report_name

    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("  FiveM Map Organizer - Organization Report")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"Date/Time:    {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Destination:  {destination}")
    lines.append(f"Operation:    {operation.upper()}")
    lines.append(f"Duration:     {duration:.2f} seconds")
    lines.append("")

    total_files = sum(
        len(r.stream_files) + len(r.meta_files) + len(r.script_files)
        for r in resources
    ) + len(unclassified)
    lines.append(f"Total Files Processed:  {total_files}")
    lines.append(f"Resources Created:      {len(resources)}")
    lines.append(f"Unclassified Files:     {len(unclassified)}")
    lines.append("")

    lines.append("-" * 70)
    lines.append("  RESOURCES")
    lines.append("-" * 70)

    for resource in resources:
        lines.append("")
        lines.append(f"  [{resource.method}] {resource.name}/")
        lines.append(f"       Status: {resource.status}")

        if resource.stream_files:
            lines.append(f"       Stream ({len(resource.stream_files)} files):")
            for f in resource.stream_files:
                lines.append(f"         - {f.name}")

        if resource.meta_files:
            lines.append(f"       Meta ({len(resource.meta_files)} files):")
            for f in resource.meta_files:
                lines.append(f"         - {f.name}")

        if resource.script_files:
            lines.append(f"       Scripts ({len(resource.script_files)} files):")
            for f in resource.script_files:
                lines.append(f"         - {f.name}")

    if unclassified:
        lines.append("")
        lines.append("-" * 70)
        lines.append("  UNCLASSIFIED FILES")
        lines.append("-" * 70)
        for f in unclassified:
            lines.append(f"    - {f.name}")

    if errors:
        lines.append("")
        lines.append("-" * 70)
        lines.append("  ERRORS")
        lines.append("-" * 70)
        for err in errors:
            lines.append(f"    ! {err}")

    lines.append("")
    lines.append("=" * 70)
    lines.append("  End of Report")
    lines.append("=" * 70)

    report_content = '\n'.join(lines)
    report_path.write_text(report_content, encoding='utf-8')

    return report_path
