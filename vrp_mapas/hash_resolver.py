#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hash_resolver.py
----------------
Constrói um dicionário reverso JOAAT a partir dos arquivos da pasta.
Calcula o hash de cada nome de arquivo e mapeia:
  "0xC13BFFF4" → "meu_modelo_customizado"

Assim quando o XML referencia "0xC13BFFF4", sabemos que o arquivo
correspondente é "meu_modelo_customizado.ydr" (ou .ytd, .ybn etc.)
"""

from pathlib import Path


# ---------------------------------------------------------------------------
# ALGORITMO JOAAT — idêntico ao usado pelo GTA5
# ---------------------------------------------------------------------------

def joaat(text: str) -> str:
    """
    Calcula o hash Jenkins One At A Time de uma string.
    O GTA5 sempre converte para lowercase antes de hashear.
    Retorna no formato '0xABCD1234' (maiúsculas, 8 dígitos hex).
    """
    key = text.lower().encode("utf-8")
    h = 0
    for byte in key:
        h = (h + byte)          & 0xFFFFFFFF
        h = (h + (h << 10))     & 0xFFFFFFFF
        h ^= (h >> 6)
    h = (h + (h << 3))          & 0xFFFFFFFF
    h ^= (h >> 11)
    h = (h + (h << 15))         & 0xFFFFFFFF
    return f"0x{h:08X}"


# ---------------------------------------------------------------------------
# CONSTRUTOR DO DICIONÁRIO REVERSO
# ---------------------------------------------------------------------------

def build_reverse_map(folder: Path) -> dict[str, str]:
    """
    Varre a pasta recursivamente e para cada arquivo:
      1. Pega o nome sem extensão  → ex: "meu_modelo_customizado"
      2. Calcula o JOAAT do nome   → ex: "0xC13BFFF4"
      3. Mapeia hash → nome_stem

    Retorna:
      {
        "0xC13BFFF4": "meu_modelo_customizado",
        "0x083251FB": "outro_modelo",
        ...
      }

    Uso no organizador:
      Se o XML tem archetypeName = "0xC13BFFF4",
      consultamos o mapa e sabemos que o arquivo é
      "meu_modelo_customizado.ydr" (ou .ytd, .ybn etc.)
    """
    reverse: dict[str, str] = {}
    collisions: list[tuple[str, str, str]] = []  # (hash, nome1, nome2)

    for path in folder.rglob("*"):
        if not path.is_file():
            continue

        stem = path.stem          # nome sem extensão
        stem_lower = stem.lower() # GTA5 é case-insensitive

        h = joaat(stem_lower)

        if h in reverse:
            existing = reverse[h]
            if existing.lower() != stem_lower:
                # Colisão real de hash (extremamente raro)
                collisions.append((h, existing, stem))
        else:
            reverse[h] = stem_lower

    if collisions:
        print(f"[AVISO] {len(collisions)} colisão(ões) de hash detectada(s):")
        for h, n1, n2 in collisions:
            print(f"  {h}: '{n1}' vs '{n2}'")

    return reverse


# ---------------------------------------------------------------------------
# FUNÇÕES DE CONSULTA
# ---------------------------------------------------------------------------

def resolve(name: str, reverse_map: dict[str, str]) -> str:
    """
    Dado um nome que pode ser hash ('0xC13BFFF4') ou texto normal
    ('prop_mesa'), retorna o nome real (stem) do arquivo.

    Se for hash e estiver no mapa → retorna o nome real.
    Se for hash e NÃO estiver     → retorna o próprio hash (sem solução).
    Se não for hash                → retorna como veio.
    """
    cleaned = name.strip().upper()
    if cleaned.startswith("0X") and len(cleaned) == 10:
        return reverse_map.get(cleaned, name)
    return name


def is_hash(name: str) -> bool:
    """Retorna True se o nome parece ser um hash JOAAT (0x + 8 hex)."""
    s = name.strip().upper()
    return s.startswith("0X") and len(s) == 10 and all(
        c in "0123456789ABCDEF" for c in s[2:]
    )


# ---------------------------------------------------------------------------
# UTILITÁRIO: verificar / demonstrar
# ---------------------------------------------------------------------------

def print_map_summary(reverse_map: dict[str, str], show_all: bool = False):
    """Imprime um resumo do dicionário construído."""
    hashes   = {k: v for k, v in reverse_map.items() if is_hash(k)}
    resolved = len(hashes)
    total    = len(reverse_map)

    print(f"\n{'='*55}")
    print(f"  Dicionário Hash → Nome")
    print(f"{'='*55}")
    print(f"  Total de arquivos indexados : {total}")
    print(f"  Destes, são hashes (0x...)  : {resolved}")
    print(f"  São nomes normais           : {total - resolved}")

    if show_all or resolved <= 50:
        print(f"\n  Hashes resolvidos:")
        for h, name in sorted(hashes.items()):
            print(f"    {h}  →  {name}")
    else:
        print(f"\n  Primeiros 20 hashes resolvidos:")
        for h, name in list(sorted(hashes.items()))[:20]:
            print(f"    {h}  →  {name}")
        print(f"  ... e mais {resolved - 20}")

    print(f"{'='*55}\n")


# ---------------------------------------------------------------------------
# USO STANDALONE: rodar direto para ver o mapa de uma pasta
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="Constrói e exibe o dicionário JOAAT reverso de uma pasta"
    )
    parser.add_argument("--folder", "-f", required=True, type=Path,
                        help="Pasta com os arquivos de mapa")
    parser.add_argument("--all", "-a", action="store_true",
                        help="Exibe todos os hashes (não trunca)")
    parser.add_argument("--lookup", "-l", type=str, default=None,
                        help="Resolve um hash específico. Ex: --lookup 0xC13BFFF4")
    parser.add_argument("--hash", type=str, default=None,
                        help="Calcula o hash de um nome. Ex: --hash meu_modelo")
    args = parser.parse_args()

    # Modo cálculo direto
    if args.hash:
        resultado = joaat(args.hash)
        print(f"\n  joaat('{args.hash}') = {resultado}\n")
        sys.exit(0)

    # Constrói o mapa
    rmap = build_reverse_map(args.folder)
    print_map_summary(rmap, show_all=args.all)

    # Modo lookup específico
    if args.lookup:
        resultado = resolve(args.lookup, rmap)
        if resultado != args.lookup:
            print(f"  RESOLVIDO: {args.lookup}  →  '{resultado}'")
        else:
            print(f"  NÃO ENCONTRADO: {args.lookup} não tem arquivo correspondente na pasta")
