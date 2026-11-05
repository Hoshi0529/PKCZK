# PKCZK

## Start the app (Windows PowerShell)

From the project folder:

```powershell
python -m streamlit run .\streamlit_app.py
```

To use the project's Python 3.11 launcher on port 8765, run `.\run.ps1`.

## Refresh local move options

Pokemon Detail uses PCBD's Singles CSV to create the local move options file.
Refresh it from the project folder with:

```powershell
python .\scripts\sync_pcbd_moves.py
```

## Page files

`streamlit_app.py` registers each page with `st.Page` and runs it through
`st.navigation`. The screen implementations are in `app_pages/`, shared UI
and styles are in `ui/`, and data access is in `back/`.
