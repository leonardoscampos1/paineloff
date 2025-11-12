import pandas as pd
import streamlit as st
import sqlite3
from datetime import date

# ============================
# ⚙️ Caminho do Banco SQLite
# ============================
ARQUIVO_SQLITE = r"C:\Hbox\Banco de Dados\banco_local.db"

# ============================
# ⚙️ Conexão SQLite
# ============================
def conectar_sqlite():
    return sqlite3.connect(ARQUIVO_SQLITE)

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

# ============================
# 🎨 Layout Streamlit
# ============================
st.set_page_config(page_title="Campanhas", page_icon="🤖", layout="wide")
st.title("📊 Apuração de Campanhas")

opcoes = ['Alud', 'Bateu, Levou!']
escolha = st.selectbox("Escolha a Campanha Vigente:", opcoes)
st.markdown(f"### 🧭 Mecânica da Campanha **{escolha}**")

# ============================
# 🏆 Tabelas de premiação
# ============================
if escolha == "Alud":
    st.subheader("🏆 Premiação Faturamento RJ")
    df_fat = pd.DataFrame({
        "Faturamento": ["R$ 30.000,00", "R$ 50.000,00"],
        "Preço Médio": ["R$ 25,90", "R$ 25,90"],
        "Caixas": [193, 322],
        "Prêmio": ["R$ 450,00", "R$ 750,00"]
    })
    st.dataframe(df_fat, use_container_width=True)

    st.subheader("🏅 Premiação Positivação RJ — Vendeu duas caixas já positiva")
    df_pos = pd.DataFrame({
        "Positivação": ["10 CNPJs", "15 CNPJs", "20 CNPJs", "25 CNPJs", "30 CNPJs"],
        "Preço Médio": ["R$ 27,90"] * 5,
        "Caixas": [20, 30, 40, 50, 60],
        "Prêmio": ["R$ 100,00", "R$ 150,00", "R$ 200,00", "R$ 250,00", "R$ 300,00"]
    })
    st.dataframe(df_pos, use_container_width=True)

elif escolha == "Bateu, Levou!":
    st.subheader("🏆 Bateu, Levou!")
    df_fat_mooving = pd.DataFrame({
        "Faturamento": ["R$ 3.200.000,00"],
        "Prêmio": ["0,5% adicionais sobre o total liquidado"]
    })
    st.dataframe(df_fat_mooving, use_container_width=True)
    st.caption("""
    **Mecânica:**  
    - Período: Novembro/25  
    - Área: Rio de Janeiro  
    - Gatilho: Faturamento ≥ R$ 3.200.000  
    - Premiação: 0,5% adicionais sobre o total liquidado
    """)

# ============================
# 🗓️ Filtros iniciais
# ============================
st.sidebar.header("📅 Filtros")
hoje = pd.Timestamp.today().date()
inicio_padrao = hoje.replace(day=1)

data_inicial = st.sidebar.date_input("Data Inicial", inicio_padrao)
data_final = st.sidebar.date_input("Data Final", hoje)

# ============================
# 📥 Carregar dados
# ============================
with st.spinner("🔄 Carregando dados do banco local..."):
    vendas = carregar_vendas(data_inicial, data_final)
    vendedores = carregar_vendedores()
    clientes = carregar_clientes()
    produtos = carregar_produtos()

# ============================
# 🔄 Junção e tratamento
# ============================
df = vendas.merge(vendedores, on="CODUSUR", how="left")
df = df.merge(clientes, on="CODCLI", how="left")
df = df.merge(produtos, on="CODPROD", how="left")

# Converter DTMOV em data (caso venha como texto ou número)
df["DTMOV"] = pd.to_datetime(df["DTMOV"], errors="coerce")
df["DATA_VENDA"] = df["DTMOV"].dt.strftime("%d/%m/%Y")
df.dropna(subset=["DATA_VENDA"], inplace=True)

df["DTCANCEL"] = pd.to_datetime(df["DTCANCEL"], errors="coerce")
df["DTCANCEL_FORMATADA"] = df["DTCANCEL"].dt.strftime("%d/%m/%Y")
df = df[df["DTCANCEL"].isna()]
df = df[df["CODOPER"]== "S"]

# Cálculos
df["VALOR_TOTAL"] = df["QT"] * df["PRECO_FINAL"]
df["CAIXAS"] = (df["QT"] / 6).astype(int)

# Filtro por campanha
if escolha == "Alud":
    df = df[df["DESCRICAO"].str.contains("ALUD", case=False, na=False)]

# ============================
# 🎛️ Filtro de Vendedor
# ============================
# Cria uma lista combinando código e nome
df_vendedores_unicos = (
    df[['CODUSUR', 'VENDEDOR']]
    .drop_duplicates()
    .dropna(subset=['VENDEDOR'])
    .sort_values('VENDEDOR')
)

# Formata para exibir "CODUSUR - VENDEDOR"
lista_vendedores_formatada = ['Todos'] + [
    f"{int(row.CODUSUR)} - {row.VENDEDOR}" for _, row in df_vendedores_unicos.iterrows()
]

# Selectbox
vendedor_formatado = st.sidebar.selectbox("👨‍💼 Selecione o Vendedor", lista_vendedores_formatada)

# Extrai o nome real do vendedor (após o "-")
if vendedor_formatado == 'Todos':
    vendedor_selecionado = 'Todos'
else:
    vendedor_selecionado = vendedor_formatado.split(" - ", 1)[1]

# Filtra
df_filtrado = df.copy()
if vendedor_selecionado != 'Todos':
    df_filtrado = df_filtrado[df_filtrado["VENDEDOR"] == vendedor_selecionado]


# ============================
# 📊 Métricas
# ============================
col1, col2, col3, col4, col5 = st.columns(5)

valor_total = df_filtrado["VALOR_TOTAL"].sum()
preco_medio = valor_total / df_filtrado["QT"].sum() if df_filtrado["QT"].sum() > 0 else 0
qtd_vendas = len(df_filtrado)
total_caixas = int(df_filtrado["CAIXAS"].sum())
qtd_clientes = df_filtrado["CODCLI"].nunique()

if escolha == "Alud":
    col1.metric("💰 Valor Total", f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col2.metric("📦 Preço Médio", f"R$ {preco_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col3.metric("🧾 Nº de Vendas", f"{qtd_vendas:,}".replace(",", "."))
    col4.metric("📦 Total de Caixas (6 unid.)", f"{total_caixas:,.0f}".replace(",", "."))
    col5.metric("👨‍🦲 Quantidade Clientes", f"{qtd_clientes}")

elif escolha == "Bateu, Levou!":
    meta = 3_200_000.00
    faltante = meta - valor_total
    # ===============================
    # 💰 MÉTRICAS PRINCIPAIS
    # ===============================
    col1, col2, col3 = st.columns([1.2, 1.2, 1.2])  # aumenta a largura das colunas

    with col1:
        st.markdown(
            f"""
            <div style="text-align:center; font-size:28px; font-weight:bold;">💰 Meta</div>
            <div style="text-align:center; font-size:36px; color:#16a34a;">
                R$ {meta:,.2f}
            </div>
            """.replace(",", "X").replace(".", ",").replace("X", "."),
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            f"""
            <div style="text-align:center; font-size:28px; font-weight:bold;">💵 Valor Faturado</div>
            <div style="text-align:center; font-size:36px; color:#dc2626;">
                R$ {valor_total:,.2f}
            </div>
            """.replace(",", "X").replace(".", ",").replace("X", "."),
            unsafe_allow_html=True
        )
    with col3:
        st.markdown(
            f"""
            <div style="text-align:center; font-size:28px; font-weight:bold;">🎯 Faltam para Meta</div>
            <div style="text-align:center; font-size:36px; color:#dc2626;">
                R$ {faltante:,.2f}
            </div>
            """.replace(",", "X").replace(".", ",").replace("X", "."),
            unsafe_allow_html=True
        )


# ============================
# 📋 Tabela de resultados
# ============================
st.subheader("📋 Detalhamento de Vendas")
limite = 1000
colunas = ["DATA_VENDA", "VENDEDOR", "CODCLI", "CLIENTE", "DESCRICAO", "QT", "PRECO_FINAL", "VALOR_TOTAL", "CAIXAS"]

if escolha == "Bateu, Levou!":
    colunas.remove("CAIXAS")

st.dataframe(df_filtrado.head(limite)[colunas].rename(columns=lambda x: x.title()), use_container_width=True)

if len(df_filtrado) > limite:
    st.caption(f"Mostrando as {limite:,} primeiras linhas de {len(df_filtrado):,}".replace(",", "."))
