from datetime import date, datetime
import io
import json
import sqlite3
import urllib.request
import pandas as pd
import streamlit as st
from google import genai
from PIL import Image

# ==========================================
# 1. CONFIGURAZIONE PAGINA E STATO SESSIONE
# ==========================================
st.set_page_config(
    page_title="Suite Algologica - Terapia del Dolore",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

LISTA_PRESTAZIONI = [
    "1. Prima Visita Algologica",
    "2. Visita di Controllo",
    "3. Procedura Infiltrativa",
    "4. Day-Hospital Infiltrazione",
    "5. Day-Hospital Ozonoterapia Sistemica",
    "6. Rinnovo Prescrizione Cannabis",
]

default_states = {
    "id_paziente_input": "",
    "fascia_eta_input": "",
    "tipo_prestazione": LISTA_PRESTAZIONI[0],
    "num_seduta_ozono": 1,
    "ultimo_quadro_nota": "",
    "ocr_estratti": "",
    "note_scale_cliniche": "",
    "bozza_referto_finale": "",
    # Variabili strutturate per la Ricerca Clinica (popolate dai calcolatori)
    "ricerca_dn4": None,
    "ricerca_fiqr": None,
    "ricerca_mme": None,
    "ricerca_cast": None,
    "gsheet_synced": False,
}
for key, val in default_states.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ==========================================
# 2. MOTORE DATABASE STRUTTURATO PER RICERCA
# ==========================================
DB_FILE = "ambulatorio_dolore_ricerca.db"


def init_db():
    """Crea la tabella strutturata con colonne atomiche per ricerca clinica e statistica."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS visite (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_paziente TEXT NOT NULL,
            fascia_eta TEXT,
            data_visita TEXT NOT NULL,
            timestamp_salvataggio TEXT NOT NULL,
            tipo_prestazione TEXT NOT NULL,
            meccanismo_dolore TEXT,
            nrs_riposo INTEGER,
            nrs_movimento INTEGER,
            pgic_esito TEXT,
            score_dn4 INTEGER,
            score_fiqr REAL,
            mme_oppioidi REAL,
            score_cast INTEGER,
            procedura_tipo TEXT,
            procedura_livello_lato TEXT,
            procedura_guida TEXT,
            ozono_seduta INTEGER,
            ozono_conc_ug_ml INTEGER,
            ozono_vol_ml INTEGER,
            cannabis_preparato TEXT,
            dati_clinici TEXT,
            ocr_estratti TEXT,
            scale_cliniche TEXT,
            referto_finale TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def invia_a_gsheet(webhook_url: str, record_dict: dict) -> bool:
    """Invia il record salvato in tempo reale al Foglio Google (Google Drive)."""
    if not webhook_url or not webhook_url.strip().startswith("https://script.google.com"):
        return False
    try:
        data_bytes = json.dumps(record_dict, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            webhook_url.strip(),
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status == 200
    except Exception:
        return False


def sincronizza_da_gsheet(webhook_url: str) -> int:
    """Se il DB SQLite locale è vuoto (es. dopo riavvio server), recupera tutto da Google Sheets."""
    if not webhook_url or not webhook_url.strip().startswith("https://script.google.com"):
        return 0
    try:
        with urllib.request.urlopen(webhook_url.strip(), timeout=8) as resp:
            records = json.loads(resp.read().decode("utf-8"))
        if not isinstance(records, list):
            return 0
        return importa_lista_record_db(records)
    except Exception:
        return 0


def salva_visita_db(record: dict, webhook_url: str = "") -> bool:
    """Salva nel DB SQLite locale e, se attivo, sincronizza sul Foglio Google."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    colonne = [
        "id_paziente",
        "fascia_eta",
        "data_visita",
        "timestamp_salvataggio",
        "tipo_prestazione",
        "meccanismo_dolore",
        "nrs_riposo",
        "nrs_movimento",
        "pgic_esito",
        "score_dn4",
        "score_fiqr",
        "mme_oppioidi",
        "score_cast",
        "procedura_tipo",
        "procedura_livello_lato",
        "procedura_guida",
        "ozono_seduta",
        "ozono_conc_ug_ml",
        "ozono_vol_ml",
        "cannabis_preparato",
        "dati_clinici",
        "ocr_estratti",
        "scale_cliniche",
        "referto_finale",
    ]
    valori = [record.get(col) for col in colonne]
    placeholders = ", ".join(["?"] * len(colonne))
    c.execute(
        f"INSERT INTO visite ({', '.join(colonne)}) VALUES ({placeholders})",
        valori,
    )
    conn.commit()
    conn.close()

    # Sincronizzazione Cloud su Google Drive (se configurata)
    return invia_a_gsheet(webhook_url, record)


def get_df_tutte_visite() -> pd.DataFrame:
    """Restituisce l'intero database come DataFrame Pandas pronto per analisi ed export."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM visite ORDER BY id DESC", conn)
    conn.close()
    return df


def elimina_visita_per_id(row_id: int):
    """Elimina una singola riga dal database locale tramite il suo ID univoco."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM visite WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()


def get_storico_paziente(id_paz: str) -> list:
    if not id_paz or not id_paz.strip():
        return []
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT * FROM visite WHERE id_paziente = ? ORDER BY id DESC",
        (id_paz.strip().upper(),),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_tutti_id_pazienti() -> list:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT DISTINCT id_paziente FROM visite ORDER BY id_paziente ASC")
    ids = [r[0] for r in c.fetchall()]
    conn.close()
    return ids


def importa_lista_record_db(records: list) -> int:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    colonne = [
        "id_paziente",
        "fascia_eta",
        "data_visita",
        "timestamp_salvataggio",
        "tipo_prestazione",
        "meccanismo_dolore",
        "nrs_riposo",
        "nrs_movimento",
        "pgic_esito",
        "score_dn4",
        "score_fiqr",
        "mme_oppioidi",
        "score_cast",
        "procedura_tipo",
        "procedura_livello_lato",
        "procedura_guida",
        "ozono_seduta",
        "ozono_conc_ug_ml",
        "ozono_vol_ml",
        "cannabis_preparato",
        "dati_clinici",
        "ocr_estratti",
        "scale_cliniche",
        "referto_finale",
    ]
    inseriti = 0
    for r in records:
        id_p = str(r.get("id_paziente", "")).strip().upper()
        ts = str(r.get("timestamp_salvataggio", "")).strip()
        if not id_p:
            continue
        c.execute(
            "SELECT COUNT(*) FROM visite WHERE id_paziente = ? AND timestamp_salvataggio = ?",
            (id_p, ts),
        )
        if c.fetchone()[0] == 0:
            valori = [r.get(col) if r.get(col) != "" else None for col in colonne]
            valori[0] = id_p
            placeholders = ", ".join(["?"] * len(colonne))
            c.execute(
                f"INSERT INTO visite ({', '.join(colonne)}) VALUES ({placeholders})",
                valori,
            )
            inseriti += 1
    conn.commit()
    conn.close()
    return inseriti


init_db()


# ==========================================
# 3. LOGICA AUTOMATICA AL CAMBIO ID PAZIENTE
# ==========================================
def aggiorna_stato_da_id(id_scelto: str):
    id_norm = id_scelto.strip().upper()
    st.session_state["id_paziente_input"] = id_norm
    storico = get_storico_paziente(id_norm)

    if storico:
        ultima = storico[0]
        if ultima.get("fascia_eta"):
            st.session_state["fascia_eta_input"] = ultima["fascia_eta"]

        sedute_ozono_fatte = [
            v for v in storico if str(v["tipo_prestazione"]).startswith("5.")
        ]
        st.session_state["num_seduta_ozono"] = len(sedute_ozono_fatte) + 1

        if str(ultima["tipo_prestazione"]).startswith("5."):
            st.session_state["tipo_prestazione"] = LISTA_PRESTAZIONI[4]
        elif st.session_state["tipo_prestazione"] == LISTA_PRESTAZIONI[0]:
            st.session_state["tipo_prestazione"] = LISTA_PRESTAZIONI[1]

        st.session_state["ultimo_quadro_nota"] = (
            f"Ultimo accesso del {ultima['data_visita']} ({ultima['tipo_prestazione']}): "
            f"NRS riposo {ultima.get('nrs_riposo', '-')}/10, dinamico {ultima.get('nrs_movimento', '-')}/10.\n"
            f"{ultima.get('dati_clinici', '')}"
        )
    else:
        st.session_state["tipo_prestazione"] = LISTA_PRESTAZIONI[0]
        st.session_state["num_seduta_ozono"] = 1
        st.session_state["ultimo_quadro_nota"] = ""


def callback_input_id():
    aggiorna_stato_da_id(st.session_state["id_paziente_input"])


def callback_select_archivio():
    scelta = st.session_state.get("selettore_archivio", "")
    if scelta and scelta != "-- Seleziona un ID in archivio --":
        aggiorna_stato_da_id(scelta)


# ==========================================
# 4. FUNZIONE CHIAMATA API GEMINI
# ==========================================
def chiama_gemini(
    api_key: str,
    prompt: str,
    image: Image.Image = None,
    model_name: str = "gemini-2.5-flash",
) -> str:
    if not api_key:
        return "⚠️ ERRORE: Inserisci una chiave API Gemini valida nella barra laterale o nei Secrets di Streamlit."
    try:
        client = genai.Client(api_key=api_key)
        contents = [image, prompt] if image is not None else [prompt]
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
        )
        return response.text
    except Exception as e:
        return f"⚠️ Errore durante la chiamata a Gemini API: {str(e)}"


# ==========================================
# 5. ATLANTE SEMEIOLOGICO ALGOLOGICO
# ==========================================
ATLANTE_SEMEIOTICA = {
    "Test di Lasègue (SLR) e Bragard — Radicolopatia L4-S1": {
        "target": "Radici L5, S1 (più raramente L4) / Conflitto disco-radicolare",
        "esecuzione": (
            "Paziente supino. Sollevamento passivo dell'arto inferiore a ginocchio esteso. "
            "Bragard: si abbassa l'arto di 5° rispetto alla soglia algica e si dorsiflette passivamente la caviglia."
        ),
        "positivita": (
            "Dolore radicolare irradiato sotto il ginocchio tra **30° e 70°**. "
            "Il Lasègue crociato ha specificità >90% per ernia discale."
        ),
        "yt_url": "https://www.youtube.com/results?search_query=Straight+Leg+Raise+Test+Lasegue+Bragard+Physiotutors",
    },
    "Test di Wasserman (Femoral Stretch) — Radicolopatia L2-L4": {
        "target": "Nervo Femorale / Radici L2, L3, L4",
        "esecuzione": "Paziente prono, flessione passiva del ginocchio a 90° ed estensione dell'anca.",
        "positivita": "Dolore lancinante/parestesie lungo la **faccia anteriore della coscia** o mediale di gamba.",
        "yt_url": "https://www.youtube.com/results?search_query=Prone+Knee+Bending+Femoral+Nerve+Stretch+Test+Physiotutors",
    },
    "Slump Test — Tensione Neurodinamica / Conflitto Durale": {
        "target": "Sacco durale, midollo e radici lombosacrali",
        "esecuzione": "Paziente seduto: flessione toraco-lombare + flessione cervicale + estensione ginocchio + dorsiflessione caviglia.",
        "positivita": "Riproduzione del sintomo radicolare che **si attenua estendendo il capo**.",
        "yt_url": "https://www.youtube.com/results?search_query=Slump+Test+radiculopathy+Physiotutors",
    },
    "Test di Kemp (Quadrant Test) — Sindrome Faccette Articolari": {
        "target": "Articolazioni Zigoapofisarie (Faccette Articolari) Lombari",
        "esecuzione": "Estensione combinata a rotazione e lateroflessione omolaterale con carico assiale.",
        "positivita": "Riproduzione del **dolore lombare paramediano** o pseudoradicolare gluteo.",
        "yt_url": "https://www.youtube.com/results?search_query=Kemp+Test+Lumbar+Facet+Joint+Physiotutors",
    },
    "Test di Patrick (FABER) e Cluster di Laslett — Sacro-Iliaca": {
        "target": "Articolazione Sacro-Iliaca (SIJ) vs Patologia Coxo-Femorale",
        "esecuzione": "FABER (figura a 4) + Cluster di Laslett (Distraction, Thigh Thrust, FABER, Compression, Gaenslen).",
        "positivita": "Dolore posteriore profondo (area di Fortin) con ≥ 3 test positivi su 5 nel Cluster di Laslett.",
        "yt_url": "https://www.youtube.com/results?search_query=Laslett+Cluster+FABER+Test+Sacroiliac+Joint+Physiotutors",
    },
    "FAIR Test e Test di Pace — Sindrome del Piriforme": {
        "target": "Muscolo Piriforme / Intrappolamento Nervo Sciatico",
        "esecuzione": "FAIR: decubito laterale, anca flessa 60°, ginocchio 90°, adduzione e intrarotazione. Pace: abduzione contro resistenza da seduto.",
        "positivita": "Dolore profondo al centro del gluteo con o senza irradiazione sciatalgica.",
        "yt_url": "https://www.youtube.com/results?search_query=FAIR+Test+Piriformis+Syndrome+Physiotutors",
    },
    "Test di Spurling — Radicolopatia Cervicale": {
        "target": "Radici Cervicali (C4-T1) / Stenosi Foraminale Cervicale",
        "esecuzione": "Estensione e lateroflessione del collo verso il lato dolente + cauta compressione assiale.",
        "positivita": "Dolore radicolare/parestesie lungo l'arto superiore omolaterale.",
        "yt_url": "https://www.youtube.com/results?search_query=Spurling+Test+Cervical+Radiculopathy+Physiotutors",
    },
    "Segno di Tinel e Manovra di Phalen — Neuropatie da Intrappolamento": {
        "target": "Nervo Mediano (Tunnel Carpale) o altri tronchi nervosi superficiali",
        "esecuzione": "Tinel: percussione sul nervo. Phalen: flessione massimale dei polsi per 60s.",
        "positivita": "Parestesie nel territorio di innervazione distale.",
        "yt_url": "https://www.youtube.com/results?search_query=Phalen+Tinel+Carpal+Tunnel+Test+Physiotutors",
    },
}


# ==========================================
# 6. SIDEBAR: CONFIGURAZIONE & CLOUD SYNC
# ==========================================
with st.sidebar:
    st.title("🩺 Suite Algologica")
    st.caption("Supporto clinico & Database Ricerca")
    st.divider()

    api_key_secret = (
        st.secrets.get("GEMINI_API_KEY", "")
        if "GEMINI_API_KEY" in st.secrets
        else ""
    )
    if api_key_secret:
        st.success("🔒 API Key Gemini attiva")
        api_key = api_key_secret
    else:
        api_key = st.text_input("🔑 Gemini API Key:", type="password")

    # Configurazione Webhook Google Sheets (per salvataggio fisico su Google Drive)
    gsheet_secret = (
        st.secrets.get("GSHEET_WEBHOOK_URL", "")
        if "GSHEET_WEBHOOK_URL" in st.secrets
        else ""
    )
    if gsheet_secret:
        gsheet_url = gsheet_secret
        st.success("☁️ Google Drive Sync attivo")
    else:
        gsheet_url = st.text_input(
            "☁️ URL Webhook Google Sheet (opz.):",
            placeholder="https://script.google.com/macros/s/...",
            help="Incolla l'URL del tuo Google Apps Script per salvare ogni visita in tempo reale sul tuo Google Drive.",
        )

    # Sincronizzazione automatica all'avvio se Google Sheet è collegato
    if gsheet_url and not st.session_state["gsheet_synced"]:
        recuperate = sincronizza_da_gsheet(gsheet_url)
        st.session_state["gsheet_synced"] = True
        if recuperate > 0:
            st.toast(f"☁️ Sincronizzate {recuperate} visite da Google Drive!")

    modello_scelto = st.selectbox(
        "Modello AI:", ["gemini-2.5-flash", "gemini-2.5-pro"], index=0
    )

    st.divider()
    tipo_prestazione = st.radio(
        "📋 Tipo di Prestazione (Auto-adattivo):",
        LISTA_PRESTAZIONI,
        key="tipo_prestazione",
    )

    st.divider()
    if st.button("🗑️ Nuovo Paziente / Svuota Schermata", use_container_width=True):
        for key, val in default_states.items():
            if key != "gsheet_synced":
                st.session_state[key] = val
        st.rerun()


# ==========================================
# 7. INTESTAZIONE PAZIENTE E RICONOSCIMENTO STORICO
# ==========================================
st.header(f"Amb. Terapia del Dolore — {tipo_prestazione.split('. ')[1]}")

col_meta1, col_meta2, col_meta3, col_meta4 = st.columns([2, 2, 1, 1])
with col_meta1:
    id_paziente = st.text_input(
        "🆔 Digita ID Paziente (Invio per cercare)",
        key="id_paziente_input",
        on_change=callback_input_id,
        placeholder="es. PAZ-001",
    )
with col_meta2:
    lista_archivio = ["-- Seleziona un ID in archivio --"] + get_tutti_id_pazienti()
    st.selectbox(
        "🔍 Oppure richiama ID già in archivio:",
        options=lista_archivio,
        key="selettore_archivio",
        on_change=callback_select_archivio,
    )
with col_meta3:
    fascia_eta = st.text_input(
        "🎂 Età", key="fascia_eta_input", placeholder="es. 64 aa"
    )
with col_meta4:
    data_visita = st.date_input("📅 Data", value=date.today())

storico_paz = get_storico_paziente(id_paziente)
sedute_ozono_pregresse = [
    v for v in storico_paz if str(v["tipo_prestazione"]).startswith("5.")
]

# Variabili per il salvataggio strutturato nel DB di ricerca
meccanismo_db = None
nrs_rip_db, nrs_mov_db = None, None
pgic_db = None
proc_tipo_db, proc_lato_db, proc_guida_db = None, None, None
oz_sed_db, oz_conc_db, oz_vol_db = None, None, None
cannabis_prep_db = None

if id_paziente.strip():
    if storico_paz:
        ultima_v = storico_paz[0]
        msg_ozono = (
            f" | 🩸 **Sedute Ozono già eseguite: {len(sedute_ozono_pregresse)}** (Prossima: **N° {len(sedute_ozono_pregresse)+1}**)"
            if sedute_ozono_pregresse
            else ""
        )
        st.success(
            f"🔄 **Paziente `{id_paziente.upper()}` riconosciuto in archivio!** "
            f"({len(storico_paz)} accessi — Ultimo: {ultima_v['data_visita']} [{ultima_v['tipo_prestazione'].split('. ')[1]}])"
            f"{msg_ozono}"
        )
        with st.expander(
            f"📚 Consulta Storico Visite di {id_paziente.upper()} ({len(storico_paz)} accessi)"
        ):
            for idx, v in enumerate(storico_paz):
                titolo_v = f"📌 {v['data_visita']} — {v['tipo_prestazione']}"
                if v.get("ozono_seduta"):
                    titolo_v += f" (Seduta GAEI N° {v['ozono_seduta']} a {v.get('ozono_conc_ug_ml')} µg/ml)"
                st.markdown(f"**{titolo_v}**")
                st.text(v.get("referto_finale") or v.get("dati_clinici") or "")
                if idx < len(storico_paz) - 1:
                    st.divider()
    else:
        st.info(
            f"🆕 **Nuovo ID Paziente (`{id_paziente.upper()}`):** Nessuna visita precedente in archivio. Impostata *Prima Visita Algologica*."
        )


# ==========================================
# 8. STRUTTURA A 5 SCHEDE (INCLUSO DB RICERCA)
# ==========================================
tab_visita, tab_ocr, tab_tools, tab_output, tab_db = st.tabs(
    [
        "📝 1. Scheda Clinica & EO",
        "📷 2. Scansione Referti (OCR)",
        "🛠️ 3. Coltellino Svizzero (Scale & Oppioidi)",
        "📄 4. Referto AI & Salvataggio",
        "📊 5. Database & Ricerca Clinica",
    ]
)

# ==============================================================================
# TAB 1: SCHEDA CLINICA DINAMICA IN BASE ALLA PRESTAZIONE
# ==============================================================================
with tab_visita:
    dati_raccolti = f"ID PAZIENTE: {id_paziente or 'Non specificato'} ({fascia_eta}) - DATA: {data_visita.strftime('%d/%m/%Y')}\n"
    dati_raccolti += f"PRESTAZIONE: {tipo_prestazione.split('. ')[1]}\n\n"

    if tipo_prestazione.startswith("1."):
        st.subheader("Anamnesi Generale e Farmacologica")
        c1, c2 = st.columns(2)
        with c1:
            apr = st.text_area("Anamnesi Patologica Remota", height=90)
            allergie_anticoag = st.text_input("⚠️ Allergie / Anticoagulanti o Antiaggreganti")
        with c2:
            terapia_domiciliare = st.text_area("Terapia Antalgica e Domiciliare in Atto", height=90)
            trattamenti_pregressi = st.text_input("Precedenti Trattamenti Antalgici / Fisioterapici")

        st.divider()
        st.subheader("Anamnesi Antalgica e Caratteristiche del Dolore")
        ca1, ca2, ca3 = st.columns(3)
        with ca1:
            esordio_durata = st.text_input("Esordio e Durata")
            sede_irradiazione = st.text_area("Sede Principale e Irradiazione", height=80)
        with ca2:
            caratteri_dolore = st.multiselect(
                "Caratteristiche Qualitative del Dolore",
                [
                    "Gravativo",
                    "Urente / Bruciante",
                    "Lancinante / Scossa elettrica",
                    "Trafittivo",
                    "Pulsante",
                    "Costrittivo",
                    "Sordo / Continuo",
                    "Parestesie / Formicolio associate",
                    "Allodinia",
                ],
            )
            ritmo_dolore = st.selectbox(
                "Andamento Temporale",
                [
                    "Continuo con esacerbazioni al carico",
                    "Prevalentemente meccanico (al movimento)",
                    "Prevalentemente notturno / a riposo",
                    "Accessionale / Parossistico",
                    "Costante h24",
                ],
            )
        with ca3:
            fattori_mod = st.text_area("Fattori Scatenanti e Allevianti", height=80)
            impatto_sonno_adl = st.selectbox(
                "Impatto sul Sonno e sulle ADL",
                [
                    "Sonno conservato, lieve limitazione ADL",
                    "Risvegli notturni occasionali, moderata limitazione ADL",
                    "Grave insonnia algica, severa limitazione funzionale nelle ADL",
                ],
            )

        st.markdown("##### Valutazione Intensità del Dolore (Scala NRS 0-10)")
        cn1, cn2, cn3 = st.columns(3)
        with cn1:
            nrs_riposo = st.slider("NRS a Riposo (Statico)", 0, 10, 4)
        with cn2:
            nrs_movimento = st.slider("NRS in Movimento (Dinamico)", 0, 10, 8)
        with cn3:
            meccanismo_prevalente = st.multiselect(
                "Ipotesi Patogenetica Prevalente",
                [
                    "Nocicettivo Meccanico/Degenerativo",
                    "Nocicettivo Infiammatorio",
                    "Neuropatico Periferico/Radicolare",
                    "Neuropatico Centrale",
                    "Nociplastico / Sensibilizzazione Centrale",
                    "Misto",
                ],
            )

        nrs_rip_db, nrs_mov_db = nrs_riposo, nrs_movimento
        meccanismo_db = ", ".join(meccanismo_prevalente)

        st.divider()
        st.subheader("Esame Obiettivo Algologico e Manovre Semeiologiche")
        ceo1, ceo2 = st.columns([2, 1])
        with ceo1:
            eo_ispezione_palpazione = st.text_area("Ispezione, Palpazione e Trigger Points", height=100)
            eo_neuro_manovre = st.text_area("Esame Neurologico Distrettuale e Manovre Provocative", height=100)
        with ceo2:
            st.markdown("🧭 **Atlante Semeiologico & Video**")
            manovra_scelta = st.selectbox("Seleziona manovra clinica:", list(ATLANTE_SEMEIOTICA.keys()))
            info_manovra = ATLANTE_SEMEIOTICA[manovra_scelta]
            with st.container(border=True):
                st.caption(f"🎯 **Target:** {info_manovra['target']}")
                st.markdown(f"**Esecuzione:** {info_manovra['esecuzione']}")
                st.markdown(f"**Positività:** {info_manovra['positivita']}")
                st.link_button("🎥 Apri Video Dimostrativi su YouTube", info_manovra["yt_url"], use_container_width=True)

        dati_raccolti += (
            f"APR: {apr}\nALLERGIE / ANTICOAGULANTI: {allergie_anticoag}\n"
            f"TERAPIA IN ATTO: {terapia_domiciliare}\nTRATTAMENTI PREGRESSI: {trattamenti_pregressi}\n\n"
            f"ANAMNESI ANTALGICA:\n- Esordio/Durata: {esordio_durata}\n- Sede e irradiazione: {sede_irradiazione}\n"
            f"- Caratteri: {', '.join(caratteri_dolore)} ({ritmo_dolore})\n- Fattori modulanti: {fattori_mod}\n"
            f"- Impatto Sonno/ADL: {impatto_sonno_adl}\n- Intensità: NRS a riposo {nrs_riposo}/10, NRS dinamico {nrs_movimento}/10\n"
            f"- Componente ipotizzata: {meccanismo_db}\n\n"
            f"ESAME OBIETTIVO:\n{eo_ispezione_palpazione}\n{eo_neuro_manovre}\n"
        )

    elif tipo_prestazione.startswith("2."):
        st.subheader("Valutazione Evolutiva di Controllo")
        cc1, cc2 = st.columns(2)
        with cc1:
            diagnosi_nota = st.text_area(
                "Quadro Clinico e Terapia Precedente (Pre-compilato dallo storico)",
                value=st.session_state.get("ultimo_quadro_nota", ""),
                height=130,
            )
            aderenza_tollerabilita = st.text_area("Aderenza alla Terapia ed Eventuali Effetti Collaterali", height=80)
        with cc2:
            esito_globale = st.selectbox(
                "Andamento Clinico Globale (PGIC)",
                [
                    "Netto miglioramento (>50% pain relief)",
                    "Miglioramento parziale (30-50% pain relief)",
                    "Quadro stazionario",
                    "Peggioramento clinico",
                ],
            )
            nrs_attuale_rip = st.slider("NRS Attuale a Riposo", 0, 10, 2)
            nrs_attuale_mov = st.slider("NRS Attuale in Movimento", 0, 10, 4)
            eo_controllo = st.text_area("Rivalutazione Obiettiva Odierna e Modifiche Terapeutiche", height=80)

        nrs_rip_db, nrs_mov_db = nrs_attuale_rip, nrs_attuale_mov
        pgic_db = esito_globale

        dati_raccolti += (
            f"QUADRO PRECEDENTE IN FOLLOW-UP:\n{diagnosi_nota}\n\n"
            f"ANDAMENTO CLINICO ODIERNO: {esito_globale} (NRS attuale a riposo {nrs_attuale_rip}/10, in movimento {nrs_attuale_mov}/10)\n"
            f"TOLLERABILITÀ/ADERENZA: {aderenza_tollerabilita}\nESAME OBIETTIVO ODIERNO: {eo_controllo}\n"
        )

    elif tipo_prestazione.startswith("3.") or tipo_prestazione.startswith("4."):
        st.subheader("Verbale Procedura Interventistica / Infiltrativa")
        ci1, ci2, ci3 = st.columns(3)
        with ci1:
            consenso_inf = st.checkbox("✅ Consenso Informato scritto acquisito", value=True)
            check_coag = st.checkbox("✅ Verifica sospensione Anticoagulanti/Antiaggreganti (ASRA/SIAARTI)", value=True)
            allergie_proc = st.text_input("Allergie note", value="Nessuna allergia nota riferita")
        with ci2:
            distretto_proc = st.selectbox(
                "Tipologia Procedura / Bersaglio Anatomico",
                [
                    "Infiltrazione Peridurale Interlaminare",
                    "Infiltrazione Peridurale Transforaminale",
                    "Infiltrazione Faccette Articolari (Medial Branch / Intra-articolare)",
                    "Infiltrazione Articolazione Sacro-Iliaca",
                    "Infiltrazione Articolare Periferica (Spalla / Anca / Ginocchio)",
                    "Infiltrazione dei Trigger Points Miofasciali",
                    "Blocco Nervoso Periferico / Fasciale",
                    "Infiltrazione Paravertebrale / Intramuscolare O2-O3",
                ],
            )
            lato_livello = st.text_input("Livello / Lato", placeholder="es. L4-L5 e L5-S1 a destra")
        with ci3:
            guida_img = st.selectbox(
                "Guida Utilizzata",
                ["Ecoguidata (US)", "Fluoroguidata (Amplificatore di brillanza)", "Reperi Anatomici"],
            )
            ago_usato = st.text_input("Ago Utilizzato e Asepsi", value="Asepsi rigorosa con Clorexidina 2%. Ago dedicato")

        miscela_farmaci = st.text_area("Miscela Farmacologica Iniettata", height=80)
        proc_tipo_db, proc_lato_db, proc_guida_db = distretto_proc, lato_livello, guida_img

        if tipo_prestazione.startswith("4."):
            cdh1, cdh2 = st.columns(2)
            with cdh1:
                param_pre = st.text_input("Parametri Vitali Pre-Procedura (PA, FC, SpO2)")
            with cdh2:
                param_post = st.text_input("Parametri Vitali Post-Procedura e Osservazione")
        else:
            param_pre, param_post = "", ""

        decorso_post = st.text_input(
            "Decorso Immediato",
            value="Procedura ben tollerata, assenza di complicanze immediate o deficit neurologici.",
        )

        dati_raccolti += (
            f"PRE-PROCEDURA: Consenso ({'Sì' if consenso_inf else 'No'}), Emostasi ({'OK' if check_coag else 'Da verificare'}), Allergie: {allergie_proc}\n"
            f"PROCEDURA ESEGUITA: {distretto_proc} ({lato_livello}) - Guida: {guida_img}\n"
            f"TECNICA E MISCELA: {ago_usato}. {miscela_farmaci}\n"
            f"{f'PARAMETRI DH: Pre ({param_pre}) -> Post ({param_post})' if param_pre else ''}\n"
            f"ESITO IMMEDIATO: {decorso_post}\n"
        )

    elif tipo_prestazione.startswith("5."):
        st.subheader("Seduta di Ozonoterapia Sistemica (Grande Autoemoinfusione - GAEI)")
        if sedute_ozono_pregresse:
            ult_oz = sedute_ozono_pregresse[0]
            st.info(
                f"🩸 **Storico GAEI Paziente:** Ha già eseguito **{len(sedute_ozono_pregresse)} sedute**. "
                f"Ultima seduta (N° {ult_oz.get('ozono_seduta')}) del {ult_oz['data_visita']} "
                f"a **{ult_oz.get('ozono_conc_ug_ml')} µg/ml** ({ult_oz.get('ozono_vol_ml')} ml)."
            )

        coz1, coz2, coz3 = st.columns(3)
        with coz1:
            num_seduta = st.number_input("Numero Seduta del Ciclo", min_value=1, max_value=50, key="num_seduta_ozono")
            check_g6pd = st.checkbox("✅ Escluso Favismo (Deficit G6PD) e Ipertiroidismo scompensato", value=True)
            indicazione_ozono = st.text_input("Indicazione Clinica", placeholder="es. Fibromialgia / Fatica cronica")
        with coz2:
            vol_sangue = st.number_input("Volume Sangue Prelevato (ml)", min_value=50, max_value=250, value=150, step=10)
            conc_ozono = st.number_input("Concentrazione Miscela O2-O3 (µg/ml)", min_value=5, max_value=60, value=25, step=5)
            vol_gas = st.number_input("Volume Miscela Gassosa O2-O3 (ml)", min_value=50, max_value=250, value=150, step=10)
        with coz3:
            anticoag_sacca = st.text_input(
                "Dispositivo e Anticoagulante",
                value="Sacca certificata SANO3 / dispositivo dedicato con Sodio Citrato (ACD-A)",
            )
            nrs_ozono = st.slider("NRS Medio Riferito Oggi", 0, 10, 5)
            note_biotekna = st.text_area("Note Cliniche / Valutazione Strumentale (es. Biotekna PPG/BIA-ACC)", height=90)

        nrs_rip_db, nrs_mov_db = nrs_ozono, nrs_ozono
        oz_sed_db, oz_conc_db, oz_vol_db = num_seduta, conc_ozono, vol_sangue

        dati_raccolti += (
            f"SEDUTA OZONOTERAPIA SISTEMICA (GAEI) N° {num_seduta}\n"
            f"Indicazione: {indicazione_ozono} | Controllo G6PD/Tiroide: {'Verificato' if check_g6pd else 'Da verificare'}\n"
            f"Protocollo: Prelievo di {vol_sangue} ml di sangue venoso in {anticoag_sacca}, "
            f"ozonizzazione con {vol_gas} ml di miscela O2-O3 a {conc_ozono} µg/ml e lenta reinfusione omologa.\n"
            f"NRS odierno: {nrs_ozono}/10. Note cliniche e biofisiche: {note_biotekna}\n"
        )

    elif tipo_prestazione.startswith("6."):
        st.subheader("Valutazione e Rinnovo Piano Terapeutico Cannabis Medica")
        ccan1, ccan2 = st.columns(2)
        with ccan1:
            patologia_cannabis = st.selectbox(
                "Indicazione Clinica (DM 9/11/2015)",
                [
                    "Dolore cronico (neuropatico / oncologico) refrattario alle terapie convenzionali",
                    "Analgesia in patologie con spasticità associata a dolore",
                    "Altra condizione prevista dal piano terapeutico regionale",
                ],
            )
            preparato_cannabis = st.selectbox(
                "Varietà / Preparato Magistrale",
                [
                    "Cannabis FM2 (THC 5-8% / CBD 7.5-12%)",
                    "Cannabis Bedrocan (THC ~22% / CBD <1%)",
                    "Cannabis Bediol (THC ~6.3% / CBD ~8%)",
                    "Cannabis Bedrolite (THC <1% / CBD ~9%)",
                    "Cannabis Pedanios / Aurora",
                    "Estratto Oleoso Titolato Magistrale",
                ],
            )
            via_somm_posologia = st.text_area("Forma Farmaceutica e Posologia Giornaliera", height=80)
        with ccan2:
            beneficio_cannabis = st.text_area("Efficacia Riferita (Dolore, Spasticità, Sonno)", height=80)
            effetti_avversi_can = st.multiselect(
                "Monitoraggio Effetti Collaterali",
                [
                    "Nessun effetto collaterale rilevante",
                    "Secchezza delle fauci",
                    "Sonnolenza diurna",
                    "Capogiri / Ipotensione ortostatica",
                    "Tachicardia",
                    "Alterazioni dell'umore / Disforia",
                    "Segni di tolleranza / Craving",
                ],
                default=["Nessun effetto collaterale rilevante"],
            )
            durata_rinnovo = st.selectbox("Durata Rinnovo Prescrizione", ["1 Mese", "3 Mesi", "6 Mesi"])

        cannabis_prep_db = preparato_cannabis
        dati_raccolti += (
            f"RINNOVO PIANO TERAPEUTICO CANNABIS MEDICA ({durata_rinnovo})\n"
            f"Indicazione: {patologia_cannabis}\nPreparato: {preparato_cannabis}\n"
            f"Posologia: {via_somm_posologia}\nEfficacia clinica: {beneficio_cannabis}\n"
            f"Sicurezza e tollerabilità: {', '.join(effetti_avversi_can)}\n"
        )


# ==============================================================================
# TAB 2: SCANSIONE REFERTI STRUMENTALI (OCR MULTIMODALE CON GEMINI)
# ==============================================================================
with tab_ocr:
    st.subheader("📷 Acquisizione ed Estrazione OCR Referti Strumentali")
    metodo_input_img = st.radio(
        "Sorgente immagine:",
        ["Usa Fotocamera (Smartphone/Tablet)", "Carica File (Immagine JPG/PNG)"],
        horizontal=True,
    )

    img_caricata = None
    if metodo_input_img == "Usa Fotocamera (Smartphone/Tablet)":
        foto_camera = st.camera_input("Inquadra il referto medico e scatta")
        if foto_camera is not None:
            img_caricata = Image.open(foto_camera)
    else:
        file_up = st.file_uploader("Seleziona immagine del referto", type=["jpg", "jpeg", "png", "webp"])
        if file_up is not None:
            img_caricata = Image.open(file_up)

    if img_caricata is not None:
        col_img, col_ocr = st.columns([1, 1])
        with col_img:
            st.image(img_caricata, caption="Referto acquisito", use_container_width=True)
        with col_ocr:
            if st.button("🔍 Estrai e Riassumi Referto con Gemini AI", type="primary", use_container_width=True):
                with st.spinner("Lettura multimodale del referto in corso..."):
                    prompt_ocr = (
                        "Sei un medico specialista in Anestesia, Rianimazione e Terapia del Dolore. "
                        "Leggi l'immagine di questo referto strumentale o clinico. "
                        "Estrai in modo rigoroso: 1) Esame e data; 2) Reperti patologici salienti; 3) Conclusioni. "
                        "Ignora qualsiasi dato anagrafico del paziente."
                    )
                    testo_ocr = chiama_gemini(api_key, prompt_ocr, image=img_caricata, model_name=modello_scelto)
                    if st.session_state["ocr_estratti"]:
                        st.session_state["ocr_estratti"] += f"\n\n---\n{testo_ocr}"
                    else:
                        st.session_state["ocr_estratti"] = testo_ocr

    st.session_state["ocr_estratti"] = st.text_area(
        "📋 Testo Indagini Strumentali Estratto:",
        value=st.session_state["ocr_estratti"],
        height=180,
    )


# ==============================================================================
# TAB 3: IL COLTELLINO SVIZZERO (SALVA ANCHE VARIABILI NUMERICHE PER RICERCA!)
# ==============================================================================
with tab_tools:
    st.subheader("🛠️ Strumenti Clinici e Calcolatori Algologici")
    scelta_tool = st.selectbox(
        "Seleziona lo strumento clinico da utilizzare:",
        [
            "1. Questionario DN4 (Screening Dolore Neuropatico)",
            "2. Calcolatore Rotazione Oppioidi ed Equianalgesia (MME)",
            "3. Questionario FIQR Completo (Impatto della Fibromialgia)",
            "4. Scala CAST (Cannabis Abuse Screening Test)",
        ],
    )
    st.divider()

    if scelta_tool.startswith("1."):
        st.markdown("#### Questionario DN4 (*Douleur Neuropathique en 4 Questions*)")
        cd1, cd2 = st.columns(2)
        with cd1:
            dn_1 = st.checkbox("1. Bruciore")
            dn_2 = st.checkbox("2. Sensazione di freddo doloroso")
            dn_3 = st.checkbox("3. Scosse elettriche")
            dn_4 = st.checkbox("4. Formicolio")
            dn_5 = st.checkbox("5. Sensazione di spilli / aghi")
            dn_6 = st.checkbox("6. Intorpidimento")
            dn_7 = st.checkbox("7. Prurito")
        with cd2:
            dn_8 = st.checkbox("8. Ipoestesia al tatto nella stessa area")
            dn_9 = st.checkbox("9. Ipoestesia alla puntura (pinprick) nella stessa area")
            dn_10 = st.checkbox("10. Allodinia meccanica dinamica allo sfregamento")

        score_dn4 = sum([dn_1, dn_2, dn_3, dn_4, dn_5, dn_6, dn_7, dn_8, dn_9, dn_10])
        esito_dn4 = "POSITIVO (>= 4/10)" if score_dn4 >= 4 else "NEGATIVO (< 4/10)"
        st.info(f"**Punteggio DN4: {score_dn4}/10** — {esito_dn4}")

        if st.button("➕ Allega Risultato DN4 alla Visita e al DB Ricerca"):
            st.session_state["ricerca_dn4"] = int(score_dn4)
            st.session_state["note_scale_cliniche"] += f"- Scala DN4: {score_dn4}/10 ({esito_dn4})\n"
            st.success(f"DN4 ({score_dn4}/10) registrato per referto e colonna statistica `score_dn4`!")

    elif scelta_tool.startswith("2."):
        st.markdown("#### Calcolatore di Equianalgesia e Rotazione degli Oppioidi")
        FATTORI_MME = {
            "Morfina Orale (mg/die)": 1.0,
            "Ossicodone Orale (mg/die)": 1.5,
            "Idromorfone Orale (mg/die)": 4.0,
            "Tapentadolo Orale (mg/die)": 0.4,
            "Tramadolo Orale (mg/die)": 0.1,
            "Fentanil Transdermico TTS (µg/h)": 2.4,
            "Buprenorfina Transdermica TTS (µg/h)": 1.8,
        }
        co1, co2, co3 = st.columns(3)
        with co1:
            oppioide_attuale = st.selectbox("Oppioide Attuale:", list(FATTORI_MME.keys()), index=1)
            dose_attuale = st.number_input("Dose Totale Giornaliera (o µg/h):", min_value=0.0, value=20.0, step=5.0)
        with co2:
            oppioide_target = st.selectbox("Oppioide Target (Nuovo):", list(FATTORI_MME.keys()), index=6)
            riduzione_cross = st.slider("Riduzione Cross-Tolerance Incompleta (%)", 0, 60, 30, step=5)
        with co3:
            mme_attuali = dose_attuale * FATTORI_MME[oppioide_attuale]
            dose_equi_piena = mme_attuali / FATTORI_MME[oppioide_target]
            dose_target_ridotta = dose_equi_piena * (1.0 - riduzione_cross / 100.0)
            st.metric("Carico Attuale in MME/die", f"{mme_attuali:.1f} mg MME")
            st.metric("Dose Equianalgesica (100%)", f"{dose_equi_piena:.1f}")
            st.metric(f"Dose Consigliata (-{riduzione_cross}%)", f"{dose_target_ridotta:.1f}")

        if st.button("➕ Allega Calcolo Rotazione Oppioidi alla Visita e al DB Ricerca"):
            st.session_state["ricerca_mme"] = round(float(mme_attuali), 1)
            st.session_state["note_scale_cliniche"] += (
                f"- Rotazione Oppioidi: da {oppioide_attuale} ({dose_attuale}) [{mme_attuali:.1f} MME/die] "
                f"a {oppioide_target} -> dose corretta (-{riduzione_cross}%) = {dose_target_ridotta:.1f}\n"
            )
            st.success(f"MME/die ({mme_attuali:.1f}) registrato nella colonna statistica `mme_oppioidi`!")

    elif scelta_tool.startswith("3."):
        st.markdown("#### Questionario FIQR (*Revised Fibromyalgia Impact Questionnaire*)")
        with st.expander("Dominio 1: Funzione Fisica (9 item - Peso 30%)", expanded=True):
            cf1, cf2, cf3 = st.columns(3)
            f1 = cf1.slider("1. Spazzolare/pettinare i capelli", 0, 10, 3)
            f2 = cf2.slider("2. Camminare per 20 minuti", 0, 10, 5)
            f3 = cf3.slider("3. Preparare un pasto fatto in casa", 0, 10, 4)
            f4 = cf1.slider("4. Passare l'aspirapolvere o spazzare", 0, 10, 6)
            f5 = cf2.slider("5. Sollevare una borsa della spesa piena", 0, 10, 7)
            f6 = cf3.slider("6. Salire una rampa di scale", 0, 10, 5)
            f7 = cf1.slider("7. Cambiare le lenzuola del letto", 0, 10, 6)
            f8 = cf2.slider("8. Stare seduto/a su una sedia per 45 min", 0, 10, 5)
            f9 = cf3.slider("9. Fare la spesa al supermercato", 0, 10, 5)
            dom1_score = sum([f1, f2, f3, f4, f5, f6, f7, f8, f9]) / 3.0

        with st.expander("Dominio 2: Impatto Globale (2 item - Peso 20%)", expanded=True):
            cg1, cg2 = st.columns(2)
            g1 = cg1.slider("1. Impedito nel raggiungere gli obiettivi settimanali", 0, 10, 5)
            g2 = cg2.slider("2. Sentito/a completamente sopraffatto/a dai sintomi", 0, 10, 5)
            dom2_score = float(g1 + g2)

        with st.expander("Dominio 3: Intensità dei Sintomi (10 item - Peso 50%)", expanded=True):
            cs1, cs2 = st.columns(2)
            s1 = cs1.slider("1. Intensità del dolore", 0, 10, 7)
            s2 = cs2.slider("2. Mancanza di energia / Astenia", 0, 10, 8)
            s3 = cs1.slider("3. Rigidità muscolare", 0, 10, 7)
            s4 = cs2.slider("4. Qualità del sonno non ristoratore", 0, 10, 8)
            s5 = cs1.slider("5. Umore depresso / tristezza", 0, 10, 5)
            s6 = cs2.slider("6. Problemi di memoria / Fibro-fog", 0, 10, 6)
            s7 = cs1.slider("7. Ansia / tensione interna", 0, 10, 6)
            s8 = cs2.slider("8. Dolorabilità al tatto", 0, 10, 7)
            s9 = cs1.slider("9. Problemi di equilibrio", 0, 10, 4)
            s10 = cs2.slider("10. Sensibilità a rumori, luci, odori o freddo", 0, 10, 6)
            dom3_score = sum([s1, s2, s3, s4, s5, s6, s7, s8, s9, s10]) / 2.0

        fiqr_totale = round(dom1_score + dom2_score + dom3_score, 1)
        sev_fiqr = "Lieve" if fiqr_totale <= 30 else ("Moderata" if fiqr_totale <= 45 else ("Elevata" if fiqr_totale <= 65 else "Molto Elevata"))
        st.info(f"**Punteggio FIQR Totale: {fiqr_totale}/100 ({sev_fiqr})**")

        if st.button("➕ Allega Punteggio FIQR alla Visita e al DB Ricerca"):
            st.session_state["ricerca_fiqr"] = float(fiqr_totale)
            st.session_state["note_scale_cliniche"] += f"- Questionario FIQR: {fiqr_totale}/100 (Severità {sev_fiqr})\n"
            st.success(f"FIQR ({fiqr_totale}) registrato nella colonna statistica `score_fiqr`!")

    elif scelta_tool.startswith("4."):
        st.markdown("#### Scala CAST (*Cannabis Abuse Screening Test*)")
        opzioni_cast = ["0 - Mai", "1 - Raramente", "2 - Di tanto in tanto", "3 - Abbastanza spesso", "4 - Molto spesso"]
        ca_1 = int(st.selectbox("1. Assunzione fuori orario prima di mezzogiorno?", opzioni_cast)[0])
        ca_2 = int(st.selectbox("2. Dosi supplementari non concordate da solo/a?", opzioni_cast)[0])
        ca_3 = int(st.selectbox("3. Problemi di memoria o concentrazione?", opzioni_cast)[0])
        ca_4 = int(st.selectbox("4. Familiari hanno suggerito di ridurre?", opzioni_cast)[0])
        ca_5 = int(st.selectbox("5. Provato a ridurre senza riuscirci?", opzioni_cast)[0])
        ca_6 = int(st.selectbox("6. Problemi (sonnolenza guida, cadute) per l'effetto?", opzioni_cast)[0])
        score_cast = ca_1 + ca_2 + ca_3 + ca_4 + ca_5 + ca_6
        interp_cast = "Basso rischio (< 3)" if score_cast < 3 else ("Rischio moderato (3-6)" if score_cast <= 6 else "Alto rischio (>= 7)")
        st.info(f"**Punteggio CAST: {score_cast}/24** — {interp_cast}")

        if st.button("➕ Allega Risultato CAST alla Visita e al DB Ricerca"):
            st.session_state["ricerca_cast"] = int(score_cast)
            st.session_state["note_scale_cliniche"] += f"- Screening CAST: {score_cast}/24 ({interp_cast})\n"
            st.success(f"CAST ({score_cast}/24) registrato nella colonna statistica `score_cast`!")

    st.divider()
    st.session_state["note_scale_cliniche"] = st.text_area(
        "📌 Riepilogo Scale e Calcolatori Allegati:",
        value=st.session_state["note_scale_cliniche"],
        height=110,
    )


# ==============================================================================
# TAB 4: SINTESI AI, COPIA PC OSPEDALE E SALVATAGGIO STORICO DB
# ==============================================================================
with tab_output:
    st.subheader("📄 Generazione Referto Clinico e Salvataggio in Archivio")

    contesto_clinico_completo = dati_raccolti
    if st.session_state["ocr_estratti"].strip():
        contesto_clinico_completo += f"\nINDAGINI STRUMENTALI (OCR):\n{st.session_state['ocr_estratti']}\n"
    if st.session_state["note_scale_cliniche"].strip():
        contesto_clinico_completo += f"\nSCALE E CALCOLATORI CLINICI:\n{st.session_state['note_scale_cliniche']}\n"

    col_btn1, col_btn2, col_btn3 = st.columns(3)
    with col_btn1:
        if st.button("✨ 1. Genera Referto con Gemini AI", type="primary", use_container_width=True):
            with st.spinner("Elaborazione clinica in corso con Gemini..."):
                prompt_referto = f"""
Sei un medico specialista esperto in Anestesia, Rianimazione e Terapia del Dolore.
Redigi un referto medico specialistico completo, formale e pronto per essere incollato nella cartella clinica ospedaliera.

DATI RACCOLTI OGGI:
{contesto_clinico_completo}

STRUTTURA RICHIESTA:
1. INQUADRAMENTO ANAMNESTICO E CLINICO
2. ESAME OBIETTIVO E VALUTAZIONE ALGOMETRICA/SCALE
3. ESAMI STRUMENTALI VISIONATI (se presenti)
4. CONCLUSIONI DIAGNOSTICHE
5. PROGRAMMA TERAPEUTICO E RACCOMANDAZIONI

Non usare formattazioni Markdown invasive (evita asterischi o cancelletti) per facilitare il copia-incolla diretto sul gestionale ospedaliero.
"""
                st.session_state["bozza_referto_finale"] = chiama_gemini(
                    api_key, prompt_referto, model_name=modello_scelto
                )

    with col_btn2:
        if st.button("⚡ Assembla Testo Rapido (Senza AI)", use_container_width=True):
            st.session_state["bozza_referto_finale"] = contesto_clinico_completo

    with col_btn3:
        if st.button("💾 2. Salva Visita nel Database di Ricerca", use_container_width=True):
            if not id_paziente or not id_paziente.strip():
                st.error("⚠️ Inserisci un ID Paziente in alto prima di salvare!")
            else:
                record_visita = {
                    "id_paziente": id_paziente.strip().upper(),
                    "fascia_eta": fascia_eta.strip(),
                    "data_visita": data_visita.strftime("%d/%m/%Y"),
                    "timestamp_salvataggio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "tipo_prestazione": tipo_prestazione,
                    "meccanismo_dolore": meccanismo_db,
                    "nrs_riposo": nrs_rip_db,
                    "nrs_movimento": nrs_mov_db,
                    "pgic_esito": pgic_db,
                    "score_dn4": st.session_state.get("ricerca_dn4"),
                    "score_fiqr": st.session_state.get("ricerca_fiqr"),
                    "mme_oppioidi": st.session_state.get("ricerca_mme"),
                    "score_cast": st.session_state.get("ricerca_cast"),
                    "procedura_tipo": proc_tipo_db,
                    "procedura_livello_lato": proc_lato_db,
                    "procedura_guida": proc_guida_db,
                    "ozono_seduta": oz_sed_db,
                    "ozono_conc_ug_ml": oz_conc_db,
                    "ozono_vol_ml": oz_vol_db,
                    "cannabis_preparato": cannabis_prep_db,
                    "dati_clinici": dati_raccolti,
                    "ocr_estratti": st.session_state["ocr_estratti"],
                    "scale_cliniche": st.session_state["note_scale_cliniche"],
                    "referto_finale": st.session_state["bozza_referto_finale"] or contesto_clinico_completo,
                }
                ok_cloud = salva_visita_db(record_visita, webhook_url=gsheet_url)
                msg_cloud = " e sincronizzata sul tuo Google Sheet!" if ok_cloud else " nel DB locale!"
                st.success(f"✅ Visita di `{id_paziente.upper()}` salvata{msg_cloud}")
                st.rerun()

    st.divider()
    st.markdown("##### Revisione del Testo")
    st.session_state["bozza_referto_finale"] = st.text_area(
        "Modifica liberamente il referto prima di copiarlo o salvarlo:",
        value=st.session_state["bozza_referto_finale"],
        height=300,
    )

    st.markdown("##### Copia in 1 Click per il PC dell'Ospedale")
    st.code(
        st.session_state["bozza_referto_finale"]
        or "Genera o assembla il referto sopra per attivare la copia rapida.",
        language="text",
    )


# ==============================================================================
# TAB 5: ESPLORAZIONE DATABASE ED ESPORTAZIONE PER RICERCA CLINICA (CSV/SQLITE)
# ==============================================================================
with tab_db:
    st.subheader("📊 Esploratore Database & Esportazione per Ricerca Clinica")
    st.caption(
        "Tutti i parametri clinici (NRS, DN4, FIQR, MME, Ozono, Procedure) sono strutturati in colonne indipendenti pronte per l'analisi statistica (Excel, R, SPSS, Jamovi)."
    )

    df_tot = get_df_tutte_visite()

    if df_tot.empty:
        st.info("Il database è attualmente vuoto. Salva almeno una visita dalla Scheda 4 per popolare la tabella di ricerca.")
    else:
        # Statistiche sintetiche del dataset
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Totale Accessi Registrati", len(df_tot))
        k2.metric("Pazienti Unici (ID)", df_tot["id_paziente"].nunique())
        nrs_medio_m = df_tot["nrs_movimento"].dropna().mean()
        k3.metric("NRS Dinamico Medio Coorte", f"{nrs_medio_m:.1f}/10" if pd.notna(nrs_medio_m) else "-")
        sedute_oz_tot = df_tot["ozono_seduta"].dropna().count()
        k4.metric("Sedute Ozonoterapia (GAEI)", int(sedute_oz_tot))

        st.divider()
        # Filtri rapidi per esplorazione coorte
        cf_1, cf_2 = st.columns(2)
        with cf_1:
            filtro_id = st.multiselect(
                "Filtra per ID Paziente:",
                options=sorted(df_tot["id_paziente"].unique()),
            )
        with cf_2:
            filtro_prest = st.multiselect(
                "Filtra per Tipo di Prestazione:",
                options=sorted(df_tot["tipo_prestazione"].unique()),
            )

        df_filtrato = df_tot.copy()
        if filtro_id:
            df_filtrato = df_filtrato[df_filtrato["id_paziente"].isin(filtro_id)]
        if filtro_prest:
            df_filtrato = df_filtrato[df_filtrato["tipo_prestazione"].isin(filtro_prest)]

        # Tabella interattiva esplorabile a schermo
        st.dataframe(df_filtrato, use_container_width=True, height=340)

        # Pulsanti di Esportazione Scientifica (CSV per Excel/SPSS, JSON e File SQLite .db grezzo)
        st.markdown("##### 📥 Esporta Dataset per Analisi Statistica")
        cexp1, cexp2, cexp3 = st.columns(3)

        with cexp1:
            # BOM UTF-8 (\ufeff) garantisce che Microsoft Excel apra subito le lettere accentate e le colonne correttamente
            csv_data = df_filtrato.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📊 Scarica Dataset Ricerca (.CSV per Excel / SPSS / R)",
                data=csv_data,
                file_name=f"dataset_terapia_dolore_{date.today().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                type="primary",
                use_container_width=True,
            )

        with cexp2:
            with open(DB_FILE, "rb") as f_db:
                db_bytes = f_db.read()
            st.download_button(
                label="🗄️ Scarica File Database SQLite (.db)",
                data=db_bytes,
                file_name=f"ambulatorio_dolore_{date.today().strftime('%Y%m%d')}.db",
                mime="application/octet-stream",
                use_container_width=True,
            )

        with cexp3:
            json_data = df_filtrato.to_json(orient="records", force_ascii=False, indent=2)
            st.download_button(
                label="📦 Scarica Backup Completo (.JSON)",
                data=json_data,
                file_name=f"backup_ricerca_{date.today().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True,
            )

        st.divider()
        with st.expander("🛠️ Manutenzione Righe / Importazione Backup"):
            cm1, cm2 = st.columns(2)
            with cm1:
                id_riga_del = st.selectbox(
                    "Seleziona ID Riga da eliminare (es. test o errore):",
                    options=df_tot["id"].tolist(),
                    format_func=lambda x: f"Riga #{x} — {df_tot.loc[df_tot['id']==x, 'id_paziente'].values[0]} ({df_tot.loc[df_tot['id']==x, 'data_visita'].values[0]})",
                )
                if st.button("🗑️ Elimina Riga Selezionata dal DB locale"):
                    elimina_visita_per_id(int(id_riga_del))
                    st.success(f"Riga #{id_riga_del} rimossa.")
                    st.rerun()
            with cm2:
                file_imp = st.file_uploader("Importa visite da file .JSON o .CSV", type=["json", "csv"])
                if file_imp is not None and st.button("⬆️ Carica Record nel Database"):
                    if file_imp.name.endswith(".json"):
                        recs = json.loads(file_imp.read().decode("utf-8"))
                    else:
                        df_up = pd.read_csv(file_imp)
                        recs = df_up.where(pd.notnull(df_up), None).to_dict(orient="records")
                    n_add = importa_lista_record_db(recs)
                    st.success(f"Aggiunte {n_add} visite al database!")
                    st.rerun()
