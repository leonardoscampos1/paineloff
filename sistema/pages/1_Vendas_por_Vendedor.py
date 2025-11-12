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

st.title("👨‍💼 Vendas por Vendedor")

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
def carregar_vendedores():
    df = pd.read_sql("SELECT CODUSUR, NOME AS VENDEDOR FROM crc.PBI_PCUSUARI", con=engine)
    return df.rename(columns=str.upper)

@st.cache_data
def carregar_clientes():
    df = pd.read_sql("SELECT CODCLI, CLIENTE FROM crc.PBI_PCCLIENT", con=engine)
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
    vendedores = carregar_vendedores()
    clientes = carregar_clientes()

# ============================
# 🔄 Junção e tratamento
# ============================
df = vendas.merge(vendedores, on="CODUSUR", how="left")
df = df.merge(clientes, on="CODCLI", how="left")

df["VALOR_TOTAL"] = df["QT"] * df["PRECO_FINAL"]
df["DATA_VENDA"] = pd.to_datetime(df["DTMOV"], errors="coerce")
df.dropna(subset=["DATA_VENDA"], inplace=True)

# ============================
# 🎛️ Filtro de Vendedor
# ============================
lista_vendedores = ['Todos'] + sorted(df['VENDEDOR'].dropna().unique().tolist())
vendedor_selecionado = st.sidebar.selectbox('Selecione o Vendedor', lista_vendedores)

df_filtrado = df.copy()
if vendedor_selecionado != 'Todos':
    df_filtrado = df_filtrado[df_filtrado["VENDEDOR"] == vendedor_selecionado]

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
st.dataframe(
    df_filtrado.head(limite)[
        ["DATA_VENDA", "VENDEDOR","CODCLI","CLIENTE", "DESCRICAO", "QT", "PRECO_FINAL", "VALOR_TOTAL"]
    ].rename(columns=lambda x: x.title()),
    use_container_width=True,
)
if len(df_filtrado) > limite:
    st.caption(f"Mostrando as {limite:,} primeiras linhas de {len(df_filtrado):,}".replace(",", "."))

# ============================
# 📈 Gráfico por Vendedor
# ============================
if not df_filtrado.empty:
    df_agrupado = df_filtrado.groupby("VENDEDOR")["VALOR_TOTAL"].sum().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(df_agrupado.index, df_agrupado.values, color="teal")
    plt.xticks(rotation=45, ha="right")
    plt.title("Vendas por Vendedor")
    plt.tight_layout()
    st.pyplot(fig)
else:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")
