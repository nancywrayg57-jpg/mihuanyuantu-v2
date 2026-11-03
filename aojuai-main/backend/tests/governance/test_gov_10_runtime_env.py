from pathlib import Path

import pytest

from governance_tools.common import assert_clean
from governance_tools.runtime_env import scan_runtime_env_access


def test_gov_10_repository_runtime_uses_settings(backend_root: Path) -> None:
    result = scan_runtime_env_access(backend_root)
    assert result.discovered
    assert "app/main.py" in result.discovered
    assert "scripts/seed_data.py" in result.discovered
    assert_clean(result)


@pytest.mark.parametrize(
    "source",
    [
        'import os\nVALUE = os.environ["GOV_MUTATION"]\n',
        'import os\nVALUE = os.getenv("GOV_MUTATION")\n',
        'import os as _os\nVALUE = _os.getenv("GOV_MUTATION")\n',
        'from os import getenv as read_env\nVALUE = read_env("GOV_MUTATION")\n',
        'from os import environ as process_env\nVALUE = process_env.get("GOV_MUTATION")\n',
    ],
)
def test_gov_10_mutation_direct_environment_access_makes_target_assertion_red(
    tmp_path: Path,
    source: str,
) -> None:
    backend = tmp_path / "backend"
    probe = backend / "app" / "domain" / "new_module" / "service.py"
    probe.parent.mkdir(parents=True)
    probe.write_text(source, encoding="utf-8")

    result = scan_runtime_env_access(backend, allowlist={})

    with pytest.raises(AssertionError, match="direct process-environment access"):
        assert_clean(result)
