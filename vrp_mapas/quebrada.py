from pathlib import Path
import struct

ytyp = Path(r"C:\Users\rian_\OneDrive\Documentos\GitHub\organizemaps\vrp_mapas\mapas_baguncados\quebradashopgraf.ytyp")
data = ytyp.read_bytes()

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

# Calcula o hash de quebradashopgraf1 e procura no arquivo
h1_le = joaat("quebradashopgraf1")
h1_be = struct.pack('>I', h1_le)
h1_le_bytes = struct.pack('<I', h1_le)

print(f"joaat('quebradashopgraf1') = 0x{h1_le:08X}")
print(f"  LE bytes: {h1_le_bytes.hex()}")
print(f"  BE bytes: {h1_be.hex()}")

if h1_le_bytes in data:
    pos = data.find(h1_le_bytes)
    print(f"  ✅ ENCONTRADO em LE no offset 0x{pos:04X}")
elif h1_be in data:
    pos = data.find(h1_be)
    print(f"  ✅ ENCONTRADO em BE no offset 0x{pos:04X}")
else:
    print("  ❌ NÃO ENCONTRADO no arquivo")

# Verifica também como string ASCII
if b"quebradashopgraf1" in data:
    print("  ✅ ENCONTRADO como string ASCII")
else:
    print("  ❌ NÃO como string ASCII")
