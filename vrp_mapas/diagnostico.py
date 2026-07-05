# diagnostico.py — cole e rode: python diagnostico.py
import struct
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

pasta = Path(r"C:\Users\rian_\OneDrive\Documentos\GitHub\organizemaps\vrp_mapas\mapas_baguncados")

# Testa com _manifestfavelapenha.ymf
ymf = pasta / "_manifestfavelapenha.ymf"
data = ymf.read_bytes()

# Monta dicionário hash→arquivo para .ymap e .ytyp
hash_map = {}
for p in pasta.iterdir():
    if p.suffix.lower() in (".ymap", ".ytyp", ".ydr", ".ytd", ".ybn"):
        h = joaat(p.stem)
        hash_map[h] = p

print(f"Arquivos indexados: {len(hash_map)}")
print(f"Tamanho do ymf: {len(data)} bytes")
print()

# Busca SEM filtro — todos os uint32 possíveis
matches = []
for i in range(0, len(data) - 3):
    val = struct.unpack_from("<I", data, i)[0]
    if val in hash_map:
        matches.append((i, val, hash_map[val].name))

if matches:
    print(f"ENCONTRADOS {len(matches)} matches:")
    for pos, val, nome in matches[:20]:
        print(f"  offset {pos:4d}: 0x{val:08X} → {nome}")
else:
    print("NENHUM match encontrado.")
    print()
    # Mostra os primeiros hashes calculados para conferir
    print("Primeiros 10 arquivos e seus hashes:")
    for p in list(pasta.iterdir())[:10]:
        if p.suffix.lower() in (".ymap", ".ytyp"):
            h = joaat(p.stem)
            print(f"  joaat('{p.stem}') = 0x{h:08X}")
    print()
    # Mostra os primeiros uint32 do ymf para comparar
    print("Primeiros 20 uint32 do ymf (little-endian, sem filtro):")
    for i in range(0, min(80, len(data)-3), 4):
        val = struct.unpack_from("<I", data, i)[0]
        print(f"  offset {i:3d}: 0x{val:08X}")
