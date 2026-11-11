import streamlit as st
from helpers import (fmt_rs, MESES_PT, ABA_DESPESAS, ABA_RECEITAS,
                     ABA_CONTAS, ABA_INVEST, ABA_TRANSF, ABA_COMPRAS,
                     excluir_linha, ler_tudo)

LIMITE = 100


def _seletor_mes(df, chave):
    meses = sorted(df["mes"].unique(), reverse=True)
    opcoes = {"Todos os meses": None}
    for m in meses:
        opcoes[f"{MESES_PT[m.month - 1]} {m.year}"] = m
    label = st.selectbox("Mês", list(opcoes.keys()), key=chave)
    return opcoes[label]


def _corte(df):
    if len(df) > LIMITE:
        st.caption(f"Mostrando os {LIMITE} mais recentes — refine os filtros "
                   "para ver o restante.")
        return df.head(LIMITE)
    return df


def _movimentos(df, tipo_nome, aba, tem_forma, prefixo):
    if df.empty:
        st.info(f"Nenhum lançamento de {tipo_nome.lower()} ainda.")
        return
    mes_sel = _seletor_mes(df, f"mes_{prefixo}")
    f1, f2 = st.columns([3, 2])
    busca = f1.text_input("🔎 Buscar por palavra na descrição",
                          key=f"busca_{prefixo}").strip().lower()
    cats = f2.multiselect("Filtrar categoria",
                          sorted(df["categoria"].dropna().unique()),
                          key=f"cat_{prefixo}")
    df_f = df if mes_sel is None else df[df["mes"] == mes_sel]
    if busca:
        df_f = df_f[df_f["descricao"].str.lower().str.contains(busca, na=False)]
    if cats:
        df_f = df_f[df_f["categoria"].isin(cats)]
    st.caption(f"{len(df_f)} lançamento(s) — total: "
               f"**{fmt_rs(df_f['valor'].sum())}**")
    if df_f.empty:
        st.info("Nada encontrado com esses filtros.")
        return
    st.divider()
    df_f = _corte(df_f)
    if tem_forma:
        cols = st.columns([1.1, 2.6, 1.9, 1.5, 1.5, 1.2, 0.5])
        rotulos = ["Data", "Descrição", "Categoria", "Conta", "Forma",
                   "Valor", ""]
    else:
        cols = st.columns([1.1, 3.2, 2.2, 1.6, 1.4, 0.5])
        rotulos = ["Data", "Descrição", "Categoria", "Conta", "Valor", ""]
    for c, rot in zip(cols, rotulos):
        c.markdown(f"**{rot}**")
    for _, r in df_f.iterrows():
        if tem_forma:
            cs = st.columns([1.1, 2.6, 1.9, 1.5, 1.5, 1.2, 0.5])
            cs[0].write(r["data"].strftime("%d/%m/%Y"))
            cs[1].write(r["descricao"])
            cs[2].write(r["categoria"])
            cs[3].write(r["conta"] if r.get("conta") else "—")
            cs[4].write(r["forma"] if r.get("forma") else "—")
            cs[5].write(fmt_rs(r["valor"]))
            botao = cs[6]
        else:
            cs = st.columns([1.1, 3.2, 2.2, 1.6, 1.4, 0.5])
            cs[0].write(r["data"].strftime("%d/%m/%Y"))
            cs[1].write(r["descricao"])
            cs[2].write(r["categoria"])
            cs[3].write(r["conta"] if r.get("conta") else "—")
            cs[4].write(fmt_rs(r["valor"]))
            botao = cs[5]
        if botao.button("🗑️", key=f"{prefixo}_{int(r['_linha'])}",
                        help="Excluir este lançamento"):
            excluir_linha(aba, int(r["_linha"]),
                          f"🗑️ Lançamento excluído: {r['descricao']}")
    st.caption("A exclusão é imediata e não pode ser desfeita. Para corrigir "
               "um lançamento, exclua e lance de novo com os dados certos.")


def _transferencias(transf):
    if transf.empty:
        st.info("Nenhuma transferência ainda.")
        return
    transf = transf.copy()
    transf["mes"] = transf["data"].dt.to_period("M")
    mes_sel = _seletor_mes(transf, "mes_t")
    df_f = transf if mes_sel is None else transf[transf["mes"] == mes_sel]
    st.caption(f"{len(df_f)} transferência(s) — total movimentado: "
               f"**{fmt_rs(df_f['valor'].sum())}**")
    if df_f.empty:
        st.info("Nada nesse filtro.")
        return
    st.divider()
    df_f = _corte(df_f)
    cols = st.columns([1.1, 2.2, 2.4, 1.4, 0.5])
    for c, rot in zip(cols, ["Data", "Descrição", "Transferência", "Valor", ""]):
        c.markdown(f"**{rot}**")
    for _, r in df_f.iterrows():
        cs = st.columns([1.1, 2.2, 2.4, 1.4, 0.5])
        cs[0].write(r["data"].strftime("%d/%m/%Y"))
        cs[1].write(r["descricao"] if r["descricao"] else "—")
        cs[2].write(f"🔁 {r['da_conta']} → {r['para_conta']}")
        cs[3].write(fmt_rs(r["valor"]))
        if cs[4].button("🗑️", key=f"t_{int(r['_linha'])}",
                        help="Excluir esta transferência"):
            excluir_linha(ABA_TRANSF, int(r["_linha"]),
                          "🗑️ Transferência excluída")


def _compras(compras):
    if compras.empty:
        st.info("Nenhuma compra no cartão ainda.")
        return
    compras = compras.copy()
    compras["mes"] = compras["data"].dt.to_period("M")
    mes_sel = _seletor_mes(compras, "mes_c")
    f1, f2 = st.columns([3, 2])
    busca = f1.text_input("🔎 Buscar por palavra na descrição",
                          key="busca_c").strip().lower()
    cartoes_f = f2.multiselect("Filtrar cartão",
                               sorted(compras["cartao"].unique()),
                               key="cartao_c")
    df_f = compras if mes_sel is None else compras[compras["mes"] == mes_sel]
    if busca:
        df_f = df_f[df_f["descricao"].str.lower().str.contains(busca, na=False)]
    if cartoes_f:
        df_f = df_f[df_f["cartao"].isin(cartoes_f)]
    st.caption(f"{len(df_f)} compra(s) — valor total: "
               f"**{fmt_rs(df_f['valor'].sum())}**")
    if df_f.empty:
        st.info("Nada encontrado com esses filtros.")
        return
    st.divider()
    df_f = _corte(df_f)
    cols = st.columns([1.1, 2.6, 1.6, 1.9, 1.0, 1.2, 0.5])
    for c, rot in zip(cols, ["Data", "Descrição", "Cartão", "Categoria",
                             "Parcelas", "Valor", ""]):
        c.markdown(f"**{rot}**")
    for _, r in df_f.iterrows():
        cs = st.columns([1.1, 2.6, 1.6, 1.9, 1.0, 1.2, 0.5])
        cs[0].write(r["data"].strftime("%d/%m/%Y"))
        cs[1].write(r["descricao"])
        cs[2].write(r["cartao"])
        cs[3].write(r["categoria"])
        cs[4].write(f"{int(r['parcelas'])}x" if int(r["parcelas"]) > 1
                    else "à vista")
        cs[5].write(fmt_rs(r["valor"]))
        if cs[6].button("🗑️", key=f"c_{int(r['_linha'])}",
                        help="Excluir esta compra"):
            excluir_linha(ABA_COMPRAS, int(r["_linha"]),
                          f"🗑️ Compra excluída: {r['descricao']}")
    st.caption("O valor mostrado é o total da compra; as parcelas entram "
               "nas faturas dos meses seguintes — veja em 💳 Cartões.")


def _contas(contas):
    if contas.empty:
        st.info("Nenhuma conta cadastrada.")
        return
    st.caption(f"Total em contas (saldos calculados): "
               f"**{fmt_rs(contas['saldo'].sum())}**")
    cols = st.columns([2.2, 1.8, 1.4, 1.4, 0.5])
    for c, rot in zip(cols, ["Conta", "Tipo", "Saldo inicial",
                             "Saldo atual", ""]):
        c.markdown(f"**{rot}**")
    for _, r in contas.iterrows():
        cs = st.columns([2.2, 1.8, 1.4, 1.4, 0.5])
        cs[0].write(r["conta"])
        cs[1].write(r["tipo"])
        cs[2].write(fmt_rs(r["saldo_inicial"]))
        cs[3].write(fmt_rs(r["saldo"]))
        if cs[4].button("🗑️", key=f"conta_{int(r['_linha'])}",
                        help="Excluir esta conta"):
            excluir_linha(ABA_CONTAS, int(r["_linha"]),
                          f"🗑️ Conta excluída: {r['conta']}")
    st.caption("Saldo atual = saldo inicial + receitas − despesas "
               "+ transferências recebidas − transferências enviadas. "
               "Para ajustar o Saldo inicial, edite na planilha (aba Contas).")


def _investimentos(inv):
    if inv.empty:
        st.info("Nenhum investimento cadastrado.")
        return
    st.caption(f"Carteira: investido **{fmt_rs(inv['investido'].sum())}** · "
               f"valor atual **{fmt_rs(inv['atual'].sum())}**")
    for _, r in inv.iterrows():
        cs = st.columns([2, 1.8, 1, 1.2, 1.2, 1.4, 0.5])
        cs[0].write(r["ativo"])
        cs[1].write(r["classe"])
        cs[2].write(f"{r['qtd']:g}")
        cs[3].write(fmt_rs(r["pm"]))
        cs[4].write(fmt_rs(r["pa"]))
        cs[5].write(fmt_rs(r["atual"]))
        if cs[6].button("🗑️", key=f"inv_{int(r['_linha'])}",
                        help="Excluir este ativo"):
            excluir_linha(ABA_INVEST, int(r["_linha"]),
                          f"🗑️ Investimento excluído: {r['ativo']}")


def render(desp, rec, contas, inv):
    _, _, _, _, transf, cartoes, compras = ler_tudo()
    st.subheader("📜 Histórico")
    tipo = st.radio("", ["💸 Despesas", "💰 Receitas", "🔁 Transferências",
                         "💳 Compras no cartão", "🏦 Contas",
                         "📈 Investimentos"], horizontal=True)
    if tipo == "💸 Despesas":
        _movimentos(desp, "despesas", ABA_DESPESAS, True, "d")
    elif tipo == "💰 Receitas":
        _movimentos(rec, "receitas", ABA_RECEITAS, False, "r")
    elif tipo == "🔁 Transferências":
        _transferencias(transf)
    elif tipo == "💳 Compras no cartão":
        _compras(compras)
    elif tipo == "🏦 Contas":
        _contas(contas)
    else:
        _investimentos(inv)
