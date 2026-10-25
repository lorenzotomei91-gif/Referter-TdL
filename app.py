from datetime import date
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

# Inizializzazione delle variabili persistenti in session_state
default_states = {
    "ocr_estratti": "",
    "note_scale_cliniche": "",
    "bozza_referto_finale": "",
    "sintesi_ai": "",
}
for key, val in default_states.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ==========================================
# 2. FUNZIONE CHIAMATA API GEMINI (SDK UFFICIALE)
# ==========================================
def chiama_gemini(api_key: str, prompt: str, image: Image.Image = None, model_name: str = "gemini-2.5-flash") -> str:
    """Invia una richiesta testuale o multimodale (immagine + testo) a Gemini."""
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
# 3. DIZIONARIO VIDEO SEMEIOLOGICI (YOUTUBE)
# ==========================================
VIDEO_SEMEIOTICA = {
    "Test di Lasègue (SLR - Radicolopatia L4-S1)": "https://www.youtube.com/watch?v=F0ac42M354M",
    "Test di Wasserman (Femoral Stretch - Radicolopatia L2-L4)": "https://www.youtube.com/watch?v=k0N2G2_A9v8",
    "Test di Patrick / FABER (Articolazione Sacroiliaca / Anca)": "https://www.youtube.com/watch?v=sa253_23c4I",
    "Test di Spurling (Radicolopatia Cervicale)": "https://www.youtube.com/watch?v=c2c6B7X8_yY",
    "Test della Sindrome del Piriforme (FAIR Test)": "https://www.youtube.com/watch?v=N2V9_p2pX7g",
}


# ==========================================
# 4. SIDEBAR: CONFIGURAZIONE E SELETTORE VISITA
# ==========================================
with st.sidebar:
    st.title("🩺 Suite Algologica")
    st.caption("Sistema di supporto clinico e refertazione rapida")
    st.divider()

    # Gestione API Key (legge da st.secrets oppure da input manuale)
    api_key_secret = st.secrets.get("GEMINI_API_KEY", "") if "GEMINI_API_KEY" in st.secrets else ""
    if api_key_secret:
        st.success("🔒 API Key Gemini attiva (da Secrets)")
        api_key = api_key_secret
    else:
        api_key = st.text_input("🔑 Inserisci Gemini API Key:", type="password", help="Ottienila gratis su aistudio.google.com")

    modello_scelto = st.selectbox(
        "Modello AI:",
        ["gemini-2.5-flash", "gemini-2.5-pro"],
        index=0,
        help="Flash è istantaneo per OCR e visite rapide; Pro è ideale per ragionamenti diagnostici complessi.",
    )

    st.divider()
    tipo_prestazione = st.radio(
        "📋 Seleziona Tipo di Prestazione:",
        [
            "1. Prima Visita Algologica",
            "2. Visita di Controllo",
            "3. Procedura Infiltrativa",
            "4. Day-Hospital Infiltrazione",
            "5. Day-Hospital Ozonoterapia Sistemica",
            "6. Rinnovo Prescrizione Cannabis",
        ],
    )

    st.divider()
    if st.button("🗑️ Nuova Visita (Svuota Campi)", use_container_width=True):
        for key in default_states.keys():
            st.session_state[key] = ""
        st.rerun()


# ==========================================
# 5. INTESTAZIONE: METADATA PAZIENTE (ANONIMO)
# ==========================================
st.header(f"Amb. Terapia del Dolore — {tipo_prestazione.split('. ')[1]}")

col_meta1, col_meta2, col_meta3 = st.columns([2, 1, 1])
with col_meta1:
    id_paziente = st.text_input("🆔 ID Paziente (Codice Anonimo Libero)", placeholder="es. PAZ-2026-042")
with col_meta2:
    fascia_eta = st.text_input("🎂 Età / Anno nascita (opz.)", placeholder="es. 64 aa")
with col_meta3:
    data_visita = st.date_input("📅 Data Prestazione", value=date.today())

# Struttura a 4 Schede (Tabs) per avere tutto a portata di mano senza perdere il segno
tab_visita, tab_ocr, tab_tools, tab_output = st.tabs([
    "📝 1. Scheda Clinica & EO",
    "📷 2. Scansione Referti (OCR)",
    "🛠️ 3. Coltellino Svizzero (Scale & Oppioidi)",
    "📄 4. Sintesi AI & Referto Finale",
])


# ==============================================================================
# TAB 1: SCHEDA CLINICA DINAMICA IN BASE ALLA PRESTAZIONE
# ==============================================================================
with tab_visita:
    dati_raccolti = f"ID PAZIENTE: {id_paziente or 'Non specificato'} ({fascia_eta}) - DATA: {data_visita.strftime('%d/%m/%Y')}\n"
    dati_raccolti += f"PRESTAZIONE: {tipo_prestazione.split('. ')[1]}\n\n"

    # --- CASO 1: PRIMA VISITA ALGOLOGICA ---
    if tipo_prestazione.startswith("1."):
        st.subheader("Anamnesi Generale e Farmacologica")
        c1, c2 = st.columns(2)
        with c1:
            apr = st.text_area("Anamnesi Patologica Remota (Comorbidità rilevanti)", height=90, placeholder="es. Ipertensione arteriosa, Diabete mellito tipo 2, IRC stadio II, pregressa chirurgia vertebrale...")
            allergie_anticoag = st.text_input("⚠️ Allergie a Farmaci / Terapia Anticoagulante o Antiaggregante in atto", placeholder="es. Allergia a FANS; assume Cardioaspirina 100 mg / Eliquis...")
        with c2:
            terapia_domiciliare = st.text_area("Terapia Antalgica e Domiciliare in Atto", height=90, placeholder="es. Pregabalin 75 mg x 2/die, Paracetamolo 1000 mg al bisogno (scarso beneficio)...")
            trattamenti_pregressi = st.text_input("Precedenti Trattamenti Antalgici / Fisioterapici", placeholder="es. Ciclo di FKT, 2 infiltrazioni cortisoniche nel 2025 con beneficio transitorio...")

        st.divider()
        st.subheader("Anamnesi Antalgica e Caratteristiche del Dolore")
        ca1, ca2, ca3 = st.columns(3)
        with ca1:
            esordio_durata = st.text_input("Esordio e Durata", placeholder="es. Insidioso da circa 8 mesi, acutizzato da 3 settimane")
            sede_irradiazione = st.text_area("Sede Principale e Irradiazione", height=80, placeholder="es. Rachide lombare con irradiazione lungo il territorio di L5 a destra fino al dorso del piede")
        with ca2:
            caratteri_dolore = st.multiselect(
                "Caratteristiche Qualitative del Dolore",
                ["Gravativo", "Urente / Bruciante", "Lancinante / Scossa elettrica", "Trafittivo", "Pulsante", "Costrittivo", "Sordo / Continuo", "Parestesie / Formicolio associate", "Allodinia"],
            )
            ritmo_dolore = st.selectbox("Andamento Temporale / Circadiano", ["Continuo con esacerbazioni al carico", "Prevalentemente meccanico (al movimento)", "Prevalentemente notturno / a riposo", "Accessionale / Parossistico", "Costante h24"])
        with ca3:
            fattori_mod = st.text_area("Fattori Scatenanti e Allevianti", height=80, placeholder="es. Peggiora con stazione eretta prolungata e flessione; migliora in clinostatismo")
            impatto_sonno_adl = st.selectbox("Impatto sul Sonno e sulle ADL", ["Sonno conservato, lieve limitazione ADL", "Risvegli notturni occasionali, moderata limitazione ADL", "Grave insonnia algica, severa limitazione funzionale nelle ADL"])

        st.markdown("##### Valutazione Intensità del Dolore (Scala NRS 0-10)")
        cn1, cn2, cn3 = st.columns(3)
        with cn1:
            nrs_riposo = st.slider("NRS a Riposo (Statico)", 0, 10, 4)
        with cn2:
            nrs_movimento = st.slider("NRS in Movimento (Dinamico)", 0, 10, 8)
        with cn3:
            meccanismo_prevalente = st.multiselect("Ipotesi Patogenetica Prevalente", ["Nocicettivo Meccanico/Degenerativo", "Nocicettivo Infiammatorio", "Neuropatico Periferico/Radicolare", "Neuropatico Centrale", "Nociplastico / Sensibilizzazione Centrale", "Misto"])

        st.divider()
        st.subheader("Esame Obiettivo Algologico e Manovre Semeiologiche")
        ceo1, ceo2 = st.columns([2, 1])
        with ceo1:
            eo_ispezione_palpazione = st.text_area(
                "Ispezione, Palpazione e Trigger Points",
                height=100,
                placeholder="es. Atteggiamento antalgico, contrattura paravertebrale lombare dx, dolenzia alla digitopressione delle apofisi spinose L4-L5 e sull'articolazione sacroiliaca dx...",
            )
            eo_neuro_manovre = st.text_area(
                "Esame Neurologico Distrettuale e Manovre Provocative",
                height=100,
                placeholder="es. Lasègue positivo a 40° a dx, Wasserman negativo, ROT simmetrici, ipoestesia tattile territorio L5 dx, forza segmentaria conservata (EHL 5/5)...",
            )
        with ceo2:
            st.markdown("🎥 **Atlante Video Semeiologico Rapido**")
            manovra_scelta = st.selectbox("Seleziona manovra da visualizzare:", list(VIDEO_SEMEIOTICA.keys()))
            with st.expander("▶️ Apri Video Dimostrativo Manovra", expanded=False):
                st.video(VIDEO_SEMEIOTICA[manovra_scelta])

        dati_raccolti += (
            f"APR: {apr}\nALLERGIE / ANTICOAGULANTI: {allergie_anticoag}\n"
            f"TERAPIA IN ATTO: {terapia_domiciliare}\nTRATTAMENTI PREGRESSI: {trattamenti_pregressi}\n\n"
            f"ANAMNESI ANTALGICA:\n- Esordio/Durata: {esordio_durata}\n- Sede e irradiazione: {sede_irradiazione}\n"
            f"- Caratteri: {', '.join(caratteri_dolore)} ({ritmo_dolore})\n- Fattori modulanti: {fattori_mod}\n"
            f"- Impatto Sonno/ADL: {impatto_sonno_adl}\n- Intensità: NRS a riposo {nrs_riposo}/10, NRS dinamico {nrs_movimento}/10\n"
            f"- Componente ipotizzata: {', '.join(meccanismo_prevalente)}\n\n"
            f"ESAME OBIETTIVO:\n{eo_ispezione_palpazione}\n{eo_neuro_manovre}\n"
        )

    # --- CASO 2: VISITA DI CONTROLLO ---
    elif tipo_prestazione.startswith("2."):
        st.subheader("Valutazione Evolutiva di Controllo")
        cc1, cc2 = st.columns(2)
        with cc1:
            diagnosi_nota = st.text_input("Quadro Diagnostico in Follow-up", placeholder="es. Lombosciatalgia destra da ernia discale L4-L5 in trattamento multimodale")
            terapia_in_corso = st.text_area("Terapia Prescritta al Precedente Controllo", height=90)
            aderenza_tollerabilita = st.text_area("Aderenza ed Eventuali Effetti Collaterali", height=80, placeholder="es. Buona tollerabilità, riferita lieve sonnolenza mattutina, alvo regolare...")
        with cc2:
            esito_globale = st.selectbox("Andamento Clinico Globale (PGIC)", ["Netto miglioramento (>50% pain relief)", "Miglioramento parziale (30-50% pain relief)", "Quadro stazionario", "Peggioramento clinico"])
            nrs_attuale_rip = st.slider("NRS Attuale a Riposo", 0, 10, 2)
            nrs_attuale_mov = st.slider("NRS Attuale in Movimento", 0, 10, 4)
            eo_controllo = st.text_area("Rivalutazione Obiettiva Odierna", height=80, placeholder="es. Riduzione della contrattura paravertebrale, Lasègue positivizzato solo oltre i 70°...")

        dati_raccolti += (
            f"QUADRO IN FOLLOW-UP: {diagnosi_nota}\nTERAPIA IN CORSO: {terapia_in_corso}\n"
            f"ANDAMENTO CLINICO: {esito_globale} (NRS attuale a riposo {nrs_attuale_rip}/10, in movimento {nrs_attuale_mov}/10)\n"
            f"TOLLERABILITÀ/ADERENZA: {aderenza_tollerabilita}\nESAME OBIETTIVO ODIERNO: {eo_controllo}\n"
        )

    # --- CASO 3 & 4: PROCEDURA INFILTRATIVA (AMBULATORIALE O DAY-HOSPITAL) ---
    elif tipo_prestazione.startswith("3.") or tipo_prestazione.startswith("4."):
        st.subheader("Verbale Procedura Interventistica / Infiltrativa")
        ci1, ci2, ci3 = st.columns(3)
        with ci1:
            consenso_inf = st.checkbox("✅ Consenso Informato scritto acquisito", value=True)
            check_coag = st.checkbox("✅ Verifica sospensione Anticoagulanti/Antiaggreganti (Linee guida ASRA/SIAARTI)", value=True)
            allergie_proc = st.text_input("Allergie note (Anestetici locali, Cortisonici, Mezzo di contrasto)", value="Nessuna allergia nota riferita")
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
            guida_img = st.selectbox("Guida Utilizzata", ["Ecoguidata (US)", "Fluoroguidata (Amplificatore di brillanza)", "Reperi Anatomici"])
            ago_usato = st.text_input("Ago Utilizzato e Asepsi", value="Asepsi rigorosa con Clorexidina 2%. Ago dedicato")

        miscela_farmaci = st.text_area(
            "Miscela Farmacologica Iniettata (Farmaci, Concentrazioni, Volumi)",
            height=80,
            placeholder="es. Ropivacaina 0.2% 3 ml + Desametasone 4 mg (1 ml), volume totale 4 ml previa aspirazione negativa per sangue/liquor.",
        )

        if tipo_prestazione.startswith("4."):
            st.markdown("##### Monitoraggio Clinico Day-Hospital")
            cdh1, cdh2 = st.columns(2)
            with cdh1:
                param_pre = st.text_input("Parametri Vitali Pre-Procedura (PA, FC, SpO2)", placeholder="es. PA 130/80 mmHg, FC 72 bpm, SpO2 99%")
            with cdh2:
                param_post = st.text_input("Parametri Vitali Post-Procedura e Osservazione", placeholder="es. PA 125/75 mmHg, FC 68 bpm, SpO2 99%, assenza di deficit sensitivo-motori acuti")
        else:
            param_pre, param_post = "", ""

        decorso_post = st.text_input("Decorso Immediato e Complicanze", value="Procedura ben tollerata, assenza di complicanze immediate o deficit neurologici.")

        dati_raccolti += (
            f"PRE-PROCEDURA: Consenso acquisito ({'Sì' if consenso_inf else 'No'}), Check emostasi ({'OK' if check_coag else 'Da verificare'}), Allergie: {allergie_proc}\n"
            f"PROCEDURA ESEGUITA: {distretto_proc} ({lato_livello}) - Guida: {guida_img}\n"
            f"TECNICA E MISCELA: {ago_usato}. {miscela_farmaci}\n"
            f"{f'PARAMETRI DH: Pre ({param_pre}) -> Post ({param_post})' if param_pre else ''}\n"
            f"ESITO IMMEDIATO: {decorso_post}\n"
        )

    # --- CASO 5: DAY-HOSPITAL OZONOTERAPIA SISTEMICA ---
    elif tipo_prestazione.startswith("5."):
        st.subheader("Seduta di Ozonoterapia Sistemica (Grande Autoemoinfusione - GAEI)")
        coz1, coz2, coz3 = st.columns(3)
        with coz1:
            num_seduta = st.number_input("Numero Seduta del Ciclo", min_value=1, max_value=30, value=1)
            check_g6pd = st.checkbox("✅ Escluso Favismo (Deficit G6PD) e Ipertiroidismo scompensato", value=True)
            indicazione_ozono = st.text_input("Indicazione Clinica", placeholder="es. Fibromialgia refrattaria / Sindrome da fatica cronica / Dolore nociplastico diffuso")
        with coz2:
            vol_sangue = st.number_input("Volume Sangue Prelevato (ml)", min_value=50, max_value=250, value=150, step=10)
            conc_ozono = st.number_input("Concentrazione Miscela O2-O3 (µg/ml)", min_value=5, max_value=60, value=25, step=5)
            vol_gas = st.number_input("Volume Miscela Gassosa O2-O3 (ml)", min_value=50, max_value=250, value=150, step=10)
        with coz3:
            anticoag_sacca = st.text_input(" Dispositivo Certificato e Anticoagulante", value="Sacca certificata SANO3 / dispositivo dedicato con Sodio Citrato (ACD-A)")
            nrs_ozono = st.slider("NRS Medio Riferito Oggi", 0, 10, 5)
            note_biotekna = st.text_area("Note Cliniche / Valutazione Strumentale (es. PPG Stress Flow / BIA-ACC Biotekna)", height=90, placeholder="es. Miglioramento dell'astenia e qualità del sonno; parametri SNA/HRV in riequilibrio...")

        dati_raccolti += (
            f"SEDUTA OZONOTERAPIA SISTEMICA (GAEI) N° {num_seduta}\n"
            f"Indicazione: {indicazione_ozono} | Controllo controindicazioni (G6PD/Tiroide): {'Verificato' if check_g6pd else 'Da verificare'}\n"
            f"Protocollo eseguito: Prelievo da accesso venoso periferico di {vol_sangue} ml di sangue venoso in {anticoag_sacca}, "
            f"ozonizzazione con {vol_gas} ml di miscela O2-O3 a concentrazione di {conc_ozono} µg/ml e lenta reinfusione omologa senza complicanze.\n"
            f"NRS odierno: {nrs_ozono}/10. Note cliniche e biofisiche: {note_biotekna}\n"
        )

    # --- CASO 6: RINNOVO PRESCRIZIONE CANNABIS ---
    elif tipo_prestazione.startswith("6."):
        st.subheader("Valutazione e Rinnovo Piano Terapeutico Cannabis Medica")
        ccan1, ccan2 = st.columns(2)
        with ccan1:
            patologia_cannabis = st.selectbox(
                "Indicazione Clinica (DM 9/11/2015)",
                [
                    "Dolore cronico (neuropatico / oncologico) refrattario alle terapie convenzionali (FANS, cortisonici, oppioidi)",
                    "Analgesia in patologie con spasticità associata a dolore (es. Sclerosi Multipla, lesioni midollari)",
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
                    "Cannabis Pedanios / Aurora (specificare titolo)",
                    "Estratto Oleoso Titolato Magistrale",
                ],
            )
            via_somm_posologia = st.text_area(
                "Forma Farmaceutica e Posologia Giornaliera",
                height=80,
                placeholder="es. Estratto oleoso 10% p/v: 8 gocce la sera + 5 gocce al mattino per via sublinguale (oppure cartine per decotto/vaporizzazione)...",
            )
        with ccan2:
            beneficio_cannabis = st.text_area(
                "Efficacia Riferita (Dolore, Spasticità, Qualità del Sonno, Risparmio di Oppioidi/FANS)",
                height=80,
                placeholder="es. Riduzione NRS da 8 a 4, netto miglioramento del riposo notturno, dimezzato l'uso di rescue medication...",
            )
            effetti_avversi_can = st.multiselect(
                "Monitoraggio Effetti Collaterali",
                ["Nessun effetto collaterale rilevante", "Secchezza delle fauci", "Sonnolenza diurna", "Capogiri / Ipotensione ortostatica", "Tachicardia", "Alterazioni dell'umore / Disforia", "Segni di tolleranza / Craving"],
                default=["Nessun effetto collaterale rilevante"],
            )
            durata_rinnovo = st.selectbox("Durata Rinnovo Prescrizione", ["1 Mese", "3 Mesi", "6 Mesi"])

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
    st.caption("Scatta una foto al referto cartaceo (RM, TC, RX, EMG/ENG) dallo smartphone oppure carica un'immagine salvata.")

    metodo_input_img = st.radio("Sorgente immagine:", ["Usa Fotocamera (Smartphone/Tablet)", "Carica File (Immagine JPG/PNG)"], horizontal=True)

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
                        "Estrai in modo rigoroso, conciso e fedele: "
                        "1) Tipo di esame e data (se visibile); "
                        "2) Reperti patologici salienti (es. livelli discali, stenosi, radicolopatie, segni EMG, lesioni); "
                        "3) Conclusioni diagnostiche del referto. "
                        "Ignora assolutamente eventuali nomi, cognomi o codici fiscali del paziente per garantire l'anonimato."
                    )
                    testo_ocr = chiama_gemini(api_key, prompt_ocr, image=img_caricata, model_name=modello_scelto)
                    if st.session_state["ocr_estratti"]:
                        st.session_state["ocr_estratti"] += f"\n\n---\n{testo_ocr}"
                    else:
                        st.session_state["ocr_estratti"] = testo_ocr

    st.session_state["ocr_estratti"] = st.text_area(
        "📋 Testo Indagini Strumentali Estratto (modificabile e incluso nel referto finale):",
        value=st.session_state["ocr_estratti"],
        height=180,
        placeholder="Qui comparirà il riassunto dei referti scansionati con la fotocamera, oppure puoi incollare manualmente gli esami...",
    )


# ==============================================================================
# TAB 3: IL COLTELLINO SVIZZERO (SCALE CLINICHE & CALCOLATORI)
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

    # --- TOOL 1: QUESTIONARIO DN4 ---
    if scelta_tool.startswith("1."):
        st.markdown("#### Questionario DN4 (*Douleur Neuropathique en 4 Questions*)")
        cd1, cd2 = st.columns(2)
        with cd1:
            st.markdown("**Intervista al Paziente (Domande 1 e 2)**")
            dn_1 = st.checkbox("1. Bruciore")
            dn_2 = st.checkbox("2. Sensazione di freddo doloroso")
            dn_3 = st.checkbox("3. Scosse elettriche")
            dn_4 = st.checkbox("4. Formicolio")
            dn_5 = st.checkbox("5. Sensazione di spilli / aghi")
            dn_6 = st.checkbox("6. Intorpidimento")
            dn_7 = st.checkbox("7. Prurito")
        with cd2:
            st.markdown("**Esame Obiettivo Sensitivo (Domande 3 e 4)**")
            dn_8 = st.checkbox("8. Ipoestesia al tatto nella stessa area")
            dn_9 = st.checkbox("9. Ipoestesia alla puntura (pinprick) nella stessa area")
            dn_10 = st.checkbox("10. Il dolore è provocato o aumentato dallo sfregamento (Allodinia meccanica dinamica)")

        score_dn4 = sum([dn_1, dn_2, dn_3, dn_4, dn_5, dn_6, dn_7, dn_8, dn_9, dn_10])
        esito_dn4 = "POSITIVO per componente neuropatica (Cut-off >= 4/10)" if score_dn4 >= 4 else "NEGATIVO per componente neuropatica prevalente (< 4/10)"
        st.info(f"**Punteggio DN4: {score_dn4}/10** — {esito_dn4}")

        if st.button("➕ Allega Risultato DN4 alla Visita"):
            st.session_state["note_scale_cliniche"] += f"- Scala DN4: {score_dn4}/10 ({esito_dn4})\n"
            st.success("Risultato DN4 aggiunto alla scheda clinica!")

    # --- TOOL 2: CALCOLATORE ROTAZIONE OPPIOIDI (MME) ---
    elif scelta_tool.startswith("2."):
        st.markdown("#### Calcolatore di Equianalgesia e Rotazione degli Oppioidi")
        st.caption("Fattori di conversione standardizzati in Equivalenti di Morfina Orale (MME/24h). Il giudizio clinico prevale sempre sul calcolo matematico.")

        # Dizionario fattori di conversione verso Morfina Orale mg/die (MME)
        FATTORI_MME = {
            "Morfina Orale (mg/die)": 1.0,
            "Ossicodone Orale (mg/die)": 1.5,
            "Idromorfone Orale (mg/die)": 4.0,
            "Tapentadolo Orale (mg/die)": 0.4,
            "Tramadolo Orale (mg/die)": 0.1,
            "Fentanil Transdermico TTS (µg/h)": 2.4,      # es. 25 mcg/h ≈ 60 mg MME/die
            "Buprenorfina Transdermica TTS (µg/h)": 1.8,   # es. 35 mcg/h ≈ 63 mg MME/die
        }

        co1, co2, co3 = st.columns(3)
        with co1:
            oppioide_attuale = st.selectbox("Oppioide Attuale:", list(FATTORI_MME.keys()), index=1)
            dose_attuale = st.number_input("Dose Totale Giornaliera (o µg/h per cerotti):", min_value=0.0, value=20.0, step=5.0)
        with co2:
            oppioide_target = st.selectbox("Oppioide Target (Nuovo):", list(FATTORI_MME.keys()), index=6)
            riduzione_cross = st.slider("Riduzione per Cross-Tolerance Incompleta (%)", 0, 60, 30, step=5, help="Le linee guida raccomandano una riduzione del 25-50% quando si ruota verso un nuovo oppioide.")
        with co3:
            mme_attuali = dose_attuale * FATTORI_MME[oppioide_attuale]
            dose_equi_piena = mme_attuali / FATTORI_MME[oppioide_target]
            dose_target_ridotta = dose_equi_piena * (1.0 - riduzione_cross / 100.0)

            st.metric("Carico Attuale in MME/die", f"{mme_attuali:.1f} mg MME")
            st.metric("Dose Equianalgesica Teorica (100%)", f"{dose_equi_piena:.1f}")
            st.metric(f"Dose Consigliata (-{riduzione_cross}%)", f"{dose_target_ridotta:.1f}")

        if st.button("➕ Allega Calcolo Rotazione Oppioidi alla Visita"):
            nota_opp = (
                f"- Valutazione Rotazione Oppioidi: da {oppioide_attuale} ({dose_attuale}) [pari a {mme_attuali:.1f} mg MME/die] "
                f"a {oppioide_target} -> dose equianalgesica corretta del -{riduzione_cross}% per cross-tolerance = {dose_target_ridotta:.1f}\n"
            )
            st.session_state["note_scale_cliniche"] += nota_opp
            st.success("Calcolo aggiunto alla scheda clinica!")

    # --- TOOL 3: QUESTIONARIO FIQR (FIBROMIALGIA) ---
    elif scelta_tool.startswith("3."):
        st.markdown("#### Questionario FIQR (*Revised Fibromyalgia Impact Questionnaire*)")
        st.caption("Valutazione degli ultimi 7 giorni su scala 0-10. Score totale 0-100.")

        with st.expander("Dominio 1: Funzione Fisica (9 item - Peso 30%)", expanded=True):
            cf1, cf2, cf3 = st.columns(3)
            f1 = cf1.slider("1. Spazzolare/pettinare i capelli", 0, 10, 3)
            f2 = cf2.slider("2. Camminare per 20 minuti", 0, 10, 5)
            f3 = cf3.slider("3. Preparare un pasto fatto in casa", 0, 10, 4)
            f4 = cf1.slider("4. Passare l'aspirapolvere o spazzare", 0, 10, 6)
            f5 = cf2.slider("5. Sollevare e portare una borsa della spesa piena", 0, 10, 7)
            f6 = cf3.slider("6. Salire una rampa di scale", 0, 10, 5)
            f7 = cf1.slider("7. Cambiare le lenzuola del letto", 0, 10, 6)
            f8 = cf2.slider("8. Stare seduto/a su una sedia per 45 minuti", 0, 10, 5)
            f9 = cf3.slider("9. Fare la spesa al supermercato", 0, 10, 5)
            dom1_score = sum([f1, f2, f3, f4, f5, f6, f7, f8, f9]) / 3.0

        with st.expander("Dominio 2: Impatto Globale (2 item - Peso 20%)", expanded=True):
            cg1, cg2 = st.columns(2)
            g1 = cg1.slider("1. La fibromialgia mi ha impedito di raggiungere gli obiettivi della settimana", 0, 10, 5)
            g2 = cg2.slider("2. Mi sono sentito/a completamente sopraffatto/a dai sintomi", 0, 10, 5)
            dom2_score = float(g1 + g2)

        with st.expander("Dominio 3: Intensità dei Sintomi (10 item - Peso 50%)", expanded=True):
            cs1, cs2 = st.columns(2)
            s1 = cs1.slider("1. Intensità del dolore", 0, 10, 7)
            s2 = cs2.slider("2. Mancanza di energia / Astenia", 0, 10, 8)
            s3 = cs1.slider("3. Rigidità muscolare", 0, 10, 7)
            s4 = cs2.slider("4. Qualità del sonno (sonno non ristoratore)", 0, 10, 8)
            s5 = cs1.slider("5. Umore depresso / tristezza", 0, 10, 5)
            s6 = cs2.slider("6. Problemi di memoria / Fibro-fog", 0, 10, 6)
            s7 = cs1.slider("7. Ansia / tensione interna", 0, 10, 6)
            s8 = cs2.slider("8. Dolorabilità al tatto (allodinia/iperalgesia)", 0, 10, 7)
            s9 = cs1.slider("9. Problemi di equilibrio", 0, 10, 4)
            s10 = cs2.slider("10. Sensibilità a rumori forti, luci, odori o freddo", 0, 10, 6)
            dom3_score = sum([s1, s2, s3, s4, s5, s6, s7, s8, s9, s10]) / 2.0

        fiqr_totale = dom1_score + dom2_score + dom3_score
        if fiqr_totale <= 30:
            sev_fiqr = "Remissione / Impatto Lieve"
        elif fiqr_totale <= 45:
            sev_fiqr = "Severità Moderata"
        elif fiqr_totale <= 65:
            sev_fiqr = "Severità Elevata"
        else:
            sev_fiqr = "Severità Molto Elevata"

        st.info(
            f"**Punteggio FIQR Totale: {fiqr_totale:.1f}/100 ({sev_fiqr})** — "
            f"[Funzione: {dom1_score:.1f}/30 | Impatto: {dom2_score:.1f}/20 | Sintomi: {dom3_score:.1f}/50]"
        )

        if st.button("➕ Allega Punteggio FIQR alla Visita"):
            st.session_state["note_scale_cliniche"] += (
                f"- Questionario FIQR: {fiqr_totale:.1f}/100 ({sev_fiqr}) "
                f"[Funzione: {dom1_score:.1f}, Impatto: {dom2_score:.1f}, Sintomi: {dom3_score:.1f}]\n"
            )
            st.success("Risultato FIQR aggiunto alla scheda clinica!")

    # --- TOOL 4: SCALA CAST (CANNABIS ABUSE SCREENING TEST) ---
    elif scelta_tool.startswith("4."):
        st.markdown("#### Scala CAST (*Cannabis Abuse Screening Test* - Monitoraggio Uso Terapeutico)")
        opzioni_cast = ["0 - Mai", "1 - Raramente", "2 - Di tanto in tanto", "3 - Abbastanza spesso", "4 - Molto spesso"]
        ca_1 = int(st.selectbox("1. Ha assunto cannabis al di fuori degli orari/dosi prescritte prima di mezzogiorno?", opzioni_cast)[0])
        ca_2 = int(st.selectbox("2. Ha assunto dosi supplementari non concordate quando era da solo/a?", opzioni_cast)[0])
        ca_3 = int(st.selectbox("3. Ha avuto problemi di memoria o concentrazione legati all'assunzione?", opzioni_cast)[0])
        ca_4 = int(st.selectbox("4. Familiari o amici le hanno suggerito di ridurre o sospendere l'assunzione?", opzioni_cast)[0])
        ca_5 = int(st.selectbox("5. Ha provato a ridurre la dose senza riuscirci per comparsa di irrequietezza?", opzioni_cast)[0])
        ca_6 = int(st.selectbox("6. Ha avuto problemi (sonnolenza alla guida, cadute, discussioni) a causa dell'effetto?", opzioni_cast)[0])

        score_cast = ca_1 + ca_2 + ca_3 + ca_4 + ca_5 + ca_6
        interp_cast = "Basso rischio di abuso/dipendenza (< 3)" if score_cast < 3 else ("Rischio moderato (3-6)" if score_cast <= 6 else "Alto rischio di uso problematico (>= 7)")
        st.info(f"**Punteggio CAST: {score_cast}/24** — {interp_cast}")

        if st.button("➕ Allega Risultato CAST alla Visita"):
            st.session_state["note_scale_cliniche"] += f"- Screening CAST (Cannabis): {score_cast}/24 ({interp_cast})\n"
            st.success("Risultato CAST aggiunto alla scheda clinica!")

    st.divider()
    st.session_state["note_scale_cliniche"] = st.text_area(
        "📌 Riepilogo Scale e Calcolatori Allegati alla Visita Corrente:",
        value=st.session_state["note_scale_cliniche"],
        height=110,
    )


# ==============================================================================
# TAB 4: SINTESI AI, PROPOSTA TERAPEUTICA E OUTPUT PER PC OSPEDALIERO
# ==============================================================================
with tab_output:
    st.subheader("📄 Generazione Referto Clinico e Supporto Decisionale AI")

    # Costruiamo il contesto completo unendo Scheda Visita + OCR + Scale
    contesto_clinico_completo = dati_raccolti
    if st.session_state["ocr_estratti"].strip():
        contesto_clinico_completo += f"\nINDAGINI STRUMENTALI (OCR):\n{st.session_state['ocr_estratti']}\n"
    if st.session_state["note_scale_cliniche"].strip():
        contesto_clinico_completo += f"\nSCALE E CALCOLATORI CLINICI:\n{st.session_state['note_scale_cliniche']}\n"

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("✨ Genera Referto Completo, Diagnosi e Piano con Gemini AI", type="primary", use_container_width=True):
            with st.spinner("Elaborazione clinica in corso con Gemini..."):
                prompt_referto = f"""
Sei un medico specialista esperto in Anestesia, Rianimazione e Terapia del Dolore.
Sulla base dei seguenti dati clinici raccolti durante la visita ambulatoriale, redigi un referto medico specialistico completo, formale, rigoroso e pronto per essere incollato nella cartella clinica ospedaliera (stile refertando.it).

DATI RACCOLTI:
{contesto_clinico_completo}

STRUTTURA RICHIESTA PER IL REFERTO:
1. INTESTAZIONE E INQUADRAMENTO ANAMNESTICO (Sintesi fluida e professionale dell'anamnesi patologica, farmacologica e antalgica).
2. ESAME OBIETTIVO E VALUTAZIONE ALGOMERTICA/SCALE (Integrazione ordinata di EO, NRS ed eventuali scale DN4/FIQR/CAST/MME presenti).
3. ESAMI STRUMENTALI VISIONATI (Se presenti dati OCR o strumentali, riassumili con terminologia radiologica/neurofisiologica appropriata).
4. CONCLUSIONI DIAGNOSTICHE (Ipotesi diagnostica nosografica ed eziopatogenetica del dolore: nocicettivo, neuropatico, nociplastico o misto).
5. PROGRAMMA TERAPEUTICO E RACCOMANDAZIONI (Proposta dettagliata e prudente articolata in: eventuale terapia farmacologica/titolazione, eventuali indicazioni interventistiche/infiltrative o ozonoterapia, indicazioni comportamentali/riabilitative e tempistiche di rivalutazione).

Non usare formattazioni Markdown invasive (evita tabelle o simboli complessi) in modo che il testo sia perfetto per un copia-incolla diretto sul software gestionale ospedaliero.
"""
                risposta_ai = chiama_gemini(api_key, prompt_referto, model_name=modello_scelto)
                st.session_state["bozza_referto_finale"] = risposta_ai

    with col_btn2:
        if st.button("⚡ Assembla Referto Rapido (Senza AI)", use_container_width=True):
            st.session_state["bozza_referto_finale"] = contesto_clinico_completo

    st.divider()
    st.markdown("##### 1. Revisione e Modifica del Testo (Puoi correggere o confermare diagnosi e terapia)")
    st.session_state["bozza_referto_finale"] = st.text_area(
        "Modifica liberamente il referto prima di copiarlo:",
        value=st.session_state["bozza_referto_finale"],
        height=320,
    )

    st.markdown("##### 2. Copia in 1 Click per il PC dell'Ospedale")
    st.caption("Passa il mouse nell'angolo in alto a destra del riquadro sottostante e clicca sull'icona dei due foglietti per copiare l'intero referto negli appunti.")
    st.code(st.session_state["bozza_referto_finale"] or "Genera o assembla il referto sopra per attivare la copia rapida.", language="text")
