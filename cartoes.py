import streamlit as st
import pandas as pd
from helpers import fmt_rs, calcular_faturas


def render(cartoes, compras, contas):
    st.subheader("💳 Cartões de crédito")
    faturas = calcular_faturas(cartoes, compras)

    if not faturas:
        st.info("Nenhum cartão cadastrado ainda. Cadastre em ➕ Lançamentos → "
                "💳 Cartão → 💳 Cadastrar cartão.")
        return

    total_prox = sum(f["faturas"][0]["total"] for f in faturas if f["faturas"])
    disponivel = sum(f["disponivel"] for f in faturas)

    c1, c2 = st.columns(2)
    c1.metric("💳 Próximas faturas (soma dos cartões)", fmt_rs(total_prox))
    c2.metric("✅ Limite disponível (soma)", fmt_rs(disponivel))

    st.divider()
    for f in faturas:
        with st.expander(
                f"💳 {f['cartao']} — fecha dia {f['fechamento']} · "
                f"vence dia {f['vencimento']}", expanded=True):
            linha = cartoes[cartoes["cartao"] == f["cartao"]]
            conta_pag = (linha.iloc[0]["conta_pag"]
                         if not linha.empty and "conta_pag" in linha.columns else "")
            st.caption(f"Bandeira: {f['bandeira'] or '—'} · "
                       f"Limite: {fmt_rs(f['limite'])} · "
                       f"Disponível: {fmt_rs(f['disponivel'])}")
            if conta_pag:
                st.caption(f"Conta de pagamento: {conta_pag}")

            futuras = [x for x in f["faturas"] if x["total"] > 0]
            if not futuras:
                st.info("Nenhuma compra nessa fatura ainda.")
            else:
                df = pd.DataFrame(futuras)
                df["venc_label"] = df["vencimento"].apply(
                    lambda d: d.strftime("%d/%m/%Y"))
                st.dataframe(
                    df[["venc_label", "total"]],
                    use_container_width=True, hide_index=True,
                    column_config={
                        "venc_label": st.column_config.TextColumn(
                            "Vencimento da fatura"),
                        "total": st.column_config.NumberColumn(
                            "Valor a pagar", format="R$ %.2f")})

            st.caption("Quando pagar a fatura, registre uma 💸 Despesa com a "
                       "categoria **Fatura do cartão**, na conta de "
                       "pagamento — o saldo da conta cai automaticamente.")
