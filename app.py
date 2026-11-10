import gspread
import pandas as pd
import plotly.express as px
import streamlit as st
from google.oauth2.service_account import Credentials

# ---------- Configuração ----------
st.set_page_config(page_title="Despesas de Casa", page_icon="🏠", layout="wide")

SPREADSHEET_ID = "1sLKJiAJd-rGGCN1Tm5gi5SV6HHM0-v-Jhg6D1NcYaY0"
ABA_LANCAMENTOS = "Lançamentos"

CATEGORIAS = [
    "Alimentação (fora de casa)", "Mercado/Supermercado", "Aluguel/Condomínio",
    "Energia elétrica", "Água", "Internet", "Telefone/Celular",
    "Transporte/Combustível", "Saúde/Plano de saúde", "Farmácia",
    "Educação", "Lazer/Entretenimento", "Vestuário", "Streaming/Assinaturas",
    "Pets", "Outros",
]

FORMAS_PAGAMENTO = [
    "Dinheiro", "Pix", "Cartão de Crédito", "Cartão de Débito",
    "Débito Automático", "Boleto", "Vale Alimentação/Refeição",
]

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
    """Formata número no padrão brasileiro: R$ 1.234,56"""
    return f"R$ {v:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def caminhos_de_chaves(no, prefixo=""):
    """Lista somente os NOMES das chaves do Secrets (nunca os valores)."""
    resultado = []
    try:
        chaves = list(no.keys())
    except Exception:
        return resultado
    for k in chaves:
        caminho = f"{prefixo}{k}"
        resultado.append(caminho)
        resultado.extend(caminhos_de_chaves(no[k], caminho + "."))
    return resultado


def obter_info_credenciais():
    """Procura as credenciais aceitando todas as estruturas comuns de Secrets."""
    candidatos = []
    for caminho in (
        ("connections", "gsheets", "service_account"),
        ("connections", "gsheets"),
        ("gsheets", "service_account"),
        ("service_account",),
    ):
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
    st.title("🏠 Despesas de Casa")
    st.error("Não encontrei as credenciais do Google no Secrets deste app.")
    estrutura = caminhos_de_chaves(st.secrets)
    st.caption("Estrutura detectada no Secrets (somente nomes, nunca valores): "
               + (", ".join(estrutura) if estrutura else "nenhuma"))
    st.markdown(
        "No app: **Manage app** (canto inferior direito) → **⋮ → Settings → "
        "Secrets**, cole o bloco abaixo preenchido com os valores do JSON e "
        "clique em **Save**:"
    )
    st.code(SECRETS_EXEMPLO, language="toml")
    st.stop()


# ---------- Conexão com o Google Sheets ----------
@st.cache_resource
def abrir_planilha():
    escopos = ["https://www.googleapis.com/auth/spreadsheets"]
    credenciais = Credentials.from_service_account_info(
        INFO_CREDENCIAIS, scopes=escopos)
    return gspread.authorize(credenciais).open_by_key(SPREADSHEET_ID)


# ---------- Leitura dos dados ----------
@st.cache_data(ttl=300)
def carregar_dados() -> pd.DataFrame:
    ws = abrir_planilha().worksheet(ABA_LANCAMENTOS)
    valores = ws.get_all_values()

    if len(valores) < 2:
        return pd.DataFrame(
            columns=["data", "descricao", "categoria", "valor", "forma", "mes"]
        )

    cabecalhos, linhas = valores[0], valores[1:]
    df = pd.DataFrame(linhas, columns=cabecalhos).rename(columns={
        "Data": "data", "Descrição": "descricao", "Categoria": "categoria",
        "Valor (R$)": "valor", "Forma de Pagamento": "forma",
    })
    df = df[(df["data"] != "") & (df["valor"] != "")]

    df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")

    def converter_valor(v):
        t = str(v).replace("R$", "").replace("\u00a0", "").strip()
        try:
            return float(t)
        except ValueError:
            try:
                return float(t.replace(".", "").replace(",", "."))
            except ValueError:
                return None

    df["valor"] = df["valor"].map(converter_valor)
    df = df.dropna(subset=["data", "valor"])
    df["valor"] = df["valor"].abs()
    df["mes"] = df["data"].dt.to_period("M")
    return df


# ---------- Barra lateral ----------
st.sidebar.title("🏠 Despesas de Casa")
if st.sidebar.button("🔄 Atualizar dados", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# ---------- Formulário de lançamento ----------
st.title("🏠 Despesas de Casa")
st.subheader("➕ Lançar despesa")

with st.form("form_lancamento", clear_on_submit=True):
    c1, c2 = st.columns(2)
    with c1:
        data = st.date_input("Data", format="DD/MM/YYYY")
    with c2:
        valor = st.number_input("Valor (R$)", min_value=0.01, format="%.2f")
    descricao = st.text_input("Descrição")
    c3, c4 = st.columns(2)
    with c3:
        categoria = st.selectbox("Categoria", CATEGORIAS)
    with c4:
        forma = st.selectbox("Forma de pagamento", FORMAS_PAGAMENTO)
    enviado = st.form_submit_button("💾 Salvar lançamento", type="primary",
                                    use_container_width=True)

if enviado:
    if not descricao.strip():
        st.error("Escreva uma descrição para o lançamento.")
    else:
        try:
            ws = abrir_planilha().worksheet(ABA_LANCAMENTOS)
            ws.append_row(
                [data.strftime("%d/%m/%Y"), descricao.strip(), categoria,
                 round(valor, 2), forma],
                value_input_option="USER_ENTERED",
            )
            st.cache_data.clear()
            st.session_state["msg_sucesso"] = (
                f"✅ Salvo: {descricao.strip()} — {fmt_rs(valor)}"
            )
            st.rerun()
        except Exception as e:
            st.error(f"Não consegui salvar na planilha: {e}")

if "msg_sucesso" in st.session_state:
    st.success(st.session_state.pop("msg_sucesso"))

# ---------- Painel ----------
st.divider()
st.subheader("📊 Painel de despesas")

try:
    dados = carregar_dados()
except Exception as e:
    st.error("Não consegui acessar a planilha do Google.")
    st.markdown("Detalhe técnico do erro:")
    st.code(str(e))
    st.markdown(
        "**Causas mais comuns:**\n"
        "1. A conta de serviço não está compartilhada na planilha — abra a "
        "planilha → **Compartilhar** → confira se "
        "`despesas-de-casa@galaxy-watch-assistente-334520.iam.gserviceaccount.com` "
        "está lá como **Editor**\n"
        "2. A **Google Sheets API** não está ativada no projeto — no Console "
        "Google Cloud: **APIs e serviços → Biblioteca** → pesquise *Google "
        "Sheets API* → **Ativar**"
    )
    st.stop()

if dados.empty:
    st.info("Nenhum lançamento ainda. Use o formulário acima para começar!")
    st.stop()

meses_com_dados = sorted(dados["mes"].unique(), reverse=True)
opcoes = {"Todos os meses": None}
for m in meses_com_dados:
    opcoes[f"{MESES_PT[m.month - 1]} {m.year}"] = m
mes_label = st.sidebar.selectbox("Mês do painel", list(opcoes.keys()), index=0)
mes_sel = opcoes[mes_label]

categorias_filtro = st.sidebar.multiselect("Filtrar categorias (opcional)", CATEGORIAS)

df_mes = dados if mes_sel is None else dados[dados["mes"] == mes_sel]
if categorias_filtro:
    df_mes = df_mes[df_mes["categoria"].isin(categorias_filtro)]

if df_mes.empty:
    st.info("Nenhum lançamento nesse filtro.")
    st.stop()

total_mes = df_mes["valor"].sum()
total_geral = dados["valor"].sum()
cat_top = df_mes.groupby("categoria")["valor"].sum().idxmax()

c1, c2, c3, c4 = st.columns(4)
c1.metric(f"Total — {mes_label}", fmt_rs(total_mes))
c2.metric("Total geral", fmt_rs(total_geral))
c3.metric("Lançamentos no período", str(len(df_mes)))
c4.metric("Categoria mais pesada", cat_top)

col_a, col_b = st.columns(2)

with col_a:
    gasto_cat = (df_mes.groupby("categoria", as_index=False)["valor"]
                 .sum().sort_values("valor"))
    gasto_cat["texto"] = gasto_cat["valor"].map(fmt_rs)
    fig_cat = px.bar(gasto_cat, x="valor", y="categoria", orientation="h",
                     text="texto", title=f"Gasto por categoria — {mes_label}")
    fig_cat.update_layout(xaxis_title=None, yaxis_title=None,
                          margin=dict(l=10, r=10, t=40, b=10))
    fig_cat.update_xaxes(visible=False)
    st.plotly_chart(fig_cat, use_container_width=True)

with col_b:
    forma_sum = df_mes.groupby("forma", as_index=False)["valor"].sum()
    fig_forma = px.pie(forma_sum, names="forma", values="valor", hole=0.55,
                       title="Formas de pagamento")
    fig_forma.update_layout(margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_forma, use_container_width=True)

evo = dados.groupby("mes", as_index=False)["valor"].sum()
evo["rotulo"] = evo["mes"].apply(lambda p: f"{MESES_PT[p.month - 1]}/{str(p.year)[2:]}")
evo["texto"] = evo["valor"].map(fmt_rs)
fig_evo = px.line(evo, x="rotulo", y="valor", text="texto", markers=True,
                  title="Evolução mês a mês")
fig_evo.update_traces(textposition="top center")
fig_evo.update_layout(yaxis_title=None, xaxis_title=None,
                      margin=dict(l=10, r=10, t=40, b=10))
st.plotly_chart(fig_evo, use_container_width=True)

st.subheader(f"📋 Lançamentos — {mes_label}")
df_tabela = df_mes.sort_values("data", ascending=False)[
    ["data", "descricao", "categoria", "valor", "forma"]]
st.dataframe(
    df_tabela, use_container_width=True, hide_index=True,
    column_config={
        "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
        "descricao": "Descrição",
        "categoria": "Categoria",
        "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
        "forma": "Pagamento",
    },
)
