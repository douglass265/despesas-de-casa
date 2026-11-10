import streamlit as st
from helpers import (fmt_rs, MESES_PT, ABA_DESPESAS, ABA_RECEITAS,
                     ABA_CONTAS, ABA_INVEST, excluir_linha)

LIMITE = 100


def _seletor_mes(df, chave):
    meses = sorted(df["mes"].unique(), reverse=True)
    opcoes = {"Todos os meses": None}
    for m in meses:
        opcoes[f"{MESES_PT[m.month - 1]} {m.year}"] = m
    label = st.selectbox("Mês", list(opcoes.keys()), key=chave)
    return opcoes[label]


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
    if len(df_f) > LIMITE:
        st.caption(f"Mostrando os {LIMITE} mais recentes — refine os filtros "
                   "para ver o restante.")
        df_f = df_f.head(LIMITE)

    if tem_forma:
        h = st.columns([1.1, 2.6, 1.9, 1.5, 1.5, 1.2, 0.5])
        rotulos = ["Data", "Descrição", "Categoria", "Conta", "Forma",
                   "Valor", ""]
    else:
        h = st.columns([1.1, 3.2, 2.2, 1.6, 1.4, 0.5])
        rotulos = ["Data", "Descrição", "Categoria", "Conta", "Valor", ""]
    for c, rot in zip(h, rotulos):
        c.markdown(f"**{rot}**")

    for _, r in df_f.iterrows():
        if tem_forma:
            cols = st.columns([1.1, 2.6, 1.9, 1.5, 1.5, 1.2, 0.5])
            cols[0].write(r["data"].strftime("%d/%m/%Y"))
            cols[1].write(r["descricao"])
            cols[2].write(r["categoria"])
            cols[3].write(r["conta"] if r.get("conta") else "—")
            cols[4].write(r["forma"] if r.get("forma") else "—")
            cols[5].write(fmt_rs(r["valor"]))
            botao = cols[6]
        else:
            cols = st.columns([1.1, 3.2, 2.2, 1.6, 1.4, 0.5])
            cols[0].write(r["data"].strftime("%d/%m/%Y"))
            cols[1].write(r["descricao"])
            cols[2].write(r["categoria"])
            cols[3].write(r["conta"] if r.get("conta") else "—")
            cols[4].write(fmt_rs(r["valor"]))
            botao = cols[5]
        if botao.button("🗑️", key=f"{prefixo}_{int(r['_linha'])}",
                        help="Excluir este lançamento"):
            excluir_linha(aba, int(r["_linha"]),
                          f"🗑️ Lançamento excluído: {r['descricao']}")
    st.caption("A exclusão é imediata e não pode ser desfeita. Para corrigir "
               "um lançamento, exclua aqui e lance de novo com os dados certos.")


def _contas(contas):
    if contas.empty:
        st.info("Nenhuma conta cadastrada.")
        return
    st.caption(f"Total em contas: **{fmt_rs(contas['saldo'].sum())}**")
    for _, r in contas.iterrows():
        c1, c2, c3, c4 = st.columns([2.6, 2, 1.4, 0.5])
        c1.write(r["conta"])
        c2.write(r["tipo"])
        c3.write(fmt_rs(r["saldo"]))
        if c4.button("🗑️", key=f"conta_{int(r['_linha'])}",
                     help="Excluir esta conta"):
            excluir_linha(ABA_CONTAS, int(r["_linha"]),
                          f"🗑️ Conta excluída: {r['conta']}")
    st.caption("Lançamentos antigos que apontavam para a conta continuam "
               "guardados com o nome dela.")


def _investimentos(inv):
    if inv.empty:
        st.info("Nenhum investimento cadastrado.")
        return
    st.caption(f"Carteira: investido **{fmt_rs(inv['investido'].sum())}** · "
               f"valor atual **{fmt_rs(inv['atual'].sum())}**")
    for _, r in inv.iterrows():
        c1, c2, c3, c4, c5, c6, c7 = st.columns(
            [2, 1.8, 1, 1.2, 1.2, 1.4, 0.5])
        c1.write(r["ativo"])
        c2.write(r["classe"])
        c3.write(f"{r['qtd']:g}")
        c4.write(fmt_rs(r["pm"]))
        c5.write(fmt_rs(r["pa"]))
        c6.write(fmt_rs(r["atual"]))
        if c7.button("🗑️", key=f"inv_{int(r['_linha'])}",
                     help="Excluir este ativo"):
            excluir_linha(ABA_INVEST, int(r["_linha"]),
                          f"🗑️ Investimento excluído: {r['ativo']}")


def render(desp, rec, contas, inv):
    st.subheader("📜 Histórico")
    tipo = st.radio("", ["💸 Despesas", "💰 Receitas", "🏦 Contas",
                         "📈 Investimentos"], horizontal=True)
    if tipo == "💸 Despesas":
        _movimentos(desp, "despesas", ABA_DESPESAS, True, "d")
    elif tipo == "💰 Receitas":
        _movimentos(rec, "receitas", ABA_RECEITAS, False, "r")
    elif tipo == "🏦 Contas":
        _contas(contas)
    else:
        _investimentos(inv)
