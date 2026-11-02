from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

selection_path = Path(__file__).resolve().parents[1] / "ChosePokemon.py"
selection_spec = spec_from_file_location("pokecham_selection_page", selection_path)
selection_module = module_from_spec(selection_spec)
selection_spec.loader.exec_module(selection_module)

selection_module.render()
