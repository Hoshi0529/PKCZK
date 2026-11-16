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

## Battle rules RAG

The chat searches Pokémon Champions Ranked Battles Regulation M-C as of
November 16, 2026 (JST). It defaults to Singles and uses Doubles when specified.

Install `requirements.txt`, then run `python -m back.seed_battle_rag` with the
app's existing `SUPABASE_CONNECTION_STRING`. The command creates the private
`battle_rag` schema, enables `pgvector` if needed, and upserts the reviewed
records in `data/battle_rag_m_c.json` by regulation and evidence ID. The
database role needs permission to create the schema and extension on first use.
The first run downloads the `BAAI/bge-m3` model from Hugging Face. The seed
command and app should use the same Python environment and model cache.
