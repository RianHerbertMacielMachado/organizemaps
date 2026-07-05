import struct
import shutil
from pathlib import Path
from collections import defaultdict

# ─── Configuração ──────────────────────────────────────────────────────────────
PASTA_ORIGEM  = Path(r"C:\Users\rian_\OneDrive\Documentos\GitHub\organizemaps\vrp_mapas\mapas_baguncados")
PASTA_DESTINO = Path(r"C:\Users\rian_\OneDrive\Documentos\GitHub\organizemaps\vrp_mapas\mapas_organizados")
MODO_SIMULACAO = False   # ← mude para False para executar de verdade
LOG_PATH = PASTA_DESTINO.parent / "organizacao_log_final.txt"

# Extensões que devem ficar na pasta do manifest (recursos "de alto nível")
EXTS_MANIFEST = {'.ymf', '.ymap', '.ytyp', '.ybn', '.obn', '.ydr', '.ytd', '.yft', '.ycd', '.ydd', '.ymt'}

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

# ─── Índice de hashes ──────────────────────────────────────────────────────────
def construir_indice(pasta: Path) -> dict[int, Path]:
    idx: dict[int, Path] = {}
    for f in pasta.iterdir():
        if not f.is_file():
            continue
        for nome in (f.stem, f.name):
            idx[joaat(nome)] = f
    return idx

# ─── Hashes de um .ymf ─────────────────────────────────────────────────────────
def extrair_hashes_ymf(caminho: Path) -> set[int]:
    data = caminho.read_bytes()
    hashes = set()
    for i in range(0, len(data) - 3, 4):
        val_be = struct.unpack_from('>I', data, i)[0]
        if val_be >= 0x10000:
            hashes.add(val_be)
    return hashes

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

# ─── Mapear ymf → arquivos associados ──────────────────────────────────────────
def mapear_ymf(ymf: Path, indice: dict[int, Path]) -> list[Path]:
    hashes = extrair_hashes_ymf(ymf)
    encontrados: list[Path] = []
    vistos: set[int] = set()
    for h, arquivo in indice.items():
        if h in hashes and h not in vistos:
            vistos.add(h)
            encontrados.append(arquivo)
    return encontrados

# ─── Copiar ou simular ─────────────────────────────────────────────────────────
def copiar_arquivo(src: Path, dst_dir: Path, simulacao: bool, log: list[str], tag: str = 'MOVE'):
    dst = dst_dir / src.name
    if dst.exists():
        log.append(f"  [JÁ EXISTE] {src.name}")
        return False
    log.append(f"  [{'SIMUL' if simulacao else tag}] {src.name}")
    if not simulacao:
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return True

# ─── Principal ─────────────────────────────────────────────────────────────────
def organizar():
    indice = construir_indice(PASTA_ORIGEM)
    todos_ymf = sorted(PASTA_ORIGEM.glob('*.ymf'))
    print(f"Índice: {len(indice)} entradas | .ymf: {len(todos_ymf)}")

    log: list[str] = []
    arquivos_alocados: set[Path] = set()
    contadores = defaultdict(int)

    # ── Fase 1: organizar por manifest ──────────────────────────────────────────
    for ymf in todos_ymf:
        pasta_nome = nome_pasta_para_ymf(ymf)
        pasta_dest = PASTA_DESTINO / pasta_nome
        associados = mapear_ymf(ymf, indice)

        todos_arquivos = [ymf] + associados
        # Remove duplicatas mantendo ordem
        vistos_p: set[Path] = set()
        unicos: list[Path] = []
        for p in todos_arquivos:
            if p not in vistos_p:
                vistos_p.add(p)
                unicos.append(p)

        if len(unicos) <= 1:
            log.append(f"[SEM MATCH] {ymf.name}")
            contadores['sem_match'] += 1
            continue

        log.append(f"\n[PASTA] {pasta_nome}/")
        log.append(f"  .ymf origem: {ymf.name}")

        if not MODO_SIMULACAO:
            pasta_dest.mkdir(parents=True, exist_ok=True)

        for arquivo in unicos:
            if arquivo in arquivos_alocados and arquivo != ymf:
                log.append(f"  [COMPARTILHADO] {arquivo.name}")
                continue
            moveu = copiar_arquivo(arquivo, pasta_dest, MODO_SIMULACAO, log)
            if moveu:
                contadores['movidos'] += 1
            else:
                contadores['ja_existe'] += 1
            arquivos_alocados.add(arquivo)

    # ── Fase 2: assets brutos orphãos → _assets/ ────────────────────────────────
    pasta_assets = PASTA_DESTINO / '_assets'
    log.append('\n\n=== ASSETS BRUTOS (sem .ymf direto) ===')

    orfaos_por_prefixo: dict[str, list[Path]] = defaultdict(list)

    for arq in sorted(PASTA_ORIGEM.iterdir()):
        if not arq.is_file():
            continue
        if arq in arquivos_alocados:
            continue
        if arq.suffix.lower() not in EXTS_MANIFEST:
            continue  # ignora desktop.ini, .rar, .xml, .cwproj, etc.

        # Agrupa por prefixo (tudo antes do primeiro dígito ou sublinhado numérico)
        prefixo = arq.stem.rstrip('0123456789abcdefghijklmnopqrstuvwxyz_')
        if not prefixo:
            prefixo = arq.stem[:10]
        orfaos_por_prefixo[prefixo].append(arq)

    # Registra e copia
    contadores['orfaos'] = 0
    for prefixo, arquivos in sorted(orfaos_por_prefixo.items()):
        for arq in arquivos:
            log.append(f"  [ASSET] {arq.name}")
            contadores['orfaos'] += 1
            if not MODO_SIMULACAO:
                pasta_assets.mkdir(parents=True, exist_ok=True)
                dst = pasta_assets / arq.name
                if not dst.exists():
                    shutil.copy2(arq, dst)

    # ── Resumo ──────────────────────────────────────────────────────────────────
    resumo = [
        '\n\n=== RESUMO FINAL ===',
        f"  Arquivos movidos para pastas   : {contadores['movidos']}",
        f"  Já existiam no destino         : {contadores['ja_existe']}",
        f"  .ymf sem matches               : {contadores['sem_match']}",
        f"  Assets brutos → _assets/       : {contadores['orfaos']}",
        f"  Modo simulação                 : {MODO_SIMULACAO}",
        f"  Total de pastas criadas        : {len(todos_ymf) - contadores['sem_match']}",
    ]
    log.extend(resumo)
    texto = '\n'.join(log)
    print(texto)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(texto, encoding='utf-8-sig')
    print(f'\nLog salvo em: {LOG_PATH}')

if __name__ == '__main__':
    organizar()
