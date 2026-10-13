import streamlit as st
import requests
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Prueba Bypass | HY-NET", page_icon="🕵️", layout="centered")
st.title("🕵️ Prueba de Lógica: Detección de Bypass")
st.write("Estructura anidada ('data' dentro de 'data') corregida.")

ps_id = st.text_input("Ingresa el ID exacto del sitio (ej. hyb_sujal):", "hyb_sujal").strip().lower()

if st.button("Evaluar Sitio"):
    session = requests.Session()
    session.headers.update({
        "X-STELLAR-OP": "hybrico",
        "X-STELLAR-ORG": "hybrico",
        "Origin": "https://stellar.newsunroad.com",
        "Referer": "https://stellar.newsunroad.com/",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    
    LOGIN_URL = "https://api.stellar.newsunroad.com/api/v0/login"
    PAYLOAD = {"username": "armando.acuna@hybricoenergy.com", "password": "Hybrico2021"}
    
    try:
        with st.spinner("Autenticando..."):
            session.post(LOGIN_URL, json=PAYLOAD, timeout=10)
        
        ahora = datetime.now(timezone.utc)
        hace_una_hora = ahora - timedelta(hours=1)
        end_sec = int(ahora.timestamp())
        start_sec = int(hace_una_hora.timestamp())
        
        url_inversor = f"https://api.stellar.newsunroad.com/api/v0/devices/{ps_id}?end={end_sec}&start={start_sec}&params=inverterLoadPower&deviceClass=Inverter"
        url_medidor = f"https://api.stellar.newsunroad.com/api/v0/devices/{ps_id}?end={end_sec}&start={start_sec}&params=acLoadPower&deviceClass=LoadMeter"
        
        with st.spinner("Descargando métricas de Inversor y Medidor..."):
            res_inv = session.get(url_inversor, timeout=15)
            res_med = session.get(url_medidor, timeout=15)
            
        data_inv = res_inv.json() if res_inv.status_code == 200 else {}
        data_med = res_med.json() if res_med.status_code == 200 else {}
        
        # Función de metadatos intacta
        def obtener_multiplicador(data_dict, parametro):
            try:
                unidad = data_dict.get('meta', {}).get('parameterUnits', {}).get(parametro, '').lower()
                return 1000 if unidad == 'kw' else 1
            except:
                return 1

        # === EL ARREGLO ESTÁ AQUÍ ===
        def extraer_valor_data(data_dict, clave_buscada):
            items = data_dict.get('data', [])
            if items and isinstance(items, list):
                for item in items:
                    # Entramos a la SUB-LLAVE 'data' que está adentro de cada dispositivo
                    inner_data = item.get('data', {}) 
                    if clave_buscada in inner_data:
                        val = inner_data[clave_buscada]
                        if isinstance(val, dict):
                            return val.get('last', val.get('mean'))
                        return val
            return None

        # Extracción Inversor
        raw_inv = extraer_valor_data(data_inv, 'inverterLoadPower')
        mult_inv = obtener_multiplicador(data_inv, 'inverterLoadPower')
        
        try:
            load_power = (float(raw_inv) * mult_inv) if raw_inv is not None else None
        except:
            load_power = None

        # Extracción Medidor
        raw_med = extraer_valor_data(data_med, 'acLoadPower')
        mult_med = obtener_multiplicador(data_med, 'acLoadPower')
        
        try:
            met_power = (float(raw_med) * mult_med) if raw_med is not None else None
        except:
            met_power = None

        # Redondear si existen
        if load_power is not None: load_power = round(load_power, 1)
        if met_power is not None: met_power = round(met_power, 1)

        # === RENDERIZADO ===
        st.markdown("### 📊 Lecturas Actuales (Última hora)")
        col1, col2 = st.columns(2)
        col1.metric("⚡ Inversor (inverterLoadPower)", f"{load_power} W" if load_power is not None else "Sin Datos")
        col2.metric("📟 Medidor (acLoadPower)", f"{met_power} W" if met_power is not None else "Sin Datos")
        
        st.markdown("### 🏷️ Clasificación del Sitio")
        if load_power is None and met_power is None:
            st.error("🚨 **Sistema no está operando o API no devolvió datos.**")
        elif load_power is not None and met_power is None:
            if load_power < 500:
                st.warning("⚠️ **SITIO EN BYPASS.** (Inversor reporta baja carga y medidor no comunica).")
            else:
                st.info("ℹ️ **No está en Bypass.** (Inversor entregando carga alta, pero medidor no comunica).")
        elif load_power is not None and met_power is not None:
            st.success("✅ **Operación Normal.** (Ambos equipos comunicando y entregando datos).")
        else:
            st.write("Estado atípico: Medidor reporta datos pero Inversor no.")

    except Exception as e:
        st.error(f"Error general: {e}")