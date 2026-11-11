import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import date
from helpers import (fmt_rs, fmt_pct, barra_h, MESES_PT, ler_tudo,
                     ler_dividendos, calcular_faturas, rentabilidade_total_row)


def render(desp, rec, contas, inv):
    st.title("📊 Painel geral")
    hoje = pd.Period(date.today(), freq="M")
    desp_mes = desp[desp["mes"] == hoje]["valor"].sum() if not desp.empty else 0.0
    rec_mes = rec[rec["mes"] == hoje]["valor"].sum() if not rec.empty else 0.0
    total_contas = contas["saldo"].sum() if not contas.empty else 0.0
    total_inv = inv["investido"].sum() if not inv.empty else 0.0
    val_atual = inv["atual"].sum() if not inv.empty else 0.0

    div = ler_dividendos()
    div_total = float(div["valor"].sum()) if not div.empty else 0.0
    div_mes = float(div[div["mes"] == hoje]["valor"].sum()) if not div.empty else 0.0
    div_por_ativo = (div.groupby("ativo")["valor"].sum().to_dict()
                     if not div.empty else {})
    rentab = ((val_atual - total_inv + div_total) / total_inv * 100.0
              if total_inv > 0 else 0.0)

    m1, m2 = st.columns(2)
    m1.metric("🏦 Saldo total das contas", fmt_rs(total_contas))
    m2.metric("💼 Patrimônio investido", fmt_rs(val_atual))
    p1, p2, p3 = st.columns(3)
    p1.metric("💰 Total aplicado", fmt_rs(total_inv))
    p2.metric("💎 Dividendos recebidos", fmt_rs(div_total))
    p3.metric("🎯 Rentabilidade total", fmt_pct(rentab))
    q1, q2 = st.columns(2)
    q1.metric(f"⚖️ Saldo de {MESES_PT[hoje.month - 1]} (rec. − desp.)",
              fmt_rs(rec_mes - desp_mes))
    q2.metric(f"💎 Dividendos de {MESES_PT[hoje.month - 1]}", fmt_rs(div_mes))

    _, _, _, _, _, cartoes_f, compras_f = ler_tudo()
    faturas = calcular_faturas(cartoes_f, compras_f)
    if faturas:
        st.divider()
        st.subheader("💳 Faturas a pagar")
        for i in range(0, len(faturas), 4):
            grupo = faturas[i:i + 4]
            cols = st.columns(len(grupo))
            for col, f in zip(cols, grupo):
                prox = f["faturas"][0] if f["faturas"] else None
                total_prox = prox["total"] if prox else 0.0
                delta = (f"vence {prox['vencimento'].strftime('%d/%m')}"
                         if prox and total_prox > 0 else "nada a pagar")
                col.metric(f"💳 {f['cartao']}", fmt_rs(total_prox),
                           delta=delta, delta_color="off")
                col.caption(f"Disponível: {fmt_rs(f['disponivel'])}")

    st.divider()
    st.subheader("📈 Minha carteira")
    if inv.empty or val_atual == 0:
        st.info("Nenhum investimento com valor ainda. Lance no menu ➕ Lançamentos.")
    else:
        c1, c2 = st.columns([2, 3])
        with c1:
            dist = inv.groupby("classe", as_index=False)["atual"].sum()
            dist = dist[dist["atual"] > 0]
            fig = px.pie(dist, names="classe", values="atual", hole=0.55,
                         title="Distribuição por classe")
            fig.update_layout(margin=dict(l=10, r=10, t=40, b=10),
                              legend_font_size=11)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            tb = inv.copy()
            tb["rent_total"] = tb.apply(
                lambda r: rentabilidade_total_row(
                    r, div_por_ativo.get(r["ativo"], 0.0)), axis=1)
            tb["div_receb"] = tb["ativo"].map(lambda a: div_por_ativo.get(a, 0.0))
            tb = tb.sort_values("atual", ascending=False)
            st.dataframe(
                tb[["ativo", "classe", "qtd", "pm", "pa", "investido",
                    "atual", "rent_total", "div_receb"]],
                use_container_width=True, hide_index=True,
                column_config={
                    "ativo": "Ativo", "classe": "Classe",
                    "qtd": st.column_config.NumberColumn("Qtd", format="%.4f"),
                    "pm": st.column_config.NumberColumn("Preço médio", format="R$ %.2f"),
                    "pa": st.column_config.NumberColumn("Preço atual", format="R$ %.2f"),
                    "investido": st.column_config.NumberColumn("Investido", format="R$ %.2f"),
                    "atual": st.column_config.NumberColumn("Valor atual", format="R$ %.2f"),
                    "rent_total": st.column_config.NumberColumn("Rent. c/ dividendos", format="%.2f%%"),
                    "div_receb": st.column_config.NumberColumn("Dividendos", format="R$ %.2f")})

    st.divider()
    st.subheader("🏦 Minhas contas")
    if contas.empty:
        st.info("Nenhuma conta cadastrada ainda.")
    else:
        cc1, cc2 = st.columns([3, 2])
        with cc1:
            st.plotly_chart(
                barra_h(contas.sort_values("saldo"), "conta", "saldo",
                        "Saldo por conta (calculado)"),
                use_container_width=True)
        with cc2:
            st.dataframe(
                contas[["conta", "tipo", "saldo"]],
                use_container_width=True, hide_index=True,
                column_config={"conta": "Conta", "tipo": "Tipo",
                               "saldo": st.column_config.NumberColumn(
                                   "Saldo", format="R$ %.2f")})

    st.divider()
    st.subheader("💵 Despesas × Receitas")
    meses = set()
    if not desp.empty:
        meses |= set(desp["mes"].unique())
    if not rec.empty:
        meses |= set(rec["mes"].unique())
    meses = sorted(meses, reverse=True)
    opcoes = {"Todos os meses": None}
    for m in meses:
        opcoes[f"{MESES_PT[m.month - 1]} {m.year}"] = m
    mes_label = st.selectbox("Período", list(opcoes.keys()))
    mes_sel = opcoes[mes_label]
    d_f = desp if mes_sel is None else desp[desp["mes"] == mes_sel]
    r_f = rec if mes_sel is None else rec[rec["mes"] == mes_sel]

    if meses:
        evo_d = (desp.groupby("mes", as_index=False)["valor"].sum()
                 .rename(columns={"valor": "Despesas"}) if not desp.empty
                 else pd.DataFrame(columns=["mes", "Despesas"]))
        evo_r = (rec.groupby("mes", as_index=False)["valor"].sum()
                 .rename(columns={"valor": "Receitas"}) if not rec.empty
                 else pd.DataFrame(columns=["mes", "Receitas"]))
        evo = pd.merge(evo_d, evo_r, on="mes", how="outer").sort_values("mes")
        evo["rotulo"] = evo["mes"].apply(
            lambda p: f"{MESES_PT[p.month - 1]}/{str(p.year)[2:]}")
        evo_melt = evo.melt(id_vars="rotulo",
                            value_vars=["Despesas", "Receitas"],
                            var_name="Tipo", value_name="valor")
        fig_e = px.bar(evo_melt, x="rotulo", y="valor", color="Tipo",
                       barmode="group",
                       color_discrete_map={"Despesas": "#d93025",
                                           "Receitas": "#0f9d58"},
                       title="Evolução mês a mês")
        fig_e.update_layout(xaxis_title=None, yaxis_title=None,
                            margin=dict(l=10, r=10, t=40, b=10),
                            legend_font_size=11)
        st.plotly_chart(fig_e, use_container_width=True)

    g1, g2 = st.columns(2)
    with g1:
        if d_f.empty:
            st.info("Sem despesas nesse período.")
        else:
            gc = d_f.groupby("categoria", as_index=False)["valor"].sum()
            gc = gc.sort_values("valor")
            st.plotly_chart(
                barra_h(gc, "categoria", "valor",
                        f"Despesas por categoria — {mes_label}"),
                use_container_width=True)
    with g2:
        if r_f.empty:
            st.info("Sem receitas nesse período.")
        else:
            gr = r_f.groupby("categoria", as_index=False)["valor"].sum()
            gr = gr.sort_values("valor")
            st.plotly_chart(
                barra_h(gr, "categoria", "valor",
                        f"Receitas por categoria — {mes_label}"),
                use_container_width=True)

    st.divider()
    with st.expander(f"📋 Ver lançamentos — {mes_label}", expanded=False):
        abas = st.tabs(["Despesas", "Receitas"])
        with abas[0]:
            if d_f.empty:
                st.info("Nenhuma despesa.")
            else:
                st.dataframe(
                    d_f.sort_values("data", ascending=False)[
                        ["data", "descricao", "categoria", "valor", "forma", "conta"]],
                    use_container_width=True, hide_index=True,
                    column_config={
                        "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                        "descricao": "Descrição", "categoria": "Categoria",
                        "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
                        "forma": "Pagamento", "conta": "Conta"})
        with abas[1]:
            if r_f.empty:
                st.info("Nenhuma receita.")
            else:
                st.dataframe(
                    r_f.sort_values("data", ascending=False)[
                        ["data", "descricao", "categoria", "valor", "conta"]],
                    use_container_width=True, hide_index=True,
                    column_config={
                        "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                        "descricao": "Descrição", "categoria": "Categoria",
                        "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
                        "conta": "Conta"})
