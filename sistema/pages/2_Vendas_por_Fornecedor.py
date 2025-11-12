import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import oracledb
from sqlalchemy import create_engine

# ============================
# 🚀 Inicialização Oracle segura
# ============================
if not getattr(oracledb, "thin_mode", False):
    try:
        oracledb.init_oracle_client(
            lib_dir=r"C:\instantclient",
            config_dir=r"C:\instantclient\network\admin"
        )
    except oracledb.Error:
        pass  # já inicializado

# ============================
# 🧹 Controle de cache inicial
# ============================
if "cache_limpo" not in st.session_state:
    st.cache_data.clear()
    st.cache_resource.clear()
    st.session_state["cache_limpo"] = True

st.title("👨‍💼 Vendas por Fornecedor")

# ============================
# 🔗 Conexão Oracle
# ============================
user = "vpn"
password = "vpn2320vpn"
dsn = "crc_oci"
engine = create_engine(f'oracle+oracledb://{user}:{password}@{dsn}')

# ============================
# 📦 Funções com cache
# ============================
@st.cache_data(ttl=300)
def carregar_vendas(data_inicial, data_final):
    query = f"""
        SELECT CODFILIAL, DTMOV, CODOPER, CODCLI, CODUSUR, CODPROD, DESCRICAO, QT, PRECO_FINAL
        FROM crc.PBI_PCMOV
        WHERE CODFILIAL = '2'
          AND CODOPER LIKE 'S%%'
          AND DTMOV BETWEEN TO_DATE('{data_inicial}', 'YYYY-MM-DD') 
                         AND TO_DATE('{data_final}', 'YYYY-MM-DD')
        ORDER BY DTMOV DESC
    """
    df = pd.read_sql(query, con=engine)
    return df.rename(columns=str.upper)

@st.cache_data
def carregar_fornecedores():
    df = pd.read_sql("SELECT CODFORNEC, FORNECEDOR FROM crc.PBI_PCFORNEC", con=engine)
    return df.rename(columns=str.upper)

@st.cache_data
def carregar_produtos():
    df = pd.read_sql("SELECT CODPROD, DESCRICAO, CODFORNEC, FORNECEDOR FROM crc.PBI_PCPRODUT", con=engine)
    return df.rename(columns=str.upper)

# ============================
# 🗓️ Filtros iniciais (datas)
# ============================
st.sidebar.header("📅 Filtros")
hoje = pd.Timestamp.today().date()
inicio_padrao = hoje.replace(day=1)

data_inicial = st.sidebar.date_input("Data Inicial", inicio_padrao)
data_final = st.sidebar.date_input("Data Final", hoje)

# ============================
# 📥 Carregar dados filtrados
# ============================
with st.spinner("🔄 Carregando dados do Oracle..."):
    vendas = carregar_vendas(data_inicial, data_final)
    fornecedores = carregar_fornecedores()
    produtos = carregar_produtos()

# ============================
# 🔄 Junção e tratamento
# ============================
df = vendas.merge(produtos, on="CODPROD", how="left", suffixes=('_VENDA', '_PROD'))
df = df.merge(fornecedores, on="CODFORNEC", how="left", suffixes=('', '_FORN'))

# Corrige coluna FORNECEDOR
df.rename(columns={'FORNECEDOR': 'FORNECEDOR'}, inplace=True)

df["VALOR_TOTAL"] = df["QT"] * df["PRECO_FINAL"]
df["DATA_VENDA"] = pd.to_datetime(df["DTMOV"], errors="coerce")
df.dropna(subset=["DATA_VENDA"], inplace=True)

# ============================
# 🎛️ Filtro de Fornecedor
# ============================
lista_fornecedores = ['Todos'] + sorted(df['FORNECEDOR'].dropna().unique().tolist())
fornecedor_selecionado = st.sidebar.selectbox('Selecione o Fornecedor', lista_fornecedores)

df_filtrado = df.copy()
if fornecedor_selecionado != 'Todos':
    df_filtrado = df_filtrado[df_filtrado["FORNECEDOR"] == fornecedor_selecionado]

# ============================
# 📊 Métricas
# ============================
col1, col2, col3 = st.columns(3)
valor_total = df_filtrado["VALOR_TOTAL"].sum()
ticket_medio = valor_total / df_filtrado["CODCLI"].nunique() if df_filtrado["CODCLI"].nunique() > 0 else 0
qtd_vendas = len(df_filtrado)

col1.metric("💰 Valor Total", f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
col2.metric("📦 Ticket Médio", f"R$ {ticket_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
col3.metric("🧾 Nº de Vendas", f"{qtd_vendas:,}".replace(",", "."))

# ============================
# 📋 Tabela (limitada)
# ============================
limite = 1000
st.dataframe(df_filtrado.head(limite).rename(columns=lambda x: x.title()))
if len(df_filtrado) > limite:
    st.caption(f"Mostrando as {limite:,} primeiras linhas de {len(df_filtrado):,}".replace(",", "."))

# ============================
# 📈 Gráfico por Fornecedor
# ============================
if not df_filtrado.empty:
    df_agrupado = df_filtrado.groupby("FORNECEDOR")["VALOR_TOTAL"].sum().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(df_agrupado.index, df_agrupado.values, color="teal")
    plt.xticks(rotation=45, ha="right")
    plt.title("Vendas por Fornecedor")
    plt.tight_layout()
    st.pyplot(fig)
else:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")
    