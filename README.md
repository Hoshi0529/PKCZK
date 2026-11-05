# PKCZK

## Start the app (Windows PowerShell)

From the project folder, run:

```powershell
.\run.ps1
```

This starts the Streamlit app using `ChosePokemon.py` as its entry point at <http://localhost:8765>. Do not run `python run`: Python treats `run` as a script filename, and this project has no file named `run`.

To start it directly instead:

```powershell
python -m streamlit run .\ChosePokemon.py --server.port 8765

## Page files

The active Streamlit pages are in `pages/`. The similarly named files in the project root (`Login.py`, `Setting.py`, `PokemonDetail.py`, and `Chat.py`) are compatibility entry points and are not used by the app navigation; the application starts from `ChosePokemon.py`.
```
