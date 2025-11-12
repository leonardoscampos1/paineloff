import pandas as pd
import oracledb
from sqlalchemy import create_engine
import sqlite3
import traceback
import schedule
import time
from datetime import datetime

# ==========================
# ⚙️ CONFIGURAÇÕES
# ==========================
ARQUIVO_SQLITE = r"C:\Hbox\Banco de Dados\banco_local.db"

USER = "vpn"
PASSWORD = "vpn2320vpn"
DSN = "crc_oci"

TABELAS = {
    "PCMOV": """
        SELECT CODFILIAL, DTMOV, CODOPER, CODCLI, CODUSUR, CODPROD, PUNIT, QT, CODFORNEC, NUMNOTA, NUMPED, CODPLPAG, NUMPED      
        FROM crc.PCMOV
    """,
    "PCUSUARI": "SELECT CODUSUR, NOME FROM crc.PCUSUARI",
    "PCPRODUT": "SELECT CODPROD, DESCRICAO, CODFORNEC FROM crc.PCPRODUT",
    "PCFORNEC": "SELECT CODFORNEC, FORNECEDOR FROM crc.PCFORNEC",
    "PCCLIENT": "SELECT CODCLI, CGCENT, CLIENTE, CODUSUR1, CODUSUR2, BLOQUEIO, LIMCRED FROM crc.PCCLIENT"
}

# ==========================
# 🔄 FUNÇÃO PRINCIPAL
# ==========================
def clonar_banco():
    print(f"\n🚀 Iniciando rotina de clonagem às {datetime.now().strftime('%H:%M:%S')}")

    try:
        # Inicializa cliente Oracle se necessário
        try:
            if not getattr(oracledb, "thin_mode", False):
                oracledb.init_oracle_client(config_dir=r"C:\instantclient\network\admin")
        except Exception as e:
            print("⚠️ Erro ao iniciar cliente Oracle:", e)

        engine = create_engine(f'oracle+oracledb://{USER}:{PASSWORD}@{DSN}')
        with engine.connect() as conn_oracle:
            print("✅ Conectado ao Oracle")

            with sqlite3.connect(ARQUIVO_SQLITE) as conn_sqlite:
                cursor = conn_sqlite.cursor()

                for nome_tabela, query in TABELAS.items():
                    try:
                        print(f"\n📤 Lendo tabela {nome_tabela}...")
                        df = pd.read_sql(query, con=conn_oracle)

                        # Verifica se a tabela já existe
                        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{nome_tabela}'")
                        tabela_existe = cursor.fetchone() is not None

                        if not tabela_existe:
                            print(f"💾 Criando tabela {nome_tabela}...")
                            df.to_sql(nome_tabela, conn_sqlite, index=False)
                        else:
                            print(f"🔄 Atualizando {nome_tabela}...")
                            df.to_sql(nome_tabela, conn_sqlite, index=False, if_exists="replace")

                        print(f"✅ {nome_tabela} atualizada com {len(df)} registros")
                    except Exception as e:
                        print(f"❌ Erro ao processar {nome_tabela}: {e}")

        print(f"🏁 Clone finalizado às {datetime.now().strftime('%H:%M:%S')}")

    except Exception:
        print("❌ Erro geral na clonagem:")
        traceback.print_exc()

# ==========================
# 🕒 AGENDAMENTO
# ==========================
schedule.every(5).minutes.do(clonar_banco)

print("🗓️ Rotina agendada para rodar a cada 5 minutos...\n")
clonar_banco()  # Executa imediatamente na inicialização

# Loop contínuo
while True:
    schedule.run_pending()
    time.sleep(10)
