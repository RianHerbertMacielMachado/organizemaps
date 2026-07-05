#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
  FiveM Map Organizer v2.0
=============================================================================
  Lê arquivos XML (OpenFormats do CodeWalker):
    - .ymf  → CPackFileMetaData  → descobre nomes de .ymap e .ytyp do mapa
    - .ytyp → CMapTypes          → descobre nomes dos assets customizados
                                   (name = textureDictionary = assetName)
    - .ymap → CMapData           → descobre archetypes usados no mundo

  Lógica de resolução de arquivos:
    1. Para cada .ymf encontrado:
       a) Lê imapName  → procura o .ymap correspondente
       b) Lê itypName  → procura o .ytyp correspondente
       c) Lê o .ytyp   → extrai todos os <name> dos archetypes
          - Para cada name: procura name.ydr, name.ytd, name.ybn, name.yft
          - textureDictionary pode ser diferente do name → procura esse .ytd
       d) Lê o .ymap   → extrai archetypeNames das entidades
          - Filtra apenas os que existem como arquivo na pasta
            (hashes customizados), ignora props nativos do GTA5
    2. Cria pasta recurso/stream/ com todos os arquivos
    3. Gera fxmanifest.lua

  AVISO: Funciona com arquivos no formato XML (OpenFormats do CodeWalker).
  Arquivos binários precisam ser exportados como XML pelo CodeWalker antes.

=============================================================================
"""

import os
import sys
import shutil
import argparse
import logging
from pathlib import Path
from collections import defaultdict
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("MapOrganizer")

# ---------------------------------------------------------------------------
# EXTENSÕES DE ASSETS CUSTOMIZADOS (arquivos que vêm com o mapa)
# ---------------------------------------------------------------------------
CUSTOM_ASSET_EXTENSIONS = [".ydr", ".ytd", ".ybn", ".yft", ".ydd", ".ycd"]

# Extensões de definição de mapa
MAP_DEF_EXTENSIONS = [".ymap", ".ytyp", ".ymf"]

# Todas as extensões relevantes
ALL_MAP_EXTENSIONS = set(CUSTOM_ASSET_EXTENSIONS + MAP_DEF_EXTENSIONS)

# Props e archetypes nativos do GTA5 — prefixos conhecidos
# Archetypes que comecem com esses prefixos provavelmente são nativos
# (não precisam de arquivo, já estão no jogo base)
NATIVE_PREFIXES = (
    "prop_", "v_", "apa_", "ba_", "bkr_", "ch_", "gr_", "h4_", "hei_",
    "int_", "p_", "sm_", "vw_", "xm_", "xs_", "ex_", "beerrow", "vodkarow",
    "winerow", "spiritsrow", "v_ret_", "v_res_", "v_corp_", "v_ind_",
    "v_ilev_", "v_ilev", "apa_p_", "apa_mp_"
)


# ---------------------------------------------------------------------------
# PARSE DO .ymf  (CPackFileMetaData)
# ---------------------------------------------------------------------------

def parse_ymf(path: Path) -> dict:
    """
    Lê o .ymf e extrai:
      - imap_names  : lista de nomes de .ymap referenciados
      - ityp_names  : lista de nomes de .ytyp referenciados
      - ityp_deps   : dependências nativas (apenas para informação)
    """
    result = {"imap_names": [], "ityp_names": [], "ityp_deps": []}

    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError as e:
        log.warning(f"[YMF] Erro ao parsear {path.name}: {e}")
        return result

    # <imapDependencies_2> → cada <Item> tem <imapName>
    for item in root.findall(".//imapDependencies_2/Item"):
        name_el = item.find("imapName")
        if name_el is not None and name_el.text:
            result["imap_names"].append(name_el.text.strip().lower())

    # <itypDependencies_2> → cada <Item> tem <itypName> e <itypDepArray>
    for item in root.findall(".//itypDependencies_2/Item"):
        name_el = item.find("itypName")
        if name_el is not None and name_el.text:
            result["ityp_names"].append(name_el.text.strip().lower())

        for dep in item.findall(".//itypDepArray/Item"):
            if dep.text:
                result["ityp_deps"].append(dep.text.strip().lower())

    log.debug(f"  [YMF] {path.name}: "
              f"{len(result['imap_names'])} ymap(s), "
              f"{len(result['ityp_names'])} ytyp(s)")
    return result


# ---------------------------------------------------------------------------
# PARSE DO .ytyp  (CMapTypes)
# ---------------------------------------------------------------------------

def parse_ytyp(path: Path) -> list[dict]:
    """
    Lê o .ytyp e extrai a lista de archetypes customizados.
    Cada archetype retorna:
      {
        'name'      : nome do archetype (= nome do .ydr/.yft),
        'txd'       : nome do dicionário de textura (= nome do .ytd),
        'physics'   : nome do dicionário de física (= nome do .ybn),
        'asset_type': ASSET_TYPE_DRAWABLE | ASSET_TYPE_FRAGMENT | etc.
      }
    """
    archetypes = []

    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError as e:
        log.warning(f"[YTYP] Erro ao parsear {path.name}: {e}")
        return archetypes

    for item in root.findall(".//archetypes/Item"):
        arch = {
            "name"      : None,
            "txd"       : None,
            "physics"   : None,
            "asset_type": None,
            "asset_name": None,
        }

        el = item.find("name")
        if el is not None and el.text:
            arch["name"] = el.text.strip().lower()

        el = item.find("textureDictionary")
        if el is not None and el.text:
            arch["txd"] = el.text.strip().lower()

        el = item.find("physicsDictionary")
        if el is not None and el.text and el.text.strip():
            arch["physics"] = el.text.strip().lower()

        el = item.find("assetType")
        if el is not None and el.text:
            arch["asset_type"] = el.text.strip()

        el = item.find("assetName")
        if el is not None and el.text:
            arch["asset_name"] = el.text.strip().lower()

        if arch["name"]:
            archetypes.append(arch)

    log.debug(f"  [YTYP] {path.name}: {len(archetypes)} archetype(s)")
    return archetypes


# ---------------------------------------------------------------------------
# PARSE DO .ymap  (CMapData)
# ---------------------------------------------------------------------------

def parse_ymap(path: Path) -> set[str]:
    """
    Lê o .ymap e retorna o set de archetypeNames de todas as entidades.
    """
    names = set()

    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError as e:
        log.warning(f"[YMAP] Erro ao parsear {path.name}: {e}")
        return names

    for el in root.findall(".//entities/Item/archetypeName"):
        if el.text:
            names.add(el.text.strip().lower())

    # MLO: archetypes dentro de CMloArchetypeDef também têm entidades
    for el in root.findall(".//archetypes/Item/entities/Item/archetypeName"):
        if el.text:
            names.add(el.text.strip().lower())

    log.debug(f"  [YMAP] {path.name}: {len(names)} archetype(s) únicos")
    return names


# ---------------------------------------------------------------------------
# CLASSE PRINCIPAL
# ---------------------------------------------------------------------------

class MapOrganizer:

    def __init__(self, input_dir: Path, output_dir: Path,
                 move_files: bool = False,
                 dry_run: bool = False,
                 verbose: bool = False):
        self.input_dir  = input_dir
        self.output_dir = output_dir
        self.move_files = move_files
        self.dry_run    = dry_run

        if verbose:
            log.setLevel(logging.DEBUG)

        # Índice: stem_lower → { ext_lower → Path }
        # Ex: "0xc13bfff4" → { ".ydr": Path(...), ".ytd": Path(...) }
        self.index: dict[str, dict[str, Path]] = defaultdict(dict)

        # Lista de todos os .ymf encontrados
        self.ymf_files: list[Path] = []

        # Controle de arquivos já atribuídos
        self.attributed: set[Path] = set()

    # ------------------------------------------------------------------
    # PASSO 1: Escanear e indexar todos os arquivos
    # ------------------------------------------------------------------

    def scan(self):
        log.info(f"Escaneando: {self.input_dir}")
        count = 0

        for path in self.input_dir.rglob("*"):
            if not path.is_file():
                continue

            ext  = path.suffix.lower()
            stem = path.stem.lower()

            if ext not in ALL_MAP_EXTENSIONS:
                continue

            # Se já existe um arquivo com mesmo stem+ext, avisa
            if ext in self.index[stem]:
                existing = self.index[stem][ext]
                if existing != path:
                    log.warning(
                        f"  [DUP] {path.name} duplicado! "
                        f"Já existe: {existing}. Mantendo o primeiro encontrado."
                    )
                continue

            self.index[stem][ext] = path
            count += 1

            if ext == ".ymf":
                self.ymf_files.append(path)

        log.info(f"  {count} arquivos indexados")
        log.info(f"  {len(self.ymf_files)} manifesto(s) .ymf encontrado(s)")

    # ------------------------------------------------------------------
    # PASSO 2: Resolver arquivos para um recurso
    # ------------------------------------------------------------------

    def find(self, stem: str, ext: str) -> Path | None:
        """Busca um arquivo pelo stem e extensão no índice."""
        return self.index.get(stem.lower(), {}).get(ext.lower())

    def resolve_resource(self, ymf_path: Path) -> tuple[str, set[Path], list[str]]:
        """
        Para um dado .ymf, resolve todos os arquivos necessários.
        Retorna: (nome_recurso, set_de_paths, lista_de_avisos)
        """
        files: set[Path] = set()
        warnings: list[str] = []
        resource_name = ymf_path.stem

        # --- 1. Inclui o próprio .ymf ---
        files.add(ymf_path)

        # --- 2. Parse do .ymf ---
        ymf_data = parse_ymf(ymf_path)

        if not ymf_data["imap_names"] and not ymf_data["ityp_names"]:
            warnings.append(
                "ymf sem imapName/itypName — "
                "tentando pelo nome do próprio ymf"
            )
            ymf_data["imap_names"] = [ymf_path.stem.lower()]
            ymf_data["ityp_names"] = [ymf_path.stem.lower()]

        # --- 3. Resolve os .ymap ---
        ymap_paths: list[Path] = []
        for imap_name in ymf_data["imap_names"]:
            ymap_path = self.find(imap_name, ".ymap")
            if ymap_path:
                files.add(ymap_path)
                ymap_paths.append(ymap_path)
                log.debug(f"    [YMAP] {ymap_path.name}")
            else:
                warnings.append(f"ymap não encontrado: {imap_name}.ymap")

        # --- 4. Resolve os .ytyp e seus assets ---
        for ityp_name in ymf_data["ityp_names"]:
            ytyp_path = self.find(ityp_name, ".ytyp")
            if not ytyp_path:
                warnings.append(f"ytyp não encontrado: {ityp_name}.ytyp")
                continue

            files.add(ytyp_path)
            log.debug(f"    [YTYP] {ytyp_path.name}")

            # Parse do .ytyp para extrair todos os assets
            archetypes = parse_ytyp(ytyp_path)

            for arch in archetypes:
                name       = arch["name"]       # ex: "0xc13bfff4"
                txd        = arch["txd"]         # ex: "0xc13bfff4"
                physics    = arch["physics"]     # ex: "0xc13bfff4" ou None
                asset_type = arch["asset_type"]  # ex: "ASSET_TYPE_DRAWABLE"
                asset_name = arch["asset_name"]  # geralmente == name

                if not name:
                    continue

                # Modelo principal
                # ASSET_TYPE_DRAWABLE  → .ydr
                # ASSET_TYPE_FRAGMENT  → .yft
                # ASSET_TYPE_ASSETLESS → sem modelo próprio (MLO shell)
                if asset_type == "ASSET_TYPE_FRAGMENT":
                    model_ext = ".yft"
                elif asset_type == "ASSET_TYPE_ASSETLESS":
                    model_ext = None
                else:
                    model_ext = ".ydr"  # padrão

                # Tenta pelo assetName primeiro, depois pelo name
                for candidate_name in {name, asset_name}:
                    if not candidate_name:
                        continue

                    # Modelo (.ydr ou .yft)
                    if model_ext:
                        p = self.find(candidate_name, model_ext)
                        if p:
                            files.add(p)
                            log.debug(f"      [MODEL] {p.name}")

                    # Textura embutida com mesmo nome
                    p = self.find(candidate_name, ".ytd")
                    if p:
                        files.add(p)
                        log.debug(f"      [YTD]   {p.name}")

                    # Colisão com mesmo nome
                    p = self.find(candidate_name, ".ybn")
                    if p:
                        files.add(p)
                        log.debug(f"      [YBN]   {p.name}")

                # Textura pelo txdName (pode ser diferente do name)
                if txd and txd != name:
                    p = self.find(txd, ".ytd")
                    if p:
                        files.add(p)
                        log.debug(f"      [TXD]   {p.name} (via txdName)")

                # Física pelo physicsDictionary (pode ser diferente)
                if physics and physics != name:
                    p = self.find(physics, ".ybn")
                    if p:
                        files.add(p)
                        log.debug(f"      [YBN]   {p.name} (via physicsDic)")

        # --- 5. Verifica archetypes do ymap que não vieram do ytyp ---
        # Isso captura casos onde o ymap usa assets que o ytyp não declarou
        # explicitamente, mas o arquivo existe na pasta
        all_ymap_archetypes: set[str] = set()
        for ymap_path in ymap_paths:
            all_ymap_archetypes.update(parse_ymap(ymap_path))

        # Também parseia o ytyp como ymap (o arquivo que você colou
        # é um .ytyp com entidades MLO embutidas — CMapTypes com entities)
        for ityp_name in ymf_data["ityp_names"]:
            ytyp_path = self.find(ityp_name, ".ytyp")
            if ytyp_path:
                all_ymap_archetypes.update(parse_ymap(ytyp_path))

        for arch_name in all_ymap_archetypes:
            # Ignora props nativos do GTA5
            if self._is_likely_native(arch_name):
                log.debug(f"      [SKIP]  {arch_name} (nativo GTA5)")
                continue

            # Tenta encontrar o arquivo correspondente
            for ext in [".ydr", ".yft", ".ytd", ".ybn", ".ydd"]:
                p = self.find(arch_name, ext)
                if p and p not in files:
                    files.add(p)
                    log.debug(f"      [EXTRA] {p.name} (via ymap archetype)")

        return resource_name, files, warnings

    def _is_likely_native(self, name: str) -> bool:
        """
        Retorna True se o archetype parece ser nativo do GTA5
        (não precisa de arquivo customizado).
        Critério: começa com prefixo nativo E não existe na pasta.
        """
        # Se existe na pasta como arquivo, não é nativo
        for ext in [".ydr", ".yft", ".ytd", ".ybn"]:
            if self.find(name, ext):
                return False

        # Se começa com prefixo nativo, provavelmente é do jogo base
        if name.startswith(NATIVE_PREFIXES):
            return True

        # Se for hash puro (0x...) e não existe na pasta, avisa mas não pula
        if name.startswith("0x"):
            return False  # hash customizado sem arquivo → relatar como faltando

        return False

    # ------------------------------------------------------------------
    # PASSO 3: Criar pasta de recurso
    # ------------------------------------------------------------------

    def create_resource(self, name: str, files: set[Path]):
        """Cria a pasta do recurso FiveM com stream/ e fxmanifest.lua."""

        # Sanitiza nome
        safe = "".join(
            c if (c.isalnum() or c in "-_") else "_"
            for c in name
        ).lower().strip("_")

        if not safe:
            safe = "map_" + str(abs(hash(name)))[:8]

        resource_dir = self.output_dir / safe
        stream_dir   = resource_dir / "stream"

        if not self.dry_run:
            stream_dir.mkdir(parents=True, exist_ok=True)

        # Conta por extensão para o resumo
        by_ext: dict[str, int] = defaultdict(int)
        name_conflicts: dict[str, int] = defaultdict(int)

        for src in sorted(files):
            dest_name = src.name
            # Resolve conflito de nome (mesmo nome, caminhos diferentes)
            if name_conflicts[dest_name] > 0:
                dest_name = f"{src.stem}_{name_conflicts[dest_name]}{src.suffix}"
            name_conflicts[src.name] += 1

            dest = stream_dir / dest_name

            if not self.dry_run:
                if self.move_files:
                    shutil.move(str(src), str(dest))
                else:
                    shutil.copy2(str(src), str(dest))

            by_ext[src.suffix.lower()] += 1
            self.attributed.add(src)
            log.debug(f"    {'MOV' if self.move_files else 'CPY'} {src.name} → {dest_name}")

        # Gera fxmanifest.lua
        self._write_manifest(resource_dir, safe, by_ext)

        log.info(
            f"  → {safe}/ : "
            + ", ".join(f"{cnt}x{ext}" for ext, cnt in sorted(by_ext.items()))
        )

        return safe, by_ext

    def _write_manifest(self, resource_dir: Path, name: str,
                        by_ext: dict[str, int]):
        content = f"""-- ===================================================
--  fxmanifest.lua  |  Recurso: {name}
--  Gerado automaticamente por FiveM Map Organizer
-- ===================================================
--  Conteúdo em stream/:
"""
        for ext, cnt in sorted(by_ext.items()):
            content += f"--    {ext:<8} : {cnt} arquivo(s)\n"

        content += """-- ===================================================

fx_version 'cerulean'
game 'gta5'
lua54 'yes'
this_is_a_map 'yes'
"""
        if not self.dry_run:
            (resource_dir / "fxmanifest.lua").write_text(
                content, encoding="utf-8"
            )

    # ------------------------------------------------------------------
    # PASSO 4: Relatório final
    # ------------------------------------------------------------------

    def report(self, results: list[dict]):
        lines = [
            "=" * 60,
            "  FiveM Map Organizer — Relatório Final",
            "=" * 60,
            f"  Entrada : {self.input_dir}",
            f"  Saída   : {self.output_dir}",
            f"  Modo    : {'MOVER' if self.move_files else 'COPIAR'}",
            f"  Dry-run : {'SIM' if self.dry_run else 'NÃO'}",
            "",
        ]

        total = 0
        for r in results:
            lines.append(f"RECURSO: {r['name']}")
            for ext, cnt in sorted(r["by_ext"].items()):
                lines.append(f"  {ext:<8}: {cnt}")
            lines.append(f"  TOTAL   : {r['total']}")
            if r["warnings"]:
                lines.append(f"  AVISOS  : {len(r['warnings'])}")
                for w in r["warnings"]:
                    lines.append(f"    ⚠ {w}")
            lines.append("")
            total += r["total"]

        # Arquivos não atribuídos
        all_files = {
            p
            for exts in self.index.values()
            for p in exts.values()
        }
        unattributed = all_files - self.attributed
        if unattributed:
            lines.append(
                f"ARQUIVOS NÃO ATRIBUÍDOS: {len(unattributed)}"
            )
            for p in sorted(unattributed)[:30]:
                lines.append(f"  {p.name}")
            if len(unattributed) > 30:
                lines.append(f"  ... e mais {len(unattributed) - 30}")
            lines.append("")

        lines += [
            "=" * 60,
            f"  Recursos criados : {len(results)}",
            f"  Arquivos totais  : {total}",
            "=" * 60,
        ]

        txt = "\n".join(lines)
        print("\n" + txt + "\n")

        if not self.dry_run:
            report_path = self.output_dir / "_relatorio.txt"
            report_path.write_text(txt, encoding="utf-8")

    # ------------------------------------------------------------------
    # EXECUÇÃO
    # ------------------------------------------------------------------

    def run(self):
        log.info("=" * 50)
        log.info("  FiveM Map Organizer v2.0")
        log.info("=" * 50)

        if not self.input_dir.exists():
            log.error(f"Pasta não encontrada: {self.input_dir}")
            sys.exit(1)

        if not self.dry_run:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        # 1. Escanear
        self.scan()

        if not self.ymf_files:
            log.warning("Nenhum .ymf encontrado! Usando modo fallback por .ymap.")
            self._fallback_ymap_mode()
            return

        results = []

        # 2. Processar cada .ymf
        for ymf_path in self.ymf_files:
            log.info(f"\nProcessando: {ymf_path.name}")
            resource_name, files, warnings = self.resolve_resource(ymf_path)

            if not files:
                log.warning(f"  Nenhum arquivo resolvido para {ymf_path.name}")
                continue

            safe_name, by_ext = self.create_resource(resource_name, files)

            results.append({
                "name"    : safe_name,
                "total"   : len(files),
                "by_ext"  : dict(by_ext),
                "warnings": warnings,
            })

        self.report(results)
        log.info("Concluído!")

    def _fallback_ymap_mode(self):
        """
        Modo sem .ymf: cada .ymap vira um recurso independente.
        Tenta resolver assets pelos archetypes do ymap que existam na pasta.
        """
        results = []
        ymap_paths = [
            p
            for exts in self.index.values()
            for p in exts.values()
            if p.suffix.lower() == ".ymap"
        ]

        for ymap_path in ymap_paths:
            log.info(f"\nProcessando (fallback): {ymap_path.name}")
            files: set[Path] = {ymap_path}

            archetypes = parse_ymap(ymap_path)
            for arch_name in archetypes:
                if self._is_likely_native(arch_name):
                    continue
                for ext in [".ydr", ".yft", ".ytd", ".ybn", ".ytyp"]:
                    p = self.find(arch_name, ext)
                    if p:
                        files.add(p)

            safe_name, by_ext = self.create_resource(ymap_path.stem, files)
            results.append({
                "name"    : safe_name,
                "total"   : len(files),
                "by_ext"  : dict(by_ext),
                "warnings": [],
            })

        self.report(results)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description="Organizador automático de mapas FiveM v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python organizer.py -i ./mapas_baguncados -o ./organizados
  python organizer.py -i ./mapas -o ./saida --dry-run --verbose
  python organizer.py -i ./mapas -o ./saida --move
        """
    )
    p.add_argument("--input",   "-i", required=True, type=Path)
    p.add_argument("--output",  "-o", required=True, type=Path)
    p.add_argument("--move",    action="store_true", default=False,
                   help="Move arquivos ao invés de copiar")
    p.add_argument("--verbose", "-v", action="store_true", default=False)
    p.add_argument("--dry-run", action="store_true", default=False,
                   help="Simula sem criar nada")
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
