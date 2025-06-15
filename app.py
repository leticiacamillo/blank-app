import streamlit as st
import fitz  # PyMuPDF
from shapely.geometry import Point, shape
import json
import pandas as pd
from geopy.geocoders import Nominatim
import re

# CONFIGURAÇÃO
GEOJSON_PATH = "Zoneamento Urbano.json"  # ajuste se necessário

parametros_zonas = {
    "ZR-1": {
        "uso_permitido": ["Residencial Unifamiliar"],
        "Área mínima do lote (m²)": 500,
        "Frente mínima do lote (m)": 15,
        "Taxa de Ocupação (%)": 50,
        "Coeficiente de Aproveitamento": 1.3,
        "Recuo frontal (m)": 5,
        "Recuo lateral mínimo (m)": 1.5,
        "Altura máxima (pavimentos)": 2,
        "Taxa mínima de permeabilidade (%)": 20
    },
    "ZPR-1": {
        "uso_permitido": ["Residencial Unifamiliar", "Residencial Multifamiliar"],
        "Área mínima do lote (m²)": 125,
        "Frente mínima do lote (m)": 5,
        "Taxa de Ocupação (%)": 65,
        "Coeficiente de Aproveitamento": 1.3,
        "Recuo frontal (m)": 5,
        "Recuo lateral mínimo (m)": 1.5,
        "Altura máxima (pavimentos)": None,
        "Taxa mínima de permeabilidade (%)": 20
    }
}

def extrair_bairro_pdf(uploaded_file):
    texto = ""
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    for pagina in doc:
        texto += pagina.get_text()
    return texto

def obter_endereco(texto):
    match = re.search(r"(rua|avenida|av\.?|estrada|travessa)[^\n,]*", texto, re.IGNORECASE)
    return match.group(0).strip() + ", Limeira - SP" if match else None

def obter_coordenadas(endereco):
    try:
        geolocator = Nominatim(user_agent="copiloto-urbanistico")
        location = geolocator.geocode(endereco, timeout=10)
        if location:
            return (location.longitude, location.latitude)
    except Exception as e:
        st.error(f"Erro ao obter coordenadas: {e}")
    return None

def detectar_zona(point: Point, geojson_path: str):
    with open(geojson_path, "r", encoding="utf-8") as f:
        dados = json.load(f)
    for feature in dados["features"]:
        try:
            geom = shape(feature["geometry"])
            if geom.contains(point):
                return feature["properties"].get("name", "Zona desconhecida")
        except Exception:
            continue
    return "Zona não localizada"

def extrair_valores_provaveis_com_fallback(texto):
    simulados = {
        "frente_lote": 15.0,
        "taxa_ocupacao": 50.0,
        "coeficiente_aproveitamento": 1.3,
        "recuo_frontal": 5.0,
        "recuo_lateral": 1.5,
        "permeabilidade": 20.0,
        "pavimentos": 0,
        "area_lote": 600.0

    }

    texto = texto.lower()
    dados = {}

    area_lote = re.search(r"area.*?(\d+[.,]?\d*)\s*m", texto)
    frente = re.search(r"frente.*?(\d+[.,]?\d*)\s*m", texto)
    to = re.search(r"taxa de ocupação.*?(\d+[.,]?\d*)\s*%", texto)
    ca = re.search(r"coeficiente de aproveitamento.*?(\d+[.,]?\d*)", texto)
    recuo_f = re.search(r"recuo frontal.*?(\d+[.,]?\d*)\s*m", texto)
    recuo_l = re.search(r"recuo lateral.*?(\d+[.,]?\d*)\s*m", texto)
    permeab = re.search(r"permeabilidade.*?(\d+[.,]?\d*)\s*%", texto)
    pav = re.search(r"(\d{1,2})\s*pavimentos", texto)

    dados["area_lote"] = float(area_lote.group(1).replace(",", ".")) if area_lote else simulados["area_lote"]
    dados["frente_lote"] = float(frente.group(1).replace(",", ".")) if frente else simulados["frente_lote"]
    dados["taxa_ocupacao"] = float(to.group(1).replace(",", ".")) if to else simulados["taxa_ocupacao"]
    dados["coeficiente_aproveitamento"] = float(ca.group(1).replace(",", ".")) if ca else simulados["coeficiente_aproveitamento"]
    dados["recuo_frontal"] = float(recuo_f.group(1).replace(",", ".")) if recuo_f else simulados["recuo_frontal"]
    dados["recuo_lateral"] = float(recuo_l.group(1).replace(",", ".")) if recuo_l else simulados["recuo_lateral"]
    dados["permeabilidade"] = float(permeab.group(1).replace(",", ".")) if permeab else simulados["permeabilidade"]
    dados["pavimentos"] = int(pav.group(1)) if pav else simulados["pavimentos"]

    return dados

def checar(valor, norma, tipo="max"):
    if norma is None:
        return "✅"
    if tipo == "max":
        return "✅" if valor <= norma else "❌"
    elif tipo == "min":
        return "✅" if valor >= norma else "❌"
    elif tipo == "igual":
        return "✅" if valor == norma else "❌"

# --- INTERFACE ---
st.title("🏗️ Copiloto Urbanístico – Limeira")

pdf_file = st.file_uploader("📄 Faça upload do memorial descritivo (PDF)", type=["pdf"])

if pdf_file:
    texto = extrair_bairro_pdf(pdf_file)
    st.success("PDF lido com sucesso!")

    endereco = obter_endereco(texto)
    if endereco:
        st.info(f"📍 Endereço identificado: {endereco}")
        coordenadas = obter_coordenadas(endereco)

        if coordenadas:
            ponto = Point(coordenadas[0], coordenadas[1])
            zona_completa = detectar_zona(ponto, GEOJSON_PATH)
            codigo_zona = zona_completa.split(":")[0].strip()

            st.info(f"🧭 Zona identificada: {zona_completa}")

            if codigo_zona in parametros_zonas:
                dados = extrair_valores_provaveis_com_fallback(texto)

                tipo_ocup = st.selectbox("Tipo de Ocupação", [
                    "Residencial Unifamiliar", "Residencial Multifamiliar",
                    "Comercial", "Industrial", "Outro"
                ])

                area_lote = st.number_input("Área do lote (m²)", min_value=0.0, value=dados["area_lote"])
                frente = st.number_input("Frente do lote (m)", value=dados["frente_lote"])
                to = st.number_input("Taxa de ocupação (%)", value=dados["taxa_ocupacao"])
                ca = st.number_input("Coeficiente de aproveitamento", value=dados["coeficiente_aproveitamento"])
                rf = st.number_input("Recuo frontal (m)", value=dados["recuo_frontal"])
                rl = st.number_input("Recuo lateral mínimo (m)", value=dados["recuo_lateral"])
                permeab = st.number_input("Taxa de permeabilidade (%)", value=dados["permeabilidade"])
                pav = st.number_input("Nº de pavimentos", min_value=0, value=dados["pavimentos"])

                p = parametros_zonas[codigo_zona]

                resultado = {
                    "Tipo de ocupação permitido": "✅" if tipo_ocup in p["uso_permitido"] else "❌",
                    "Área do lote (mín.)": checar(area_lote, p["Área mínima do lote (m²)"], "min"),
                    "Frente do lote (mín.)": checar(frente, p["Frente mínima do lote (m)"], "min"),
                    "Taxa de ocupação (máx.)": checar(to, p["Taxa de Ocupação (%)"], "max"),
                    "Coef. de aproveitamento (máx.)": checar(ca, p["Coeficiente de Aproveitamento"], "max"),
                    "Recuo frontal (mín.)": checar(rf, p["Recuo frontal (m)"], "min"),
                    "Recuo lateral mínimo (mín.)": checar(rl, p["Recuo lateral mínimo (m)"], "min"),
                    "Permeabilidade (mín.)": checar(permeab, p["Taxa mínima de permeabilidade (%)"], "min"),
                    "Nº de pavimentos": checar(pav, p["Altura máxima (pavimentos)"], "max")
                }

                st.header(f"📋 Checklist de Conformidade – {codigo_zona}")
                for k, v in resultado.items():
                    st.write(f"{k}: {v}")
            else:
                st.warning(f"Zona detectada ({codigo_zona}) ainda não implementada.")
        else:
            st.error("❌ Não foi possível obter coordenadas para o endereço.")
    else:
        st.error("❌ Endereço não encontrado no texto do PDF.")
