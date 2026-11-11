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


@st.cache_data(ttl=3600)
def cdi_do_periodo(dias):
    """CDI acumulado no período (pro rata die), igual aos bancos.
    Tenta a API do Banco Central de duas formas antes de desistir."""
    fim = date.today()
    ini = fim - timedelta(days=dias)
    urls = [
        (f"https://api.bcb.gov.br/dados/serie/bcdata.sgp.11/dados"
         f"?formato=json&dataInicial={ini.strftime('%d/%m/%Y')}"
         f"&dataFinal={fim.strftime('%d/%m/%Y')}"),
        (f"https://api.bcb.gov.br/dados/serie/bcdata.sgp.11/dados"
         f"/ultimos/500?formato=json"),
    ]
    for u in urls:
        try:
            dados = requests.get(u, timeout=15).json()
            if not dados:
                continue
            acum = 1.0
            for d in dados:
                if "data" in d:
                    dd = pd.to_datetime(d["data"], dayfirst=True).date()
                    if dd < ini or dd > fim:
                        continue
                acum *= 1.0 + float(str(d["valor"]).replace(",", ".")) / 100.0
            return (acum - 1.0) * 100.0
        except Exception:
            continue
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

@st.cache_data(ttl=300)
def ler_dividendos():
    d = ler_aba(ABA_DIVID, {"Data": "data", "Ativo": "ativo",
                            "Valor (R$)": "valor",
                            "Conta de Destino": "conta"})
    if d.empty:
        return d
    d["data"] = converter_datas(d["data"])
    d["valor"] = d["valor"].map(converter_valor)
    d = d.dropna(subset=["data", "valor"])
    d["valor"] = d["valor"].abs()
    d["mes"] = d["data"].dt.to_period("M")
    d = d.sort_values("data", ascending=False).reset_index(drop=True)
    d["_linha"] = d.index + 2
    return d[["data", "ativo", "valor", "conta", "mes", "_linha"]]


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
                               "Valor Atual (R$)": "atual",
                               "% do CDI": "pct_cdi",
                               "Data da Aplicação": "data_apl",
                               "Conta de Origem": "conta_orig"})
    if not inv.empty:
        inv = inv[inv["ativo"] != ""]
        for c in ["qtd", "pm", "pa", "investido", "atual", "pct_cdi"]:
            inv[c] = inv[c].map(converter_valor).fillna(0.0)
        inv["data_apl"] = converter_datas(inv["data_apl"])
        inv = inv.reset_index(drop=True)
        inv["_linha"] = inv.index + 2
        dol = cotacao_dolar()
        for i, r in inv.iterrows():
            try:
                if r["classe"] in CLASSES_MOEDA_USD and dol:
                    inv.at[i, "investido"] = round(r["qtd"] * r["pm"] * dol, 2)
                    inv.at[i, "atual"] = round(r["qtd"] * r["pa"] * dol, 2)
                elif (r["classe"] in CLASSES_RENDA_FIXA and r["pct_cdi"] > 0
                      and not pd.isna(r["data_apl"])):
                    v = valor_cdb_hoje(r["investido"], r["pct_cdi"],
                                       r["data_apl"])
                    if v:
                        inv.at[i, "atual"] = round(v, 2)
            except Exception:
                pass
        if not contas.empty and "conta_orig" in inv.columns:
            inv_saidas = inv.groupby("conta_orig")["investido"].sum()
            contas["saldo"] = contas.apply(
                lambda r: r["saldo"] - float(inv_saidas.get(r["conta"], 0.0)),
                axis=1)
        grupos = []
        for (ativo, classe), g in inv.groupby(["ativo", "classe"],
                                              sort=False):
            qtd_t = float(g["qtd"].sum())
            inv_t = round(float(g["investido"].sum()), 2)
            at_t = round(float(g["atual"].sum()), 2)
            pm_t = (round(float((g["qtd"] * g["pm"]).sum() / qtd_t), 2)
                    if qtd_t > 0 else round(float(g["pm"].mean()), 2))
            if classe in CLASSES_RENDA_FIXA and qtd_t > 0:
                pa_t = round(at_t / qtd_t, 2)
            elif qtd_t > 0:
                pa_t = round(float((g["qtd"] * g["pa"]).sum() / qtd_t), 2)
            else:
                pa_t = round(float(g["pa"].mean()), 2)
            com_cdi = g.loc[g["pct_cdi"] > 0, "pct_cdi"]
            pct = float(com_cdi.iloc[0]) if not com_cdi.empty else 0.0
            orig = ", ".join(sorted({str(x) for x in g["conta_orig"]
                                     if str(x) and str(x) not in ("nan", "None")}))
            grupos.append({
                "ativo": ativo, "classe": classe, "qtd": round(qtd_t, 4),
                "pm": pm_t, "pa": pa_t, "investido": inv_t, "atual": at_t,
                "pct_cdi": pct, "data_apl": g["data_apl"].min(),
                "conta_orig": orig,
                "_linha": int(g["_linha"].iloc[0])})
        inv = pd.DataFrame(grupos)
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
