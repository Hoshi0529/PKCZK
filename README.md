# PKCZK

## Start the app (Windows PowerShell)

From the project folder:

```powershell
python -m streamlit run .\streamlit_app.py
```

To use the project's Python 3.11 launcher on port 8765, run `.\run.ps1`.

## Page files

`streamlit_app.py` registers each page with `st.Page` and runs it through
`st.navigation`. The screen implementations are in `app_pages/`, shared UI
and styles are in `ui/`, and data access is in `back/`.
