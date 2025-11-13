import pandas as pd
import streamlit as st
import sqlite3
import requests
from io import BytesIO
from datetime import date

# ============================
# ⚙️ URL do SQLite remoto
# ============================
URL_SQLITE = "https://hbox.houseti.com.br/s/D2nXxuYkkeuV6r3/download"

# ============================
# 🔄 Função para baixar o SQLite
# ============================
@st.cache_data(ttl=300)
def baixar_banco():
    r = requests.get(URL_SQLITE)
    r.raise_for_status()  # garante erro se falhar
    return BytesIO(r.content)

# ============================
# ⚙️ Conexão SQLite
# ============================
def conectar_sqlite():
    banco_memoria = baixar_banco()
    return sqlite3.connect(banco_memoria)

# ============================
# 🗃️ Funções com cache
# ============================
@st.cache_data(ttl=300)
def carregar_vendas(data_inicial, data_final):
    query = f"""
        SELECT CODFILIAL, DTMOV, CODOPER, CODCLI, CODUSUR, CODPROD, QT, PUNIT AS PRECO_FINAL, DTCANCEL
        FROM PCMOV
        WHERE CODOPER LIKE 'S%%'
          AND DTMOV BETWEEN '{data_inicial}' AND '{data_final}'
        ORDER BY DTMOV DESC
    """
    with conectar_sqlite() as con:
        df = pd.read_sql(query, con)
    return df.rename(columns=str.upper)

@st.cache_data
def carregar_vendedores():
    query = "SELECT CODUSUR, NOME AS VENDEDOR FROM PCUSUARI"
    with conectar_sqlite() as con:
        df = pd.read_sql(query, con)
    return df.rename(columns=str.upper)

@st.cache_data
def carregar_clientes():
    query = "SELECT CODCLI, CLIENTE FROM PCCLIENT"
    with conectar_sqlite() as con:
        df = pd.read_sql(query, con)
    return df.rename(columns=str.upper)

@st.cache_data
def carregar_produtos():
    query = "SELECT CODPROD, DESCRICAO, CODFORNEC FROM PCPRODUT"
    with conectar_sqlite() as con:
        df = pd.read_sql(query, con)
    return df.rename(columns=str.upper)
