import gspread
import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import date
from google.oauth2.service_account import Credentials

# ---------- Configuração ----------
st.set_page_config(page_title="Finanças da Casa", page_icon="🏠", layout="wide")

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

SECRETS_EXEMPLO = '''[connections.gsheets.service_account]
type = "service_account"
project_id = "galaxy-watch-assistente-334520"
private_key_id = "COPIE_DO_JSON"
private_key = "-----BEGIN PRIVATE KEY-----\\nCOPIE_A_CONTEUDO_DA_CHAVE_AQUI\\n-----END PRIVATE KEY-----\\n"
client_email = "despesas-de-casa@galaxy-watch-assistente-334520.iam.gserviceaccount.com"
client_id = "COPIE_DO_JSON"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "COPIE_DO_JSON"
universe_domain = "googleapis.com"'''


def fmt_rs(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def fmt_pct(v: float) -> str:
    sinal = "+" if v >= 0 else ""
    return f"{sinal}{v:,.2f}%".replace(",", "@").replace(".", ",").replace("@", ".")


# ---------- Credenciais ----------
def caminhos_de_chaves(no, prefixo=""):
    resultado = []
    try:
        chaves = list(no.keys())
    except Exception:
        return resultado
    for k in chaves:
        resultado.append(f"{prefixo}{k}")
        resultado.extend(caminhos_de_chaves(no[k], f"{prefixo}{k}."))
    return resultado


def obter_info_credenciais():
    candidatos = []
    for caminho in (("connections", "gsheets", "service_account"),
                    ("connections", "gsheets"),
                    ("gsheets", "service_account"),
                    ("service_account",)):
        try:
            no = st.secrets
            for parte in caminho:
                no = no[parte]
            candidatos.append(dict(no))
        except (KeyError, TypeError):
            pass
    try:
        candidatos.append(dict(st.secrets))
    except (KeyError, TypeError):
        pass
    for c in candidatos:
        if {"private_key", "client_email"}.issubset(c.keys()):
            return c
    return None


INFO_CREDENCIAIS = obter_info_credenciais()

if INFO_CREDENCIAIS is None:
    st.title("🏠 Finanças da Casa")
    st.error("Não encontrei as credenciais do Google no Secrets deste app.")
    estrutura = caminhos_de_chaves(st.secrets)
    st.caption("Estrutura detectada no Secrets (somente nomes): "
               + (", ".join(estrutura) if estrutura else "nenhuma"))
    st.code(SECRETS_EXEMPLO, language="toml")
    st.stop()


@st.cache_resource
def abrir_planilha():
    escopos = ["https://www.googleapis.com/auth/spreadsheets"]
    credenciais = Credentials.from_service_account_info(
        INFO_CREDENCIAIS, scopes=escopos)
    return gspread.authorize(credenciais).open_by_key(SPREADSHEET_ID)


def converter_valor(v):
    t = str(v).replace("R$", "").replace("\u00a0", "").strip()
    try:
        return float(t)
    except ValueError:
        try:
            return float(t.replace(".", "").replace(",", "."))
        except ValueError:
            return None


def converter_qtd(v):
    x = converter_valor(v)
    return 0.0 if x is None else x


def converter_data_serie(serie):
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_datetime(serie, unit="D", origin="1899-12-30", errors="coerce")
    return pd.to_datetime(serie, dayfirst=True, errors="coerce")


def _ler_aba(nome_aba, nomes):
    valores = abrir_planilha().worksheet(nome_aba).get_all_values()
    if len(valores) < 2:
        return pd.DataFrame(columns=nomes)
    df = pd.DataFrame(valores[1:], columns=valores[0]).rename(columns=nomes)
    return df


@st.cache_data(ttl=300)
def ler_despesas() -> pd.DataFrame:
    df = _ler_aba(ABA_DESPESAS, {"Data": "data", "Descrição": "descricao",
                                 "Categoria": "categoria", "Valor (R$)": "valor",
                                 "Forma de Pagamento": "forma"})
    if df.empty:
        return df
    df["data"] = converter_data_serie(df["data"])
    df["valor"] = df["valor"].map(converter_valor)
    df = df.dropna(subset=["data", "valor"])
    df["valor"] = df["valor"].abs()
    df["mes"] = df["data"].dt.to_period("M")
    return df


@st.cache_data(ttl=300)
def ler_receitas() -> pd.DataFrame:
    df = _ler_aba(ABA_RECEITAS, {"Data": "data", "Descrição": "descricao",
                                 "Categoria": "categoria", "Valor (R$)": "valor"})
    if df.empty:
        return df
    df["data"] = converter_data_serie(df["data"])
    df["valor"] = df["valor"].map(converter_valor)
    df = df.dropna(subset=["data", "valor"])
    df["valor"] = df["valor"].abs()
    df["mes"] = df["data"].dt.to_period("M")
    return df


@st.cache_data(ttl=300)
def ler_contas() -> pd.DataFrame:
    df = _ler_aba(ABA_CONTAS, {"Banco/Conta": "conta", "Tipo": "tipo",
                               "Saldo Atual (R$)": "saldo"})
    if df.empty:
        return df
    df = df[df["conta"] != ""]
    df["saldo"] = df["saldo"].map(converter_valor).fillna(0.0)
    return df


@st.cache_data(ttl=300)
def ler_investimentos() -> pd.DataFrame:
    df = _ler_aba(ABA_INVEST, {"Ativo": "ativo", "Classe": "classe",
                               "Quantidade": "qtd", "Preço Médio (R$)": "pm",
                               "Preço Atual (R$)": "pa",
                               "Total Investido (R$)": "investido",
                               "Valor Atual (R$)": "atual"})
    if df.empty:
        return df
    df = df[df["ativo"] != ""]
    for c in ["qtd", "pm", "pa", "investido", "atual"]:
        df[c] = df[c].map(converter_valor).fillna(0.0)
    return df


despesas, receitas = ler_despesas(), ler_receitas()
contas, investimentos = ler_contas(), ler_investimentos()

# ---------- Barra lateral ----------
st.sidebar.title("🏠 Finanças da Casa")
pagina = st.sidebar.radio("Navegar", ["📊 Painel", "➕ Lançamentos"])
if st.sidebar.button("🔄 Atualizar dados", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# ================== PÁGINA PAINEL ==================
if pagina == "📊 Painel":
    st.title("📊 Painel geral")

    hoje = pd.Period(date.today(), freq="M")
    desp_mes = despesas[despesas["mes"] == hoje]["valor"].sum() if not despesas.empty else 0.0
    rec_mes = receitas[receitas["mes"] == hoje]["valor"].sum() if not receitas.empty else 0.0
    total_contas = contas["saldo"].sum() if not contas.empty else 0.0
    total_investido = investimentos["investido"].sum() if not investimentos.empty else 0.0
    valor_atual = investimentos["atual"].sum() if not investimentos.empty else 0.0
    rentab = ((valor_atual - total_investido) / total_investido * 100
              if total_investido > 0 else 0.0)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"Total em contas", fmt_rs(total_contas))
    m2.metric("Total investido", fmt_rs(total_investido))
    m3.metric("Carteira hoje", fmt_rs(valor_atual))
    m4.metric("Rentabilidade", fmt_pct(rentab))
    p1, p2 = st.columns(2)
    p1.metric("💼 Patrimônio total (contas + carteira)",
              fmt_rs(total_contas + valor_atual))
    p2.metric(f"Saldo de {MESES_PT[hoje.month - 1]} (receitas − despesas)",
              fmt_rs(rec_mes - desp_mes))

    st.divider()

    # Carteira estilo Investidor10
    st.subheader("📈 Minha carteira")
    if investimentos.empty or valor_atual == 0:
        st.info("Nenhum investimento com valor ainda. Lance pelo menu ➕ Lançamentos.")
    else:
        c1, c2 = st.columns([2, 3])
        with c1:
            dist = (investimentos.groupby("classe", as_index=False)["atual"]
                    .sum().query("atual > 0"))
            fig = px.pie(dist, names="classe", values="atual", hole=0.55,
                         title="Distribuição por classe")
            fig.update_layout(margin=dict(l=10, r=10, t=40, b=10),
                              legend_font_size=11)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            tb = investimentos.copy()
            tb["variacao"] = ((tb["atual"] - tb["investido"]) / tb["investido"] * 100
                              ).where(tb["investido"] > 0, 0.0)
            tb = tb[["ativo", "classe", "qtd", "pm", "pa", "investido",
                     "atual", "variacao"]].sort_values("atual", ascending=False)
            st.dataframe(
                tb, use_container_width=True, hide_index=True,
                column_config={
                    "ativo": "Ativo", "classe": "Classe",
                    "qtd": st.column_config.NumberColumn("Qtd", format="%.4f"),
                    "pm": st.column_config.NumberColumn("Preço médio", format="R$ %.2f"),
                    "pa": st.column_config.NumberColumn("Preço atual", format="R$ %.2f"),
                    "investido": st.column_config.NumberColumn("Investido", format="R$ %.2f"),
                    "atual": st.column_config.NumberColumn("Valor atual", format="R$ %.2f"),
                    "variacao": st.column_config.NumberColumn("Variação", format="%.2f%%"),
                })

    st.divider()

    # Contas
    st.subheader("🏦 Minhas contas")
    if contas.empty:
        st.info("Nenhuma conta cadastrada ainda.")
    else:
        cc1, cc2 = st.columns([3, 2])
        with cc1:
            fig_c = px.bar(contas.sort_values("saldo"), x="saldo", y="conta",
                           orientation="h", text=contas.sort_values("saldo")["saldo"].map(fmt_rs),
                           title="Saldo por conta")
            fig_c.update_layout(xaxis_title=None, yaxis_title=None,
                                margin=dict(l=10, r=10, t=40, b=10))
            fig_c.update_xaxes(visible=False)
            st.plotly_chart(fig_c, use_container_width=True)
        with cc2:
            st.dataframe(
                contas[["conta", "tipo", "saldo"]], use_container_width=True,
                hide_index=True,
                column_config={
                    "conta": "Conta", "tipo": "Tipo",
                    "saldo": st.column_config.NumberColumn("Saldo", format="R$ %.2f")})

    st.divider()

    # Filtro de mês + despesas x receitas
    st.subheader("💵 Despesas × Receitas")
    meses = sorted(set(list(despesas["mes"].unique()) if not despesas.empty else []
                       + list(receitas["mes"].unique()) if not receitas.empty else []),
                   reverse=True)
    opcoes = {"Todos os meses": None}
    for m in meses:
        opcoes[f"{MESES_PT[m.month - 1]} {m.year}"] = m
    mes_label = st.selectbox("Período", list(opcoes.keys()), index=0)
    mes_sel = opcoes[mes_label]

    d_f = despesas if mes_sel is None else despesas[despesas["mes"] == mes_sel]
    r_f = receitas if mes_sel is None else receitas[receitas["mes"] == mes_sel]

    evo_d = (despesas.groupby("mes", as_index=False)["valor"].sum()
             .rename(columns={"valor": "Despesas"}) if not despesas.empty
             else pd.DataFrame(columns=["mes", "Despesas"]))
    evo_r = (receitas.groupby("mes", as_index=False)["valor"].sum()
             .rename(columns={"valor": "Receitas"}) if not receitas.empty
             else pd.DataFrame(columns=["mes", "Receitas"]))
    evo = pd.merge(evo_d, evo_r, on="mes", how="outer").sort_values("mes")
    if not evo.empty:
        evo["rotulo"] = evo["mes"].apply(
            lambda p: f"{MESES_PT[p.month - 1]}/{str(p.year)[2:]}")
        evo_melt = evo.melt(id_vars="rotulo", value_vars=["Despesas", "Receitas"],
                            var_name="Tipo", value_name="valor")
        fig_e = px.bar(evo_melt, x="rotulo", y="valor", color="Tipo", barmode="group",
                       color_discrete_map={"Despesas": "#d93025", "Receitas": "#0f9d58"},
                       title="Evolução mês a mês")
        fig_e.update_layout(yaxis_title=None, xaxis_title=None,
                            margin=dict(l=10, r=10, t=40, b=10),
                            legend_font_size=11)
        st.plotly_chart(fig_e, use_container_width=True)

    g1, g2 = st.columns(2)
    with g1:
        if not d_f.empty:
            gc = (d_f.groupby("categoria", as_index=False)["valor"].sum()
                  .sort_values("valor"))
            fig_gc = px.bar(gc, x="valor", y="categoria", orientation="h",
                            text=gc["valor"].map(fmt_rs),
                            title=f"Despesas por categoria — {mes_label}")
            fig_gc.update_layout(xaxis_title=None, yaxis_title=None,
                                 margin=dict(l=10, r=10, t=40, b=10))
            fig_gc.update_xaxes(visible=False)
            st.plotly_chart(fig_gc, use_container_width=True)
    with g2:
        if not r_f.empty:
           
