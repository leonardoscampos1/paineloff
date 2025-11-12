import requests
import sqlite3
import pandas as pd
import tempfile
import os
import re

URL_DB = "https://hbox.houseti.com.br/s/D2nXxuYkkeuV6r3/download"

def normalizar_cnpj(cnpj):
    return re.sub(r'\D', '', str(cnpj))

def consulta_cliente(cnpj):
    tmp_path = None
    conn = None
    try:
        # 1) Baixa o .db
        r = requests.get(URL_DB, timeout=30)
        r.raise_for_status()

        # 2) Grava em arquivo temporário (precisa ser um caminho no disco)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp.write(r.content)
            tmp_path = tmp.name

        # 3) Conecta ao SQLite usando o arquivo temporário
        conn = sqlite3.connect(tmp_path)

        # 4) Lê a tabela e normaliza colunas
        tabela_cliente = pd.read_sql("SELECT * FROM PCCLIENT", conn)
        tabela_cliente.columns = tabela_cliente.columns.str.upper()

        # 5) Normaliza CNPJ e faz busca
        cnpj_norm = normalizar_cnpj(cnpj)
        if "CGCENT" not in tabela_cliente.columns:
            return "❌ A coluna 'CGCENT' não existe na tabela PCCLIENT."

        tabela_cliente["CGCENT"] = tabela_cliente["CGCENT"].apply(normalizar_cnpj)
        resultado = tabela_cliente[tabela_cliente["CGCENT"] == cnpj_norm]

        if not resultado.empty:
            codcli = resultado.iloc[0].get("CODCLI", "")
            cliente = resultado.iloc[0].get("CLIENTE", "")
            cgc = resultado.iloc[0].get("CGCENT", "")
            return f"Sim — CNPJ {cgc} cadastrado com código {codcli} ({cliente})."
        else:
            return f"Não encontramos o CNPJ {cnpj} na base de clientes."

    except requests.RequestException as e:
        return f"❌ Erro ao baixar o banco: {e}"
    except pd.io.sql.DatabaseError as e:
        return f"❌ Erro ao ler a tabela no banco: {e}"
    except Exception as e:
        return f"❌ Erro ao consultar o banco: {e}"
    finally:
        # fecha conexão e remove arquivo temporário
        try:
            if conn:
                conn.close()
        except Exception:
            pass
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
