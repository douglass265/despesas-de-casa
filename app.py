import streamlit as st
from helpers import (INFO, SECRETS_EXEMPLO, caminhos_de_chaves, ler_tudo)

st.set_page_config(page_title="Finanças da Casa", page_icon="🏠", layout="wide")

if INFO is None:
    st.title("🏠 Finanças da Casa")
    st.error("Não encontrei as credenciais do Google no Secrets deste app.")
    estrutura = caminhos_de_chaves(st.secrets)
    st.caption("Estrutura detectada (somente nomes): "
               + (", ".join(estrutura) if estrutura else "nenhuma"))
    st.code(SECRETS_EXEMPLO, language="toml")
    st.stop()

try:
    desp, rec, contas, inv = ler_tudo()
except Exception as e:
    st.error("Não consegui acessar a planilha do Google.")
    st.code(str(e))
    st.markdown("**Causas comuns:** a conta de serviço saiu do compartilhamento "
                "da planilha (precisa estar como **Editor**) ou a **Google "
                "Sheets API** está desativada no projeto do Google Cloud.")
    st.stop()

if "msg_ok" in st.session_state:
    st.success(st.session_state.pop("msg_ok"))

st.sidebar.title("🏠 Finanças da Casa")
pagina = st.sidebar.radio("Navegar", ["📊 Painel", "➕ Lançamentos",
                                      "📜 Histórico"])
if st.sidebar.button("🔄 Atualizar dados", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

if pagina == "📊 Painel":
    from painel import render
    render(desp, rec, contas, inv)
elif pagina == "➕ Lançamentos":
    from lancamentos import render
    render()
else:
    from historico import render
    render(desp, rec, contas, inv)
