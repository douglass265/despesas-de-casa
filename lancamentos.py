import streamlit as st
from helpers import (CATEGORIAS_DESPESA, CATEGORIAS_RECEITA, FORMAS_PAGAMENTO,
                     CLASSES, ABA_DESPESAS, ABA_RECEITAS, ABA_CONTAS,
                     ABA_INVEST, salvar)

TIPOS_CONTA = ["Conta corrente", "Conta digital/Pix", "Poupança",
               "Cartão de crédito", "Dinheiro", "Outro"]


def render():
    st.subheader("➕ Lançamentos")
    aba = st.radio("", ["💸 Despesa", "💰 Receita", "🏦 Conta",
                        "📈 Investimento"], horizontal=True)

    if aba == "💸 Despesa":
        with st.form("f_despesa", clear_on_submit=True):
            c1, c2 = st.columns(2)
            data = c1.date_input("Data", format="DD/MM/YYYY")
            valor = c2.number_input("Valor (R$)", min_value=0.01, format="%.2f")
            desc = st.text_input("Descrição")
            c3, c4 = st.columns(2)
            cat = c3.selectbox("Categoria", CATEGORIAS_DESPESA)
            forma = c4.selectbox("Forma de pagamento", FORMAS_PAGAMENTO)
            if st.form_submit_button("💾 Salvar despesa", type="primary",
                                     use_container_width=True):
                if desc.strip():
                    salvar(ABA_DESPESAS, [data.strftime("%d/%m/%Y"),
                                          desc.strip(), cat, round(valor, 2),
                                          forma],
                           f"✅ Despesa salva: {desc.strip()} — R$ {valor:.2f}")
                else:
                    st.error("Escreva uma descrição.")

    elif aba == "💰 Receita":
        with st.form("f_receita", clear_on_submit=True):
            c1, c2 = st.columns(2)
            data = c1.date_input("Data", format="DD/MM/YYYY", key="dr")
            valor = c2.number_input("Valor (R$)", min_value=0.01, format="%.2f",
                                    key="vr")
            desc = st.text_input("Descrição", key="descr")
            cat = st.selectbox("Categoria", CATEGORIAS_RECEITA)
            if st.form_submit_button("💾 Salvar receita", type="primary",
                                     use_container_width=True):
                if desc.strip():
                    salvar(ABA_RECEITAS, [data.strftime("%d/%m/%Y"),
                                          desc.strip(), cat, round(valor, 2)],
                           f"✅ Receita salva: {desc.strip()} — R$ {valor:.2f}")
                else:
                    st.error("Escreva uma descrição.")

    elif aba == "🏦 Conta":
        st.caption("Para atualizar o saldo de uma conta que já existe, edite "
                   "direto na aba **Contas** da planilha.")
        with st.form("f_conta", clear_on_submit=True):
            nome = st.text_input("Banco / Conta (ex.: Nubank)")
            c1, c2 = st.columns(2)
            tipo = c1.selectbox("Tipo", TIPOS_CONTA)
            saldo = c2.number_input("Saldo atual (R$)", format="%.2f")
            if st.form_submit_button("💾 Salvar conta", type="primary",
                                     use_container_width=True):
                if nome.strip():
                    salvar(ABA_CONTAS, [nome.strip(), tipo, round(saldo, 2)],
                           f"✅ Conta salva: {nome.strip()}")
                else:
                    st.error("Escreva o nome da conta.")

    else:
        with st.form("f_inv", clear_on_submit=True):
            c1, c2 = st.columns(2)
            ativo = c1.text_input("Ativo (ex.: PETR4, HGLG11, CDB Inter)")
            classe = c2.selectbox("Classe", CLASSES)
            c3, c4, c5 = st.columns(3)
            qtd = c3.number_input("Quantidade", min_value=0.0, format="%.4f")
            pm = c4.number_input("Preço médio (R$)", min_value=0.0, format="%.2f")
            pa = c5.number_input("Preço atual (R$)", min_value=0.0, format="%.2f")
            if st.form_submit_button("💾 Salvar investimento", type="primary",
                                     use_container_width=True):
                if ativo.strip() and qtd > 0:
                    salvar(ABA_INVEST,
                           [ativo.strip(), classe, round(qtd, 4), round(pm, 2),
                            round(pa, 2), round(qtd * pm, 2), round(qtd * pa, 2)],
                           f"✅ Investimento salvo: {ativo.strip()}")
                else:
                    st.error("Informe o ativo e a quantidade.")
