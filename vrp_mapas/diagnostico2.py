# diagnostico2.py
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

# Monta índice hash→arquivo para TODAS as extensões
hash_map: dict[int, list[Path]] = {}
for p in pasta.iterdir():
    if not p.is_file():
        continue
    h = joaat(p.stem)
    if h not in hash_map:
        hash_map[h] = []
    hash_map[h].append(p)

# Para cada ymf, calcula o hash do NOME DO YMF
# e vê o que mais tem o mesmo hash
print("=== Hash do nome de cada YMF ===\n")
ymfs = sorted(pasta.glob("*.ymf"))
for ymf in ymfs[:10]:  # mostra os 10 primeiros
    h = joaat(ymf.stem)
    matches = hash_map.get(h, [])
    outros = [p for p in matches if p != ymf]
    print(f"{ymf.name}")
    print(f"  joaat('{ymf.stem}') = 0x{h:08X}")
    if outros:
        print(f"  MESMO HASH: {[p.name for p in outros]}")
    else:
        print(f"  Sem outros arquivos com mesmo hash")
    print()

# Agora: para cada ymap, calcula hash e vê se existe ymf com mesmo hash
print("\n=== Ymaps e seus hashes ===\n")
ymaps = sorted(pasta.glob("*.ymap"))
ymap_hashes = {joaat(p.stem): p for p in ymaps}

for ymf in ymfs[:10]:
    h_ymf = joaat(ymf.stem)
    print(f"{ymf.name} → 0x{h_ymf:08X}")
    # Procura ymap com mesmo hash
    if h_ymf in ymap_hashes:
        print(f"  ✓ YMAP COM MESMO HASH: {ymap_hashes[h_ymf].name}")
    else:
        # Procura ymaps cujo hash do YMF bate com algo
        # Talvez o ymf hash aponte para o ymap hash
        print(f"  Sem ymap com hash 0x{h_ymf:08X}")
    print()

# Investiga: será que o hash do ymf SEM o prefixo _manifest bate com algum ymap?
print("\n=== Ymaps buscados pelo stem sem prefixo ===\n")
import re
for ymf in ymfs[:15]:
    stem = ymf.stem.lower()
    # Remove prefixos comuns
    clean = re.sub(r'^_?manifest_?', '', stem).strip('_')
    h_clean = joaat(clean)
    print(f"{ymf.name}")
    print(f"  stem limpo: '{clean}' → 0x{h_clean:08X}")
    if h_clean in ymap_hashes:
        print(f"  ✓ YMAP: {ymap_hashes[h_clean].name}")
    elif clean in [p.stem.lower() for p in ymaps]:
        print(f"  ✓ YMAP DIRETO: {clean}.ymap")
    else:
        # Lista ymaps que contenham o stem limpo
        parciais = [p.name for p in ymaps if clean in p.stem.lower()][:3]
        if parciais:
            print(f"  ~ Ymaps parciais: {parciais}")
        else:
            print(f"  ✗ Nenhum ymap encontrado")
    print()
