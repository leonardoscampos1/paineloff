# chatbot_inteligente.py

import streamlit as st
import pandas as pd
import re
import sqlite3
import requests
from io import BytesIO
from dotenv import load_dotenv
import random
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.chat_models import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
import smtplib
from email.message import EmailMessage
import tempfile

# ==========================
# 🗄️ Caminhos e Configurações
# ==========================
URL_SQLITE = "https://hbox.houseti.com.br/s/D2nXxuYkkeuV6r3/download"
CAMINHO_DB = r"C:\Users\LeonardoCampos\HBox\Off Trade\sistema\db"

st.set_page_config(page_title="ChatBot Inteligente", page_icon="🤖", layout="wide")
st.title("🤖 ChatBot Inteligente com Memória")
st.write("Converse com o assistente com base na sua base de conhecimento Chroma e banco de clientes.")

load_dotenv()

# ==========================
# 📌 Funções auxiliares
# ==========================
def extrair_cnpj(texto):
    padrao = r'\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}'
    resultado = re.search(padrao, texto)
    return resultado.group() if resultado else None

def normalizar_cnpj(cnpj):
    return re.sub(r'\D', '', str(cnpj))
def consulta_cliente(cnpj):
    """Consulta o cliente na base de dados baixada (com cache local)."""
    try:
        # 🧠 Carrega e mantém a tabela em cache
        if "tabela_cliente" not in st.session_state:
            st.info("📥 Carregando base de clientes pela primeira vez... (pode levar alguns segundos)")
            r = requests.get(URL_SQLITE)
            r.raise_for_status()

            # Cria arquivo temporário
            with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
                tmp.write(r.content)
                caminho_temp = tmp.name
                st.session_state.caminho_db_temp = caminho_temp

            # Conecta e carrega tabela completa
            conn = sqlite3.connect(caminho_temp)
            df = pd.read_sql("SELECT CODCLI, CGCENT, CLIENTE FROM PCCLIENT", conn)
            conn.close()

            # Normaliza CNPJ e coloca em cache
            df.columns = df.columns.str.upper()
            df["CGCENT"] = df["CGCENT"].apply(lambda x: re.sub(r'\D', '', str(x)))
            st.session_state.tabela_cliente = df
            st.success("✅ Base de clientes carregada com sucesso!")

        # 🔎 Busca o CNPJ informado
        df_clientes = st.session_state.tabela_cliente
        cnpj_norm = re.sub(r'\D', '', str(cnpj))
        resultado = df_clientes[df_clientes["CGCENT"] == cnpj_norm]

        if not resultado.empty:
            codcli, cliente, cgc = resultado.iloc[0][["CODCLI", "CLIENTE", "CGCENT"]]
            return f"✅ O CNPJ {cgc} está cadastrado com o código {codcli} ({cliente})."
        else:
            return f"🚫 Não encontramos o CNPJ {cnpj} na base de clientes."

    except Exception as e:
        return f"❌ Erro ao consultar o banco: {e}"

def enviar_email_cadastro(cnpj, solicitante, destino="leonardo.campos@rigarr.com.br"):
    """Envia e-mail solicitando cadastro de CNPJ"""
    try:
        # 🧼 Remove quebras de linha e espaços extras
        cnpj_limpo = str(cnpj).strip().replace("\n", "").replace("\r", "")
        solicitante_limpo = str(solicitante).strip().replace("\n", "").replace("\r", "")
        destino_limpo = str(destino).strip().replace("\n", "").replace("\r", "")

        msg = EmailMessage()
        msg["Subject"] = f"Solicitação de cadastro de CNPJ: {cnpj_limpo}"
        msg["From"] = "leonardo.campos@rigarr.com.br"
        msg["To"] = destino_limpo
        msg.set_content(f"""
Olá, equipe de cadastro!

O CNPJ {cnpj_limpo} não foi encontrado na base de clientes.
Solicitante: {solicitante_limpo}

Por favor, providenciem o cadastro.
        """)

        # 🔐 Usa STARTTLS (porta 587)
        with smtplib.SMTP("smtp.emailzimbraonline.com", 587) as smtp:
            smtp.starttls()
            smtp.login("leonardo.campos@rigarr.com.br", "Br@sil34@")
            smtp.send_message(msg)
        return True

    except Exception as e:
        st.error(f"Erro ao enviar e-mail: {e}")
        return False


# ==========================
# 🧠 Função responder GPT
# ==========================
prompt_template = """
Você é um assistente útil e educado. 
Responda à pergunta do usuário com base no contexto abaixo.

Pergunta atual: {pergunta}
Contexto relevante: {base_conhecimento}
Histórico da conversa: {historico}

Se não souber a resposta, responda de forma educada com base no seu conhecimento geral.
"""

def responder(pergunta, historico_chat, limite_historico=6):
    pergunta_lower = pergunta.strip().lower()
    saudacoes = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "e aí", "hello", "hi"]
    respostas_saudacao = [
        "Olá! Como posso te ajudar hoje?",
        "Oi! Tudo bem com você?",
        "E aí! Pronto para conversar?",
        "Olá! Que bom te ver aqui!"
    ]
    if pergunta_lower in saudacoes:
        return random.choice(respostas_saudacao)

    # Histórico últimos turnos
    ultimos_turnos = historico_chat[-limite_historico:]
    historico_formatado = "\n".join([
        f"Usuário: {m.content}" if isinstance(m, HumanMessage) else f"Bot: {m.content}"
        for m in ultimos_turnos
    ])

    # Base Chroma
    funcao_embedding = OpenAIEmbeddings()
    db = Chroma(persist_directory=CAMINHO_DB, embedding_function=funcao_embedding)
    resultados = db.similarity_search_with_relevance_scores(pergunta, k=3)
    resultados = [r for r in resultados if r[1] >= 0.7]
    base_conhecimento = "\n\n----\n\n".join([r[0].page_content for r in resultados]) if resultados else ""

    prompt = ChatPromptTemplate.from_template(prompt_template)
    prompt_formatado = prompt.format(
        pergunta=pergunta,
        base_conhecimento=base_conhecimento,
        historico=historico_formatado
    )

    chat = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
    resposta = chat.generate([[HumanMessage(content=prompt_formatado)]])
    return resposta.generations[0][0].text

# ==========================
# ⚙️ Sessão e histórico
# ==========================
if "historico_chat" not in st.session_state:
    st.session_state.historico_chat = []

if "acao_atual" not in st.session_state:
    st.session_state.acao_atual = None

# Exibe histórico
for msg in st.session_state.historico_chat:
    with st.chat_message("user" if isinstance(msg, HumanMessage) else "assistant"):
        st.markdown(msg.content)

# ==========================
# 🎛️ Menu de ações
# ==========================
col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("CADASTRO"):
        st.session_state.acao_atual = "cadastro"
        st.session_state.historico_chat.append(HumanMessage(content="CADASTRO"))
        with st.chat_message("assistant"):
            st.markdown("Você escolheu **CADASTRO**. Quer que eu verifique o CNPJ? (Sim/Não)")

with col2:
    if st.button("NOTA"):
        st.session_state.acao_atual = "nota"
        st.session_state.historico_chat.append(HumanMessage(content="NOTA"))
        with st.chat_message("assistant"):
            st.markdown("Você escolheu **NOTA**. Qual número da nota deseja consultar?")

with col3:
    if st.button("LIMITE DE CRÉDITO"):
        st.session_state.acao_atual = "limite_credito"
        st.session_state.historico_chat.append(HumanMessage(content="LIMITE DE CRÉDITO"))
        with st.chat_message("assistant"):
            st.markdown("Você escolheu **LIMITE DE CRÉDITO**. Por favor, informe o cliente ou CNPJ.")

with col4:
    if st.button("SAIR"):
        st.session_state.historico_chat = []
        st.session_state.acao_atual = None
        with st.chat_message("assistant"):
            st.markdown("Conversa encerrada. Até logo! 👋")
        st.rerun()

# ==========================
# 💬 Entrada do usuário
# ==========================
pergunta = st.chat_input("Digite sua mensagem...")

if pergunta:
    st.session_state.historico_chat.append(HumanMessage(content=pergunta))
    with st.chat_message("user"):
        st.markdown(pergunta)
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            if st.session_state.acao_atual == "cadastro":
                if pergunta.lower() in ["sim", "s", "yes"]:
                    st.markdown("Perfeito! Por favor, digite o CNPJ que deseja consultar.")
                    st.session_state.acao_atual = "aguardando_cnpj"
                else:
                    st.markdown("Ok, cancelando a verificação de cadastro.")
                    st.session_state.acao_atual = None

            elif st.session_state.acao_atual == "aguardando_cnpj":
                cnpj_digitado = pergunta
                st.session_state.cnpj_para_cadastro = cnpj_digitado
                resposta = consulta_cliente(cnpj_digitado)
                st.markdown(resposta)
                st.session_state.historico_chat.append(AIMessage(content=resposta))
                if "Não encontramos" in resposta:
                    st.markdown("Deseja enviar este CNPJ para o time de cadastro? (Sim/Não)")
                    st.session_state.acao_atual = "enviar_email_cadastro"

            elif st.session_state.acao_atual == "enviar_email_cadastro":
                if pergunta.lower() in ["sim", "s", "yes"]:
                    cnpj_envio = st.session_state.get("cnpj_para_cadastro", None)
                    if cnpj_envio:
                        sucesso = enviar_email_cadastro(cnpj=cnpj_envio, solicitante="Usuário ChatBot")
                        if sucesso:
                            st.markdown(f"✅ E-mail enviado com sucesso! CNPJ: {cnpj_envio}")
                        else:
                            st.markdown("❌ Falha ao enviar o e-mail. Tente novamente mais tarde.")
                    else:
                        st.markdown("❌ Não foi possível identificar o CNPJ para envio.")
                else:
                    st.markdown("Ok, não será enviado para o cadastro.")
                st.session_state.acao_atual = None





