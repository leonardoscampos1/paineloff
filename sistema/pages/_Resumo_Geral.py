import streamlit as st
import pandas as pd
import sqlite3
from datetime import date
from dateutil.relativedelta import relativedelta

# ==========================
# 🗄 Caminho do banco SQLite
# ==========================
ARQUIVO_SQLITE = r"C:\Hbox\Banco de Dados\banco_local.db"

# ==========================
# 🔄 Função de carregamento
# ==========================
@st.cache_data(hash_funcs={date: str})
def carregar_dados_sqlite(data_inicial, data_final):
    # Garante formato ISO (YYYY-MM-DD)
    data_inicial_str = data_inicial.isoformat() if isinstance(data_inicial, date) else str(data_inicial)
    data_final_str = data_final.isoformat() if isinstance(data_final, date) else str(data_final)

    conn = sqlite3.connect(ARQUIVO_SQLITE, check_same_thread=False)

    query_mov = """
        SELECT 
            m.CODFILIAL,
            DATE(m.DTMOV) AS DTMOV,   -- <<< converte para data pura
            m.CODOPER,
            m.CODCLI,
            m.CODUSUR,
            m.CODPROD,
            p.DESCRICAO,
            m.QT,
            p.CODFORNEC,
            m.PUNIT,
            m.DTCANCEL
        FROM PCMOV m
        LEFT JOIN PCPRODUT p ON m.CODPROD = p.CODPROD
        WHERE m.CODOPER LIKE 'S%'
          AND DATE(m.DTMOV) BETWEEN ? AND ?
    """

    tabela_mov = pd.read_sql(query_mov, conn, params=(data_inicial_str, data_final_str))
    tabela_usur = pd.read_sql("SELECT CODUSUR, NOME FROM PCUSUARI", conn)
    tabela_cliente = pd.read_sql("SELECT CODCLI, CLIENTE, CODUSUR1 AS RCA, CODUSUR2 AS RCA2 FROM PCCLIENT", conn)
    tabela_fornec = pd.read_sql("SELECT CODFORNEC, FORNECEDOR FROM PCFORNEC", conn)

    conn.close()

    # Padronizar colunas
    for t in [tabela_mov, tabela_usur, tabela_cliente, tabela_fornec]:
        t.columns = t.columns.str.upper().str.strip()

    # Junta todas as informações
    tabela_mov = (
        tabela_mov
        .merge(tabela_usur, on='CODUSUR', how='left')
        .rename(columns={'NOME': 'VENDEDOR'})
        .merge(tabela_cliente, on='CODCLI', how='left')
        .merge(tabela_fornec, on='CODFORNEC', how='left')
    )

    # Converte DTMOV em datetime.date para evitar hora
    tabela_mov['DTMOV'] = pd.to_datetime(tabela_mov['DTMOV']).dt.date

    return tabela_mov, tabela_cliente, tabela_fornec



# ==========================
# 💰 Função para calcular faturamento
# ==========================
def calcular_faturamento(df, vendedores_selecionados):
    df = df[df['VENDEDOR'].isin(vendedores_selecionados)].copy()
    
    for col in ['QT', 'PUNIT']:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    
    df['PREÇO_FINAL'] = df['QT'] * df['PUNIT']
    faturamento_total = df['PREÇO_FINAL'].sum()
    
    return df, faturamento_total

# ==========================
# 🎛️ Filtros
# ==========================
st.sidebar.header("📅 Filtros")
hoje = date.today()
primeiro_dia_mes = hoje.replace(day=1)

data_inicial = st.sidebar.date_input("Data Inicial", primeiro_dia_mes)
data_final = st.sidebar.date_input("Data Final", hoje)

# Carregar dados
tabela_mov, tabela_cliente, tabela_fornec = carregar_dados_sqlite(data_inicial, data_final)
tabela_mov = tabela_mov[tabela_mov['DTCANCEL'].isna()]

# Filtro de vendedores
vendedores = sorted(tabela_mov['VENDEDOR'].dropna().unique())
vendedor_selecionado = st.sidebar.multiselect(
    "👨‍💼 Selecione o(s) vendedor(es)",
    vendedores,
    default=vendedores
)

# ==========================
# 💰 Cálculo de faturamento
# ==========================
tabela_filtrada, faturamento_atual = calcular_faturamento(tabela_mov, vendedor_selecionado)
tabela_filtrada = tabela_filtrada.drop("DTCANCEL", axis=1)

# Mês anterior
data_inicial_ant = data_inicial - relativedelta(months=1)
data_final_ant = data_final - relativedelta(months=1)
tabela_mesmo_periodo_ant, faturamento_mesmo_periodo_ant = calcular_faturamento(
    carregar_dados_sqlite(data_inicial_ant, data_final_ant)[0],
    vendedor_selecionado
)

# Ano anterior
data_inicial_ano_ant = data_inicial - relativedelta(years=1)
data_final_ano_ant = data_final - relativedelta(years=1)
tabela_ano_ant_temp, _, _ = carregar_dados_sqlite(data_inicial_ano_ant, data_final_ano_ant)
tabela_ano_ant, faturamento_ano_ant = pd.DataFrame(), 0
if not tabela_ano_ant_temp.empty:
    tabela_ano_ant, faturamento_ano_ant = calcular_faturamento(tabela_ano_ant_temp, vendedor_selecionado)

# Variações
variacao_periodo = ((faturamento_atual - faturamento_mesmo_periodo_ant) / faturamento_mesmo_periodo_ant * 100) if faturamento_mesmo_periodo_ant else 0
variacao_ano = ((faturamento_atual - faturamento_ano_ant) / faturamento_ano_ant * 100) if faturamento_ano_ant else 0

# ==========================
# 🧾 Exibição métricas
# ==========================
st.title("📊 Painel de Vendas por Vendedor")
col1, col2, col3, col4 = st.columns(4)
col1.metric("💰 Faturamento Atual", f"R$ {faturamento_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
col2.metric("🗓️ Mês Anterior", f"R$ {faturamento_mesmo_periodo_ant:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
col3.metric("📈 Variação Mês", f"{variacao_periodo:.2f}%")
col4.metric("📆 Ano Anterior", f"R$ {faturamento_ano_ant:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), delta=f"{variacao_ano:.2f}%")

# ==========================
# 📋 Detalhamento de vendas
# ==========================
st.divider()
st.subheader("📋 Detalhamento de Vendas")
st.dataframe(tabela_filtrada)

# ==========================
# 👥 Clientes e Indústrias
# ==========================
st.divider()
st.subheader("Clientes e Indústrias Atendidos / Não Atendidos")

# Filtrar clientes vinculados aos vendedores selecionados
codigos_vendedores = tabela_mov.loc[tabela_mov['VENDEDOR'].isin(vendedor_selecionado), 'CODUSUR'].unique()
clientes_vendedor = tabela_cliente[
    (tabela_cliente['RCA'].isin(codigos_vendedores)) |
    (tabela_cliente['RCA2'].isin(codigos_vendedores))
]

# Clientes atendidos / não atendidos
clientes_atendidos = tabela_filtrada['CODCLI'].unique()
clientes_nao_atendidos = clientes_vendedor[~clientes_vendedor['CODCLI'].isin(clientes_atendidos)]

# Indústrias atendidas / não atendidas
industria_atendidas = tabela_filtrada['CODFORNEC'].unique()
todas_industrias = tabela_fornec.copy()
industria_nao_atendidas = todas_industrias[~todas_industrias['CODFORNEC'].isin(industria_atendidas)]
 
# Filtrar tabela atual e mês anterior
tabela_atual = tabela_filtrada.copy()
tabela_mes_ant, _=calcular_faturamento(carregar_dados_sqlite(data_inicial_ant, data_final_ant)[0],vendedor_selecionado)

# Clientes atendidos no mês anterior
clientes_mes_ant = tabela_mes_ant['CODCLI'].unique()
# Indústrias atendidas no mês anterior
industrias_mes_ant = tabela_mes_ant['CODFORNEC'].unique()

# Clientes que compraram no mês anterior, mas ainda não compraram agora
clientes_nao_atual = clientes_mes_ant[~pd.Series(clientes_mes_ant).isin(tabela_atual['CODCLI'])]
# Indústrias que venderam no mês anterior, mas ainda não venderam agora
industrias_nao_atual = industrias_mes_ant[~pd.Series(industrias_mes_ant).isin(tabela_atual['CODFORNEC'])]

# Produtos pedidos pelos clientes que não compraram agora
produtos_clientes = tabela_mes_ant[tabela_mes_ant['CODCLI'].isin(clientes_nao_atual)][
    ['CODCLI', 'CLIENTE', 'CODPROD', 'DESCRICAO', 'QT', 'PUNIT', 'PREÇO_FINAL']
]

# Produtos pedidos pelas indústrias que não compraram agora
produtos_industrias = tabela_mes_ant[tabela_mes_ant['CODFORNEC'].isin(industrias_nao_atual)][
    ['CODFORNEC', 'FORNECEDOR', 'CODPROD', 'DESCRICAO', 'QT', 'PUNIT', 'PREÇO_FINAL']
]

# Exibir lado a lado
col1, col2 = st.columns(2)

with col1:
    st.subheader("👥 Clientes")
    st.write(f"✅ Clientes atendidos: {len(clientes_atendidos)}")
    st.dataframe(clientes_vendedor[clientes_vendedor['CODCLI'].isin(clientes_atendidos)][['CODCLI', 'CLIENTE', 'RCA', 'RCA2']])
    st.divider()
    st.write(f"🚫 Clientes não atendidos: {len(clientes_nao_atendidos)}")
    st.dataframe(clientes_nao_atendidos[['CODCLI', 'CLIENTE', 'RCA', 'RCA2']])

with col2:
    st.subheader("🏭 Indústrias")
    st.write(f"✅ Indústrias atendidas: {len(industria_atendidas)}")
    st.dataframe(todas_industrias[todas_industrias['CODFORNEC'].isin(industria_atendidas)])
    st.divider()    
    st.write(f"🚫 Indústrias não atendidas: {len(industria_nao_atendidas)}")
    st.dataframe(industria_nao_atendidas)
st.divider()
st.subheader("Clientes e Indústrias Atendidos no Mês Anterior e Ainda Não Atendidos")

col1, col2 = st.columns(2)

with col1:
    st.subheader("👥 Clientes")
    st.write(f"Clientes que compraram no mês anterior, mas não compraram agora: {len(clientes_nao_atual)}")
    st.dataframe(produtos_clientes)

with col2:
    st.subheader("🏭 Indústrias")
    st.write(f"Indústrias que venderam no mês anterior, mas não venderam agora: {len(industrias_nao_atual)}")
    st.dataframe(produtos_industrias)
