"""Script to create all 22 PVSK paper package scaffolds."""
import uuid
from pathlib import Path

BASE = Path("/personal/Gaia/tests/fixtures/storage/pvsk")

# (dir_name, package_name, import_name, year, description)
PAPERS = [
    ("2009", "pvsk-kojima2009-gaia", "pvsk_kojima2009", 2009,
     "Kojima et al. JACS 2009 — First perovskite photovoltaic cell"),
    ("2012-1", "pvsk-kim2012-gaia", "pvsk_kim2012", 2012,
     "Kim et al. Sci Rep 2012 — All-solid-state PSC >9%"),
    ("2012-2", "pvsk-lee2012-gaia", "pvsk_lee2012", 2012,
     "Lee et al. Science 2012 — Meso-superstructured PSC 10.9%"),
    ("2013", "pvsk-burschka2013-gaia", "pvsk_burschka2013", 2013,
     "Burschka et al. Nature 2013 — Sequential deposition ~15%"),
    ("nature12509", "pvsk-liu2013-gaia", "pvsk_liu2013", 2013,
     "Liu et al. Nature 2013 — Planar heterojunction by vapour deposition >15%"),
    ("2014", "pvsk-jeon2014-gaia", "pvsk_jeon2014", 2014,
     "Jeon et al. Nat Mater 2014 — Solvent engineering"),
    ("2015", "pvsk-jeon2015-gaia", "pvsk_jeon2015", 2015,
     "Jeon et al. Nature 2015 — Compositional engineering FA-based >18%"),
    ("c5ee03874j", "pvsk-saliba2016-gaia", "pvsk_saliba2016", 2016,
     "Saliba et al. EES 2016 — Triple cation perovskites"),
    ("2017", "pvsk-grancini2017-gaia", "pvsk_grancini2017", 2017,
     "Grancini et al. Nat Commun 2017 — 2D/3D one-year stability"),
    ("science.aay7044", "pvsk-min2020-gaia", "pvsk_min2020", 2020,
     "Min et al. Science 2020 — alpha-FAPbI3 inherent bandgap"),
    ("s41586-021-03406-5", "pvsk-jeong2021-gaia", "pvsk_jeong2021", 2021,
     "Jeong et al. Nature 2021 — Pseudo-halide anion engineering"),
    ("s41586-021-04372-8", "pvsk-park2021-gaia", "pvsk_park2021", 2021,
     "Park et al. Nature 2021 — Improved carrier management ~25%"),
    ("science.abm5784", "pvsk-lin2022-gaia", "pvsk_lin2022", 2022,
     "Lin et al. Science 2022 — Damp heat stable 2D/3D PSCs"),
    ("science.abn5679", "pvsk-zhao2022-gaia", "pvsk_zhao2022", 2022,
     "Zhao et al. Science 2022 — Accelerated aging all-inorganic PSCs"),
    ("science.adk1633", "pvsk-liu2023a-gaia", "pvsk_liu2023a", 2023,
     "Liu et al. Science 2023 — Bimolecular passivation p-i-n"),
    ("s41560-023-01254-3", "pvsk-gu2023-gaia", "pvsk_gu2023", 2023,
     "Gu et al. Nat Energy 2023 — Bifacial minimodule optimization"),
    ("s41586-023-06278-z", "pvsk-lin2023-gaia", "pvsk_lin2023", 2023,
     "Lin et al. Nature 2023 — All-perovskite tandem 3D/3D"),
    ("s41586-024-07997-7", "pvsk-hou2024-gaia", "pvsk_hou2024", 2024,
     "Hou et al. Nature 2024 — Perovskite/Si tandem 33.89%"),
    ("s41560-024-01667-8", "pvsk-li2024-gaia", "pvsk_li2024", 2024,
     "Li et al. Nat Energy 2024 — Module passivation layer"),
    ("s41467-024-46016-1", "pvsk-jelly2024-gaia", "pvsk_jelly2024", 2024,
     "Jelly et al. Nat Commun 2024 — Roll-to-roll fabricated modules"),
    ("s41586-025-09333-z", "pvsk-he2025-gaia", "pvsk_he2025", 2025,
     "He et al. Nature 2025 — Perovskite/Si tandem ~35%"),
    ("s41586-025-09773-7", "pvsk-liu2025-gaia", "pvsk_liu2025", 2025,
     "Liu et al. Nature 2025 — All-perovskite tandem 30.1%"),
]

for source_dir, pkg_name, import_name, year, desc in PAPERS:
    pkg_dir = BASE / pkg_name
    src_dir = pkg_dir / "src" / import_name
    src_dir.mkdir(parents=True, exist_ok=True)

    # pyproject.toml
    pyproject = f"""[project]
name = "{pkg_name}"
version = "1.0.0"
description = "{desc}"
requires-python = ">=3.12"
dependencies = [
    "gaia-lang",
    "pvsk-meta-gaia",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{import_name}"]

[tool.gaia]
namespace = "pvsk"
type = "knowledge-package"
uuid = "{uuid.uuid4()}"
"""
    (pkg_dir / "pyproject.toml").write_text(pyproject)

    # .gitignore
    gitignore = """.gaia/beliefs.json
.gaia/dep_beliefs/
"""
    (pkg_dir / ".gitignore").write_text(gitignore)

    # Placeholder __init__.py
    (src_dir / "__init__.py").write_text(f"# {desc}\n")

print(f"Created {len(PAPERS)} packages")
for _, pkg_name, _, year, desc in PAPERS:
    print(f"  {year}: {pkg_name}")
