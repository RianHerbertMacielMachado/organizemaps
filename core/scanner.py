"""
FiveM Map Organizer - Core Scanner Module.

Implements the complete dependency graph algorithm for grouping
GTA V/FiveM map files into proper resources.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Stream file extensions recognized by FiveM
STREAM_EXTENSIONS: set[str] = {
    '.ymap', '.ytyp', '.ymf', '.ybn', '.ydr', '.ydd', '.ytd',
    '.yft', '.ycd', '.ynd', '.ynv', '.yld', '.ysc', '.rpf', '.ymt'
}

# Meta file extensions
META_EXTENSIONS: set[str] = {'.meta', '.xml', '.json'}

# Script extension
SCRIPT_EXTENSION: str = '.lua'

# Suffix cleanup regex for name grouping fallback
SUFFIX_CLEANUP_PATTERN: re.Pattern = re.compile(
    r'(_lod\d*|_hi|\+hi|_slod\d*|_col|_shadow|_detail|_decal|_proxy|_physics|_interior|_\d+)$',
    re.IGNORECASE
)


@dataclass
class FileInfo:
    """Represents a single file in the source folder."""

    path: Path
    basename: str          # filename without extension, lowercase
    basename_original: str # filename without extension, original case
    extension: str         # lowercase extension including dot
    hi_prefix: bool        # whether file has hi@ prefix
    base_without_hi: str   # basename with hi@ prefix removed, lowercase

    @staticmethod
    def from_path(filepath: Path) -> 'FileInfo':
        """Create FileInfo from a file path."""
        name = filepath.stem
        ext = filepath.suffix.lower()
        has_hi = name.lower().startswith('hi@')
        base_no_hi = name[3:].lower() if has_hi else name.lower()

        return FileInfo(
            path=filepath,
            basename=name.lower(),
            basename_original=name,
            extension=ext,
            hi_prefix=has_hi,
            base_without_hi=base_no_hi
        )


@dataclass
class MapResource:
    """Represents a grouped FiveM resource."""

    name: str
    stream_files: list[Path] = field(default_factory=list)
    meta_files: list[Path] = field(default_factory=list)
    script_files: list[Path] = field(default_factory=list)
    unclassified_files: list[Path] = field(default_factory=list)
    status: str = 'ready'       # 'ready' | 'meta_only' | 'no_stream'
    method: str = 'NAME'        # 'YMF' | 'XML' | 'NAME'

    def compute_status(self) -> None:
        """Compute the resource status based on file composition."""
        has_stream = len(self.stream_files) > 0
        has_meta = len(self.meta_files) > 0

        if has_stream:
            self.status = 'ready'
        elif has_meta:
            self.status = 'meta_only'
        else:
            self.status = 'no_stream'


class UnionFind:
    """Union-Find data structure with path compression and union by rank."""

    def __init__(self) -> None:
        """Initialize empty Union-Find."""
        self._parent: dict[str, str] = {}
        self._rank: dict[str, int] = {}

    def make_set(self, x: str) -> None:
        """Create a new set containing only x."""
        if x not in self._parent:
            self._parent[x] = x
            self._rank[x] = 0

    def find(self, x: str) -> str:
        """Find the representative of the set containing x with path compression."""
        if x not in self._parent:
            self.make_set(x)
        if self._parent[x] != x:
            self._parent[x] = self.find(self._parent[x])
        return self._parent[x]

    def union(self, x: str, y: str) -> None:
        """Union the sets containing x and y by rank."""
        rx = self.find(x)
        ry = self.find(y)
        if rx == ry:
            return
        if self._rank[rx] < self._rank[ry]:
            self._parent[rx] = ry
        elif self._rank[rx] > self._rank[ry]:
            self._parent[ry] = rx
        else:
            self._parent[ry] = rx
            self._rank[rx] += 1

    def get_groups(self) -> dict[str, list[str]]:
        """Return all groups as {representative: [members]}."""
        groups: dict[str, list[str]] = defaultdict(list)
        for item in self._parent:
            groups[self.find(item)].append(item)
        return dict(groups)


def parse_ymf_binary(path: Path) -> set[str]:
    """
    Extract ASCII string references from a binary .ymf file.

    Supports two RSC7 sub-formats:
    1. PSO/PSIG format: has a STRS section with null-terminated strings
    2. Standard RSC7: strings embedded between null bytes

    Args:
        path: Path to the .ymf binary file.

    Returns:
        Set of lowercase name strings found in the binary.
    """
    try:
        data = path.read_bytes()
    except (OSError, IOError):
        return set()

    names: set[str] = set()

    # Check for STRS section (PSO format used by CodeWalker)
    strs_pos = data.find(b'STRS')
    if strs_pos >= 0:
        # STRS section contains length-prefixed or null-separated strings
        strs_section = data[strs_pos + 4:]
        # Extract all valid identifier strings from STRS section
        # Format: often a byte length prefix followed by the string
        strs_matches = re.findall(rb'([a-zA-Z][a-zA-Z0-9_@]{2,63})', strs_section)
        for m in strs_matches:
            try:
                name = m.decode('ascii').lower()
                # Filter out known section markers
                if name not in ('strs', 'chks', 'psin', 'pmap', 'psch', 'psig', 'zvnp', 'yppp'):
                    names.add(name)
            except (UnicodeDecodeError, ValueError):
                continue

    # Also scan the full binary for string patterns
    # Pattern 1: ASCII strings preceded by non-null or start
    matches1 = re.findall(rb'(?<!\x00)([a-zA-Z][a-zA-Z0-9_@]{2,63})(?=\x00)', data)
    # Pattern 2: ASCII strings between null bytes
    matches2 = re.findall(rb'\x00([a-zA-Z][a-zA-Z0-9_@]{2,63})\x00', data)
    # Pattern 3: Any identifier-like string 5+ chars (more aggressive for RSC7)
    matches3 = re.findall(rb'([a-z][a-z0-9_@]{4,63})', data)

    for m in matches1 + matches2 + matches3:
        try:
            name = m.decode('ascii').lower()
            # Filter out RSC7 section markers and common false positives
            if name in ('psin', 'pmap', 'psch', 'psig', 'zvnp', 'strs', 'chks', 'yppp',
                        'null', 'none', 'false', 'true', 'string', 'array'):
                continue
            # Must be at least 3 chars and look like a filename
            if len(name) >= 3:
                names.add(name)
        except (UnicodeDecodeError, ValueError):
            continue

    return names


def parse_ymf_xml(path: Path) -> dict[str, set[str]]:
    """
    Parse a .ymf XML file to extract dependency references.

    Args:
        path: Path to the .ymf.xml or _manifest.ymf.xml file.

    Returns:
        Dict with keys 'imap_names', 'ityp_names', 'ybn_names'.
    """
    result: dict[str, set[str]] = {
        'imap_names': set(),
        'ityp_names': set(),
        'ybn_names': set()
    }

    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except (ET.ParseError, OSError, IOError):
        return result

    # imapDependencies_2/Item/imapName
    for elem in root.iter('imapName'):
        if elem.text and elem.text.strip():
            result['imap_names'].add(elem.text.strip().lower())

    # imapDependencies_2/Item/itypDepArray/Item
    for dep2 in root.iter('imapDependencies_2'):
        for item in dep2.iter('Item'):
            for ityp_item in item.iter('itypDepArray'):
                for sub_item in ityp_item.iter('Item'):
                    if sub_item.text and sub_item.text.strip():
                        result['ityp_names'].add(sub_item.text.strip().lower())

    # MapDataGroups/Item/Bounds/Item
    for mdg in root.iter('MapDataGroups'):
        for item in mdg.iter('Item'):
            for bounds in item.iter('Bounds'):
                for bound_item in bounds.iter('Item'):
                    if bound_item.text and bound_item.text.strip():
                        result['ybn_names'].add(bound_item.text.strip().lower())

    return result


def parse_ymap(path: Path) -> Optional[dict[str, object]]:
    """
    Parse a .ymap XML file to extract entity references.

    Args:
        path: Path to the .ymap or .ymap.xml file.

    Returns:
        Dict with keys 'name', 'archetype_names', 'physics_dictionaries',
        or None if parsing fails.
    """
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except (ET.ParseError, OSError, IOError):
        return None

    result: dict[str, object] = {
        'name': '',
        'archetype_names': set(),
        'physics_dictionaries': set()
    }

    # Get map name from <name> element or <block><name>
    name_elem = root.find('name')
    if name_elem is not None and name_elem.text and name_elem.text.strip():
        result['name'] = name_elem.text.strip().lower()
    else:
        block = root.find('.//block/name')
        if block is not None and block.text and block.text.strip():
            result['name'] = block.text.strip().lower()

    # archetypeNames from entities
    archetype_names: set[str] = set()
    for arch in root.iter('archetypeName'):
        if arch.text and arch.text.strip():
            val = arch.text.strip().lower()
            if val and val != 'null' and val != 'none':
                archetype_names.add(val)
    result['archetype_names'] = archetype_names

    # physicsDictionaries
    physics: set[str] = set()
    for pd in root.iter('physicsDictionaries'):
        for item in pd.iter('Item'):
            if item.text and item.text.strip():
                physics.add(item.text.strip().lower())
    result['physics_dictionaries'] = physics

    return result


def parse_ytyp(path: Path) -> Optional[dict[str, object]]:
    """
    Parse a .ytyp XML file to extract archetype references.

    Args:
        path: Path to the .ytyp or .ytyp.xml file.

    Returns:
        Dict with keys 'name', 'textures', 'clips', 'drawables',
        'assets_ydr', 'assets_yft', 'assets_ydd', 'assets_ybn',
        'physics_dicts', 'archetype_names',
        or None if parsing fails.
    """
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except (ET.ParseError, OSError, IOError):
        return None

    result: dict[str, object] = {
        'name': '',
        'textures': set(),
        'clips': set(),
        'drawables': set(),
        'assets_ydr': set(),
        'assets_yft': set(),
        'assets_ydd': set(),
        'assets_ybn': set(),
        'physics_dicts': set(),
        'archetype_names': set()
    }

    # Get ytyp name - direct child <name> of root
    name_elem = root.find('name')
    if name_elem is not None and name_elem.text and name_elem.text.strip():
        result['name'] = name_elem.text.strip().lower()

    # Process each archetype item
    for arch_item in root.iter('Item'):
        item_type = arch_item.get('type', '')
        if 'Archetype' not in item_type and item_type != '':
            # Only process archetype Items at the right level
            pass

        # Archetype name
        name_el = arch_item.find('name')
        if name_el is not None and name_el.text and name_el.text.strip():
            val = name_el.text.strip().lower()
            if val and val != 'null':
                result['archetype_names'].add(val)

        # textureDictionary
        td = arch_item.find('textureDictionary')
        if td is not None and td.text and td.text.strip():
            val = td.text.strip().lower()
            if val and val != 'null' and val != 'none':
                result['textures'].add(val)

        # clipDictionary
        cd = arch_item.find('clipDictionary')
        if cd is not None and cd.text and cd.text.strip():
            val = cd.text.strip().lower()
            if val and val != 'null' and val != 'none':
                result['clips'].add(val)

        # drawableDictionary
        dd = arch_item.find('drawableDictionary')
        if dd is not None and dd.text and dd.text.strip():
            val = dd.text.strip().lower()
            if val and val != 'null' and val != 'none':
                result['drawables'].add(val)

        # physicsDictionary
        phd = arch_item.find('physicsDictionary')
        if phd is not None and phd.text and phd.text.strip():
            val = phd.text.strip().lower()
            if val and val != 'null' and val != 'none':
                result['physics_dicts'].add(val)

        # assetName + assetType
        asset_name_el = arch_item.find('assetName')
        asset_type_el = arch_item.find('assetType')
        if (asset_name_el is not None and asset_name_el.text and
                asset_name_el.text.strip() and
                asset_type_el is not None and asset_type_el.text):
            asset_name = asset_name_el.text.strip().lower()
            asset_type = asset_type_el.text.strip()

            if asset_name and asset_name != 'null':
                if asset_type == 'ASSET_TYPE_DRAWABLE':
                    result['assets_ydr'].add(asset_name)
                elif asset_type == 'ASSET_TYPE_FRAGMENT':
                    result['assets_yft'].add(asset_name)
                elif asset_type == 'ASSET_TYPE_DRAWABLEDICTIONARY':
                    result['assets_ydd'].add(asset_name)
                elif asset_type == 'ASSET_TYPE_ASSETLESS':
                    result['assets_ybn'].add(asset_name)

    return result


def _clean_basename(name: str) -> str:
    """
    Iteratively remove known suffixes from a basename for grouping.

    Args:
        name: The basename to clean (lowercase).

    Returns:
        Cleaned basename with all known suffixes removed.
    """
    prev = ''
    cleaned = name
    while cleaned != prev:
        prev = cleaned
        cleaned = SUFFIX_CLEANUP_PATTERN.sub('', cleaned)
    return cleaned


def _determine_group_name(file_keys: list[str], file_infos: dict[str, FileInfo]) -> str:
    """
    Determine the best name for a resource group.

    Priority: .ymf basename > .ymap basename > .ytyp basename > longest cleaned name.

    Args:
        file_keys: List of file keys in this group.
        file_infos: Dict mapping key to FileInfo.

    Returns:
        The determined resource name.
    """
    # Check for .ymf (non-_manifest)
    for key in file_keys:
        info = file_infos.get(key)
        if info and info.extension == '.ymf':
            name = info.basename_original
            if name.lower().startswith('_manifest'):
                continue
            return name

    # Check for .ytyp first (it usually has the canonical resource name)
    ytyp_names: list[str] = []
    for key in file_keys:
        info = file_infos.get(key)
        if info and info.extension == '.ytyp' and not info.hi_prefix:
            ytyp_names.append(info.basename_original)
    if ytyp_names:
        # Prefer shortest name (most likely the base resource name)
        ytyp_names.sort(key=lambda n: len(n))
        return ytyp_names[0]

    # Check for .ymap - prefer the shortest non-suffix name
    ymap_names: list[str] = []
    for key in file_keys:
        info = file_infos.get(key)
        if info and info.extension == '.ymap' and not info.hi_prefix:
            ymap_names.append(info.basename_original)
    if ymap_names:
        # Prefer shortest name (base map, not _interior, _lod variants)
        ymap_names.sort(key=lambda n: len(n))
        return ymap_names[0]

    # Fallback: longest cleaned basename
    best_name = ''
    best_cleaned = ''
    for key in file_keys:
        info = file_infos.get(key)
        if info:
            cleaned = _clean_basename(info.base_without_hi)
            if len(cleaned) > len(best_cleaned):
                best_cleaned = cleaned
                best_name = cleaned

    return best_name if best_name else 'unnamed_resource'


def _determine_method(file_keys: list[str], file_infos: dict[str, FileInfo],
                      ymf_parsed: set[str], xml_parsed: set[str]) -> str:
    """
    Determine how a group was identified.

    Args:
        file_keys: List of file keys in this group.
        file_infos: Dict mapping key to FileInfo.
        ymf_parsed: Set of keys that were connected via YMF parsing.
        xml_parsed: Set of keys that were connected via XML parsing.

    Returns:
        'YMF', 'XML', or 'NAME'.
    """
    for key in file_keys:
        if key in ymf_parsed:
            return 'YMF'
    for key in file_keys:
        if key in xml_parsed:
            return 'XML'
    return 'NAME'


def _classify_file(info: FileInfo) -> str:
    """
    Classify a file into stream, meta, script, or unclassified.

    Args:
        info: FileInfo for the file.

    Returns:
        'stream', 'meta', 'script', or 'unclassified'.
    """
    ext = info.extension
    filename_lower = info.path.name.lower()

    if ext in STREAM_EXTENSIONS:
        return 'stream'
    elif ext in META_EXTENSIONS:
        return 'meta'
    elif ext == SCRIPT_EXTENSION:
        if filename_lower in ('fxmanifest.lua', '__resource.lua'):
            return 'unclassified'
        return 'script'
    else:
        return 'unclassified'


def scan_folder(source: Path, include_subfolders: bool = False,
                progress_callback: Optional[callable] = None) -> tuple[list[MapResource], list[Path]]:
    """
    Scan a source folder and group files into FiveM resources.

    Implements the complete algorithm from Sections 1-3 of the specification:
    Steps A through F.

    Args:
        source: Path to the source folder containing mixed map files.
        include_subfolders: Whether to scan subdirectories recursively.
        progress_callback: Optional callback(current, total, message) for progress.

    Returns:
        Tuple of (list of MapResource groups, list of unclassified file paths).
    """
    # === STEP A: Initial Inventory ===
    all_files: list[Path] = []
    if include_subfolders:
        for p in source.rglob('*'):
            if p.is_file():
                all_files.append(p)
    else:
        for p in source.iterdir():
            if p.is_file():
                all_files.append(p)

    if not all_files:
        return [], []

    total_files = len(all_files)

    # Build FileInfo for each file
    file_infos: dict[str, FileInfo] = {}  # key = absolute path string
    # Lookup: base_name_lower -> list of file keys
    basename_lookup: dict[str, list[str]] = defaultdict(list)
    # Lookup without hi@: base_without_hi_lower -> list of file keys
    base_no_hi_lookup: dict[str, list[str]] = defaultdict(list)

    for filepath in all_files:
        info = FileInfo.from_path(filepath)
        key = str(filepath)
        file_infos[key] = info
        basename_lookup[info.basename].append(key)
        base_no_hi_lookup[info.base_without_hi].append(key)

    if progress_callback:
        progress_callback(10, 100, "Inventory complete...")

    # === STEP B: Parse all readable content files ===
    uf = UnionFind()
    for key in file_infos:
        uf.make_set(key)

    # Track which keys were connected by which method
    ymf_connected: set[str] = set()
    xml_connected: set[str] = set()

    # Parse .ymf files (binary extraction)
    ymf_files = [k for k, v in file_infos.items() if v.extension == '.ymf']
    for ymf_key in ymf_files:
        info = file_infos[ymf_key]
        # Try XML parse first (if .xml companion exists)
        xml_path = info.path.with_suffix('.ymf.xml')
        xml_refs: set[str] = set()

        if xml_path.exists():
            parsed_xml = parse_ymf_xml(xml_path)
            xml_refs = (parsed_xml['imap_names'] |
                        parsed_xml['ityp_names'] |
                        parsed_xml['ybn_names'])

        # Binary extraction
        binary_refs = parse_ymf_binary(info.path)

        # Combine all references
        all_refs = xml_refs | binary_refs

        # Connect ymf to all referenced files that exist in source
        for ref_name in all_refs:
            ref_lower = ref_name.lower()
            # Check basename lookup
            if ref_lower in basename_lookup:
                for target_key in basename_lookup[ref_lower]:
                    uf.union(ymf_key, target_key)
                    ymf_connected.add(ymf_key)
                    ymf_connected.add(target_key)
            # Check base_no_hi lookup
            if ref_lower in base_no_hi_lookup:
                for target_key in base_no_hi_lookup[ref_lower]:
                    uf.union(ymf_key, target_key)
                    ymf_connected.add(ymf_key)
                    ymf_connected.add(target_key)

    if progress_callback:
        progress_callback(30, 100, "YMF parsing complete...")

    # Parse .ymap files (XML)
    ymap_files = [k for k, v in file_infos.items() if v.extension == '.ymap']
    for ymap_key in ymap_files:
        info = file_infos[ymap_key]
        parsed = parse_ymap(info.path)
        if parsed is None:
            continue

        refs: set[str] = set()
        refs.update(parsed['archetype_names'])
        refs.update(parsed['physics_dictionaries'])

        for ref_name in refs:
            ref_lower = ref_name.lower()
            if ref_lower in basename_lookup:
                for target_key in basename_lookup[ref_lower]:
                    uf.union(ymap_key, target_key)
                    xml_connected.add(ymap_key)
                    xml_connected.add(target_key)
            if ref_lower in base_no_hi_lookup:
                for target_key in base_no_hi_lookup[ref_lower]:
                    uf.union(ymap_key, target_key)
                    xml_connected.add(ymap_key)
                    xml_connected.add(target_key)

    if progress_callback:
        progress_callback(50, 100, "YMAP parsing complete...")

    # Parse .ytyp files (XML)
    ytyp_files = [k for k, v in file_infos.items() if v.extension == '.ytyp']
    for ytyp_key in ytyp_files:
        info = file_infos[ytyp_key]
        parsed = parse_ytyp(info.path)
        if parsed is None:
            continue

        refs: set[str] = set()
        refs.update(parsed['textures'])
        refs.update(parsed['clips'])
        refs.update(parsed['drawables'])
        refs.update(parsed['assets_ydr'])
        refs.update(parsed['assets_yft'])
        refs.update(parsed['assets_ydd'])
        refs.update(parsed['assets_ybn'])
        refs.update(parsed['physics_dicts'])
        refs.update(parsed['archetype_names'])

        for ref_name in refs:
            ref_lower = ref_name.lower()
            if ref_lower in basename_lookup:
                for target_key in basename_lookup[ref_lower]:
                    uf.union(ytyp_key, target_key)
                    xml_connected.add(ytyp_key)
                    xml_connected.add(target_key)
            if ref_lower in base_no_hi_lookup:
                for target_key in base_no_hi_lookup[ref_lower]:
                    uf.union(ytyp_key, target_key)
                    xml_connected.add(ytyp_key)
                    xml_connected.add(target_key)

    if progress_callback:
        progress_callback(65, 100, "YTYP parsing complete...")

    # === STEP C & D: hi@ convention - connect hi@ files to their base ===
    for key, info in file_infos.items():
        if info.hi_prefix:
            # Find base file (without hi@ prefix)
            base_name = info.base_without_hi
            if base_name in basename_lookup:
                for base_key in basename_lookup[base_name]:
                    uf.union(key, base_key)

    if progress_callback:
        progress_callback(75, 100, "Hi@ convention applied...")

    # === STEP E: Fallback regex grouping for unconnected files ===
    # Connect all groups by cleaned basename. This handles:
    # - Singletons (1 file) that share a cleaned base with a larger group
    # - Small groups (e.g., file + hi@ pair) that share a cleaned base with larger groups
    # - Multiple singletons that share the same cleaned base

    # Build a mapping: cleaned_name -> list of (representative, group_size)
    groups = uf.get_groups()
    cleaned_to_groups: dict[str, list[tuple[str, int]]] = defaultdict(list)

    for rep, members in groups.items():
        # Compute all cleaned names for this group
        group_cleaned_names: set[str] = set()
        for key in members:
            info = file_infos[key]
            cleaned = _clean_basename(info.base_without_hi)
            group_cleaned_names.add(cleaned)

        for cn in group_cleaned_names:
            cleaned_to_groups[cn].append((rep, len(members)))

    # For each cleaned name that maps to multiple groups, union them all together
    for cleaned_name, group_list in cleaned_to_groups.items():
        if len(group_list) > 1:
            # Find a representative from the largest group
            group_list.sort(key=lambda x: x[1], reverse=True)
            primary_rep = group_list[0][0]
            # Find an actual key with this representative
            primary_key: Optional[str] = None
            for key in file_infos:
                if uf.find(key) == primary_rep:
                    primary_key = key
                    break
            if primary_key:
                for other_rep, _ in group_list[1:]:
                    # Find a key from the other group
                    for key in file_infos:
                        if uf.find(key) == other_rep:
                            uf.union(primary_key, key)
                            break

    if progress_callback:
        progress_callback(85, 100, "Fallback grouping complete...")

    # === STEP F: Build final MapResource objects ===
    final_groups_result = uf.get_groups()

    resources: list[MapResource] = []
    unclassified_paths: list[Path] = []

    for rep, members in final_groups_result.items():
        # Classify all files in this group
        stream: list[Path] = []
        meta: list[Path] = []
        scripts: list[Path] = []
        unclassified: list[Path] = []
        has_known_ext = False

        for key in members:
            info = file_infos[key]
            classification = _classify_file(info)
            ext = info.extension

            # Check if this file has a known FiveM extension
            if ext in STREAM_EXTENSIONS or ext in META_EXTENSIONS or ext == SCRIPT_EXTENSION:
                has_known_ext = True

            if classification == 'stream':
                stream.append(info.path)
            elif classification == 'meta':
                meta.append(info.path)
            elif classification == 'script':
                scripts.append(info.path)
            else:
                unclassified.append(info.path)

        # If group has no known FiveM extensions at all, send to unclassified
        if not has_known_ext:
            for key in members:
                unclassified_paths.append(file_infos[key].path)
            continue

        # Determine group name
        group_name = _determine_group_name(members, file_infos)

        # Handle _manifest prefix
        if group_name.lower() == '_manifest':
            # Try to find better name from other files
            for key in members:
                info = file_infos[key]
                if info.extension in ('.ymap', '.ytyp') and not info.hi_prefix:
                    group_name = info.basename_original
                    break

        # Determine method
        method = _determine_method(members, file_infos, ymf_connected, xml_connected)

        resource = MapResource(
            name=group_name,
            stream_files=sorted(stream, key=lambda p: p.name.lower()),
            meta_files=sorted(meta, key=lambda p: p.name.lower()),
            script_files=sorted(scripts, key=lambda p: p.name.lower()),
            unclassified_files=sorted(unclassified, key=lambda p: p.name.lower()),
            method=method
        )
        resource.compute_status()

        # Move unclassified files from within a valid group to global unclassified
        # only if the group itself has valid files
        if resource.stream_files or resource.meta_files or resource.script_files:
            resources.append(resource)
            # Keep unclassified files within the resource for now
        else:
            # Entire group is unclassified
            for key in members:
                unclassified_paths.append(file_infos[key].path)

    if progress_callback:
        progress_callback(100, 100, "Scan complete!")

    # Sort resources by name
    resources.sort(key=lambda r: r.name.lower())

    return resources, unclassified_paths
