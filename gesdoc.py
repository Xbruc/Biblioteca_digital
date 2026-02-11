import os
from pathlib import Path
import shutil
import io
import zipfile
import hashlib
import base64

import pandas as pd
import streamlit as st
import geopandas as gpd
import fiona
import mammoth
import bcrypt

from docx import Document
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="SRH | Biblioteca Digital",
    page_icon="📁",
    layout="wide",
)

BASE_DIR = Path("data/SRH")

MONTHS = ["JAN","FEV","MAR","ABR","MAI","JUN","JUL","AGO","SET","OUT","NOV","DEZ"]
YEARS  = ["2023","2024","2025","2026","2027"]

PARECER_TIPOS = [
    "Renovação de outorga",
    "Outorga preventiva",
    "Outorga direito de uso",
]

CARTAS_TIPOS = [
    "Cartas de Pendência",
    "Cartas de Indeferimento",
]

METAS = [f"Meta {i}" for i in range(1,8)]

AREAS = [
    "Outorgas",
    "Gestão Participativa",
    "Gestão Planejamento",
    "Carta de Inexigibilidade",
    "Manifestação Técnica",
    "Empresas Perfuradoras",
    "Base de Dados",
    "Fiscalização",
    "D Tamponamento",
]

# =========================================================
# LOGIN
# =========================================================

USERS = st.secrets["AUTH_USERS"].split(",")
PASSWORD_HASH = st.secrets["PASSWORD_HASH"].encode()

def autenticar():
    if "auth" not in st.session_state:
        st.session_state.auth = False

    if st.session_state.auth:
        return

    with st.form("login"):
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if email in USERS and bcrypt.checkpw(senha.encode(), PASSWORD_HASH):
                st.session_state.auth = True
                st.rerun()
            else:
                st.error("Credenciais inválidas")
    st.stop()

autenticar()

# =========================================================
# CRIAR ESTRUTURA COMPLETA
# =========================================================

def criar_estrutura():
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    for area in AREAS:
        (BASE_DIR / area.replace(" ","_")).mkdir(parents=True, exist_ok=True)

criar_estrutura()

# =========================================================
# INDEXAÇÃO
# =========================================================

@st.cache_data
def build_index():
    rows = []
    for root, _, files in os.walk(BASE_DIR):
        for f in files:
            full = Path(root)/f
            rel = full.relative_to(BASE_DIR)
            rows.append({
                "arquivo": f,
                "caminho": str(full),
                "relativo": str(rel)
            })
    return pd.DataFrame(rows)

df = build_index()

# =========================================================
# VISUALIZADOR
# =========================================================

def visualizar(path: Path):
    ext = path.suffix.lower()

    if ext in [".png",".jpg",".jpeg",".gif",".webp"]:
        st.image(str(path), use_container_width=True)
        return

    if ext == ".pdf":
        with open(path,"rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        st.components.v1.html(
            f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="800"></iframe>'
        )
        return

    if ext == ".docx":
        with open(path,"rb") as f:
            html = mammoth.convert_to_html(f).value
        st.components.v1.html(html, height=800, scrolling=True)
        return

    if ext in [".xlsx",".xls"]:
        df_excel = pd.read_excel(path)
        st.dataframe(df_excel, use_container_width=True)
        return

    if ext == ".pptx":
        prs = Presentation(path)
        for i,slide in enumerate(prs.slides):
            with st.expander(f"Slide {i+1}"):
                for shape in slide.shapes:
                    if hasattr(shape,"text"):
                        st.write(shape.text)
        return

    if ext == ".shp":
        gdf = gpd.read_file(path)
        gdf = gdf.to_crs(epsg=4326)
        gdf["lat"]=gdf.geometry.centroid.y
        gdf["lon"]=gdf.geometry.centroid.x
        st.map(gdf[["lat","lon"]])
        return

    st.info("Visualização não disponível.")

# =========================================================
# HEADER
# =========================================================

st.title("SRH | Biblioteca Digital")

# =========================================================
# UPLOAD
# =========================================================

with st.expander("Adicionar Documento"):
    area = st.selectbox("Área", AREAS)
    uploaded = st.file_uploader("Arquivo")

    if uploaded and st.button("Salvar"):
        target = BASE_DIR / area.replace(" ","_")
        target.mkdir(parents=True, exist_ok=True)
        with open(target/uploaded.name,"wb") as f:
            f.write(uploaded.getbuffer())
        build_index.clear()
        st.success("Arquivo salvo.")
        st.rerun()

# =========================================================
# BUSCA GLOBAL
# =========================================================

busca = st.text_input("Buscar arquivo")

if busca:
    view = df[df["arquivo"].str.contains(busca,case=False,na=False)]
else:
    view = df

# =========================================================
# LISTAGEM
# =========================================================

for i,row in view.iterrows():
    path = Path(row["caminho"])
    with st.container():
        c1,c2,c3 = st.columns([2,1,1])

        with c1:
            st.write(row["arquivo"])

        with c2:
            st.download_button(
                "Baixar",
                data=open(path,"rb"),
                file_name=path.name
            )

        with c3:
            if st.button("Visualizar",key=f"v{i}"):
                visualizar(path)

# =========================================================
# DASHBOARD
# =========================================================

def get_directory_size(path):
    total=0
    for p in path.rglob("*"):
        if p.is_file():
            total+=p.stat().st_size
    return total

st.divider()
st.subheader("Uso de Armazenamento")

data_size = get_directory_size(BASE_DIR)
disk = shutil.disk_usage(BASE_DIR)

percent = data_size/disk.total
st.progress(percent)

st.metric("Data (GB)", f"{data_size/1024**3:.2f}")
st.metric("Total Disco (GB)", f"{disk.total/1024**3:.0f}")
