# AgriShield

AgriShield is a context-aware pest and disease intervention recommender. It combines:

- Weather-aware filtering for humidity, heat, rain, and available dry hours.
- Collaborative ranking from similar historical outbreaks.
- A local treatment knowledge base that can be replaced with PlantVillage, IPM guide, and Open-Meteo ingestion jobs.

## Run locally

```powershell
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL shown by Streamlit. To run the core checks:

```powershell
pytest
```

The current JSON files are intentionally small demonstration datasets. They make the app deterministic and runnable offline while leaving a clear adapter boundary for real data ingestion.
