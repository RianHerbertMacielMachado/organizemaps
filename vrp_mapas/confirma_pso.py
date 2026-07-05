# confirma_pso.py
from pathlib import Path

def joaat(s: str) -> int:
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

import struct

pasta = Path(r"C:\Users\rian_\OneDrive\Documentos\GitHub\organizemaps\vrp_mapas\mapas_baguncados")

# Carrega ambos os ymfs
banner = (pasta / "sallyencia_banner.ymf").read_bytes()
penha  = (pasta / "_manifestfavelapenha.ymf").read_bytes()

print("=== sallyencia_banner.ymf ===")
print(f"Bytes 0x10-0x1F em hex:")
for i in range(0x10, 0x30, 4):
    val = struct.unpack_from("<I", banner, i)[0]
    print(f"  offset 0x{i:02X}: 0x{val:08X}")

print()

# Calcula hash do nome do ymap associado
# No banner existe: sallyencia_banner.ymap, sallyencia_banner.ytyp
for nome in ["sallyencia_banner", "sallyencia_banners", "sallyencia_banner.ymap"]:
    h = joaat(nome)
    print(f"  joaat('{nome}') = 0x{h:08X}")

print()
print("=== _manifestfavelapenha.ymf — offsets 0x10 a 0x60 ===")
for i in range(0x10, 0x70, 4):
    val = struct.unpack_from("<I", penha, i)[0]
    print(f"  offset 0x{i:02X}: 0x{val:08X}")

print()
# Arquivos que poderiam ser do ymf favelapenha
candidatos = [
    "faveladapenha", "favelapenha", "faveladapenha_mlo_",
    "faveladapenha", "quebradashop_favelapenha",
    "faveladapenha_occ", "favelapedreira2026",
]
for nome in candidatos:
    h = joaat(nome)
    print(f"  joaat('{nome}') = 0x{h:08X}")

# Verifica se 0xF7DDB744 (que aparece no offset 0x10 da penha)
# bate com algum arquivo da pasta
target = 0xF7DDB744
print(f"\nBuscando arquivo com hash 0x{target:08X}:")
for p in pasta.iterdir():
    if p.suffix.lower() in (".ymap", ".ytyp", ".ydr", ".ytd"):
        h = joaat(p.stem)
        if h == target:
            print(f"  ENCONTRADO: {p.name}")
