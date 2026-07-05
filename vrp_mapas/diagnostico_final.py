# diagnostico_final.py
import struct
from pathlib import Path

def joaat(s: str) -> int:
    h = 0
    for b in s.lower().encode():
        h = (h + b) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= (h >> 6)
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= (h >> 11)
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h

PASTA = Path(r"C:\Users\rian_\OneDrive\Documentos\GitHub\organizemaps\vrp_mapas\mapas_baguncados")

# Constrói índice hash → arquivo
print("Construindo índice de hashes...")
hash_para_arquivo = {}
for f in PASTA.iterdir():
    if f.is_file():
        h = joaat(f.stem)
        hash_para_arquivo[h] = f
        # Também tenta com extensão
        h2 = joaat(f.name)
        hash_para_arquivo[h2] = f

# Analisa sallyencia_banner.ymf
print("\n" + "="*60)
print("=== sallyencia_banner.ymf ===")
ymf_path = PASTA / "sallyencia_banner.ymf"
data = ymf_path.read_bytes()

# Lê todos os uint32 do arquivo
print(f"Tamanho: {len(data)} bytes")
print("\nTodos os uint32 únicos e seus matches:")
seen = set()
for i in range(0, len(data) - 3, 4):
    val = struct.unpack_from('<I', data, i)[0]
    if val in seen or val < 0x10000:
        continue
    seen.add(val)
    if val in hash_para_arquivo:
        print(f"  offset 0x{i:04X}: 0x{val:08X} → MATCH: {hash_para_arquivo[val].name}")
    # Também testa byte-reversed
    val_rev = struct.unpack_from('>I', data, i)[0]
    if val_rev in hash_para_arquivo and val_rev not in seen:
        seen.add(val_rev)
        print(f"  offset 0x{i:04X}: 0x{val:08X} (big-endian: 0x{val_rev:08X}) → MATCH: {hash_para_arquivo[val_rev].name}")

# Analisa _manifestfavelapenha.ymf
print("\n" + "="*60)
print("=== _manifestfavelapenha.ymf ===")
ymf2_path = PASTA / "_manifestfavelapenha.ymf"
data2 = ymf2_path.read_bytes()
print(f"Tamanho: {len(data2)} bytes")
print("\nTodos os uint32 únicos e seus matches:")
seen2 = set()
matches_count = 0
for i in range(0, len(data2) - 3, 4):
    val = struct.unpack_from('<I', data2, i)[0]
    if val in seen2 or val < 0x10000:
        continue
    seen2.add(val)
    if val in hash_para_arquivo:
        matches_count += 1
        print(f"  offset 0x{i:04X}: 0x{val:08X} → MATCH: {hash_para_arquivo[val].name}")

print(f"\nTotal de matches encontrados: {matches_count}")

# Testa hipótese: hash do próprio nome bate com offset 0x10?
print("\n" + "="*60)
print("=== Verificação do padrão de offset 0x10 ===")
for ymf_file in list(PASTA.glob("*.ymf"))[:10]:
    d = ymf_file.read_bytes()
    if len(d) < 0x14:
        continue
    val_at_10 = struct.unpack_from('<I', d, 0x10)[0]
    h_stem = joaat(ymf_file.stem)
    h_stem_clean = joaat(ymf_file.stem.lstrip('_').replace('manifest_','').replace('_manifest','').replace('manifest',''))
    print(f"{ymf_file.name}")
    print(f"  val@0x10 = 0x{val_at_10:08X}")
    print(f"  joaat(stem)       = 0x{h_stem:08X} {'✅ MATCH' if val_at_10 == h_stem else ''}")
    print(f"  joaat(stem_clean) = 0x{h_stem_clean:08X} {'✅ MATCH' if val_at_10 == h_stem_clean else ''}")
    if val_at_10 in hash_para_arquivo:
        print(f"  val@0x10 → arquivo: {hash_para_arquivo[val_at_10].name} ✅")
    else:
        print(f"  val@0x10 → sem match na pasta")
    print()
