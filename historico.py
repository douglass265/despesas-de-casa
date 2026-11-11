import pandas as pd
import streamlit as st
from helpers import (fmt_rs, MESES_PT, ABA_DESPESAS, ABA_RECEITAS,
                     ABA_CONTAS, ABA_INVEST, ABA_VENDAS, ABA_DIVID,
                     ABA_TRANSF, ABA_COMPRAS, excluir_linha, ler_aba,
                     ler_tudo, ler_dividendos, ler_vendas, converter_datas,
                     converter_valor)

LIMITE = 100


def _txt(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    t = str(v).strip()
    return t if t and t not in ("nan", "None") else "—"


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
    if df_f.empty:
        st.info("Nada encontrado com esses filtros.")
        return
    st.caption(f"{len(df_f)} lançamento(s) — total: "
               f"**{fmt_rs(df_f['valor'].sum())}**")
    st.divider()
    df_f = _corte(df_f)
    if tem_forma:
        cols = st.columns([1.1, 3.2, 1.6, 1.4, 1.2, 0.5])
        rots = ["Data", "Descrição", "Conta", "Pagamento", "Valor", ""]
    else:
        cols = st.columns([1.1, 3.6, 1.8, 1.4, 0.5])
        rots = ["Data", "Descrição", "Conta", "Valor", ""]
    for c, rot in zip(cols, rots):
        c.markdown(f"**{rot}**")
    totais = (df_f.groupby("categoria")["valor"].sum()
              .sort_values(ascending=False))
    for cat in totais.index:
        g = df_f[df_f["categoria"] == cat].sort_values("data", ascending=False)
        st.markdown(f"**{cat}** — {fmt_rs(totais[cat])}")
        for _, r in g.iterrows():
            if tem_forma:
                cs = st.columns([1.1, 3.2, 1.6, 1.4, 1.2, 0.5])
                cs[0].write(r["data"].strftime("%d/%m/%Y"))
                cs[1].write(r["descricao"])
                cs[2].write(_txt(r.get("conta")))
                cs[3].write(_txt(r.get("forma")))
                cs[4].write(fmt_rs(r["valor"]))
                botao = cs[5]
            else:
                cs = st.columns([1.1, 3.6, 1.8, 1.4, 0.5])
                cs[0].write(r["data"].strftime("%d/%m/%Y"))
                cs[1].write(r["descricao"])
                cs[2].write(_txt(r.get("conta")))
                cs[3].write(fmt_rs(r["valor"]))
                botao = cs[4]
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
        cs[1].write(_txt(r["descricao"]))
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
    busca = st.text_input("🔎 Buscar por palavra na descrição",
                          key="busca_c").strip().lower()
    df_f = compras if mes_sel is None else compras[compras["mes"] == mes_sel]
    if busca:
        df_f = df_f[df_f["descricao"].str.lower().str.contains(busca, na=False)]
    if df_f.empty:
        st.info("Nada encontrado com esses filtros.")
        return
    st.caption(f"{len(df_f)} compra(s) — valor total: "
               f"**{fmt_rs(df_f['valor'].sum())}**")
    st.divider()
    df_f = _corte(df_f)
    cols = st.columns([1.1, 3.0, 1.6, 1.2, 1.2, 0.5])
    for c, rot in zip(cols, ["Data", "Descrição", "Cartão", "Parcelas",
                             "Valor", ""]):
        c.markdown(f"**{rot}**")
    totais = (df_f.groupby("categoria")["valor"].sum()
              .sort_values(ascending=False))
    for cat in totais.index:
        g = df_f[df_f["categoria"] == cat].sort_values("data", ascending=False)
        st.markdown(f"**{cat}** — {fmt_rs(totais[cat])}")
        for _, r in g.iterrows():
            cs = st.columns([1.1, 3.0, 1.6, 1.2, 1.2, 0.5])
            cs[0].write(r["data"].strftime("%d/%m/%Y"))
            cs[1].write(r["descricao"])
            cs[2].write(r["cartao"])
            npar = int(r["parcelas"]) if r["parcelas"] else 1
            cs[3].write(f"{npar}x" if npar > 1 else "à vista")
            cs[4].write(fmt_rs(r["valor"]))
            if cs[5].button("🗑️", key=f"c_{int(r['_linha'])}",
                            help="Excluir esta compra"):
                excluir_linha(ABA_COMPRAS, int(r["_linha"]),
                              f"🗑️ Compra excluída: {r['descricao']}")
    st.caption("O valor mostrado é o total da compra; as parcelas entram "
               "nas faturas dos meses seguintes — veja em 💳 Cartões.")


def _dividendos(div):
    if div.empty:
        st.info("Nenhum dividendo lançado ainda — registre em ➕ Lançamentos "
                "→ 💎 Dividendos.")
        return
    mes_sel = _seletor_mes(div, "mes_div")
    busca = st.text_input("🔎 Buscar por ativo",
                          key="busca_div").strip().upper()
    df_f = div if mes_sel is None else div[div["mes"] == mes_sel]
    if busca:
        df_f = df_f[df_f["ativo"].str.upper().str.contains(busca, na=False)]
    st.caption(f"{len(df_f)} dividendo(s) — total: "
               f"**{fmt_rs(df_f['valor'].sum())}**")
    if df_f.empty:
        st.info("Nada encontrado com esses filtros.")
        return
    st.divider()
    df_f = _corte(df_f)
    cols = st.columns([1.1, 2.6, 2.6, 1.4, 0.5])
    for c, rot in zip(cols, ["Data", "Ativo", "Conta de destino", "Valor", ""]):
        c.markdown(f"**{rot}**")
    for _, r in df_f.iterrows():
        cs = st.columns([1.1, 2.6, 2.6, 1.4, 0.5])
        cs[0].write(r["data"].strftime("%d/%m/%Y"))
        cs[1].write(r["ativo"])
        cs[2].write(_txt(r.get("conta")))
        cs[3].write(fmt_rs(r["valor"]))
        if cs[4].button("🗑️", key=f"div_{int(r['_linha'])}",
                        help="Excluir este dividendo"):
            excluir_linha(ABA_DIVID, int(r["_linha"]),
                          f"🗑️ Dividendo excluído: {r['ativo']}")


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
               "+ transferências recebidas − transferências enviadas "
               "+ vendas recebidas − investimentos debitados. "
               "Para ajustar o Saldo inicial, edite na planilha (aba Contas).")


def _investimentos():
    compras_inv = ler_aba(ABA_INVEST, {
        "Ativo": "ativo", "Classe": "classe", "Quantidade": "qtd",
        "Total Investido (R$)": "investido",
        "Data da Aplicação": "data_apl", "Conta de Origem": "conta"})
    vendas = ler_vendas()
    linhas = []
    if not compras_inv.empty:
        compras_inv["_linha"] = compras_inv.index + 2
        compras_inv = compras_inv[compras_inv["ativo"] != ""]
        for _, r in compras_inv.iterrows():
            d = converter_datas(pd.Series([r["data_apl"]])).iloc[0]
            linhas.append({
                "data": d, "acao": "🛒 Compra", "ativo": r["ativo"],
                "classe": r["classe"], "qtd": converter_valor(r["qtd"]) or 0.0,
                "valor": converter_valor(r["investido"]) or 0.0,
                "conta": r.get("conta"), "aba": ABA_INVEST,
                "linha": int(r["_linha"])})
    if not vendas.empty:
        for _, r in vendas.iterrows():
            linhas.append({
                "data": r["data"], "acao": "📤 Venda", "ativo": r["ativo"],
                "classe": "—", "qtd": float(r["qtd"]),
                "valor": float(r["valor"]), "conta": r.get("conta_dest"),
                "aba": ABA_VENDAS, "linha": int(r["_linha"])})
    if not linhas:
        st.info("Nenhum investimento ou venda lançado ainda.")
        return
    for l in linhas:
        l["chave"] = pd.Timestamp.min if pd.isna(l["data"]) else l["data"]
    linhas.sort(key=lambda x: x["chave"], reverse=True)
    if len(linhas) > LIMITE:
        st.caption(f"Mostrando os {LIMITE} movimentos mais recentes.")
        linhas = linhas[:LIMITE]
    n_compras = sum(1 for l in linhas if l["acao"] == "🛒 Compra")
    tot_c = sum(l["valor"] for l in linhas if l["acao"] == "🛒 Compra")
    tot_v = sum(l["valor"] for l in linhas if l["acao"] == "📤 Venda")
    st.caption(f"{n_compras} compra(s) e {len(linhas) - n_compras} venda(s) — "
               f"comprado: **{fmt_rs(tot_c)}** · vendido: **{fmt_rs(tot_v)}**")
    st.divider()
    cols = st.columns([1.0, 1.2, 2.0, 1.6, 0.8, 1.2, 1.4, 0.5])
    for c, rot in zip(cols, ["Data", "Ação", "Ativo", "Classe", "Qtd",
                             "Valor", "Conta", ""]):
        c.markdown(f"**{rot}**")
    for l in linhas:
        cs = st.columns([1.0, 1.2, 2.0, 1.6, 0.8, 1.2, 1.4, 0.5])
        cs[0].write("—" if pd.isna(l["data"])
                    else l["data"].strftime("%d/%m/%Y"))
        cs[1].write(l["acao"])
        cs[2].write(l["ativo"])
        cs[3].write(_txt(l["classe"]))
        cs[4].write(f"{l['qtd']:g}")
        cs[5].write(fmt_rs(l["valor"]))
        cs[6].write(_txt(l["conta"]))
        if cs[7].button("🗑️", key=f"mvt_{l['aba']}_{l['linha']}",
                        help="Excluir este lançamento"):
            excluir_linha(l["aba"], l["linha"],
                          f"🗑️ {l['acao']} excluída: {l['ativo']}")
    st.caption("Cada linha é um movimento individual (um aporte ou uma "
               "venda) — dá para excluir um por vez. Excluir uma venda "
               "devolve o valor ao saldo da conta automaticamente.")


def render(desp, rec, contas, inv):
    _, _, _, _, transf, cartoes, compras = ler_tudo()
    div = ler_dividendos()
    st.subheader("📜 Histórico")
    tipo = st.radio("", ["💸 Despesas", "💰 Receitas", "🔁 Transferências",
                         "💳 Compras no cartão", "💎 Dividendos",
                         "🏦 Contas", "📈 Investimentos"], horizontal=True)
    if tipo == "💸 Despesas":
        _movimentos(desp, "despesas", ABA_DESPESAS, True, "d")
    elif tipo == "💰 Receitas":
        _movimentos(rec, "receitas", ABA_RECEITAS, False, "r")
    elif tipo == "🔁 Transferências":
        _transferencias(transf)
    elif tipo == "💳 Compras no cartão":
        _compras(compras)
    elif tipo == "💎 Dividendos":
        _dividendos(div)
    elif tipo == "🏦 Contas":
        _contas(contas)
    else:
        _investimentos()
