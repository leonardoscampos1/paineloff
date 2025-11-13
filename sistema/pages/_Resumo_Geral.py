import streamlit as st
import pandas as pd
import sqlite3
import requests
import tempfile
import time
import os
from io import BytesIO
from datetime import date
from dateutil.relativedelta import relativedelta
st.cache_data.clear()

# =====================================================
# 🧠 CONFIGURAÇÃO GERAL
# =====================================================
URL_SQLITE = "https://hbox.houseti.com.br/s/D2nXxuYkkeuV6r3/download"
TEMP_DIR = tempfile.gettempdir()
SQLITE_LOCAL = os.path.join(TEMP_DIR, "banco_temp.db")
PARQUET_PATH = os.path.join(TEMP_DIR, "banco_cache.parquet")
ETAG_FILE = os.path.join(TEMP_DIR, "banco_etag.txt")

def atualizar_banco_local(URL_SQLITE, SQLITE_LOCAL, ETAG_FILE):
    """Verifica se o banco remoto mudou e atualiza o cache local."""
    try:
        resposta_head = requests.head(URL_SQLITE)
        etag_remota = resposta_head.headers.get("ETag", "")
        etag_local = ""

        if os.path.exists(ETAG_FILE):
            with open(ETAG_FILE, "r") as f:
                etag_local = f.read().strip()

        # Só baixa se o arquivo mudou
        if not os.path.exists(SQLITE_LOCAL) or etag_local != etag_remota:
            st.info("🔄 Atualizando banco de dados remoto...")
            resposta = requests.get(URL_SQLITE)
            resposta.raise_for_status()

            with open(SQLITE_LOCAL, "wb") as f:
                f.write(resposta.content)
            with open(ETAG_FILE, "w") as f:
                f.write(etag_remota)
        else:
            with st.empty():
                st.info("✅ Banco local já está atualizado.")
                time.sleep(2)

    except Exception as e:
        st.warning(f"⚠️ Falha ao verificar atualização: {e}")

    return SQLITE_LOCAL

# =====================================================
# 📦 Carregamento e conversão para Parquet (rápido)
# =====================================================
@st.cache_data
def carregar_tabelas_completas():
    """Lê o banco SQLite, junta tudo e salva em Parquet."""
    caminho = atualizar_banco_local(URL_SQLITE, SQLITE_LOCAL, ETAG_FILE)
    conn = sqlite3.connect(caminho)

    tabela_mov = pd.read_sql("""
        SELECT 
            m.CODFILIAL, DATE(m.DTMOV) AS DTMOV, m.CODOPER,
            m.CODCLI, m.CODUSUR, m.CODPROD, p.DESCRICAO,
            m.QT, p.CODFORNEC, m.PUNIT, m.DTCANCEL
        FROM PCMOV m
        LEFT JOIN PCPRODUT p ON m.CODPROD = p.CODPROD
        WHERE m.CODOPER LIKE 'S%'
    """, conn)

    tabela_usur = pd.read_sql("SELECT CODUSUR, NOME FROM PCUSUARI", conn)
    tabela_cliente = pd.read_sql("SELECT CODCLI, CLIENTE, CODUSUR1 AS RCA, CODUSUR2 AS RCA2 FROM PCCLIENT", conn)
    tabela_fornec = pd.read_sql("SELECT CODFORNEC, FORNECEDOR FROM PCFORNEC", conn)
    conn.close()

    for t in [tabela_mov, tabela_usur, tabela_cliente, tabela_fornec]:
        t.columns = t.columns.str.upper().str.strip()

    tabela_mov['DTMOV'] = pd.to_datetime(tabela_mov['DTMOV']).dt.date
    tabela_mov = (
        tabela_mov
        .merge(tabela_usur, on='CODUSUR', how='left')
        .rename(columns={'NOME': 'VENDEDOR'})
        .merge(tabela_cliente, on='CODCLI', how='left')
        .merge(tabela_fornec, on='CODFORNEC', how='left')
    )

    tabela_mov.to_parquet(PARQUET_PATH, index=False)

    return tabela_mov, tabela_cliente, tabela_fornec


@st.cache_data
def carregar_dados_periodo(data_inicial, data_final):
    """Filtra os dados no Parquet conforme o período."""
    if os.path.exists(PARQUET_PATH):
        tabela_mov = pd.read_parquet(PARQUET_PATH)
    else:
        tabela_mov, _, _ = carregar_tabelas_completas()

    tabela_mov['DTMOV'] = pd.to_datetime(tabela_mov['DTMOV']).dt.date
    tabela_filtrada = tabela_mov[
        (tabela_mov['DTMOV'] >= data_inicial) &
        (tabela_mov['DTMOV'] <= data_final)
    ].copy()

    _, tabela_cliente, tabela_fornec = carregar_tabelas_completas()
    return tabela_filtrada, tabela_cliente, tabela_fornec


# =====================================================
# 💰 Função de faturamento
# =====================================================
def calcular_faturamento(df, vendedores_selecionados):
    df = df[df['VENDEDOR'].isin(vendedores_selecionados)].copy()

    for col in ['QT', 'PUNIT']:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

    df['PREÇO_FINAL'] = df['QT'] * df['PUNIT']
    faturamento_total = df['PREÇO_FINAL'].sum()

    return df, faturamento_total


# =====================================================
# 🎛️ Filtros
# =====================================================
st.sidebar.header("📅 Filtros")
hoje = date.today()
primeiro_dia_mes = hoje.replace(day=1)

data_inicial = st.sidebar.date_input("Data Inicial", primeiro_dia_mes)
data_final = st.sidebar.date_input("Data Final", hoje)

# =====================================================
# 🗂️ Carregamento principal
# =====================================================
tabela_mov, tabela_cliente, tabela_fornec = carregar_dados_periodo(data_inicial, data_final)
tabela_mov = tabela_mov[tabela_mov['DTCANCEL'].isna()]

vendedores = sorted(tabela_mov['VENDEDOR'].dropna().unique())
vendedor_selecionado = st.sidebar.multiselect("👨‍💼 Vendedores", vendedores, default=vendedores)

# =====================================================
# 💰 Cálculos
# =====================================================
tabela_filtrada, faturamento_atual = calcular_faturamento(tabela_mov, vendedor_selecionado)

# Mês anterior
data_inicial_ant = data_inicial - relativedelta(months=1)
data_final_ant = data_final - relativedelta(months=1)
tabela_mes_ant, _, _ = carregar_dados_periodo(data_inicial_ant, data_final_ant)
tabela_mes_ant, faturamento_mes_ant = calcular_faturamento(tabela_mes_ant, vendedor_selecionado)

# Ano anterior
data_inicial_ano_ant = data_inicial - relativedelta(years=1)
data_final_ano_ant = data_final - relativedelta(years=1)
tabela_ano_ant, _, _ = carregar_dados_periodo(data_inicial_ano_ant, data_final_ano_ant)
tabela_ano_ant, faturamento_ano_ant = calcular_faturamento(tabela_ano_ant, vendedor_selecionado)

# Variações
variacao_mes = ((faturamento_atual - faturamento_mes_ant) / faturamento_mes_ant * 100) if faturamento_mes_ant else 0
variacao_ano = ((faturamento_atual - faturamento_ano_ant) / faturamento_ano_ant * 100) if faturamento_ano_ant else 0


# =====================================================
# 🧾 Exibição
# =====================================================
st.title("📊 Painel de Vendas por Vendedor")
col1, col2, col3, col4 = st.columns(4)
col1.metric("💰 Faturamento Atual", f"R$ {faturamento_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
col2.metric("🗓️ Mês Anterior", f"R$ {faturamento_mes_ant:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
col3.metric("📈 Variação Mês", f"{variacao_mes:.2f}%")
col4.metric("📆 Ano Anterior", f"R$ {faturamento_ano_ant:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), delta=f"{variacao_ano:.2f}%")

st.divider()
st.subheader("📋 Detalhamento de Vendas")
st.dataframe(tabela_filtrada)

# =====================================================
# 👥 Clientes / Indústrias
# =====================================================
st.divider()
st.subheader("Clientes e Indústrias Atendidos / Não Atendidos")

cod_vendedores = tabela_mov.loc[tabela_mov['VENDEDOR'].isin(vendedor_selecionado), 'CODUSUR'].unique()
clientes_vendedor = tabela_cliente[
    (tabela_cliente['RCA'].isin(cod_vendedores)) |
    (tabela_cliente['RCA2'].isin(cod_vendedores))
]

clientes_atendidos = tabela_filtrada['CODCLI'].unique()
clientes_nao = clientes_vendedor[~clientes_vendedor['CODCLI'].isin(clientes_atendidos)]

ind_atendidas = tabela_filtrada['CODFORNEC'].unique()
ind_nao = tabela_fornec[~tabela_fornec['CODFORNEC'].isin(ind_atendidas)]

col1, col2 = st.columns(2)
with col1:
    st.subheader("👥 Clientes")
    st.write(f"✅ Atendidos: {len(clientes_atendidos)}")
    st.dataframe(clientes_vendedor[clientes_vendedor['CODCLI'].isin(clientes_atendidos)][['CODCLI','CLIENTE','RCA','RCA2']])
    st.divider()
    st.write(f"🚫 Não atendidos: {len(clientes_nao)}")
    st.dataframe(clientes_nao[['CODCLI','CLIENTE','RCA','RCA2']])

with col2:
    st.subheader("🏭 Indústrias")
    st.write(f"✅ Atendidas: {len(ind_atendidas)}")
    st.dataframe(tabela_fornec[tabela_fornec['CODFORNEC'].isin(ind_atendidas)])
    st.divider()
    st.write(f"🚫 Não atendidas: {len(ind_nao)}")
    st.dataframe(ind_nao)

st.divider()
st.caption("⚡ Otimizado com cache local e Parquet — carregamento até 10x mais rápido.")













