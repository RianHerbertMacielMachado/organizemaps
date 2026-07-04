"""
FiveM Map Organizer - Core Scanner Module.

Implements prefix-based clustering algorithm for grouping
GTA V/FiveM map files into proper resources.

Works with both XML and binary RSC7 format files.
When files are binary (most real-world cases), grouping relies entirely
on filename-based heuristics using prefix clustering.
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

# Known variant suffixes that indicate same logical model/map
# These are stripped iteratively to find the "base name" of a file
VARIANT_SUFFIXES: list[str] = [
    '_col', '_occ', '_lod', '_lod0', '_lod1', '_lod2',
    '_slod', '_slod2', '_slod3', '_slod4',
    '_detail', '_detail1', '_detail2', '_detail3', '_detail4',
    '_ext', '_ext2', '_ext3', '_ext4',
    '_shell', '_shadow', '_proxy', '_physics',
    '_interior', '_milo_', '_milo',
    '_hi', '+hi', '_hd',
]

# Suffix cleanup regex for legacy compatibility
SUFFIX_CLEANUP_PATTERN: re.Pattern = re.compile(
    r'(_lod\d*|_hi|\+hi|_slod\d*|_col|_shadow|_detail\d*|_decal|_proxy|_physics|_interior|_\d+)$',
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
        path = []
        while self._parent[x] != x:
            path.append(x)
            x = self._parent[x]
        for p in path:
            self._parent[p] = x
        return x

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


def _strip_variant_suffixes(name: str) -> str:
    """
    Iteratively strip known variant suffixes from a name.

    Args:
        name: The filename basename (lowercase, no extension).

    Returns:
        Base name with all known suffixes removed.
    """
    changed = True
    while changed:
        changed = False
        for suf in VARIANT_SUFFIXES:
            if name.endswith(suf):
                name = name[:-len(suf)]
                changed = True
                break
    return name


def _strip_trailing_letter_variant(name: str) -> str:
    """
    Strip trailing single lowercase letter after a digit.

    Handles patterns like: quebradashop10a -> quebradashop10
    But NOT: quebradashop (no digit before letter)

    Args:
        name: The base name.

    Returns:
        Name with trailing letter variant stripped.
    """
    if len(name) >= 3 and name[-1].isalpha() and name[-2].isdigit():
        return name[:-1]
    return name


def _get_grouping_key(name: str) -> str:
    """
    Compute the grouping key for a filename.

    This determines which files should be in the same resource group.
    The key is derived by:
    1. Stripping leading single digit prefix (1xxx, 2xxx -> xxx)
    2. Stripping known variant suffixes (_col, _ext, _shell, etc.)
    3. Stripping trailing letter variants after digits (10a -> 10)
    4. Stripping trailing digits for numbered model series (shop10 -> shop)

    Args:
        name: Lowercase basename without extension and without hi@ prefix.

    Returns:
        The grouping key string.
    """
    key = name

    # Step 0: Strip leading single digit prefix for variant numbering
    # Handles: 1quebradashop, 2quebradashop -> quebradashop
    # Also: 1qs_bandeira, 2qs_bandeira -> qs_bandeira
    # Rule: only strip if a single digit precedes a letter AND
    # the remaining name is >= 5 chars
    if (len(key) >= 6 and key[0].isdigit() and
            not key[1].isdigit() and key[1].isalpha()):
        key = key[1:]

    # Step 1: Strip variant suffixes
    key = _strip_variant_suffixes(key)

    # Step 2: Strip trailing letter variant (e.g., "10a" -> "10")
    key = _strip_trailing_letter_variant(key)

    # Step 3: Strip trailing digits for numbered series
    # This handles: quebradashop10, quebradashop11 -> quebradashop
    # But we need to be careful not to strip meaningful numbers
    # Rule: strip trailing digits ONLY if what remains is >= 5 chars
    # and the digits are at the very end
    stripped = key.rstrip('0123456789')
    if stripped and len(stripped) >= 5 and stripped != key:
        key = stripped

    return key


def _extract_ymf_resource_name(filename: str) -> Optional[str]:
    """
    Extract resource name from a .ymf manifest filename.

    Patterns:
        _manifestXXX.ymf -> XXX
        manifest_XXX.ymf -> XXX
        XXX_manifest.ymf -> XXX
        manifestXXX.ymf -> XXX (if not 'manifest_')

    Args:
        filename: The .ymf filename (with extension).

    Returns:
        Resource name or None if not a manifest file.
    """
    name = filename.rsplit('.', 1)[0].lower()

    if name.startswith('_manifest') and len(name) > 9:
        return name[9:]
    elif name.startswith('manifest_') and len(name) > 9:
        return name[9:]
    elif name.endswith('_manifest'):
        return name[:-9]
    elif (name.startswith('manifest') and
          not name.startswith('manifest_') and
          len(name) > 8):
        return name[8:]

    return None


def _get_match_name(filename: str) -> str:
    """
    Get the normalized name for prefix matching.

    Strips extension, lowercases, removes hi@ prefix.

    Args:
        filename: The original filename.

    Returns:
        Normalized match name.
    """
    name = filename.rsplit('.', 1)[0].lower() if '.' in filename else filename.lower()
    if name.startswith('hi@'):
        name = name[3:]
    return name


def parse_ymf_binary(path: Path) -> set[str]:
    """
    Extract ASCII string references from a binary .ymf file.

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

    # Check for STRS section (PSO format)
    strs_pos = data.find(b'STRS')
    if strs_pos >= 0:
        strs_section = data[strs_pos + 4:]
        strs_matches = re.findall(rb'([a-zA-Z][a-zA-Z0-9_@]{2,63})', strs_section)
        for m in strs_matches:
            try:
                name = m.decode('ascii').lower()
                if name not in ('strs', 'chks', 'psin', 'pmap', 'psch', 'psig', 'zvnp', 'yppp'):
                    names.add(name)
            except (UnicodeDecodeError, ValueError):
                continue

    # Scan for string patterns
    matches1 = re.findall(rb'(?<!\x00)([a-zA-Z][a-zA-Z0-9_@]{2,63})(?=\x00)', data)
    matches2 = re.findall(rb'\x00([a-zA-Z][a-zA-Z0-9_@]{2,63})\x00', data)

    for m in matches1 + matches2:
        try:
            name = m.decode('ascii').lower()
            if name in ('psin', 'pmap', 'psch', 'psig', 'zvnp', 'strs', 'chks', 'yppp',
                        'null', 'none', 'false', 'true', 'string', 'array'):
                continue
            if len(name) >= 3:
                names.add(name)
        except (UnicodeDecodeError, ValueError):
            continue

    return names


def parse_ymap(path: Path) -> Optional[dict[str, object]]:
    """
    Parse a .ymap XML file to extract entity references.

    Args:
        path: Path to the .ymap file.

    Returns:
        Dict with references or None if binary/unparseable.
    """
    try:
        # Quick check if it's binary RSC7
        with open(path, 'rb') as f:
            magic = f.read(4)
        if magic == b'RSC7':
            return None  # Binary format, cannot parse XML

        tree = ET.parse(path)
        root = tree.getroot()
    except (ET.ParseError, OSError, IOError):
        return None

    result: dict[str, object] = {
        'name': '',
        'archetype_names': set(),
        'physics_dictionaries': set()
    }

    name_elem = root.find('name')
    if name_elem is not None and name_elem.text and name_elem.text.strip():
        result['name'] = name_elem.text.strip().lower()

    archetype_names: set[str] = set()
    for arch in root.iter('archetypeName'):
        if arch.text and arch.text.strip():
            val = arch.text.strip().lower()
            if val and val != 'null' and val != 'none':
                archetype_names.add(val)
    result['archetype_names'] = archetype_names

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
        path: Path to the .ytyp file.

    Returns:
        Dict with references or None if binary/unparseable.
    """
    try:
        with open(path, 'rb') as f:
            magic = f.read(4)
        if magic == b'RSC7':
            return None  # Binary format

        tree = ET.parse(path)
        root = tree.getroot()
    except (ET.ParseError, OSError, IOError):
        return None

    result: dict[str, object] = {
        'name': '',
        'textures': set(),
        'drawables': set(),
        'assets_ydr': set(),
        'assets_yft': set(),
        'archetype_names': set()
    }

    name_elem = root.find('name')
    if name_elem is not None and name_elem.text and name_elem.text.strip():
        result['name'] = name_elem.text.strip().lower()

    for arch_item in root.iter('Item'):
        name_el = arch_item.find('name')
        if name_el is not None and name_el.text and name_el.text.strip():
            val = name_el.text.strip().lower()
            if val and val != 'null':
                result['archetype_names'].add(val)

        td = arch_item.find('textureDictionary')
        if td is not None and td.text and td.text.strip():
            val = td.text.strip().lower()
            if val and val != 'null' and val != 'none':
                result['textures'].add(val)

        dd = arch_item.find('drawableDictionary')
        if dd is not None and dd.text and dd.text.strip():
            val = dd.text.strip().lower()
            if val and val != 'null' and val != 'none':
                result['drawables'].add(val)

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

    return result


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


def _determine_group_name(file_keys: list[str], file_infos: dict[str, FileInfo],
                          ymf_resource_names: dict[str, str]) -> str:
    """
    Determine the best name for a resource group.

    Priority:
    1. YMF-derived resource name (if a _manifest*.ymf is in the group)
    2. .ymap basename (shortest, non-suffix)
    3. .ytyp basename (shortest)
    4. Shortest non-hi@ filename in the group

    Args:
        file_keys: List of file keys in this group.
        file_infos: Dict mapping key to FileInfo.
        ymf_resource_names: Dict mapping ymf filename -> resource name.

    Returns:
        The determined resource name.
    """
    # Check for .ymf manifest in group -> use its resource name
    for key in file_keys:
        info = file_infos.get(key)
        if info and info.extension == '.ymf':
            rname = _extract_ymf_resource_name(info.path.name)
            if rname and len(rname) >= 3:
                return rname

    # Check for .ymap (shortest basename)
    ymap_names = []
    for key in file_keys:
        info = file_infos.get(key)
        if info and info.extension == '.ymap' and not info.hi_prefix:
            ymap_names.append(info.base_without_hi)
    if ymap_names:
        ymap_names.sort(key=len)
        return ymap_names[0]

    # Check for .ytyp
    ytyp_names = []
    for key in file_keys:
        info = file_infos.get(key)
        if info and info.extension == '.ytyp' and not info.hi_prefix:
            ytyp_names.append(info.base_without_hi)
    if ytyp_names:
        ytyp_names.sort(key=len)
        return ytyp_names[0]

    # Fallback: shortest basename
    all_names = []
    for key in file_keys:
        info = file_infos.get(key)
        if info and not info.hi_prefix:
            all_names.append(info.base_without_hi)
    if all_names:
        all_names.sort(key=len)
        return all_names[0]

    return 'unnamed_resource'


def scan_folder(source: Path, include_subfolders: bool = False,
                progress_callback: Optional[callable] = None) -> tuple[list[MapResource], list[Path]]:
    """
    Scan a source folder and group files into FiveM resources.

    Uses a multi-phase algorithm:
    Phase 1: Inventory all files
    Phase 2: Try XML-based dependency linking (for non-binary files)
    Phase 3: hi@ convention linking
    Phase 4: Prefix-based clustering using grouping keys
    Phase 5: Merge small groups into larger ones with shared prefix
    Phase 6: Build final MapResource objects

    Args:
        source: Path to the source folder containing mixed map files.
        include_subfolders: Whether to scan subdirectories recursively.
        progress_callback: Optional callback(current, total, message) for progress.

    Returns:
        Tuple of (list of MapResource groups, list of unclassified file paths).
    """
    # === PHASE 1: Initial Inventory ===
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

    # Build FileInfo for each file
    file_infos: dict[str, FileInfo] = {}  # key = absolute path string
    basename_lookup: dict[str, list[str]] = defaultdict(list)
    base_no_hi_lookup: dict[str, list[str]] = defaultdict(list)

    for filepath in all_files:
        info = FileInfo.from_path(filepath)
        key = str(filepath)
        file_infos[key] = info
        basename_lookup[info.basename].append(key)
        base_no_hi_lookup[info.base_without_hi].append(key)

    if progress_callback:
        progress_callback(10, 100, "Inventário completo...")

    # Extract YMF resource names for naming
    ymf_resource_names: dict[str, str] = {}  # filename -> resource_name
    for key, info in file_infos.items():
        if info.extension == '.ymf':
            rname = _extract_ymf_resource_name(info.path.name)
            if rname:
                ymf_resource_names[info.path.name.lower()] = rname

    # === PHASE 2: XML-based dependency linking (only for non-binary files) ===
    uf = UnionFind()
    for key in file_infos:
        uf.make_set(key)

    xml_connected: set[str] = set()

    # Try parsing .ymap files
    ymap_files = [k for k, v in file_infos.items() if v.extension == '.ymap']
    for ymap_key in ymap_files:
        info = file_infos[ymap_key]
        parsed = parse_ymap(info.path)
        if parsed is None:
            continue  # Binary RSC7, skip

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
        progress_callback(25, 100, "Análise XML completa...")

    # Try parsing .ytyp files
    ytyp_files = [k for k, v in file_infos.items() if v.extension == '.ytyp']
    for ytyp_key in ytyp_files:
        info = file_infos[ytyp_key]
        parsed = parse_ytyp(info.path)
        if parsed is None:
            continue

        refs: set[str] = set()
        refs.update(parsed.get('textures', set()))
        refs.update(parsed.get('drawables', set()))
        refs.update(parsed.get('assets_ydr', set()))
        refs.update(parsed.get('assets_yft', set()))
        refs.update(parsed.get('archetype_names', set()))

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
        progress_callback(40, 100, "Análise YTYP completa...")

    # === PHASE 3: hi@ convention ===
    for key, info in file_infos.items():
        if info.hi_prefix:
            base_name = info.base_without_hi
            if base_name in basename_lookup:
                for base_key in basename_lookup[base_name]:
                    uf.union(key, base_key)

    if progress_callback:
        progress_callback(50, 100, "Convenção hi@ aplicada...")

    # === PHASE 4: Prefix-based clustering using grouping keys ===
    # Compute grouping key for each file
    key_to_group_key: dict[str, str] = {}
    group_key_members: dict[str, list[str]] = defaultdict(list)

    for key, info in file_infos.items():
        match_name = info.base_without_hi
        gk = _get_grouping_key(match_name)
        key_to_group_key[key] = gk
        group_key_members[gk].append(key)

    # Union all files sharing the same grouping key
    for gk, members in group_key_members.items():
        if len(members) > 1:
            first = members[0]
            for other in members[1:]:
                uf.union(first, other)

    if progress_callback:
        progress_callback(65, 100, "Agrupamento por chave completo...")

    # === PHASE 5: Merge groups that share prefix at underscore boundary ===
    # Get current groups and their grouping keys
    current_groups = uf.get_groups()

    # For each group, compute a "group prefix" from its members' grouping keys
    group_prefixes: dict[str, str] = {}  # representative -> prefix
    for rep, members in current_groups.items():
        # Collect all grouping keys in this group
        gkeys = set()
        for m in members:
            gkeys.add(key_to_group_key[m])
        # The group prefix is the LCP of all grouping keys
        sorted_gkeys = sorted(gkeys)
        if len(sorted_gkeys) == 1:
            group_prefixes[rep] = sorted_gkeys[0]
        else:
            first = sorted_gkeys[0]
            last = sorted_gkeys[-1]
            lcp = 0
            for k in range(min(len(first), len(last))):
                if first[k] == last[k]:
                    lcp += 1
                else:
                    break
            group_prefixes[rep] = first[:lcp] if lcp >= 3 else sorted_gkeys[0]

    # Identify which groups contain a .ymf manifest (these should NOT be merged together)
    groups_with_ymf: set[str] = set()
    for rep, members in current_groups.items():
        for m in members:
            if file_infos[m].extension == '.ymf':
                groups_with_ymf.add(rep)
                break

    # Sort groups by their prefix for adjacent merging
    sorted_reps = sorted(current_groups.keys(), key=lambda r: group_prefixes.get(r, ''))

    # Merge adjacent groups sharing prefix at _ boundary
    for i in range(len(sorted_reps) - 1):
        rep1 = sorted_reps[i]
        rep2 = sorted_reps[i + 1]

        # CRITICAL: Never merge two groups if BOTH contain a .ymf manifest
        # Each manifest defines its own separate resource
        if rep1 in groups_with_ymf and rep2 in groups_with_ymf:
            continue

        prefix1 = group_prefixes.get(rep1, '')
        prefix2 = group_prefixes.get(rep2, '')

        # Compute common prefix
        cp_len = 0
        for k in range(min(len(prefix1), len(prefix2))):
            if prefix1[k] == prefix2[k]:
                cp_len += 1
            else:
                break

        if cp_len < 5:
            continue

        prefix = prefix1[:cp_len]
        r1 = prefix1[cp_len:]
        r2 = prefix2[cp_len:]

        # Merge rules
        should_merge = False

        # Key rule: if the shared prefix ends with underscore, everything
        # after it is a sub-variant of the same parent resource
        # e.g., "1quebradashop_" + "comercio" vs "predinho" -> same resource
        if prefix.endswith('_') and cp_len >= 6:
            should_merge = True
        # Both diverge at underscore or end
        elif (not r1 or r1[0] == '_') and (not r2 or r2[0] == '_'):
            should_merge = True
        # One ends, other has underscore
        elif (not r1 and r2 and r2[0] == '_') or (not r2 and r1 and r1[0] == '_'):
            should_merge = True
        # One ends, other continues without underscore
        elif (not r1 or not r2):
            longer = r1 if r1 else r2
            if longer and longer[0].isdigit() and cp_len >= 6:
                # Digit continuation (e.g., "shop10" vs "shop")
                should_merge = True
            elif longer and len(longer) <= 6 and cp_len >= 12:
                # Short extension of a long common prefix
                # e.g., "quebradashopgraf" + "atl" (16 char prefix, 3 char extension)
                should_merge = True
        # Both continue without underscore but prefix contains underscore
        # and is long enough (e.g., "quebradashop_v3" prefix with "9" vs "10")
        elif '_' in prefix and cp_len >= 10:
            should_merge = True

        if should_merge:
            # Find actual keys from each group to union
            key1 = current_groups[rep1][0]
            key2 = current_groups[rep2][0]
            uf.union(key1, key2)

    if progress_callback:
        progress_callback(75, 100, "Mesclagem de prefixos completa...")

    # === PHASE 5.5: YMF Anchoring ===
    # Manifests define resources — absorb orphan groups into manifest groups
    phase55_groups = uf.get_groups()

    # Identify groups that contain a _manifest*.ymf
    manifest_groups: dict[str, str] = {}  # resource_name -> representative key of manifest group
    manifest_reps: set[str] = set()       # representatives that have manifests

    for rep, members in phase55_groups.items():
        for m in members:
            info = file_infos[m]
            if info.extension == '.ymf':
                rname = _extract_ymf_resource_name(info.path.name)
                if rname and len(rname) >= 3:
                    manifest_groups[rname] = rep
                    manifest_reps.add(rep)
                    break

    if manifest_groups:
        # Find groups WITHOUT a manifest
        orphan_reps = [r for r in phase55_groups if r not in manifest_reps]

        # Strategy 1: If there's exactly 1 manifest and the total file count is
        # relatively small (<=100), this is likely a single-resource folder.
        # Absorb ALL orphan groups into the manifest group.
        total_file_count = len(file_infos)
        if len(manifest_groups) == 1 and total_file_count <= 100:
            manifest_rep_key = list(manifest_groups.values())[0]
            manifest_any_member = phase55_groups[manifest_rep_key][0]
            for orphan_rep in orphan_reps:
                orphan_any_member = phase55_groups[orphan_rep][0]
                uf.union(manifest_any_member, orphan_any_member)
        else:
            # Strategy 2: For large multi-manifest datasets, absorb orphan groups
            # whose grouping key contains the manifest resource name as a substring
            # or starts with it.
            for orphan_rep in orphan_reps:
                orphan_members = phase55_groups[orphan_rep]
                # Get the set of grouping keys in this orphan group
                orphan_gkeys = set()
                for m in orphan_members:
                    orphan_gkeys.add(key_to_group_key[m])

                # Check each manifest for a match
                best_manifest = None
                best_match_len = 0

                for rname, mrep in manifest_groups.items():
                    for ogk in orphan_gkeys:
                        # Match: grouping key starts with resource name
                        if ogk.startswith(rname) and len(rname) > best_match_len:
                            best_manifest = mrep
                            best_match_len = len(rname)
                        # Match: resource name starts with grouping key
                        elif rname.startswith(ogk) and len(ogk) >= 5 and len(ogk) > best_match_len:
                            best_manifest = mrep
                            best_match_len = len(ogk)

                if best_manifest and best_match_len >= 5:
                    manifest_member = phase55_groups[best_manifest][0]
                    orphan_member = orphan_members[0]
                    uf.union(manifest_member, orphan_member)

    if progress_callback:
        progress_callback(85, 100, "Ancoragem YMF completa...")

    # === PHASE 6: Build final MapResource objects ===
    final_groups = uf.get_groups()

    resources: list[MapResource] = []
    unclassified_paths: list[Path] = []

    for rep, members in final_groups.items():
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

        # If group has no known FiveM extensions, send to unclassified
        if not has_known_ext:
            for key in members:
                unclassified_paths.append(file_infos[key].path)
            continue

        # Determine group name
        group_name = _determine_group_name(members, file_infos, ymf_resource_names)

        # Determine method
        method = 'NAME'
        for key in members:
            if key in xml_connected:
                method = 'XML'
                break

        resource = MapResource(
            name=group_name,
            stream_files=sorted(stream, key=lambda p: p.name.lower()),
            meta_files=sorted(meta, key=lambda p: p.name.lower()),
            script_files=sorted(scripts, key=lambda p: p.name.lower()),
            unclassified_files=sorted(unclassified, key=lambda p: p.name.lower()),
            method=method
        )
        resource.compute_status()

        if resource.stream_files or resource.meta_files or resource.script_files:
            resources.append(resource)
        else:
            for key in members:
                unclassified_paths.append(file_infos[key].path)

    if progress_callback:
        progress_callback(100, 100, "Escaneamento completo!")

    # Sort resources by name
    resources.sort(key=lambda r: r.name.lower())

    return resources, unclassified_paths
