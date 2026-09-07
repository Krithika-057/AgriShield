from __future__ import annotations

import streamlit as st

from recommender import WeatherContext, load_records, recommend


st.set_page_config(page_title="AgriShield", page_icon="🌱", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Space+Grotesk:wght@500;600;700&display=swap');
:root { --ink:#173b35; --muted:#6c7d78; --leaf:#2b8068; --mint:#e7f3ec; --sun:#f2b84b; --line:#dce8e1; }
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; color: var(--ink); }
h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; letter-spacing: -0.02em; }
.hero { background: linear-gradient(120deg, #dcefe4, #f7f4e9 58%, #f9ead1); border: 1px solid #cfe3d7; padding: 2.2rem 2.4rem; border-radius: 18px; margin-bottom: 1.3rem; }
.eyebrow { text-transform: uppercase; font-size: .72rem; letter-spacing: .14em; font-weight: 700; color: var(--leaf); }
.hero h1 { font-size: 3rem; margin: .35rem 0 .4rem; color: var(--ink); }
.hero p { max-width: 660px; color: #536b64; font-size: 1.06rem; }
.metric { border-left: 3px solid var(--sun); padding-left: 12px; }
.metric strong { display:block; font: 700 1.65rem 'Space Grotesk'; }
.metric span { color: var(--muted); font-size: .82rem; }
.rec { border: 1px solid #c7d8cf; border-radius: 14px; padding: 1.1rem 1.25rem; margin: .8rem 0; background: #ffffff; color: #173b35; }
.rec h3 { margin: 0; font-size: 1.1rem; color: #102f2a; }
.rec p, .rec li, .rec small { color: #294b42; }
.rec b { color: #102f2a; }
.pill { display:inline-block; padding: .22rem .55rem; border-radius: 20px; background: #cce8d9; color: #135d46; font-size: .72rem; font-weight:700; margin: .2rem .3rem .4rem 0; }
.score { color: #0d5a43; background: #e1f1e8; border: 1px solid #b9d9c8; border-radius: 10px; padding: .55rem .7rem; font: 700 1.4rem 'Space Grotesk'; text-align:center; }
.score small { color: #31584c; font: 500 .72rem 'DM Sans'; }
.warning { background:#fff7e8; border-left: 4px solid var(--sun); padding: .75rem 1rem; color:#735423; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

treatments = load_records("treatments.json")
outbreaks = load_records("outbreaks.json")
crops = sorted({crop for treatment in treatments for crop in treatment["crops"]})
diagnoses = sorted({diagnosis for treatment in treatments for diagnosis in treatment["targets"]})

with st.sidebar:
    st.markdown("## AgriShield")
    st.caption("Context-aware intervention intelligence")
    st.divider()
    st.markdown("### Farm context")
    crop = st.selectbox("Crop", crops, index=crops.index("Tomato"))
    diagnosis = st.selectbox("Observed pest or disease", diagnoses, index=diagnoses.index("Late blight"))
    category = st.selectbox("Intervention preference", ["Any", "Organic", "Biological", "Chemical"])
    st.markdown("### Live conditions")
    temperature = st.slider("Temperature (C)", 10, 42, 26)
    humidity = st.slider("Relative humidity (%)", 20, 100, 84)
    rain = st.slider("Rain expected in next 6 hours (mm)", 0.0, 30.0, 0.0, 0.5)
    dry_hours = st.slider("Forecast dry window (hours)", 0.0, 24.0, 8.0, 0.5)
    submitted = st.button("Rank interventions", type="primary", use_container_width=True)

if "weather" not in st.session_state or submitted:
    st.session_state.weather = WeatherContext(temperature, humidity, rain, dry_hours)
    st.session_state.crop = crop
    st.session_state.diagnosis = diagnosis
    st.session_state.category = category

weather = st.session_state.weather
results = recommend(st.session_state.crop, st.session_state.diagnosis, weather, st.session_state.category, treatments, outbreaks)

st.markdown('<div class="hero"><div class="eyebrow">AgriShield / intervention desk</div><h1>Make the next treatment count.</h1><p>Recommendations combine the outbreak signal from comparable farms with the weather window available on your field right now.</p></div>', unsafe_allow_html=True)

metric_cols = st.columns(4)
for column, value, label in zip(metric_cols, [st.session_state.crop, st.session_state.diagnosis, f"{weather.humidity_pct:.0f}%", f"{weather.rain_next_6h_mm:g} mm"], ["Crop", "Detected pressure", "Humidity", "Rain in 6h"]):
    with column:
        st.markdown(f'<div class="metric"><strong>{value}</strong><span>{label}</span></div>', unsafe_allow_html=True)

st.markdown("## Ranked action plan")
if weather.rain_next_6h_mm > 2:
    st.markdown('<div class="warning">Rain is on the way. Foliar sprays are held back until a reliable dry window opens.</div>', unsafe_allow_html=True)

if not results:
    st.info("No treatment currently satisfies the crop, diagnosis, category, and weather constraints. Try a longer dry window or broaden the intervention preference.")
else:
    for index, result in enumerate(results):
        left, right = st.columns([5, 1])
        with left:
            st.markdown(f'<div class="rec"><span class="pill">#{index + 1} {result["category"]}</span><h3>{result["name"]}</h3><p>{result["instructions"]}</p><b>Why it fits</b><ul>{"".join(f"<li>{reason}</li>" for reason in result["reasons"])}</ul><small><b>Safety:</b> {result["safety"]}</small></div>', unsafe_allow_html=True)
        with right:
            st.markdown(f'<div class="score">{result["score"]}<br><small>match score</small></div>', unsafe_allow_html=True)

with st.expander("How this ranking works"):
    st.write("The score blends 62% similar-outbreak success, 18% cost efficiency, and 20% weather/context fit. Treatments are filtered first when rain, heat, or insufficient dry hours would make an application unreliable or unsafe.")
    st.caption(f"Knowledge base: {len(treatments)} treatment profiles and {len(outbreaks)} historical outbreak records.")
