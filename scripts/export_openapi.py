"""
Exporta el esquema OpenAPI de la aplicación a ``openapi.yml``.

FastAPI es code-first: el contrato se genera desde los decoradores de ruta y los
modelos Pydantic. Este script materializa ese contrato en un archivo estático
para que el frontend pueda consumirlo (generación de clientes, tipos, mocks,
validación en CI, etc.).

No levanta el servidor ni abre conexión a MongoDB: solo importa la app y vuelca
``app.openapi()``.

Uso (desde la raíz del proyecto):

    python scripts/export_openapi.py
"""

import io
import sys
from pathlib import Path

import yaml

# Raíz del proyecto (un nivel por encima de scripts/), para poder importar `app`
# aunque el script se ejecute directamente desde cualquier directorio.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

# Salida: raíz del proyecto -> openapi.yml
OUTPUT = ROOT / "openapi.yml"


def _represent_str(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    """Usa bloque literal (``|``) para cadenas multilínea (descripciones legibles)."""
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


def main() -> None:
    # Registramos el representer para que las descripciones largas no se
    # serialicen como una única línea entre comillas.
    yaml.SafeDumper.add_representer(str, _represent_str)

    spec = app.openapi()
    content = yaml.safe_dump(
        spec,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1000,
    )

    io.open(OUTPUT, "w", encoding="utf-8", newline="\n").write(content)
    print(f"openapi.yml generado ({len(spec['paths'])} rutas): {OUTPUT}")


if __name__ == "__main__":
    main()
