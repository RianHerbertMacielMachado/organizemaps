# diagnostico_offsets_ymf.py
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

# Índice hash BE → arquivo por extensão
print("Construindo índice...")
hash_para_arquivo: dict[int, dict[str, Path]] = {}
for f in PASTA.iterdir():
    if not f.is_file():
        continue
    h = joaat(f.stem)
    if h not in hash_para_arquivo:
        hash_para_arquivo[h] = {}
    hash_para_arquivo[h][f.suffix.lower()] = f

def scan_ymf(path: Path) -> dict:
    """Varre um ymf e retorna todos os offsets que têm match de arquivo."""
    d = path.read_bytes()
    results = {}
    for i in range(0, len(d) - 3, 4):
        val = struct.unpack_from('>I', d, i)[0]
        if val in hash_para_arquivo:
            results[i] = (val, hash_para_arquivo[val])
    return results

# ================================================================
# Varre TODOS os ymf e registra em quais offsets há matches
# ================================================================
print("\nAnalisando todos os .ymf...\n")

# Estrutura: offset → lista de (ymf_name, ext_encontrada, arquivo)
offset_stats: dict[int, list] = {}
ymf_resultados = {}

for ymf_file in sorted(PASTA.glob("*.ymf")):
    d = ymf_file.read_bytes()
    matches = scan_ymf(ymf_file)
    
    ymap_found = []
    ytyp_found = []
    other_found = []
    
    for offset, (val, ext_dict) in matches.items():
        for ext, fpath in ext_dict.items():
            entry = (ymf_file.name, ext, fpath.name, offset)
            if offset not in offset_stats:
                offset_stats[offset] = []
            offset_stats[offset].append(entry)
            
            if ext == '.ymap':
                ymap_found.append((offset, fpath.name))
            elif ext == '.ytyp':
                ytyp_found.append((offset, fpath.name))
            else:
                other_found.append((offset, ext, fpath.name))
    
    ymf_resultados[ymf_file.name] = {
        'size': len(d),
        'ymap': ymap_found,
        'ytyp': ytyp_found,
        'other': other_found
    }
    
    if ymap_found or ytyp_found:
        print(f"✅ {ymf_file.name} ({len(d)}b)")
        for off, name in ytyp_found:
            print(f"   YTYP @ 0x{off:04X} → {name}")
        for off, name in ymap_found:
            print(f"   YMAP @ 0x{off:04X} → {name}")
        for off, ext, name in other_found:
            print(f"   {ext.upper()} @ 0x{off:04X} → {name}")
    else:
        print(f"❌ {ymf_file.name} ({len(d)}b) — sem matches")

# ================================================================
# Resumo: quais offsets são mais comuns para ymap e ytyp?
# ================================================================
print("\n" + "="*60)
print("=== OFFSETS MAIS FREQUENTES ===\n")

ymap_offsets: dict[int, int] = {}
ytyp_offsets: dict[int, int] = {}

for ymf_name, res in ymf_resultados.items():
    for off, _ in res['ymap']:
        ymap_offsets[off] = ymap_offsets.get(off, 0) + 1
    for off, _ in res['ytyp']:
        ytyp_offsets[off] = ytyp_offsets.get(off, 0) + 1

print("Offsets de YMAP (frequência):")
for off, count in sorted(ymap_offsets.items(), key=lambda x: -x[1]):
    print(f"  0x{off:04X}  →  {count}x")

print("\nOffsets de YTYP (frequência):")
for off, count in sorted(ytyp_offsets.items(), key=lambda x: -x[1]):
    print(f"  0x{off:04X}  →  {count}x")

# ================================================================
# Resumo final
# ================================================================
print("\n" + "="*60)
print("=== RESUMO FINAL ===\n")
total = len(list(PASTA.glob("*.ymf")))
com_ymap = sum(1 for r in ymf_resultados.values() if r['ymap'])
com_ytyp = sum(1 for r in ymf_resultados.values() if r['ytyp'])
sem_nada = sum(1 for r in ymf_resultados.values() if not r['ymap'] and not r['ytyp'])

print(f"Total ymf    : {total}")
print(f"Com ymap     : {com_ymap}")
print(f"Com ytyp     : {com_ytyp}")
print(f"Sem matches  : {sem_nada}")
