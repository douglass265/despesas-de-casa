import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1sLKJiAJd-rGGCN1Tm5gi5SV6HHM0-v-Jhg6D1NcYaY0"
ABA_DESPESAS, ABA_RECEITAS = "Despesas", "Receitas"
ABA_CONTAS, ABA_INVEST = "Contas", "Investimentos"

CATEGORIAS_DESPESA = [
    "Alimentação (fora de casa)", "Mercado/Supermercado", "Aluguel/Condomínio",
    "Energia elétrica", "Água", "Internet", "Telefone/Celular",
    "Transporte/Combustível", "Saúde/Plano de saúde", "Farmácia",
    "Educação", "Lazer/Entretenimento", "Vestuário", "Streaming/Assinaturas",
    "Pets", "Outros",
]
CATEGORIAS_RECEITA = ["Salário", "Freelance/Extra", "Aluguel recebido",
                      "Rendimentos", "Vendas", "Presente", "Outros"]
FORMAS_PAGAMENTO = ["Dinheiro", "Pix", "Cartão de Crédito", "Cartão de Débito",
                    "Débito Automático", "Boleto", "Vale Alimentação/Refeição"]
CLASSES = ["Ações", "FIIs", "Renda Fixa", "Tesouro Direto", "CDB/LCI/LCA",
           "ETFs", "BDRs", "Criptomoedas", "Fundos", "Outros"]
MESES_PT = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

SECRETS_EXEMPLO = ('[connections.gsheets.service_account]\n'
                   'type = "service_account"\n'
                   'project_id = "galaxy-watch-assistente-334520"\n'
                   'private_key_id = "COPIE_DO_JSON"\n'
                   'private_key = "-----BEGIN PRIVATE KEY-----\\nSUA_CHAVE\\n"\n'
                   'client_email = "despesas-de-casa@galaxy-watch-assistente-334520.iam.gserviceaccount.com"\n'
                   'client_id = "COPIE_DO_JSON"\n'
                   'auth_uri = "https://accounts.google.com/o/oauth2/auth"\n'
                   'token_uri = "https://oauth2.googleapis.com/token"\n'
                   'auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"\n'
                   'client_x509_cert_url = "COPIE_DO_JSON"\n'
                   'universe_domain = "googleapis.com"')


def fmt_rs(v):
    return f"R$ {v:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def fmt_pct(v):
    return ("+" if v >= 0 else "") + f"{v:,.2f}%".replace(",", "@").replace(".", ",").replace("@", ".")


def obter_info_credenciais():
    for caminho in (("connections", "gsheets", "service_account"),
                    ("connections", "gsheets"), ("gsheets", "service_account"),
                    ("service_account",)):
        try:
            no = st.secrets
            for parte in caminho:
                no = no[parte]
            c = dict(no)
            if {"private_key", "client_email"}.issubset(c.keys()):
                return c
        except (KeyError, TypeError):
            pass
    try:
        c = dict(st.secrets)
        if {"private_key", "client_email"}.issubset(c.keys()):
            return c
    except Exception:
        pass
    return None


def caminhos_de_chaves(no, prefixo=""):
    try:
        chaves = list(no.keys())
    except Exception:
        return []
    saida = []
    for k in chaves:
        saida.append(f"{prefixo}{k}")
        saida.extend(caminhos_de_chaves(no[k], f"{prefixo}{k}."))
    return saida


INFO = obter_info_credenciais()


@st.cache_resource
def abrir_planilha():
    escopos = ["https://www.googleapis.com/auth/spreadsheets"]
    cred = Credentials.from_service_account_info(INFO, scopes=escopos)
    return gspread.authorize(cred).open_by_key(SPREADSHEET_ID)


def converter_valor(v):
    t = str(v).replace("R$", "").replace("\u00a0", "").strip()
    try:
        return float(t)
    except ValueError:
        try:
            return float(t.replace(".", "").replace(",", "."))
        except ValueError:
            return None


def converter_datas(serie):
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_datetime(serie, unit="D", origin="1899-12-30", errors="coerce")
    return pd.to_datetime(serie, dayfirst=True, errors="coerce")


def ler_aba(nome, renomear):
    valores = abrir_planilha().worksheet(nome).get_all_values()
    if len(valores) < 2:
        return pd.DataFrame(columns=list(renomear.values()))
    return pd.DataFrame(valores[1:], columns=valores[0]).rename(columns=renomear)


@st.cache_data(ttl=300)
def ler_tudo():
    desp = ler_aba(ABA_DESPESAS, {"Data": "data", "Descrição": "descricao",
                                  "Categoria": "categoria", "Valor (R$)": "valor",
                                  "Forma de Pagamento": "forma"})
    if not desp.empty:
        desp["data"] = converter_datas(desp["data"])
        desp["valor"] = desp["valor"].map(converter_valor)
        desp = desp.dropna(subset=["data", "valor"])
        desp["valor"] = desp["valor"].abs()
        desp["mes"] = desp["data"].dt.to_period("M")

    rec = ler_aba(ABA_RECEITAS, {"Data": "data", "Descrição": "descricao",
                                 "Categoria": "categoria", "Valor (R$)": "valor"})
    if not rec.empty:
        rec["data"] = converter_datas(rec["data"])
        rec["valor"] = rec["valor"].map(converter_valor)
        rec = rec.dropna(subset=["data", "valor"])
        rec["valor"] = rec["valor"].abs()
        rec["mes"] = rec["data"].dt.to_period("M")

    contas = ler_aba(ABA_CONTAS, {"Banco/Conta": "conta", "Tipo": "tipo",
                                  "Saldo Atual (R$)": "saldo"})
    if not contas.empty:
        contas = contas[contas["conta"] != ""]
        contas["saldo"] = contas["saldo"].map(converter_valor).fillna(0.0)

    inv = ler_aba(ABA_INVEST, {"Ativo": "ativo", "Classe": "classe",
                               "Quantidade": "qtd", "Preço Médio (R$)": "pm",
                               "Preço Atual (R$)": "pa",
                               "Total Investido (R$)": "investido",
                               "Valor Atual (R$)": "atual"})
    if not inv.empty:
        inv = inv[inv["ativo"] != ""]
        for c in ["qtd", "pm", "pa", "investido", "atual"]:
            inv[c] = inv[c].map(converter_valor).fillna(0.0)
    return desp, rec, contas, inv


def salvar(aba, valores, ok_msg):
    try:
        abrir_planilha().worksheet(aba).append_row(
            valores, value_input_option="USER_ENTERED")
        st.cache_data.clear()
        st.session_state["msg_ok"] = ok_msg
        st.rerun()
    except Exception as e:
        st.error(f"Não consegui salvar na planilha: {e}")


def barra_h(df, y, x, titulo):
    import plotly.express as px
    fig = px.bar(df, x=x, y=y, orientation="h", text=df[x].map(fmt_rs),
                 title=titulo)
    fig.update_layout(xaxis_title=None, yaxis_title=None,
                      margin=dict(l=10, r=10, t=40, b=10))
    fig.update_xaxes(visible=False)
    return fig
