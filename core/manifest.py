"""
FiveM Map Organizer - Manifest Generator Module.

Generates correct fxmanifest.lua files for FiveM resources.
"""

from __future__ import annotations

from pathlib import Path

from core.scanner import MapResource


def _infer_data_file_type(filename: str) -> str:
    """
    Infer the FiveM data_file type from the filename.

    Args:
        filename: The .meta filename to classify.

    Returns:
        The appropriate FiveM data_file type string.
    """
    name_lower = filename.lower()

    if 'vehicle' in name_lower and 'variation' not in name_lower:
        return 'VEHICLE_METADATA_FILE'
    elif 'handling' in name_lower:
        return 'HANDLING_FILE'
    elif 'carcols' in name_lower:
        return 'CARCOLS_FILE'
    elif 'carvariat' in name_lower or 'variation' in name_lower:
        return 'VEHICLE_VARIATION_FILE'
    elif 'ped' in name_lower:
        return 'PED_METADATA_FILE'
    else:
        return 'EXTRA_TITLE_UPDATE_DATA'


def generate_manifest(resource: MapResource) -> str:
    """
    Generate fxmanifest.lua content for a FiveM resource.

    Following the specification in Section 5:
    - Always includes fx_version, game, this_is_a_map, description, author, version
    - Includes files{} and data_file only if .meta files exist
    - Includes client_scripts{} only if .lua scripts exist
    - Never references stream/ paths

    Args:
        resource: The MapResource to generate manifest for.

    Returns:
        Complete fxmanifest.lua content as string.
    """
    lines: list[str] = []

    # Required fields
    lines.append("fx_version 'cerulean'")
    lines.append("game 'gta5'")
    lines.append("")
    lines.append("this_is_a_map 'yes'")
    lines.append("")
    lines.append(f"description '{resource.name}'")
    lines.append("author 'FiveM Map Organizer'")
    lines.append("version '1.0.0'")

    # files{} and data_file for .meta files
    meta_filenames = [p.name for p in resource.meta_files if p.suffix.lower() == '.meta']

    if meta_filenames:
        lines.append("")
        lines.append("files {")
        for fname in sorted(meta_filenames):
            lines.append(f"    '{fname}',")
        lines.append("}")
        lines.append("")
        for fname in sorted(meta_filenames):
            dtype = _infer_data_file_type(fname)
            lines.append(f"data_file '{dtype}' '{fname}'")

    # client_scripts{} for .lua scripts
    if resource.script_files:
        lines.append("")
        lines.append("client_scripts {")
        lines.append("    'scripts/*.lua',")
        lines.append("}")

    lines.append("")
    return '\n'.join(lines)


def write_manifest(resource: MapResource, dest_folder: Path) -> Path:
    """
    Write fxmanifest.lua to the resource destination folder.

    Args:
        resource: The MapResource to generate manifest for.
        dest_folder: The root folder of the resource (where fxmanifest.lua goes).

    Returns:
        Path to the written fxmanifest.lua file.
    """
    content = generate_manifest(resource)
    manifest_path = dest_folder / 'fxmanifest.lua'
    manifest_path.write_text(content, encoding='utf-8')
    return manifest_path
