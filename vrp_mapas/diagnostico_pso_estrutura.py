# diagnostico_pso_estrutura.py
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

# Índice hash (big-endian) → arquivo
print("Construindo índice de hashes (big-endian)...")
hash_be_para_arquivo = {}
for f in PASTA.iterdir():
    if f.is_file():
        h = joaat(f.stem)
        hash_be_para_arquivo[h] = f

# ================================================================
# Analisa sallyencia_banner.ymf — arquivo pequeno, fácil de mapear
# ================================================================
print("\n" + "="*60)
print("=== sallyencia_banner.ymf — scan big-endian ===")
ymf_path = PASTA / "sallyencia_banner.ymf"
data = ymf_path.read_bytes()
print(f"Tamanho: {len(data)} bytes\n")

# Imprime todos os uint32 big-endian e verifica match
print("Offset | LE value     | BE value     | Match")
print("-"*60)
for i in range(0, len(data) - 3, 4):
    val_le = struct.unpack_from('<I', data, i)[0]
    val_be = struct.unpack_from('>I', data, i)[0]
    match_le = hash_be_para_arquivo.get(val_le)
    match_be = hash_be_para_arquivo.get(val_be)
    if match_le or match_be or val_le > 0x100000:
        m = ""
        if match_be:
            m = f"BE→ {match_be.name}"
        elif match_le:
            m = f"LE→ {match_le.name}"
        print(f"0x{i:04X}  | 0x{val_le:08X}   | 0x{val_be:08X}   | {m}")

# ================================================================
# Verifica padrão: offset 0x10 sempre = hash do próprio stem (BE)?
# ================================================================
print("\n" + "="*60)
print("=== Padrão offset 0x10 = joaat(stem) big-endian ===\n")
for ymf_file in list(PASTA.glob("*.ymf"))[:15]:
    d = ymf_file.read_bytes()
    if len(d) < 0x14:
        continue
    val_be = struct.unpack_from('>I', d, 0x10)[0]
    h_stem = joaat(ymf_file.stem)
    match = hash_be_para_arquivo.get(val_be)
    status = "✅ self" if val_be == h_stem else ("🔍 " + match.name if match else "❌")
    print(f"{ymf_file.name[:45]:<45} val_BE=0x{val_be:08X}  joaat=0x{h_stem:08X}  {status}")

# ================================================================
# Para ymf com ymap conhecido (barragemcapital), mapeia estrutura
# ================================================================
print("\n" + "="*60)
print("=== farm_manifestmlobarragemcapital.ymf — mapeamento completo ===")
ymf3 = PASTA / "farm_manifestmlobarragemcapital.ymf"
if ymf3.exists():
    d3 = ymf3.read_bytes()
    h_ymap = joaat("barragemcapital")
    h_mlo  = joaat("mlobarragemcapital")
    h_farm = joaat("farm_manifestmlobarragemcapital")
    print(f"Tamanho: {len(d3)} bytes")
    print(f"joaat('barragemcapital')                   = 0x{h_ymap:08X}")
    print(f"joaat('mlobarragemcapital')                = 0x{h_mlo:08X}")
    print(f"joaat('farm_manifestmlobarragemcapital')   = 0x{h_farm:08X}\n")
    print("Offset | BE value     | Match")
    print("-"*50)
    for i in range(0, min(len(d3)-3, 0x100), 4):
        val_be = struct.unpack_from('>I', d3, i)[0]
        match  = hash_be_para_arquivo.get(val_be)
        if val_be > 0x100000 or match:
            m = match.name if match else ""
            eq_ymap = " ← ymap!" if val_be == h_ymap else ""
            eq_mlo  = " ← mlo!"  if val_be == h_mlo  else ""
            eq_self = " ← self!" if val_be == h_farm  else ""
            print(f"0x{i:04X}  | 0x{val_be:08X}   | {m}{eq_ymap}{eq_mlo}{eq_self}")
