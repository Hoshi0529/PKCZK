from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

chat_path = Path(__file__).resolve().parents[1] / "Chat.py"
chat_spec = spec_from_file_location("pokecham_chat_page", chat_path)
chat_module = module_from_spec(chat_spec)
chat_spec.loader.exec_module(chat_module)

chat_module.render()
