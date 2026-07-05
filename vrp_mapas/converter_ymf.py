# converter_ymf.py — Converte ymfs binários para XML usando CodeWalker CLI
# Depois rode o organizer.py normalmente

import subprocess
import sys
from pathlib import Path

def encontrar_codewalker() -> Path | None:
    """Procura o CodeWalker em locais comuns."""
    candidatos = [
        Path(r"C:\Program Files\CodeWalker\CodeWalkerCLI.exe"),
        Path(r"C:\Program Files (x86)\CodeWalker\CodeWalkerCLI.exe"),
        Path(r"C:\CodeWalker\CodeWalkerCLI.exe"),
        Path(r"C:\Tools\CodeWalker\CodeWalkerCLI.exe"),
        # Procura na pasta do script também
        Path(__file__).parent / "CodeWalkerCLI.exe",
        Path(__file__).parent / "CodeWalker" / "CodeWalkerCLI.exe",
    ]
    for c in candidatos:
        if c.exists():
            return c
    return None


def is_xml(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            h = f.read(6)
        return h.startswith(b"<?xml") or h.startswith(b"<")
    except Exception:
        return False


def converter_com_codewalker(cw_exe: Path, pasta: Path):
    """Converte todos os ymfs binários usando CodeWalkerCLI."""
    ymfs = list(pasta.glob("*.ymf"))
    binarios = [y for y in ymfs if not is_xml(y)]

    if not binarios:
        print("Todos os .ymf já são XML. Nada a converter.")
        return

    print(f"Convertendo {len(binarios)} .ymf binários para XML...")
    erros = []

    for ymf in binarios:
        print(f"  Convertendo: {ymf.name}", end="", flush=True)
        try:
            result = subprocess.run(
                [str(cw_exe), "convert", str(ymf), "-o", str(ymf.with_suffix(".ymf.xml"))],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                print(" ✓")
            else:
                # Tenta sintaxe alternativa
                result2 = subprocess.run(
                    [str(cw_exe), str(ymf)],
                    capture_output=True, text=True, timeout=30
                )
                if result2.returncode == 0:
                    print(" ✓")
                else:
                    print(f" ✗ ({result.stderr.strip()[:60]})")
                    erros.append(ymf.name)
        except subprocess.TimeoutExpired:
            print(" ✗ (timeout)")
            erros.append(ymf.name)
        except Exception as e:
            print(f" ✗ ({e})")
            erros.append(ymf.name)

    print(f"\nConvertidos: {len(binarios) - len(erros)}/{len(binarios)}")
    if erros:
        print(f"Erros: {erros}")


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Converte ymf binários para XML usando CodeWalker"
    )
    parser.add_argument("--pasta", "-p", required=True, type=Path,
                        help="Pasta com os arquivos de mapa")
    parser.add_argument("--codewalker", "-cw", type=Path, default=None,
                        help="Caminho para CodeWalkerCLI.exe (opcional)")
    args = parser.parse_args()

    cw = args.codewalker or encontrar_codewalker()
    if not cw:
        print("CodeWalker CLI não encontrado.")
        print("Por favor informe o caminho: --codewalker C:\\caminho\\CodeWalkerCLI.exe")
        print()
        print("Alternativa manual no CodeWalker GUI:")
        print("  1. Abra o CodeWalker")
        print("  2. Arraste os .ymf para dentro")
        print("  3. File → Export as XML → salve na mesma pasta")
        sys.exit(1)

    converter_com_codewalker(cw, args.pasta)


if __name__ == "__main__":
    main()
