import struct
import shutil
from pathlib import Path
from collections import defaultdict

# ─── Configuração ──────────────────────────────────────────────────────────────
PASTA_ORIGEM = Path(r"C:\Users\rian_\OneDrive\Documentos\GitHub\organizemaps\vrp_mapas\mapas_baguncados")
PASTA_DESTINO = Path(r"C:\Users\rian_\OneDrive\Documentos\GitHub\organizemaps\vrp_mapas\mapas_organizados")
MODO_SIMULACAO = True   # True = só mostra o que faria | False = move os arquivos de verdade
LOG_PATH = PASTA_DESTINO.parent / "organizacao_log.txt"

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

# ─── Índice de hashes (big-endian) ──────────────────────────────────────────────
def construir_indice(pasta: Path) -> dict[int, Path]:
    idx: dict[int, Path] = {}
    for f in pasta.iterdir():
        if not f.is_file():
            continue
        for nome in (f.stem, f.name):
            idx[joaat(nome)] = f
    return idx

# ─── Leitura de hashes de um .ymf ──────────────────────────────────────────────
def extrair_hashes_ymf(caminho: Path) -> set[int]:
    data = caminho.read_bytes()
    hashes = set()
    for i in range(0, len(data) - 3, 4):
        val_be = struct.unpack_from('>I', data, i)[0]
        if val_be >= 0x10000:
            hashes.add(val_be)
    return hashes

# ─── Determinar nome da pasta de destino ────────────────────────────────────────
def nome_pasta_para_ymf(ymf: Path) -> str:
    """
    Deriva um nome de pasta limpo a partir do nome do .ymf.
    Remove prefixos como '_manifest', 'manifest', 'farm_manifest', etc.
    """
    stem = ymf.stem.lower()

    # Remove prefixos conhecidos
    for prefixo in ('_manifestfavela', '_manifestfvl', '_manifestmlo',
                    'farm_manifestmlo', '_manifest', 'manifest', 'farm_manifest'):
        if stem.startswith(prefixo):
            resto = stem[len(prefixo):]
            if resto:
                return resto
            break

    # Caso o stem seja exatamente o prefixo (ex: "_manifest.ymf")
    return stem.lstrip('_')

# ─── Core: mapear ymf → arquivos associados ──────────────────────────────────────
def mapear_ymf(ymf: Path, indice: dict[int, Path]) -> dict[str, list[Path]]:
    """
    Retorna dicionário  extensão → [lista de arquivos encontrados]
    """
    hashes = extrair_hashes_ymf(ymf)
    resultado: dict[str, list[Path]] = defaultdict(list)
    vistos: set[int] = set()

    for h, arquivo in indice.items():
        if h in hashes and h not in vistos:
            vistos.add(h)
            ext = arquivo.suffix.lower()
            resultado[ext].append(arquivo)

    return resultado

# ─── Operação principal ──────────────────────────────────────────────────────────
def organizar():
    indice = construir_indice(PASTA_ORIGEM)
    print(f"Índice construído: {len(indice)} entradas")

    todos_ymf = sorted(PASTA_ORIGEM.glob('*.ymf'))
    print(f"Total de .ymf: {len(todos_ymf)}\n")

    log_linhas: list[str] = []
    estatisticas = {'movidos': 0, 'sem_match': 0, 'ja_na_pasta': 0}
    arquivos_ja_alocados: set[Path] = set()  # evita mover o mesmo arquivo para 2 pastas

    for ymf in todos_ymf:
        pasta_nome = nome_pasta_para_ymf(ymf)
        pasta_dest = PASTA_DESTINO / pasta_nome
        mapeamento = mapear_ymf(ymf, indice)

        # Sempre inclui o próprio .ymf
        todos_arquivos: list[Path] = [ymf]
        for lista in mapeamento.values():
            todos_arquivos.extend(lista)

        # Remove duplicatas mantendo ordem
        vistos_paths: set[Path] = set()
        arquivos_unicos: list[Path] = []
        for p in todos_arquivos:
            if p not in vistos_paths:
                vistos_paths.add(p)
                arquivos_unicos.append(p)

        if len(arquivos_unicos) <= 1:
            estatisticas['sem_match'] += 1
            log_linhas.append(f"[SEM MATCH] {ymf.name}")
            continue

        log_linhas.append(f"\n[PASTA] {pasta_nome}/")
        log_linhas.append(f"  .ymf origem: {ymf.name}")

        if not MODO_SIMULACAO:
            pasta_dest.mkdir(parents=True, exist_ok=True)

        for arquivo in arquivos_unicos:
            if arquivo in arquivos_ja_alocados and arquivo != ymf:
                # arquivo já foi copiado para outra pasta — registra mas não move
                log_linhas.append(f"  [COMPARTILHADO] {arquivo.name} (já em outra pasta)")
                continue

            destino = pasta_dest / arquivo.name
            if destino.exists():
                estatisticas['ja_na_pasta'] += 1
                log_linhas.append(f"  [JÁ EXISTE] {arquivo.name}")
            else:
                estatisticas['movidos'] += 1
                log_linhas.append(f"  {'[SIMUL]' if MODO_SIMULACAO else '[MOVE]'} {arquivo.name}")
                if not MODO_SIMULACAO:
                    shutil.copy2(arquivo, destino)

            arquivos_ja_alocados.add(arquivo)

    # ─── Identificar arquivos não vinculados a nenhum .ymf ───────────────────────
    todos_na_pasta = set(PASTA_ORIGEM.iterdir())
    todos_ymf_set = set(todos_ymf)
    nao_vinculados = todos_na_pasta - arquivos_ja_alocados - todos_ymf_set

    log_linhas.append("\n\n=== ARQUIVOS SEM .ymf ASSOCIADO ===")
    pasta_orfaos = PASTA_DESTINO / "_orfaos"
    for arq in sorted(nao_vinculados):
        if not arq.is_file():
            continue
        log_linhas.append(f"  [ORFAO] {arq.name}")
        if not MODO_SIMULACAO:
            pasta_orfaos.mkdir(parents=True, exist_ok=True)
            shutil.copy2(arq, pasta_orfaos / arq.name)

    # ─── Resumo ─────────────────────────────────────────────────────────────────
    log_linhas.append("\n\n=== RESUMO ===")
    log_linhas.append(f"  Arquivos movidos/copiados : {estatisticas['movidos']}")
    log_linhas.append(f"  Já existiam no destino    : {estatisticas['ja_na_pasta']}")
    log_linhas.append(f"  .ymf sem matches          : {estatisticas['sem_match']}")
    log_linhas.append(f"  Arquivos órfãos           : {len([l for l in log_linhas if '[ORFAO]' in l])}")
    log_linhas.append(f"  Modo simulação            : {MODO_SIMULACAO}")

    # ─── Escreve log ─────────────────────────────────────────────────────────────
    log_texto = '\n'.join(log_linhas)
    print(log_texto)

    if not MODO_SIMULACAO or True:  # sempre grava o log
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOG_PATH.write_text(log_texto, encoding='utf-8')
        print(f"\nLog salvo em: {LOG_PATH}")

if __name__ == '__main__':
    organizar()
