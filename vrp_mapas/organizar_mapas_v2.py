import struct
import shutil
import re
from pathlib import Path
from collections import defaultdict

# ─── Configuração ──────────────────────────────────────────────────────────────
PASTA_ORIGEM  = Path(r"C:\Users\rian_\OneDrive\Documentos\GitHub\organizemaps\vrp_mapas\mapas_baguncados")
PASTA_DESTINO = Path(r"C:\Users\rian_\OneDrive\Documentos\GitHub\organizemaps\vrp_mapas\mapas_organizados")
MODO_SIMULACAO = False
LOG_PATH = PASTA_DESTINO.parent / "organizacao_log_v6.txt"

FXMANIFEST_TEMPLATE = '''fx_version 'cerulean'
game 'gta5'

this_is_a_map 'yes'

files {{
    'stream/**',
}}

data_file 'DLC_ITYP_REQUEST' 'stream/*.ytyp'
'''

# ─── JOAAT ─────────────────────────────────────────────────────────────────────
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

# ─── Índice duplo ──────────────────────────────────────────────────────────────
def construir_indice(pasta: Path) -> tuple[dict[int, Path], dict[str, Path]]:
    idx_hash: dict[int, Path] = {}
    idx_nome: dict[str, Path] = {}
    for f in pasta.iterdir():
        if not f.is_file():
            continue
        sl = f.stem.lower()
        nl = f.name.lower()
        idx_hash[joaat(sl)] = f
        idx_hash[joaat(nl)] = f
        idx_nome[sl] = f
        idx_nome[nl] = f
    return idx_hash, idx_nome

# ─── Índice de prefixos ─────────────────────────────────────────────────────────
def construir_indice_prefixo(pasta: Path) -> dict[str, list[Path]]:
    ytyps = [f for f in pasta.iterdir() if f.is_file() and f.suffix.lower() == '.ytyp']
    prefixos = sorted(
        [(f.stem.lower(), f) for f in ytyps],
        key=lambda x: len(x[0]),
        reverse=True
    )
    idx: dict[str, list[Path]] = defaultdict(list)
    for arq in pasta.iterdir():
        if not arq.is_file():
            continue
        if arq.suffix.lower() == '.ytyp':
            continue
        stem_l = arq.stem.lower()
        for prefixo, ytyp_path in prefixos:
            if stem_l.startswith(prefixo):
                idx[prefixo].append(arq)
                break
    return dict(idx)

# ─── Extração de hashes ─────────────────────────────────────────────────────────
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

# ─── Extração de strings ────────────────────────────────────────────────────────
_RE_STR = re.compile(rb'[a-zA-Z0-9_\-\.]{4,}')

def extrair_strings(data: bytes) -> set[str]:
    encontradas: set[str] = set()
    for m in _RE_STR.finditer(data):
        s = m.group().decode('ascii', errors='ignore').lower()
        encontradas.add(s)
        if '.' in s:
            encontradas.add(s.rsplit('.', 1)[0])
    return encontradas

# ─── Resolução recursiva ────────────────────────────────────────────────────────
def resolver_dependencias(
    arquivo: Path,
    idx_hash: dict[int, Path],
    idx_nome: dict[str, Path],
    visitados: set[Path],
    profundidade: int = 3
) -> set[Path]:
    if arquivo in visitados or profundidade == 0:
        return set()
    visitados.add(arquivo)
    encontrados: set[Path] = set()
    data = arquivo.read_bytes()

    hashes = extrair_hashes(data)
    for h, dep in idx_hash.items():
        if h in hashes and dep not in visitados:
            encontrados.add(dep)
            if dep.suffix.lower() in ('.ytyp', '.ymap', '.ymf'):
                sub = resolver_dependencias(dep, idx_hash, idx_nome, visitados, profundidade - 1)
                encontrados.update(sub)

    strings = extrair_strings(data)
    for s in strings:
        if s in idx_nome:
            dep = idx_nome[s]
            if dep not in visitados and dep not in encontrados:
                encontrados.add(dep)
                if dep.suffix.lower() in ('.ytyp', '.ymap', '.ymf'):
                    sub = resolver_dependencias(dep, idx_hash, idx_nome, visitados, profundidade - 1)
                    encontrados.update(sub)

    return encontrados

# ─── Nome de pasta limpo ────────────────────────────────────────────────────────
def nome_pasta_para_ymf(ymf: Path) -> str:
    stem = ymf.stem.lower()
    prefixos = (
        '_manifestfavela', '_manifestfvl', '_manifestmlo',
        'farm_manifestmlo', '_manifest', 'manifest', 'farm_manifest',
    )
    for p in prefixos:
        if stem.startswith(p):
            resto = stem[len(p):]
            if resto:
                return resto
            break
    return stem.lstrip('_') or stem

# ─── Gera fxmanifest.lua ────────────────────────────────────────────────────────
def gerar_fxmanifest(pasta_dest: Path, simulacao: bool):
    manifest_path = pasta_dest / 'fxmanifest.lua'
    if not simulacao:
        manifest_path.write_text(FXMANIFEST_TEMPLATE, encoding='utf-8')

# ─── Principal ─────────────────────────────────────────────────────────────────
def organizar():
    print("Construindo índices...")
    idx_hash, idx_nome = construir_indice(PASTA_ORIGEM)
    idx_prefixo = construir_indice_prefixo(PASTA_ORIGEM)
    todos_ymf = sorted(PASTA_ORIGEM.glob('*.ymf'))
    print(f"Hash: {len(idx_hash)} | Nome: {len(idx_nome)} | Prefixos: {len(idx_prefixo)} | .ymf: {len(todos_ymf)}\n")

    log: list[str] = []
    contadores = defaultdict(int)

    for ymf in todos_ymf:
        pasta_nome = nome_pasta_para_ymf(ymf)
        pasta_dest = PASTA_DESTINO / pasta_nome
        # subpasta stream/ onde ficam todos os assets
        pasta_stream = pasta_dest / 'stream'

        # ── Resolve dependências ─────────────────────────────────────────────
        visitados: set[Path] = set()
        deps = resolver_dependencias(ymf, idx_hash, idx_nome, visitados, profundidade=3)
        deps.add(ymf)

        # ── Adiciona filhos por prefixo de cada .ytyp encontrado ─────────────
        ytyps_encontrados = {d for d in deps if d.suffix.lower() == '.ytyp'}
        for ytyp in ytyps_encontrados:
            prefixo = ytyp.stem.lower()
            if prefixo in idx_prefixo:
                for filho in idx_prefixo[prefixo]:
                    deps.add(filho)

        unicos: list[Path] = [ymf] + sorted(deps - {ymf}, key=lambda p: p.name)

        if len(unicos) <= 1:
            log.append(f"[SEM MATCH] {ymf.name}")
            contadores['sem_match'] += 1
            continue

        log.append(f"\n[RESOURCE] {pasta_nome}/  ({len(unicos)} arquivos)")

        if not MODO_SIMULACAO:
            pasta_stream.mkdir(parents=True, exist_ok=True)
            gerar_fxmanifest(pasta_dest, MODO_SIMULACAO)

        for arq in unicos:
            # .ymf vai para a raiz do resource (não dentro de stream/)
            if arq.suffix.lower() == '.ymf':
                dst = pasta_dest / arq.name
                destino_log = arq.name
            else:
                # todos os outros vão para stream/
                dst = pasta_stream / arq.name
                destino_log = f"stream/{arq.name}"

            tag = 'SIMUL' if MODO_SIMULACAO else 'COPY'

            if dst.exists():
                log.append(f"  [JÁ EXISTE] {destino_log}")
                contadores['ja_existe'] += 1
            else:
                log.append(f"  [{tag}] {destino_log}")
                contadores['copiados'] += 1
                if not MODO_SIMULACAO:
                    shutil.copy2(arq, dst)

        contadores['resources'] += 1

    # ── Resumo ──────────────────────────────────────────────────────────────────
    resumo = [
        '\n\n=== RESUMO FINAL ===',
        f"  Resources criados              : {contadores['resources']}",
        f"  Arquivos copiados (total)      : {contadores['copiados']}",
        f"  Já existiam no destino         : {contadores['ja_existe']}",
        f"  .ymf sem matches               : {contadores['sem_match']}",
        f"  Modo simulação                 : {MODO_SIMULACAO}",
    ]
    log.extend(resumo)

    texto = '\n'.join(log)
    print(texto[-3000:])  # mostra só o final no terminal
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(texto, encoding='utf-8-sig')
    print(f'\nLog completo salvo em: {LOG_PATH}')

if __name__ == '__main__':
    organizar()
