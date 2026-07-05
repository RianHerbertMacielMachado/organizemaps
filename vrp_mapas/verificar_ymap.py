from pathlib import Path
import struct
import re

PASTA = Path(r"C:\Users\rian_\OneDrive\Documentos\GitHub\organizemaps\vrp_mapas\mapas_baguncados")

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

# Constrói índice hash → arquivo para TODOS os arquivos
idx_hash: dict[int, Path] = {}
idx_nome: dict[str, Path] = {}
for f in PASTA.iterdir():
    if not f.is_file():
        continue
    sl = f.stem.lower()
    nl = f.name.lower()
    idx_hash[joaat(sl)] = f
    idx_hash[joaat(nl)] = f
    idx_nome[sl] = f
    idx_nome[nl] = f

# Pega os arquivos "órfãos" conhecidos (exemplos da _assets que sobram)
orfaos_amostra = [
    "casa7vb.ydr", "barraco.ydr", "covid.ydr", "escada.ydr",
    "casas_tunnel.ydr", "bloco3.ydr", "muro.ydr", "poste.ydr",
    "adegasamu.ydr", "barracoloja.ydr"
]

_RE_STR = re.compile(rb'[a-zA-Z0-9_\-\.]{4,}')

def extrair_hashes(data: bytes) -> set[int]:
    hashes: set[int] = set()
    for i in range(0, len(data) - 3, 4):
        le = struct.unpack_from('<I', data, i)[0]
        if le >= 0x10000:
            hashes.add(le)
        be = struct.unpack_from('>I', data, i)[0]
        if be >= 0x10000:
            hashes.add(be)
    return hashes

def extrair_strings(data: bytes) -> set[str]:
    encontradas: set[str] = set()
    for m in _RE_STR.finditer(data):
        s = m.group().decode('ascii', errors='ignore').lower()
        encontradas.add(s)
        if '.' in s:
            encontradas.add(s.rsplit('.', 1)[0])
    return encontradas

print("=== VERIFICANDO SE ÓRFÃOS SÃO REFERENCIADOS NOS .YMAP ===\n")

# Para cada órfão, calcula seu hash e procura nos .ymap
for nome_orfao in orfaos_amostra:
    stem = nome_orfao.rsplit('.', 1)[0].lower()
    h = joaat(stem)
    
    achou_em = []
    for ymap in PASTA.glob('*.ymap'):
        data = ymap.read_bytes()
        hashes = extrair_hashes(data)
        strings = extrair_strings(data)
        
        if h in hashes or stem in strings:
            achou_em.append(ymap.name)
    
    if achou_em:
        print(f"✅ {nome_orfao}")
        print(f"   hash: 0x{h:08X}")
        print(f"   referenciado em: {achou_em[:5]}{'...' if len(achou_em) > 5 else ''}")
    else:
        print(f"❌ {nome_orfao} — não encontrado em nenhum .ymap")
    print()

# Agora faz a varredura completa: para cada .ymap, encontra assets que não foram alocados
print("\n=== ASSETS REFERENCIADOS POR .YMAP QUE ESTÃO SOLTOS ===\n")

# Carrega lista de arquivos já alocados pelo v5 (aproximação: todos que têm ytyp com prefixo)
# Vamos listar quais ydr/ytd/ybn ficam órfãos mas são citados em algum ymap
ydr_orfaos = {f.stem.lower(): f for f in PASTA.iterdir() 
              if f.is_file() and f.suffix.lower() in ('.ydr', '.ytd', '.ybn', '.yft')
              and not any(PASTA.glob(f.stem.lower() + '.ytyp'))}

print(f"Total de assets sem .ytyp homônimo: {len(ydr_orfaos)}")

# Para cada asset órfão, verifica se aparece em algum ymap
citados_em_ymap: dict[str, list[str]] = {}
todos_ymaps = list(PASTA.glob('*.ymap'))
print(f"Verificando em {len(todos_ymaps)} .ymap files...")

# Cache dos ymaps para não reler
ymap_cache = {}
for ymap in todos_ymaps:
    data = ymap.read_bytes()
    ymap_cache[ymap.name] = (extrair_hashes(data), extrair_strings(data))

for stem, f in list(ydr_orfaos.items())[:200]:  # testa os primeiros 200
    h = joaat(stem)
    refs = []
    for nome_ymap, (hashes, strings) in ymap_cache.items():
        if h in hashes or stem in strings:
            refs.append(nome_ymap)
    if refs:
        citados_em_ymap[stem] = refs

print(f"\nAssets órfãos que aparecem em algum .ymap: {len(citados_em_ymap)}")
for stem, ymaps in list(citados_em_ymap.items())[:20]:
    print(f"  {stem} → {ymaps[:3]}{'...' if len(ymaps) > 3 else ''}")
