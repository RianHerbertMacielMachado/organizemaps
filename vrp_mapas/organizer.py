#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
organizer.py — FiveM Map Organizer v6.0

LÓGICA CENTRAL:
  1. Calcula joaat de cada arquivo da pasta → dicionário hash→arquivo
  2. Para cada .ymf binário: varre os bytes procurando hashes de 4 bytes
     que coincidam com arquivos .ymap ou .ytyp da pasta
  3. Para cada .ytyp XML encontrado: lê archetypes → name/textureDictionary
     → resolve .ydr, .ytd, .ybn, .yft na pasta pelo mesmo sistema de hash
  4. Cria recurso FiveM com todos os arquivos do grupo
"""

import sys
import shutil
import struct
import argparse
import logging
from pathlib import Path
from collections import defaultdict
import xml.etree.ElementTree as ET

from hash_resolver import build_reverse_map, joaat, is_hash

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("MapOrganizer")

ALL_MAP_EXTENSIONS = {
    ".ymap", ".ymf", ".ytyp",
    ".ydr", ".yft", ".ytd",
    ".ybn", ".ydd", ".ycd", ".obn",
}

NATIVE_PREFIXES = (
    "prop_", "v_", "apa_", "ba_", "bkr_", "ch_", "gr_",
    "h4_", "hei_", "int_", "p_", "sm_", "vw_", "xm_",
    "xs_", "ex_",
)


# ---------------------------------------------------------------------------
# UTILITÁRIOS
# ---------------------------------------------------------------------------

def is_xml(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            h = f.read(6)
        return h.startswith(b"<?xml") or h.startswith(b"<C") or h.startswith(b"<P")
    except Exception:
        return False


def safe_name(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9_\-]", "_", s.lower()).strip("_") or "map_unknown"


# ---------------------------------------------------------------------------
# PARSER BINÁRIO DO .ymf (PSO)
# Estratégia: varrer todos os grupos de 4 bytes little-endian
# e verificar se correspondem a algum arquivo .ymap ou .ytyp da pasta
# ---------------------------------------------------------------------------

def extract_hashes_from_binary(data: bytes) -> list[int]:
    """
    Extrai todos os valores uint32 possíveis de um arquivo binário.
    Retorna lista de inteiros únicos encontrados.
    """
    hashes = set()
    # Lê cada grupo de 4 bytes como uint32 little-endian
    for i in range(0, len(data) - 3, 1):
        val = struct.unpack_from("<I", data, i)[0]
        if val > 0:
            hashes.add(val)
    return list(hashes)


def find_files_in_binary(
    ymf_data: bytes,
    hash_to_file: dict[int, dict[str, Path]],
    target_exts: list[str]
) -> list[Path]:
    """
    Dado o conteúdo binário de um ymf, encontra arquivos da pasta
    cujos hashes aparecem no binário.
    """
    found: list[Path] = []
    seen: set[Path] = set()

    # Extrai todos os uint32 do binário
    all_uint32 = set()
    for i in range(0, len(ymf_data) - 3, 1):
        val = struct.unpack_from("<I", ymf_data, i)[0]
        if val > 0x0000FFFF:  # Filtra valores muito pequenos (ruído)
            all_uint32.add(val)

    # Verifica quais correspondem a arquivos com as extensões desejadas
    for h in all_uint32:
        if h in hash_to_file:
            file_dict = hash_to_file[h]
            for ext in target_exts:
                if ext in file_dict:
                    p = file_dict[ext]
                    if p not in seen:
                        seen.add(p)
                        found.append(p)

    return found


# ---------------------------------------------------------------------------
# PARSERS XML
# ---------------------------------------------------------------------------

def parse_ytyp_xml(path: Path, hash_to_file: dict) -> dict:
    """
    Lê CMapTypes XML e extrai para cada archetype:
    - name (hash ou texto)
    - textureDictionary
    - physicsDictionary
    - assetName
    - assetType
    Retorna lista de dicts.
    """
    archetypes = []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        log.warning(f"  [YTYP-XML] {path.name}: {e}")
        return archetypes

    for item in root.findall(".//archetypes/Item"):
        arch = {}
        for tag in ("name", "textureDictionary", "physicsDictionary",
                    "assetName", "assetType"):
            el = item.find(tag)
            if el is not None and el.text and el.text.strip():
                arch[tag] = el.text.strip().lower()
        if arch.get("name"):
            archetypes.append(arch)

    return archetypes


def parse_ymap_xml(path: Path) -> set[str]:
    """Extrai archetypeNames de um ymap XML."""
    names = set()
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return names

    for el in root.findall(".//entities/Item/archetypeName"):
        if el.text:
            names.add(el.text.strip().lower())
    for el in root.findall(".//archetypes/Item/entities/Item/archetypeName"):
        if el.text:
            names.add(el.text.strip().lower())
    return names


# ---------------------------------------------------------------------------
# ÍNDICE PRINCIPAL
# ---------------------------------------------------------------------------

class FileIndex:
    """
    Mantém dois índices:
      1. stem_lower → { ext → Path }        (busca por nome)
      2. hash_uint32 → { ext → Path }        (busca por hash JOAAT)
    """

    def __init__(self):
        # stem → {ext → Path}
        self.by_stem: dict[str, dict[str, Path]] = defaultdict(dict)
        # hash int → {ext → Path}
        self.by_hash: dict[int, dict[str, Path]] = defaultdict(dict)
        self.all_paths: list[Path] = []

    def add(self, path: Path):
        ext  = path.suffix.lower()
        stem = path.stem.lower()

        if ext not in self.by_stem[stem]:
            self.by_stem[stem][ext] = path
            self.all_paths.append(path)

            # Calcula hash do stem e indexa
            h = self._joaat_int(stem)
            self.by_hash[h][ext] = path

    @staticmethod
    def _joaat_int(s: str) -> int:
        key = s.lower().encode("utf-8")
        h = 0
        for byte in key:
            h = (h + byte) & 0xFFFFFFFF
            h = (h + (h << 10)) & 0xFFFFFFFF
            h ^= (h >> 6)
        h = (h + (h << 3)) & 0xFFFFFFFF
        h ^= (h >> 11)
        h = (h + (h << 15)) & 0xFFFFFFFF
        return h

    def find_by_name(self, name: str, ext: str) -> Path | None:
        """Busca por nome (texto ou hash 0x...)."""
        stem = name.lower().strip()
        ext  = ext.lower()

        # Tenta direto pelo stem
        p = self.by_stem.get(stem, {}).get(ext)
        if p:
            return p

        # Se for hash textual "0xABCD1234", converte para int e busca
        if stem.startswith("0x"):
            try:
                h = int(stem, 16)
                p = self.by_hash.get(h, {}).get(ext)
                if p:
                    return p
            except ValueError:
                pass

        # Se for nome normal, calcula o hash e busca
        if not stem.startswith("0x"):
            h = self._joaat_int(stem)
            p = self.by_hash.get(h, {}).get(ext)
            if p:
                return p

        return None

    def find_by_hash_int(self, h: int, ext: str) -> Path | None:
        """Busca diretamente por hash uint32."""
        return self.by_hash.get(h, {}).get(ext)

    def is_native(self, name: str) -> bool:
        """Retorna True se é prop nativo sem arquivo na pasta."""
        for ext in (".ydr", ".yft", ".ytd", ".ybn"):
            if self.find_by_name(name, ext):
                return False
        return name.lower().startswith(NATIVE_PREFIXES)


# ---------------------------------------------------------------------------
# ORGANIZADOR PRINCIPAL
# ---------------------------------------------------------------------------

class MapOrganizer:

    def __init__(self, input_dir: Path, output_dir: Path,
                 move_files=False, dry_run=False, verbose=False):
        self.input_dir  = input_dir
        self.output_dir = output_dir
        self.move_files = move_files
        self.dry_run    = dry_run
        self.index      = FileIndex()
        self.ymf_files: list[Path] = []
        self.attributed: set[Path] = set()

        if verbose:
            log.setLevel(logging.DEBUG)

    # ------------------------------------------------------------------
    # SCAN
    # ------------------------------------------------------------------

    def scan(self):
        log.info(f"Escaneando: {self.input_dir}")
        count = 0

        for path in self.input_dir.rglob("*"):
            if not path.is_file():
                continue
            ext = path.suffix.lower()
            if ext not in ALL_MAP_EXTENSIONS:
                continue
            self.index.add(path)
            count += 1
            if ext == ".ymf":
                self.ymf_files.append(path)

        log.info(f"  {count} arquivos indexados")
        log.info(f"  {len(self.ymf_files)} manifesto(s) .ymf encontrado(s)")

    # ------------------------------------------------------------------
    # RESOLUÇÃO DE UM .ymf
    # ------------------------------------------------------------------

    def resolve_ymf(self, ymf_path: Path) -> tuple[str, set[Path], list[str]]:
        """
        Para um .ymf (binário ou XML), resolve todos os arquivos do recurso.
        """
        files: set[Path] = {ymf_path}
        warnings: list[str] = []
        resource_name = ymf_path.stem.lower().lstrip("_")

        # ---- Lê o conteúdo do ymf ----
        ymf_data = ymf_path.read_bytes()

        # ---- Encontra ymaps referenciados ----
        # Estratégia: busca todos os uint32 do binário que correspondam
        # a um .ymap na pasta
        ymap_paths: list[Path] = []

        if is_xml(ymf_path):
            # Se for XML, parseia normalmente
            ymap_paths, ytyp_paths = self._parse_ymf_xml(ymf_path)
        else:
            # Se for binário PSO: varre bytes procurando hashes de .ymap
            log.debug(f"  [YMF-BIN] {ymf_path.name} → varredura binária")
            ymap_paths = find_files_in_binary(
                ymf_data, self.index.by_hash, [".ymap"]
            )
            ytyp_paths = find_files_in_binary(
                ymf_data, self.index.by_hash, [".ytyp"]
            )

        if not ymap_paths:
            warnings.append(f"Nenhum .ymap encontrado para {ymf_path.name}")
        if not ytyp_paths:
            log.debug(f"  Nenhum .ytyp encontrado para {ymf_path.name}")

        log.info(
            f"  {ymf_path.name}: "
            f"{len(ymap_paths)} ymap(s), {len(ytyp_paths)} ytyp(s)"
        )

        # Adiciona ymaps ao grupo
        for ymap_path in ymap_paths:
            files.add(ymap_path)
            log.debug(f"    [YMAP] {ymap_path.name}")

        # ---- Resolve assets dos ytyps ----
        for ytyp_path in ytyp_paths:
            files.add(ytyp_path)
            log.debug(f"    [YTYP] {ytyp_path.name}")

            if is_xml(ytyp_path):
                archetypes = parse_ytyp_xml(ytyp_path, self.index.by_hash)
                self._add_archetype_assets(archetypes, files)
            else:
                # ytyp binário: varre por hashes de .ydr/.ytd/.ybn/.yft
                log.debug(f"    [YTYP-BIN] {ytyp_path.name} → varredura binária")
                ytyp_data = ytyp_path.read_bytes()
                for ext in [".ydr", ".yft", ".ytd", ".ybn", ".ydd"]:
                    found = find_files_in_binary(
                        ytyp_data, self.index.by_hash, [ext]
                    )
                    for p in found:
                        files.add(p)
                        log.debug(f"      [{ext.upper()[1:]}] {p.name}")

        # ---- Resolve archetypes extras dos ymaps (XML) ----
        for ymap_path in ymap_paths:
            if is_xml(ymap_path):
                arch_names = parse_ymap_xml(ymap_path)
                for name in arch_names:
                    if self.index.is_native(name):
                        continue
                    for ext in [".ydr", ".yft", ".ytd", ".ybn", ".ydd"]:
                        p = self.index.find_by_name(name, ext)
                        if p and p not in files:
                            files.add(p)
                            log.debug(f"      [EXTRA] {p.name}")

        # ---- Varredura binária dos ymaps (se binários) ----
        for ymap_path in ymap_paths:
            if not is_xml(ymap_path):
                ymap_data = ymap_path.read_bytes()
                for ext in [".ydr", ".yft", ".ytd", ".ybn"]:
                    found = find_files_in_binary(
                        ymap_data, self.index.by_hash, [ext]
                    )
                    for p in found:
                        if p not in files:
                            files.add(p)
                            log.debug(f"      [BIN-EXTRA] {p.name}")

        # ---- Define nome do recurso pelo ymap/ytyp encontrado ----
        if ymap_paths:
            resource_name = ymap_paths[0].stem.lower()
            # Remove sufixos comuns de ymap
            for suffix in ["_milo_", "_milo", "_occ", "_hd"]:
                if resource_name.endswith(suffix):
                    resource_name = resource_name[:-len(suffix)]
                    break

        return resource_name, files, warnings

    def _parse_ymf_xml(self, path: Path) -> tuple[list[Path], list[Path]]:
        """Parse de ymf XML → retorna (ymaps, ytyps)."""
        ymaps, ytyps = [], []
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            return ymaps, ytyps

        for item in root.findall(".//imapDependencies_2/Item"):
            el = item.find("imapName")
            if el is not None and el.text:
                p = self.index.find_by_name(el.text.strip(), ".ymap")
                if p:
                    ymaps.append(p)

        for item in root.findall(".//itypDependencies_2/Item"):
            el = item.find("itypName")
            if el is not None and el.text:
                p = self.index.find_by_name(el.text.strip(), ".ytyp")
                if p:
                    ytyps.append(p)

        return ymaps, ytyps

    def _add_archetype_assets(self, archetypes: list[dict], files: set[Path]):
        """Adiciona assets (.ydr, .ytd, .ybn etc.) de uma lista de archetypes."""
        for arch in archetypes:
            name       = arch.get("name", "")
            txd        = arch.get("texturedictionary", "")
            physics    = arch.get("physicsdictionary", "")
            asset_name = arch.get("assetname", "")
            asset_type = arch.get("assettype", "")

            if not name:
                continue

            # Modelo
            model_ext = ".yft" if asset_type == "asset_type_fragment" else ".ydr"

            for candidate in {name, asset_name}:
                if not candidate:
                    continue
                if asset_type != "asset_type_assetless":
                    p = self.index.find_by_name(candidate, model_ext)
                    if p:
                        files.add(p)
                        log.debug(f"      [MODEL] {p.name}")
                for extra_ext in (".ytd", ".ybn"):
                    p = self.index.find_by_name(candidate, extra_ext)
                    if p:
                        files.add(p)
                        log.debug(f"      [{extra_ext[1:].upper()}] {p.name}")

            # TXD separado
            if txd and txd != name:
                p = self.index.find_by_name(txd, ".ytd")
                if p:
                    files.add(p)

            # Física separada
            if physics and physics != name:
                p = self.index.find_by_name(physics, ".ybn")
                if p:
                    files.add(p)

    # ------------------------------------------------------------------
    # CRIAÇÃO DO RECURSO
    # ------------------------------------------------------------------

    def create_resource(self, name: str, files: set[Path]) -> tuple[str, dict]:
        sname = safe_name(name) or f"map_{abs(hash(name)):08x}"
        resource_dir = self.output_dir / sname
        stream_dir   = resource_dir / "stream"

        if not self.dry_run:
            stream_dir.mkdir(parents=True, exist_ok=True)

        by_ext: dict[str, int] = defaultdict(int)
        name_count: dict[str, int] = defaultdict(int)

        for src in sorted(files):
            dest_name = src.name
            if name_count[dest_name] > 0:
                dest_name = f"{src.stem}_{name_count[src.name]}{src.suffix}"
            name_count[src.name] += 1

            dest = stream_dir / dest_name
            if not self.dry_run:
                try:
                    if self.move_files:
                        shutil.move(str(src), str(dest))
                    else:
                        shutil.copy2(str(src), str(dest))
                except Exception as e:
                    log.warning(f"    Erro: {src.name}: {e}")

            by_ext[src.suffix.lower()] += 1
            self.attributed.add(src)

        self._write_manifest(resource_dir, sname, by_ext)

        summary = "  ".join(f"{c}x{e}" for e, c in sorted(by_ext.items()))
        log.info(f"  → {sname}/  ({len(files)} arquivos)  {summary}")

        return sname, dict(by_ext)

    def _write_manifest(self, resource_dir: Path, name: str, by_ext: dict):
        lines = [
            f"-- fxmanifest.lua | {name}",
            f"-- FiveM Map Organizer v6.0",
            "--",
        ]
        for ext, cnt in sorted(by_ext.items()):
            lines.append(f"--   {ext:<8}: {cnt}")
        lines += ["", "fx_version 'cerulean'",
                  "game 'gta5'", "lua54 'yes'", "this_is_a_map 'yes'"]
        if not self.dry_run:
            (resource_dir / "fxmanifest.lua").write_text(
                "\n".join(lines), encoding="utf-8"
            )

    # ------------------------------------------------------------------
    # RUN
    # ------------------------------------------------------------------

    def run(self):
        log.info("=" * 52)
        log.info("  FiveM Map Organizer v6.0")
        log.info("=" * 52)

        if not self.input_dir.exists():
            log.error(f"Pasta não encontrada: {self.input_dir}")
            sys.exit(1)

        if not self.dry_run:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        self.scan()

        if not self.ymf_files:
            log.warning("Nenhum .ymf encontrado.")
            sys.exit(1)

        results = []

        for ymf_path in self.ymf_files:
            log.info(f"\nProcessando: {ymf_path.name}")
            name, files, warnings = self.resolve_ymf(ymf_path)

            for w in warnings:
                log.warning(f"  ⚠ {w}")

            if not files:
                log.warning(f"  Nenhum arquivo resolvido, pulando.")
                continue

            sname, by_ext = self.create_resource(name, files)
            results.append({
                "name": sname, "total": len(files),
                "by_ext": by_ext, "warnings": warnings
            })

        self._report(results)

    def _report(self, results: list[dict]):
        all_files = set(self.index.all_paths)
        unattr = all_files - self.attributed

        lines = [
            "=" * 55,
            "  FiveM Map Organizer v6.0 — Relatório",
            "=" * 55,
            f"\n  Recursos criados : {len(results)}",
            f"  Arquivos totais  : {sum(r['total'] for r in results)}",
        ]

        if unattr:
            lines.append(f"\nNÃO ATRIBUÍDOS ({len(unattr)}):")
            for p in sorted(unattr)[:30]:
                lines.append(f"  {p.name}")
            if len(unattr) > 30:
                lines.append(f"  ... e mais {len(unattr) - 30}")

        txt = "\n".join(lines)
        print("\n" + txt + "\n")
        if not self.dry_run:
            (self.output_dir / "_relatorio.txt").write_text(
                txt, encoding="utf-8"
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="FiveM Map Organizer v6.0")
    p.add_argument("--input",   "-i", required=True, type=Path)
    p.add_argument("--output",  "-o", required=True, type=Path)
    p.add_argument("--move",    action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    MapOrganizer(
        input_dir  = args.input,
        output_dir = args.output,
        move_files = args.move,
        dry_run    = args.dry_run,
        verbose    = args.verbose,
    ).run()


if __name__ == "__main__":
    main()
