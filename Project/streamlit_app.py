import streamlit as st
from streamlit_autorefresh import st_autorefresh
import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import plotly.express as px
from datetime import datetime

# =========================
# CONFIG A MODIFIER
# =========================
DATABASE_URL = "https://project-final-463aa-default-rtdb.europe-west1.firebasedatabase.app/"
SERVICE_KEY  = "serviceAccountKey.json"

# Chemins Firebase (adapte si besoin)
PATH_LATEST  = "node2/latest"     # ex: node2/latest
PATH_HISTORY = "node2/history"    # ex: node2/history (si tu l'as)
PATH_CMD     = "node2/commands"   # ex: node2/commands

REFRESH_MS   = 2000  # 2s

# =========================
# INIT FIREBASE (1 fois)
# =========================
if not firebase_admin._apps:
    cred = credentials.Certificate(SERVICE_KEY)
    firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})

# =========================
# PAGE CONFIG + CSS
# =========================
st.set_page_config(page_title="Dashboard IoT - Node2", page_icon="📡", layout="wide")

CUSTOM_CSS = """
<style>
:root{
  --bg:#0b1220;
  --card:#101a2f;
  --card2:#0f172a;
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
    # Ajuste les seuils selon ton projet
    TEMP_HIGH  = 30.0
    LUM_NIGHT  = 1200
    SOUND_HIGH = 2500  # si ton capteur sonore est 0..4095 (analogRead)

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
    ref = db.reference(PATH_LATEST)
    data = ref.get() or {}
    return data

def get_history_as_df(limit=60):
    # Si tu n'as pas de history, on renvoie None
    ref = db.reference(PATH_HISTORY)
    hist = ref.get()
    if not hist:
        return None

    # hist peut être dict {pushId: {..}, pushId2: {..}}
    rows = []
    for k, v in hist.items():
        if isinstance(v, dict):
            rows.append(v)

    if not rows:
        return None

    df = pd.DataFrame(rows)

    # Normaliser colonne timestamp si présente
    if "timestamp" in df.columns:
        # timestamp peut être epoch ou string
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

    # Colonnes attendues
    for c in ["temperature","humidity","luminosity","sound"]:
        if c not in df.columns:
            df[c] = None

    df = df.sort_values("dt", na_position="last").tail(limit)
    return df

def send_command(payload: dict):
    db.reference(PATH_CMD).update(payload)

# =========================
# HEADER
# =========================
colA, colB = st.columns([3,1])
with colA:
    st.title("📡 Tableau de bord IoT — Node2")
    st.caption("Données temps réel (Firebase RTDB) + commandes (LED RGB, mode nuit, force publish).")
with colB:
    st.markdown('<div class="card">🔄 Rafraîchissement auto: <b>2s</b><br/><span style="color:#94a3b8">Localhost</span></div>', unsafe_allow_html=True)

# =========================
# LOAD DATA
# =========================
latest = get_latest()

temp = safe_float(latest.get("temperature"))
hum  = safe_float(latest.get("humidity"))
ldr  = safe_int(latest.get("luminosity"))
son  = safe_int(latest.get("sound"))
ts   = latest.get("timestamp", None)

status_txt, status_cls = compute_status(temp, ldr, son)

# =========================
# KPI ROW
# =========================
k1, k2, k3, k4, k5 = st.columns([1.2,1.2,1.2,1.2,1.2])

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
    kpi_card("Température", None if temp is None else round(temp,1), " °C", "Capteur DHT11")
with k2:
    kpi_card("Humidité", None if hum is None else round(hum,1), " %", "Capteur DHT11")
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
