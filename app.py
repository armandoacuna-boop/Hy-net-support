import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import concurrent.futures

st.set_page_config(page_title="HY-NET | NOC Dashboard", page_icon="⚡", layout="wide")
st.title("⚡ HY-NET | Dashboard de Soporte NOC")
st.caption("Filtro de alarmas corregido: Diferenciación entre Stellar Edge y Periféricos.")

@st.cache_data(ttl=60, show_spinner=False)
def cargar_datos_completos():
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
        session.post(LOGIN_URL, json=PAYLOAD, timeout=10)
    except Exception as e:
        return pd.DataFrame(), f"Fallo de login: {e}"

    regiones_reales = {"tigo_hn": "Tigo Honduras", "tigo_gt": "Tigo GT"}
    ahora = datetime.now(timezone.utc)
    ayer = ahora - timedelta(hours=24)
    end_sec = int(ahora.timestamp())
    start_sec = int(ayer.timestamp())
    
    sitios_info = []

    def consultar_region(region_id):
        url = f"https://api.stellar.newsunroad.com/api/v0/summary?end={end_sec}&start={start_sec}&region={region_id}"
        try:
            # AUMENTAMOS EL TIMEOUT A 45s porque Tigo GT tiene 369 sitios con historial pesado
            r = session.get(url, timeout=45)
            if r.status_code == 200:
                return region_id, r.json()
        except Exception as e:
            print(f"Error descargando {region_id}: {e}")
        return region_id, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        resultados = executor.map(consultar_region, regiones_reales.keys())
        for region_id, summary_data in resultados:
            if summary_data and isinstance(summary_data, dict):
                items = summary_data.get('data', [])
                
                for item in items:
                    if isinstance(item, dict):
                        ps_id = item.get('powerSystemId', 'Desconocido')
                        nombre = item.get('powerSystemName', ps_id).upper()
                        
                        estado = "Online"
                        indicador = "🟢 Online"
                        detalle = "Sin alarmas críticas"
                        
                        inner_data = item.get('data', {})
                        if isinstance(inner_data, dict) and 'statusAlerts' in inner_data:
                            for alert in inner_data['statusAlerts']:
                                metric = str(alert.get('metric')).lower()
                                status = str(alert.get('status')).lower()
                                desc = str(alert.get('description', '')).lower()
                                entity = str(alert.get('entityName', '')).lower()
                                
                                # Solo nos importa si es un error de conexión
                                if ('connection' in metric or 'offline' in metric) and status == 'error':
                                    # Verificamos que la caída sea del cerebro (Stellar Edge)
                                    if 'stellar edge' in desc or 'stellar edge' in entity:
                                        estado = "Offline"
                                        indicador = "🔴 Offline"
                                        detalle = alert.get('description', 'Pérdida de comunicación (Edge)')
                                        break # El sitio está caído, dejamos de buscar
                                    elif estado == "Online":
                                        # Si es de un periférico, lo anotamos pero el sitio sigue Online
                                        detalle = f"Alerta Periférico: {alert.get('entityName', 'Sensor')}"

                        sitios_info.append({
                            "REGION": regiones_reales[region_id],
                            "NOMBRE_SITIO": nombre,
                            "SITIO_ID": ps_id,
                            "ESTADO": estado,
                            "INDICADOR": indicador,
                            "DETALLE": detalle
                        })

    return pd.DataFrame(sitios_info), None

# ================= RENDERIZADO VISUAL ================= #

with st.spinner("📡 Descargando datos masivos (Tigo GT puede tardar unos segundos)..."):
    df, error = cargar_datos_completos()

if df.empty:
    st.error("No se pudieron descargar los datos. Intenta recargar la página.")
    st.stop()

st.sidebar.header("🔍 Filtros de Visualización")
regiones = ["Todas"] + sorted(df["REGION"].unique().tolist())
region_sel = st.sidebar.selectbox("Seleccionar Región:", regiones)
estado_sel = st.sidebar.radio("Estado de Conexión:", ["Todos", "Online", "Offline"])

if st.sidebar.button("🔄 Actualizar Datos Ahora"):
    st.cache_data.clear()
    st.rerun()

df_filt = df.copy()
if region_sel != "Todas":
    df_filt = df_filt[df_filt["REGION"] == region_sel]
if estado_sel != "Todos":
    df_filt = df_filt[df_filt["ESTADO"] == estado_sel]

total = len(df_filt)
online = len(df_filt[df_filt["ESTADO"] == "Online"])
offline = total - online
disp = (online / total * 100) if total > 0 else 0.0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Sitios (Piloto)", f"{total}")
c2.metric("Con Gestión 🟢", f"{online}")
c3.metric("Sin Gestión 🔴", f"{offline}")
c4.metric("% Disponibilidad de Red", f"{disp:.1f}%")

st.markdown("---")

if total > 0:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("📊 Resumen Operativo")
        st.dataframe(df_filt["ESTADO"].value_counts().reset_index(), hide_index=True, use_container_width=True)
    with col2:
        st.subheader("📍 Sitios por Región")
        st.bar_chart(df_filt.groupby(["REGION", "ESTADO"]).size().unstack(fill_value=0))

    st.subheader("📋 Detalle de Seguimiento")
    st.dataframe(
        df_filt.sort_values(by="ESTADO")[["REGION", "NOMBRE_SITIO", "SITIO_ID", "INDICADOR", "DETALLE"]], 
        use_container_width=True, 
        hide_index=True
    )