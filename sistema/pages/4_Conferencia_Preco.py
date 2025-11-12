import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import oracledb
from sqlalchemy import create_engine

# ============================
# 🚀 Inicialização Oracle segura
# ============================
try:
    oracledb.init_oracle_client(
        lib_dir=r"C:\instantclient",
        config_dir=r"C:\instantclient\network\admin"
    )
except oracledb.ProgrammingError:
    pass
except oracledb.Error as e:
    st.warning(f"⚠️ Erro ao iniciar Oracle Client: {e}")

# ============================
# 🧹 Controle de cache inicial
# ============================
if "cache_limpo" not in st.session_state:
    st.cache_data.clear()
    st.cache_resource.clear()
    st.session_state["cache_limpo"] = True

st.title("👨‍💼 Conferência de Preços OFF TRADE")

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
          AND DTMOV BETWEEN TO_DATE('{data_inicial}', 'YYYY-MM-DD') AND TO_DATE('{data_final}', 'YYYY-MM-DD')
        ORDER BY DTMOV DESC
    """
    df = pd.read_sql(query, con=engine)
    df.columns = df.columns.str.upper()
    return df

@st.cache_data
def carregar_vendedores():
    df = pd.read_sql("SELECT CODUSUR, NOME FROM crc.PBI_PCUSUARI", con=engine)
    df.columns = df.columns.str.upper()
    return df

@st.cache_data
def carregar_tabelas_excel():
    tabela_27 = pd.read_excel(
        r"C:\Hbox\Off Trade\TABELA _OFF RJ - CRC - 12 E 27 CREDITO - SEMANA 4 - OUTUBRO.xlsx",
        sheet_name="TABELA RIGARR (ESPECIAL)", skiprows=3
    )
    tabela_promo_rigarr = pd.read_excel(
        r"C:\Hbox\Off Trade\TABELA PROMO - OFF - CREDITO 12 - SEMANA 4 - OUTUBRO.xlsx",
        sheet_name="TABELA", skiprows=5
    )
    tabela_promo_castas = pd.read_excel(
        r"C:\Hbox\Off Trade\TABELA PROMO - OFF - CREDITO 12 - SEMANA 4 - OUTUBRO.xlsx",
        sheet_name="TABELA CASTAS", skiprows=5
    )
    
    # Normalizar nomes de colunas
    for df in [tabela_27, tabela_promo_rigarr, tabela_promo_castas]:
        df.columns = df.columns.str.strip().str.upper()
    
    return tabela_27, tabela_promo_rigarr, tabela_promo_castas

# ============================
# 🗓️ Filtros
# ============================
st.sidebar.header("📅 Filtros")
hoje = pd.Timestamp.today().date()
inicio_padrao = hoje.replace(day=1)
data_inicial = st.sidebar.date_input("Data Inicial", inicio_padrao)
data_final = st.sidebar.date_input("Data Final", hoje)

# ============================
# 📥 Carregar dados
# ============================
with st.spinner("🔄 Carregando dados do Oracle e Excel..."):
    vendas = carregar_vendas(data_inicial, data_final)
    vendedores = carregar_vendedores()
    tabela_27, tabela_promo_rigarr, tabela_promo_castas = carregar_tabelas_excel()

# ============================
# 🔄 Junção e tratamento
# ============================
df = vendas.merge(vendedores, on="CODUSUR", how="left")
df["VALOR_TOTAL"] = df["QT"] * df["PRECO_FINAL"]
df["DATA_VENDA"] = pd.to_datetime(df["DTMOV"], errors="coerce")
df.dropna(subset=["DATA_VENDA"], inplace=True)

# ============================
# 🎛️ Filtro por vendedor
# ============================
usuarios = ['Todos'] + sorted(df["NOME"].dropna().unique().tolist())
usuario_selecionado = st.sidebar.selectbox("Selecione o Vendedor", usuarios)
df_filtrado = df.copy()
if usuario_selecionado != "Todos":
    df_filtrado = df_filtrado[df_filtrado["NOME"] == usuario_selecionado]

# ============================
# 🔍 Preparar DataFrames para conferência
# ============================
# Renomear colunas para facilitar
tabela_27 = tabela_27.rename(columns={'COD':'CODPROD','PRECO':'PRECO_REF'})
tabela_promo_rigarr = tabela_promo_rigarr.rename(columns={'COD CRC':'CODPROD','PREÇO':'PRECO_REF'})
tabela_promo_castas = tabela_promo_castas.rename(columns={'COD CRC':'CODPROD','PREÇO':'PRECO_REF'})

# Concatenar todas as tabelas de referência
tabelas_ref = pd.concat([tabela_27[['CODPROD','PRECO_REF']],
                          tabela_promo_rigarr[['CODPROD','PRECO_REF']],
                          tabela_promo_castas[['CODPROD','PRECO_REF']]])

# Manter apenas o menor preço como referência
tabelas_ref = tabelas_ref.groupby('CODPROD')['PRECO_REF'].min().reset_index()

# Merge com vendas
df_filtrado = df_filtrado.merge(tabelas_ref, on='CODPROD', how='left')

# ============================
# 🧮 Conferência de preços
# ============================
def conferir(preco_venda, preco_ref):
    if pd.isna(preco_ref):
        return "Não encontrado"
    elif preco_venda > preco_ref:
        return "MAIOR"
    elif preco_venda < preco_ref:
        return "MENOR"
    else:
        return "IGUAL"

df_filtrado['CONFERENCIA_PRECO'] = df_filtrado.apply(
    lambda row: conferir(row['PRECO_FINAL'], row['PRECO_REF']),
    axis=1
)

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
# 📋 Tabela final
# ============================
limite = 1000
st.dataframe(df_filtrado[['CODPROD','DESCRICAO','PRECO_FINAL','PRECO_REF','CONFERENCIA_PRECO']].head(limite))
if len(df_filtrado) > limite:
    st.caption(f"Mostrando as {limite:,} primeiras linhas de {len(df_filtrado):,}".replace(",", "."))

# ============================
# 📈 Gráfico de conferência
# ============================
if not df_filtrado.empty:
    df_grafico = df_filtrado.groupby("CONFERENCIA_PRECO")["VALOR_TOTAL"].sum()
    fig, ax = plt.subplots(figsize=(8,5))
    ax.bar(df_grafico.index, df_grafico.values, color=["green","orange","red","gray"])
    plt.title("Conferência de Preços")
    plt.ylabel("Valor Total")
    plt.tight_layout()
    st.pyplot(fig)
else:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")
