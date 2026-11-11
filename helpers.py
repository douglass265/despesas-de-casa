import gspread
import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import date
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1sLKJiAJd-rGGCN1Tm5gi5SV6HHM0-v-Jhg6D1NcYaY0"
ABA_DESPESAS, ABA_RECEITAS = "Despesas", "Receitas"
ABA_CONTAS, ABA_INVEST = "Contas", "Investimentos"
ABA_CARTOES, ABA_COMPRAS, ABA_TRANSF = "Cartões", "Compras Cartão", "Transferências"

CATEGORIAS_DESPESA = [
    "Alimentação (fora de casa)", "Mercado/Supermercado", "Aluguel/Condomínio",
    "Energia elétrica", "Água", "Internet", "Telefone/Celular",
    "Transporte/Combustível", "Saúde/Plano de saúde", "Farmácia",
    "Educação", "Lazer/Entretenimento", "Vestuário", "Streaming/Assinaturas",
    "Pets", "Fatura do cartão", "Outros",
]
CATEGORIAS_RECEITA = ["Salário", "Freelance/Extra", "Aluguel recebido",
                      "Rendimentos", "Vendas", "Presente", "Outros"]
FORMAS_PAGAMENTO = ["Dinheiro", "Pix", "Cartão de Crédito", "Cartão de Débito",
                    "Débito Automático", "Boleto", "Vale Alimentação/Refeição"]
CLASSES = ["Ações", "FIIs", "Renda Fixa", "Tesouro Direto", "CDB/LCI/LCA",
           "ETFs", "BDRs", "Criptomoedas", "Fundos", "Outros"]
BANDEIRAS = ["Visa", "Mastercard", "Elo", "American Express", "Hipercard",
             "Outra"]
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


def _limpar_movimentos(df, colunas_finais):
    if df.empty:
        return df
    df["data"] = converter_datas(df["data"])
    df["valor"] = df["valor"].map(converter_valor)
    df = df.dropna(subset=["data", "valor"])
    df["valor"] = df["valor"].abs()
    df["mes"] = df["data"].dt.to_period("M")
    df = df.sort_values("data", ascending=False).reset_index(drop=True)
    df["_linha"] = df.index + 2
    return df[colunas_finais + ["mes", "_linha"]]


def _proximo_fechamento(fech, a_partir_de):
    """Primeiro dia 'fech' do mês estritamente após a data informada."""
    y, m = a_partir_de.year, a_partir_de.month
    for i in range(1, 15):
        mm = m + i
        yy = y + (mm - 1) // 12
        mm = (mm - 1) % 12 + 1
        try:
            return date(yy, mm, fech)
        except ValueError:
            continue
    return None


def _fechamento_anterior(fech, data_fech):
    if data_fech.month > 1:
        y, m = data_fech.year, data_fech.month - 1
    else:
        y, m = data_fech.year - 1, 12
    f = fech
    while f >= 28:
        try:
            return date(y, m, f)
        except ValueError:
            f -= 1
    return None


def _vencimento_da_fatura(venc, data_fech):
    if venc > data_fech.day:
        return date(data_fech.year, data_fech.month, venc)
    if data_fech.month < 12:
        y, m = data_fech.year, data_fech.month + 1
    else:
        y, m = data_fech.year + 1, 1
    f = venc
    while f >= 28:
        try:
            return date(y, m, f)
        except ValueError:
            f -= 1
    return data_fech


def calcular_faturas(cartoes, compras):
    """Calcula as próximas faturas de cada cartão (inclui parcelas futuras)."""
    hoje = date.today()
    resultado = []
    if cartoes.empty:
        return resultado
    for _, card in cartoes.iterrows():
        nome = card["cartao"]
        fech_v = converter_valor(card["fechamento"])
        venc_v = converter_valor(card["vencimento"])
        if fech_v is None or venc_v is None:
            continue
        fech, venc = int(fech_v), int(venc_v)
        if not (1 <= fech <= 31) or not (1 <= venc <= 31):
            continue
        limite = converter_valor(card["limite"]) or 0.0
        do_cartao = (compras[compras["cartao"] == nome]
                     if not compras.empty else pd.DataFrame())
        fech_futuros = []
        base = hoje
        for _ in range(6):
            prox = _proximo_fechamento(fech, base)
            if prox is None:
                break
            fech_futuros.append(prox)
            base = prox
        faturas = []
        for F in fech_futuros:
            F_ant = _fechamento_anterior(fech, F)
            total = 0.0
            for _, c in do_cartao.iterrows():
                dcomp = (c["data"].date() if hasattr(c["data"], "date")
                         else c["data"])
                npar = int(c["parcelas"]) if c["parcelas"] else 1
                if npar <= 1:
                    if F_ant and (F_ant < dcomp <= F):
                        total += float(c["valor"])
                else:
                    primeira = _proximo_fechamento(fech, dcomp)
                    if primeira is None:
                        continue
                    for k in range(1, npar + 1):
                        mm = primeira.month + (k - 1)
                        yy = primeira.year + (mm - 1) // 12
                        mm = (mm - 1) % 12 + 1
                        try:
                            fk = date(yy, mm, fech)
                        except ValueError:
                            continue
                        if fk == F:
                            total += float(c["valor"]) / npar
            faturas.append({"fechamento": F,
                            "vencimento": _vencimento_da_fatura(venc, F),
                            "total": round(total, 2)})
        comprometido = round(sum(f["total"] for f in faturas), 2)
        resultado.append({
            "cartao": nome,
            "bandeira": card["bandeira"] if "bandeira" in card else "",
            "fechamento": fech, "vencimento": venc, "limite": limite,
            "faturas": faturas, "comprometido": comprometido,
            "disponivel": round(max(limite - comprometido, 0.0), 2)})
    return resultado


@st.cache_data(ttl=300)
def ler_tudo():
    desp = ler_aba(ABA_DESPESAS, {"Data": "data", "Descrição": "descricao",
                                  "Categoria": "categoria", "Valor (R$)": "valor",
                                  "Forma de Pagamento": "forma", "Conta": "conta"})
    desp = _limpar_movimentos(desp, ["data", "descricao", "categoria",
                                     "valor", "forma", "conta"])

    rec = ler_aba(ABA_RECEITAS, {"Data": "data", "Descrição": "descricao",
                                 "Categoria": "categoria", "Valor (R$)": "valor",
                                 "Conta (recebido em)": "conta"})
    rec = _limpar_movimentos(rec, ["data", "descricao", "categoria",
                                   "valor", "conta"])

    transf = ler_aba(ABA_TRANSF, {"Data": "data", "Descrição": "descricao",
                                  "Da Conta": "da_conta",
                                  "Para a Conta": "para_conta",
                                  "Valor (R$)": "valor"})
    if not transf.empty:
        transf["data"] = converter_datas(transf["data"])
        transf["valor"] = transf["valor"].map(converter_valor)
        transf = transf.dropna(subset=["data", "valor"])
        transf["valor"] = transf["valor"].abs()
        transf = transf.sort_values("data", ascending=False).reset_index(drop=True)
        transf["_linha"] = transf.index + 2

    contas = ler_aba(ABA_CONTAS, {"Banco/Conta": "conta", "Tipo": "tipo",
                                  "Saldo Inicial (R$)": "saldo_inicial"})
    if not contas.empty:
        contas = contas[contas["conta"] != ""]
        contas["saldo_inicial"] = (contas["saldo_inicial"]
                                   .map(converter_valor).fillna(0.0))
        contas = contas.reset_index(drop=True)
        contas["_linha"] = contas.index + 2
        saidas = (desp.groupby("conta")["valor"].sum() if not desp.empty
                  else pd.Series(dtype=float))
        entradas = (rec.groupby("conta")["valor"].sum() if not rec.empty
                    else pd.Series(dtype=float))
        t_env = (transf.groupby("da_conta")["valor"].sum() if not transf.empty
                 else pd.Series(dtype=float))
        t_rec = (transf.groupby("para_conta")["valor"].sum() if not transf.empty
                 else pd.Series(dtype=float))

        def _saldo(row):
            c = row["conta"]
            return (float(row["saldo_inicial"])
                    + float(entradas.get(c, 0.0)) - float(saidas.get(c, 0.0))
                    - float(t_env.get(c, 0.0)) + float(t_rec.get(c, 0.0)))

        contas["saldo"] = contas.apply(_saldo, axis=1)

    cartoes = ler_aba(ABA_CARTOES, {"Cartão (apelido)": "cartao",
                                    "Bandeira/Emissor": "bandeira",
                                    "Dia do Fechamento": "fechamento",
                                    "Dia do Vencimento": "vencimento",
                                    "Limite (R$)": "limite",
                                    "Conta de Pagamento": "conta_pag"})
    if not cartoes.empty:
        cartoes = cartoes[cartoes["cartao"] != ""]
        cartoes["fechamento"] = (cartoes["fechamento"]
                                 .map(converter_valor).fillna(0))
        cartoes["vencimento"] = (cartoes["vencimento"]
                                 .map(converter_valor).fillna(0))
        cartoes["limite"] = cartoes["limite"].map(converter_valor).fillna(0.0)
        cartoes = cartoes.reset_index(drop=True)
        cartoes["_linha"] = cartoes.index + 2

    compras = ler_aba(ABA_COMPRAS, {"Data da Compra": "data",
                                    "Descrição": "descricao", "Cartão": "cartao",
                                    "Categoria": "categoria",
                                    "Valor Total (R$)": "valor",
                                    "Parcelas": "parcelas",
                                    "Compra Parcelada?": "parcelada"})
    if not compras.empty:
        compras["data"] = converter_datas(compras["data"])
        compras["valor"] = compras["valor"].map(converter_valor)
        compras["parcelas"] = compras["parcelas"].map(converter_valor).fillna(1)
        compras = compras.dropna(subset=["data", "valor"])
        compras["valor"] = compras["valor"].abs()
        compras = compras.sort_values("data", ascending=False).reset_index(drop=True)
        compras["_linha"] = compras.index + 2

    inv = ler_aba(ABA_INVEST, {"Ativo": "ativo", "Classe": "classe",
                               "Quantidade": "qtd", "Preço Médio (R$)": "pm",
                               "Preço Atual (R$)": "pa",
                               "Total Investido (R$)": "investido",
                               "Valor Atual (R$)": "atual"})
    if not inv.empty:
        inv = inv[inv["ativo"] != ""]
        for c in ["qtd", "pm", "pa", "investido", "atual"]:
            inv[c] = inv[c].map(converter_valor).fillna(0.0)
        inv = inv.reset_index(drop=True)
        inv["_linha"] = inv.index + 2
    return desp, rec, contas, inv, transf, cartoes, compras


def salvar(aba, valores, ok_msg):
    try:
        abrir_planilha().worksheet(aba).append_row(
            valores, value_input_option="USER_ENTERED")
        st.cache_data.clear()
        st.session_state["msg_ok"] = ok_msg
        st.rerun()
    except Exception as e:
        st.error(f"Não consegui salvar na planilha: {e}")

def excluir_linha(aba, numero_linha, ok_msg):
    try:
        abrir_planilha().worksheet(aba).delete_rows(numero_linha)
        st.cache_data.clear()
        st.session_state["msg_ok"] = ok_msg
        st.rerun()
    except Exception as e:
        st.error(f"Não consegui excluir o lançamento: {e}")


def barra_h(df, y, x, titulo):
    fig = px.bar(df, x=x, y=y, orientation="h", text=df[x].map(fmt_rs),
                 title=titulo)
    fig.update_layout(xaxis_title=None, yaxis_title=None,
                      margin=dict(l=10, r=10, t=40, b=10))
    fig.update_xaxes(visible=False)
    return fig
