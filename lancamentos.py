import streamlit as st
from datetime import date
from helpers import (CATEGORIAS_DESPESA, CATEGORIAS_RECEITA, FORMAS_PAGAMENTO,
                     CLASSES, BANDEIRAS, CLASSES_MOEDA_USD, CLASSES_RENDA_FIXA,
                     ABA_DESPESAS, ABA_RECEITAS, ABA_CONTAS, ABA_INVEST,
                     ABA_CARTOES, ABA_COMPRAS, ABA_TRANSF, ABA_DIVID,
                     salvar, abrir_planilha, cotacao_dolar, cdi_do_periodo,
                     fmt_rs)

TIPOS_CONTA = ["Conta corrente", "Conta digital/Pix", "Poupança",
               "Cartão de crédito", "Dinheiro", "Outro"]


@st.cache_data(ttl=300)
def listar_contas():
    try:
        valores = abrir_planilha().worksheet(ABA_CONTAS).get_all_values()
        return [l[0].strip() for l in valores[1:] if l and l[0].strip()]
    except Exception:
        return []


@st.cache_data(ttl=300)
def listar_cartoes():
    try:
        valores = abrir_planilha().worksheet(ABA_CARTOES).get_all_values()
        return [l[0].strip() for l in valores[1:] if l and l[0].strip()]
    except Exception:
        return []


@st.cache_data(ttl=300)
def listar_ativos():
    try:
        valores = abrir_planilha().worksheet(ABA_INVEST).get_all_values()
        return [l[0].strip() for l in valores[1:] if l and l[0].strip()]
    except Exception:
        return []


def _form_despesa(opcoes_conta):
    with st.form("f_despesa", clear_on_submit=True):
        c1, c2 = st.columns(2)
        data = c1.date_input("Data", format="DD/MM/YYYY")
        valor = c2.number_input("Valor (R$)", min_value=0.01, format="%.2f")
        desc = st.text_input("Descrição")
        c3, c4 = st.columns(2)
        cat = c3.selectbox("Categoria", CATEGORIAS_DESPESA)
        forma = c4.selectbox("Forma de pagamento", FORMAS_PAGAMENTO)
        conta_sel = st.selectbox("💳 Pagar com a conta", opcoes_conta)
        if st.form_submit_button("💾 Salvar despesa", type="primary",
                                 use_container_width=True):
            if desc.strip():
                salvar(ABA_DESPESAS,
                       [data.strftime("%d/%m/%Y"), desc.strip(), cat,
                        round(valor, 2), forma,
                        "" if conta_sel == "(sem conta)" else conta_sel],
                       f"✅ Despesa salva: {desc.strip()} — R$ {valor:.2f}")
            else:
                st.error("Escreva uma descrição.")


def _form_receita(opcoes_conta):
    with st.form("f_receita", clear_on_submit=True):
        c1, c2 = st.columns(2)
        data = c1.date_input("Data", format="DD/MM/YYYY", key="dr")
        valor = c2.number_input("Valor (R$)", min_value=0.01, format="%.2f",
                                key="vr")
        desc = st.text_input("Descrição", key="descr")
        cat = st.selectbox("Categoria", CATEGORIAS_RECEITA)
        conta_sel = st.selectbox("💳 Recebido na conta", opcoes_conta, key="cr")
        if st.form_submit_button("💾 Salvar receita", type="primary",
                                 use_container_width=True):
            if desc.strip():
                salvar(ABA_RECEITAS,
                       [data.strftime("%d/%m/%Y"), desc.strip(), cat,
                        round(valor, 2),
                        "" if conta_sel == "(sem conta)" else conta_sel],
                       f"✅ Receita salva: {desc.strip()} — R$ {valor:.2f}")
            else:
                st.error("Escreva uma descrição.")


def _form_transferencia(contas_reais):
    if len(contas_reais) < 2:
        st.warning("Cadastre pelo menos duas contas para poder transferir.")
    with st.form("f_transf", clear_on_submit=True):
        c1, c2 = st.columns(2)
        data = c1.date_input("Data", format="DD/MM/YYYY", key="dt")
        valor = c2.number_input("Valor (R$)", min_value=0.01, format="%.2f",
                                key="vt")
        desc = st.text_input("Descrição (opcional)", key="dtr")
        origem = st.selectbox("🔁 Da conta", contas_reais)
        destino = st.selectbox("➡️ Para a conta", contas_reais, key="tdest")
        if st.form_submit_button("💾 Salvar transferência", type="primary",
                                 use_container_width=True):
            if origem == destino:
                st.error("Escolha contas diferentes para a transferência.")
            else:
                salvar(ABA_TRANSF,
                       [data.strftime("%d/%m/%Y"), desc.strip(), origem,
                        destino, round(valor, 2)],
                       f"✅ Transferência: {origem} → {destino} — R$ {valor:.2f}")


def _form_compra_cartao(cartoes):
    if not cartoes:
        st.warning("Cadastre um cartão primeiro, em 💳 Cadastrar cartão.")
    with st.form("f_compra", clear_on_submit=True):
        c1, c2 = st.columns(2)
        data = c1.date_input("Data da compra", format="DD/MM/YYYY")
        cartao = c2.selectbox("Cartão", cartoes)
        desc = st.text_input("Descrição da compra")
        cat = st.selectbox("Categoria", CATEGORIAS_DESPESA)
        c3, c4 = st.columns(2)
        valor = c3.number_input("Valor total (R$)", min_value=0.01, format="%.2f")
        parcelada = c4.selectbox("Compra parcelada?", ["Não", "Sim"])
        n_parcelas = 1
        if parcelada == "Sim":
            n_parcelas = st.number_input("Número de parcelas", min_value=2,
                                         max_value=24, value=2, step=1)
        if st.form_submit_button("💾 Salvar compra", type="primary",
                                 use_container_width=True):
            if desc.strip() and cartao:
                extra = f" em {n_parcelas}x" if parcelada == "Sim" else ""
                salvar(ABA_COMPRAS,
                       [data.strftime("%d/%m/%Y"), desc.strip(), cartao, cat,
                        round(valor, 2), n_parcelas, parcelada,
                        "Cartão de Crédito"],
                       f"✅ Compra salva: {desc.strip()} — R$ {valor:.2f}{extra}")
            else:
                st.error("Escreva a descrição da compra.")


def _form_cadastro_cartao(opcoes_conta):
    with st.form("f_cartao", clear_on_submit=True):
        apelido = st.text_input("Apelido do cartão (ex.: Nubank)")
        c1, c2 = st.columns(2)
        bandeira = c1.selectbox("Bandeira / Emissor", BANDEIRAS)
        limite = c2.number_input("Limite (R$)", min_value=0.0, format="%.2f")
        c3, c4 = st.columns(2)
        fechamento = c3.number_input("Dia do fechamento", min_value=1,
                                     max_value=31, value=20, step=1)
        vencimento = c4.number_input("Dia do vencimento", min_value=1,
                                     max_value=31, value=28, step=1)
        conta_pag = st.selectbox("Conta de pagamento", opcoes_conta)
        if st.form_submit_button("💾 Salvar cartão", type="primary",
                                 use_container_width=True):
            if apelido.strip():
                salvar(ABA_CARTOES,
                       [apelido.strip(), bandeira, int(fechamento),
                        int(vencimento), round(limite, 2),
                        "" if conta_pag == "(sem conta)" else conta_pag],
                       f"✅ Cartão salvo: {apelido.strip()}")
            else:
                st.error("Escreva o apelido do cartão.")

def _form_dividendo(ativos, contas):
    if not ativos:
        st.info("Nenhum ativo na carteira ainda — cadastre em 📈 Investimento.")
    with st.form("f_divid", clear_on_submit=True):
        c1, c2 = st.columns(2)
        data = c1.date_input("Data do crédito", format="DD/MM/YYYY", key="dd")
        valor = c2.number_input("Valor (R$)", min_value=0.01, format="%.2f",
                                key="vd")
        if ativos:
            ativo = st.selectbox("Ativo", ativos, key="da_s")
        else:
            ativo = st.text_input("Ativo (ex.: PETR4, MXRF11)", key="da_t")
        conta_sel = st.selectbox("Conta onde caiu (informativo)",
                                 ["(nenhuma)"] + contas, key="dc")
        if st.form_submit_button("💾 Salvar dividendo", type="primary",
                                 use_container_width=True):
            if ativo and str(ativo).strip():
                salvar(ABA_DIVID,
                       [data.strftime("%d/%m/%Y"), str(ativo).strip(),
                        round(valor, 2),
                        "" if conta_sel == "(nenhuma)" else conta_sel],
                       f"✅ Dividendo salvo: {str(ativo).strip()} — R$ {valor:.2f}")
            else:
                st.error("Informe o ativo.")


def _form_investimento():
    dol = cotacao_dolar()
    if dol:
        st.caption(f"💵 Cotação do dólar hoje: R$ {dol:.2f}")
    with st.form("f_inv", clear_on_submit=True):
        c1, c2 = st.columns(2)
        ativo = c1.text_input("Ativo (ex.: PETR4, HGLG11, IVVB11, AAPL, CDB Inter)")
        classe = c2.selectbox("Classe", CLASSES)
        moeda = "US$" if classe in CLASSES_MOEDA_USD else "R$"
        c3, c4 = st.columns(2)
        qtd = c3.number_input("Quantidade", min_value=0.0, format="%.4f")
        pm = c4.number_input(f"Preço médio ({moeda})", min_value=0.0, format="%.2f")
        pa = st.number_input(f"Preço atual ({moeda})", min_value=0.0,
                             format="%.2f")
        pct_cdi = 0.0
        data_apl = None
        if classe in CLASSES_RENDA_FIXA:
            c5, c6 = st.columns(2)
            pct_cdi = c5.number_input("% do CDI contratada", min_value=0.0,
                                      max_value=300.0, value=100.0, step=5.0,
                                      format="%.1f")
            data_apl = c6.date_input("Data da aplicação", format="DD/MM/YYYY",
                                     key="dapl")
            dias = max((date.today() - data_apl).days, 1)
            cdi_info = cdi_do_periodo(dias)
            if cdi_info is not None and pm > 0:
                est = pm * (1.0 + (cdi_info / 100.0) * (pct_cdi / 100.0))
                st.caption(f"CDI acumulado em {dias} dias: {cdi_info:.2f}% — "
                           f"valor estimado hoje: R$ {est:,.2f}")
        if st.form_submit_button("💾 Salvar investimento", type="primary",
                                 use_container_width=True):
            if ativo.strip() and qtd > 0:
                salvar(ABA_INVEST,
                       [ativo.strip(), classe, round(qtd, 4), round(pm, 2),
                        round(pa, 2), round(qtd * pm, 2), round(qtd * pa, 2),
                        pct_cdi if pct_cdi else "",
                        data_apl.strftime("%d/%m/%Y") if data_apl else ""],
                       f"✅ Investimento salvo: {ativo.strip()}")
            else:
                st.error("Informe o ativo e a quantidade.")


def _form_conta():
    st.caption("O saldo é calculado automaticamente: preencha o **Saldo "
               "Inicial** com o valor que a conta tinha antes dos lançamentos.")
    with st.form("f_conta", clear_on_submit=True):
        nome = st.text_input("Banco / Conta (ex.: Nubank)")
        c1, c2 = st.columns(2)
        tipo = c1.selectbox("Tipo", TIPOS_CONTA)
        saldo = c2.number_input("Saldo inicial (R$)", format="%.2f")
        if st.form_submit_button("💾 Salvar conta", type="primary",
                                 use_container_width=True):
            if nome.strip():
                salvar(ABA_CONTAS, [nome.strip(), tipo, round(saldo, 2)],
                       f"✅ Conta salva: {nome.strip()}")
            else:
                st.error("Escreva o nome da conta.")


def render():
    st.subheader("➕ Lançamentos")
    aba = st.radio("Tipo de lançamento",
                   ["💸 Despesa", "💰 Receita", "🔁 Transferência",
                    "💳 Cartão", "💎 Dividendos", "🏦 Conta",
                    "📈 Investimento"],
                   horizontal=True, label_visibility="collapsed")
    contas = listar_contas()
    opcoes_conta = ["(sem conta)"] + contas
    cartoes = listar_cartoes()
    ativos = listar_ativos()

    if aba == "💸 Despesa":
        _form_despesa(opcoes_conta)
    elif aba == "💰 Receita":
        _form_receita(opcoes_conta)
    elif aba == "🔁 Transferência":
        _form_transferencia(contas)
    elif aba == "💳 Cartão":
        sub = st.radio("O que você quer lançar?",
                       ["🛍️ Compra no cartão", "💳 Cadastrar cartão"],
                       horizontal=True, key="sub_cartao")
        if sub == "🛍️ Compra no cartão":
            _form_compra_cartao(cartoes)
        else:
            _form_cadastro_cartao(opcoes_conta)
    elif aba == "💎 Dividendos":
        _form_dividendo(ativos, contas)
    elif aba == "🏦 Conta":
        _form_conta()
    else:
        _form_investimento()
                salvar(ABA_DIVID,
                       [data.strftime("%d/%m/%Y"), str(ativo).strip(),
                        round(valor, 2),
                        "" if 
