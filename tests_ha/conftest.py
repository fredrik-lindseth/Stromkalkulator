"""Conftest for ekte-HA-testene.

Dette treet kjøres mot en ekte Home Assistant fra
pytest-homeassistant-custom-component, i motsetning til `tests/`, som stubber
`homeassistant.*` i `sys.modules`. De to kan ikke dele miljø: stubbene og den
ekte pakken ville kollidert i samme `sys.modules`. Derfor ligger de i hvert sitt
katalogtre med hver sin conftest, og i hvert sitt virtuelle miljø
(`just test-unit` mot gruppen `unit`, `just test-ha` mot `ha-minimum` eller
`ha-current`).

Kjøres via `just test-ha target=minimum|current`, som sender
`-o asyncio_mode=auto` fordi `hass`-fixturen er en async generator.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Repo-roten på sys.path, slik at både `import custom_components.stromkalkulator`
# og HA-loaderens interne `import custom_components` finner integrasjonen.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def pytest_collection_modifyitems(session, config, items: list) -> None:
    """Tom collection er rødt.

    Et ekte-HA-miljø som ikke fant en eneste test har ikke bevist noe. Uten
    denne vakten ville `just test-ha` gått grønn på en feilstavet sti eller en
    import som stille sluttet å samles inn.
    """
    if not items:
        pytest.exit("tests_ha samlet inn null tester. Det er rødt, ikke grønt.", returncode=1)


@pytest.fixture(autouse=True)
def _enable_custom(enable_custom_integrations):
    """Slå på lasting av custom_components/ for alle ekte-HA-tester."""
    yield
