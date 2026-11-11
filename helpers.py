import gspread
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from datetime import date, timedelta
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1sLKJiAJd-rGGCN1Tm5gi5SV6HHM0-v-Jhg6D1NcYaY0"
ABA_DESPESAS, ABA_RECEITAS = "Despesas", "Receitas"
ABA_CONTAS, ABA_INVEST = "Contas", "Investimentos"
ABA_CARTOES, ABA_COMPRAS, ABA_TRANSF = "Cartões", "Compras Cartão", "Transferências"
ABA_DIVID = "Dividendos"

CATEGORIAS_DESPESA = [
    "Alimentação (fora de casa)", "Mercado/Supermercado", "Aluguel/Condomínio",
    "Energia elétrica", "Água", "Internet", "Telefone/Celular",
    "Transporte/Combustível", "Saúde/Plano de saúde", "Farmácia",
    "Educação", "Lazer/Entretenimento", "Vestuário", "Streaming/Assinaturas",
    "Pets", "Fatura do cartão", "Outros",
]
CATEGORIAS_RECEITA = ["Salário", "Freelance/Extra", "Aluguel recebido",
                      "Rendimentos", "Dividendos", "Vendas", "Presente", "Outros"]
FORMAS_PAGAMENTO = ["Dinheiro", "Pix", "Cartão de Crédito", "Cartão de Débito",
                    "Débito Automático", "Boleto", "Vale Alimentação/Refeição"]
CLASSES = ["Ações", "FIIs", "ETFs", "ETFs Internacionais", "Stocks",
           "Renda Fixa", "Tesouro Direto", "CDB/LCI/LCA", "BDRs",
           "Criptomoedas", "Fundos", "Outros"]
CLASSES_MOEDA_USD = ["ETFs Internacionais", "Stocks"]
CLASSES_RENDA_FIXA = ["Renda Fixa", "Tesouro Direto", "CDB/LCI/LCA"]
BANDEIRAS = ["Visa", "Mastercard", "Elo", "American Express", "Hipercard",
             "Outra"]
MESES_PT = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

SECRETS_EXEMPLO = ('[connections.gsheets.service_account]\n'
                   'type = "service_account"\n'
                   'project_id = "seu-projeto"\n'
                   'private_key = "-----BEGIN PRIVATE KEY-----\\nSUA_CHAVE\\n"\n'
                   'client_email = "conta@seu-projeto.iam.gserviceaccount.com"')


def fmt_rs(v):
    return f"R$ {v:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def fmt_pct(v):
    return ("+" if v >= 0 else "") + f"{v:,.2f}%".replace(",", "@").replace(".", ",").replace("@", ".")


@st.cache_data(ttl=21600)
def cdi_do_periodo(dias):
    """CDI acumulado no período (pro rata die), igual aos bancos."""
    fim = date.today()
    ini = fim - timedelta(days=dias)
    u = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgp.11/dados"
         f"?formato=json&dataInicial={ini.strftime('%d/%m/%Y')}"
         f"&dataFinal={fim.strftime('%d/%m/%Y')}")
    try:
        dados = requests.get(u, timeout=15).json()
        acum = 1.0
        for d in dados:
            acum *= 1.0 + float(str(d["valor"]).replace(",", ".")) / 100.0
        return (acum - 1.0) * 100.0
    except Exception:
        return None


@st.cache_data(ttl=3600)
def cotacao_dolar():
    try:
        r = requests.get("https://economia.awesomeapi.com.br/last/USD-BRL",
                         timeout=15)
        return float(r.json()["USDBRL"]["bid"])
    except Exception:
        return None


def valor_cdb_hoje(valor_aplicado, pct_cdi, data_apl):
    """Valor estimado hoje de um CDB a % do CDI, pro rata die."""
    if valor_aplicado is None or valor_aplicado <= 0:
        return None
    if pd.isna(data_apl):
        return None
    dias = max((date.today() - data_apl.date()).days, 0)
    if dias < 1:
        return None
    cdi = cdi_do_periodo(dias)
    if cdi is None:
        return None
    return valor_aplicado * (1.0 + (cdi / 100.0) * (pct_cdi / 100.0))


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


def rentabilidade_total_row(r, div_ativo):
    """Variação de preço + dividendos recebidos (estilo Investidor10)."""
    inv = float(r["investido"]) if r["investido"] else 0.0
    if inv <= 0:
        return 0.0
    var = (float(r["atual"]) - inv) / inv * 100.0
    div = float(div_ativo) if div_ativo else 0.0
    return var + (div / inv) * 100.0
