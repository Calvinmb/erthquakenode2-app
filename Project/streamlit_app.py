import streamlit as st
from streamlit_autorefresh import st_autorefresh
import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import plotly.express as px
from datetime import datetime

# =========================
# CONFIG (STREAMLIT SECRETS)
# =========================
PATH_LATEST  = "node2/latest"
PATH_HISTORY = "node2/history"     # si tu l'as
PATH_CMD     = "node2/commands"

REFRESH_MS   = 2000  # 2s

# =========================
# INIT FIREBASE (1 fois)
# =========================
def init_firebase():
    if firebase_admin._apps:
        return

    # URL RTDB
    DATABASE_URL = st.secrets["FIREBASE_DATABASE_URL"]

    # Service account (depuis Secrets)
    service_account = dict(st.secrets["firebase"])

    # Corrige les \n si Streamlit les garde en texte
    if "private_key" in service_account and isinstance(service_account["private_key"], str):
        service_account["private_key"] = service_account["private_key"].replace("\\n", "\n")

    cred = credentials.Certificate(service_account)
    firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})

init_firebase()

# =========================
# PAGE CONFIG + CSS
# =========================
st.set_page_config(page_title="Dashboard IoT - Node2", page_icon="📡", layout="wide")

CUSTOM_CSS = """
<style>
:root{
  --bg:#0b1220;
  --card:#101a2f;
  --text:#e5e7eb;
  --muted:#94a3b8;
  --accent:#60a5fa;
  --good:#22c55e;
  --warn:#f59e0b;
  --bad:#ef4444;
  --violet:#a855f7;
}
.main { background: linear-gradient(135deg, #0b1220 0%, #0b1630 55%, #0b1220 100%); }
.block-container { padding-top: 1.4rem; }
h1,h2,h3 { color: var(--text) !important; }
p,div,span,label { color: var(--text); }

.card{
  background: rgba(16,26,47,0.82);
  border: 1px solid rgba(148,163,184,0.14);
  border-radius: 18px;
  padding: 16px 18px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.25);
}

.kpi-title{ font-size: 0.85rem; color: var(--muted); margin-bottom: 8px; }
.kpi-value{ font-size: 2rem; font-weight: 800; color: var(--text); line-height: 1; }
.kpi-sub{ font-size: 0.85rem; color: var(--muted); margin-top: 6px; }

.badge{
  display:inline-block;
  padding: 6px 10px;
  border-radius: 999px;
  font-weight: 700;
  font-size: 0.8rem;
  border: 1px solid rgba(148,163,184,0.18);
  background: rgba(15,23,42,0.65);
}
.badge.ok{ color: var(--good); }
.badge.hot{ color: var(--bad); }
.badge.night{ color: var(--accent); }
.badge.noise{ color: var(--violet); }
.badge.unk{ color: var(--warn); }

hr{ border: none; height: 1px; background: rgba(148,163,184,0.15); margin: 18px 0; }

section[data-testid="stSidebar"]{
  background: rgba(10,16,31,0.92);
  border-right: 1px solid rgba(148,163,184,0.12);
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Auto-refresh
st_autorefresh(interval=REFRESH_MS, key="refresh")

# =========================
# HELPERS
# =========================
def safe_float(x):
    try:
        return float(x)
    except:
        return None

def safe_int(x):
    try:
        return int(x)
    except:
        return None

def compute_status(t, lum, snd):
    TEMP_HIGH  = 30.0
    LUM_NIGHT  = 1200
    SOUND_HIGH = 2500

    if t is None or lum is None or snd is None:
        return "UNKNOWN", "unk"
    if t >= TEMP_HIGH:
        return "HOT", "hot"
    if snd >= SOUND_HIGH:
        return "NOISE", "noise"
    if lum < LUM_NIGHT:
        return "NIGHT", "night"
    return "OK", "ok"

def get_latest():
    return db.reference(PATH_LATEST).get() or {}

def get_history_as_df(limit=80):
    hist = db.reference(PATH_HISTORY).get()
    if not hist:
        return None

    rows = []
    if isinstance(hist, dict):
        for _, v in hist.items():
            if isinstance(v, dict):
                rows.append(v)

    if not rows:
        return None

    df = pd.DataFrame(rows)

    # timestamp -> dt
    if "timestamp" in df.columns:
        def to_dt(val):
            try:
                if isinstance(val, (int, float)):
                    return datetime.fromtimestamp(val)
                return pd.to_datetime(val)
            except:
                return pd.NaT
        df["dt"] = df["timestamp"].apply(to_dt)
    else:
        df["dt"] = pd.NaT

    for c in ["temperature", "humidity", "luminosity", "sound"]:
        if c not in df.columns:
            df[c] = None

    df = df.sort_values("dt", na_position="last").tail(limit)
    return df

def send_command(payload: dict):
    db.reference(PATH_CMD).update(payload)

# =========================
# HEADER
# =========================
colA, colB = st.columns([3, 1])
with colA:
    st.title("📡 Tableau de bord IoT — Node2")
    st.caption("Données temps réel (Firebase RTDB) + commandes.")
with colB:
    st.markdown(
        f'<div class="card">🔄 Rafraîchissement auto: <b>{REFRESH_MS/1000:.0f}s</b><br/>'
        f'<span style="color:#94a3b8">Streamlit Cloud</span></div>',
        unsafe_allow_html=True
    )

# =========================
# SIDEBAR (COMMANDES)
# =========================
st.sidebar.title("🎛️ Commandes")
color = st.sidebar.selectbox("Couleur LED", ["off", "red", "green", "blue", "white", "yellow", "purple", "cyan"])
night = st.sidebar.toggle("Mode nuit")

if st.sidebar.button("📤 Envoyer commande LED"):
    send_command({"led": color})
    st.sidebar.success(f"Commande LED envoyée: {color}")

if st.sidebar.button("🌙 Appliquer mode nuit"):
    send_command({"night_mode": bool(night)})
    st.sidebar.success(f"Mode nuit: {night}")

if st.sidebar.button("⚡ Force envoi données"):
    send_command({"force_publish": True})
    st.sidebar.success("Force publish demandé")

# =========================
# LOAD DATA
# =========================
latest = get_latest()
temp = safe_float(latest.get("temperature"))
hum  = safe_float(latest.get("humidity"))
ldr  = safe_int(latest.get("luminosity"))
son  = safe_int(latest.get("sound"))
ts   = latest.get("timestamp")

status_txt, status_cls = compute_status(temp, ldr, son)

# =========================
# KPI ROW
# =========================
k1, k2, k3, k4, k5 = st.columns([1.2, 1.2, 1.2, 1.2, 1.2])

def kpi_card(title, value, suffix="", sub=""):
    val = "—" if value is None else f"{value}{suffix}"
    st.markdown(
        f"""
        <div class="card">
          <div class="kpi-title">{title}</div>
          <div class="kpi-value">{val}</div>
          <div class="kpi-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with k1:
    kpi_card("Température", None if temp is None else round(temp, 1), " °C", "Capteur DHT11")
with k2:
    kpi_card("Humidité", None if hum is None else round(hum, 1), " %", "Capteur DHT11")
with k3:
    kpi_card("Luminosité", ldr, "", "LDR (0–4095)")
with k4:
    kpi_card("Son", son, "", "KY-038 (analog)")
with k5:
    badge_html = f'<span class="badge {status_cls}">STATUT: {status_txt}</span>'
    ts_txt = "Aucun" if not ts else str(ts)
    st.markdown(
        f"""
        <div class="card">
          <div class="kpi-title">État</div>
          <div style="margin-bottom:10px;">{badge_html}</div>
          <div class="kpi-sub">Horodatage : {ts_txt}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("<hr/>", unsafe_allow_html=True)

# =========================
# GRAPHIQUES (HISTORY)
# =========================
st.subheader("📈 Historique (si disponible)")
df = get_history_as_df(limit=80)

if df is None or df.empty:
    st.info("Aucun historique trouvé dans Firebase (node2/history). Tu peux garder uniquement latest, ou activer l’historique côté Node-RED.")
else:
    # Conserver uniquement les lignes valides
    df_plot = df.copy()
    if "dt" in df_plot.columns:
        df_plot = df_plot.dropna(subset=["dt"])

    c1, c2 = st.columns(2)
    with c1:
        fig1 = px.line(df_plot, x="dt", y="temperature", title="Température (°C)")
        st.plotly_chart(fig1, use_container_width=True)
    with c2:
        fig2 = px.line(df_plot, x="dt", y="humidity", title="Humidité (%)")
        st.plotly_chart(fig2, use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        fig3 = px.line(df_plot, x="dt", y="luminosity", title="Luminosité (LDR)")
        st.plotly_chart(fig3, use_container_width=True)
    with c4:
        fig4 = px.line(df_plot, x="dt", y="sound", title="Son (KY-038)")
        st.plotly_chart(fig4, use_container_width=True)

    st.markdown("<div class='card'><div class='kpi-title'>Dernières lignes</div></div>", unsafe_allow_html=True)
    st.dataframe(df.tail(15), use_container_width=True)
