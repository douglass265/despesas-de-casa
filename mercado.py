"""Cotacoes e indices: B3, exterior, cripto e CDI.

Cada numero aqui vem de uma fonte publica identificada, para que a tela possa
dizer de onde saiu:

- acoes e FIIs da B3        -> Yahoo Finance, ticker + ".SA"
- ETFs e acoes no exterior  -> Yahoo Finance, ticker em dolar
- cripto                    -> CoinGecko, ja em real
- dolar                     -> Yahoo Finance
- CDI                       -> Banco Central, serie SGS 11 (taxa diaria)

Regra do fechamento: mostra o ultimo pregao ENCERRADO. Durante o pregao isso e
o fechamento do dia anterior; depois das 18h (horario de Brasilia) passa a ser
o fechamento do proprio dia, porque a sessao ja terminou.
"""

from datetime import date, datetime, timedelta, UTC
from zoneinfo import ZoneInfo

import requests
import streamlit as st

FUSO_BR = ZoneInfo("America/Sao_Paulo")
URL_SPARK = "https://query2.finance.yahoo.com/v8/finance/spark"
URL_CDI = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.11"
URL_CRIPTO = "https://api.coingecko.com/api/v3/simple/price"

CABECALHO = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/121.0 Safari/537.36"),
    "Accept": "application/json,text/plain,*/*",
}

# nome na planilha -> id no CoinGecko (cotacao em real)
MOEDAS = {
    "BTC": "bitcoin", "BITCOIN": "bitcoin",
    "ETH": "ethereum", "ETHEREUM": "ethereum",
    "USDC": "usd-coin", "USDT": "tether",
    "SOL": "solana", "ADA": "cardano", "XRP": "ripple",
    "DOGE": "dogecoin", "BNB": "binancecoin", "LTC": "litecoin",
}


def agora_br():
    return datetime.now(FUSO_BR)


def _ultima_sessao_encerrada():
    """Data do ultimo pregao cujo fechamento ja e definitivo."""
    agora = agora_br()
    # depois das 18h a sessao do dia ja fechou
    if agora.hour >= 18:
        return agora.date()
    return agora.date() - timedelta(days=1)


@st.cache_data(ttl=1800, show_spinner=False)
def cotacoes_fechamento(tickers, sem_sufixo=()):
    """Fechamento do ultimo pregao encerrado, na moeda do ativo.

    `tickers` sao os nomes como estao na planilha (ex.: ("PETR4", "XPML11")).
    `sem_sufixo` lista os que NAO sao da B3 e ja sao o simbolo completo
    (ex.: ("VYM", "KO")), para nao receberem o ".SA".
    Devolve {ticker: {"fech": float, "data": date, "var": float}}.
    Ticker sem resposta simplesmente nao aparece, e a tela cai para o preco
    que o usuario digitou em vez de inventar um numero.
    """
    saida = {}
    if not tickers:
        return saida
    externos = {str(t).strip().upper() for t in sem_sufixo}
    simbolos = [t if ("=" in t or str(t).strip().upper() in externos)
                else f"{t}.SA" for t in tickers]
    limite = _ultima_sessao_encerrada()

    for i in range(0, len(simbolos), 8):
        lote = simbolos[i:i + 8]
        try:
            r = requests.get(URL_SPARK,
                             params={"symbols": ",".join(lote),
                                     "range": "1mo", "interval": "1d"},
                             headers=CABECALHO, timeout=20)
            if r.status_code != 200:
                continue
            dados = r.json()
        except Exception:
            continue
        if not isinstance(dados, dict):
            continue
        for simbolo, bloco in dados.items():
            if not isinstance(bloco, dict) or not bloco.get("close"):
                continue
            ticker = simbolo.replace(".SA", "")
            try:
                sessoes = []
                for marca, valor in zip(bloco.get("timestamp") or [],
                                        bloco.get("close") or []):
                    if valor is None:
                        continue
                    sessoes.append((datetime.fromtimestamp(marca, UTC).date(),
                                    float(valor)))
                sessoes.sort()
                validas = [s for s in sessoes if s[0] <= limite]
                if not validas:
                    continue
                dia, fech = validas[-1]
                var = 0.0
                if len(validas) >= 2 and validas[-2][1]:
                    var = (fech - validas[-2][1]) / validas[-2][1] * 100.0
                saida[ticker] = {"fech": fech, "data": dia, "var": var}
            except Exception:
                continue
    return saida


@st.cache_data(ttl=1800, show_spinner=False)
def cotacoes_cripto(moeda_dolar=None):
    """Cripto em real pelo CoinGecko (fonte publica, sem chave).

    Devolve {ticker_planilha: {"fech": float, "var": float}}.
    """
    saida = {}
    ids = sorted(set(MOEDAS.values()))
    try:
        r = requests.get(URL_CRIPTO,
                         params={"ids": ",".join(ids), "vs_currencies": "brl",
                                 "include_24hr_change": "true"},
                         headers=CABECALHO, timeout=20)
        if r.status_code != 200:
            return saida
        dados = r.json()
    except Exception:
        return saida
    if not isinstance(dados, dict):
        return saida
    for ticker, ident in MOEDAS.items():
        bloco = dados.get(ident)
        if not bloco or "brl" not in bloco:
            continue
        saida[ticker] = {"fech": float(bloco["brl"]),
                         "var": float(bloco.get("brl_24h_change") or 0.0)}
    return saida


@st.cache_data(ttl=43200, show_spinner=False)
def cdi_do_periodo(dias):
    """CDI acumulado em % no periodo (pro rata die), serie SGS 11."""
    if not dias or dias < 1:
        return None
    fim = agora_br().date()
    ini = fim - timedelta(days=dias)
    try:
        r = requests.get(f"{URL_CDI}/dados",
                         params={"formato": "json",
                                 "dataInicial": ini.strftime("%d/%m/%Y"),
                                 "dataFinal": fim.strftime("%d/%m/%Y")},
                         headers=CABECALHO, timeout=25)
        if r.status_code != 200:
            return None
        dados = r.json()
    except Exception:
        return None
    if not dados:
        return None
    acumulado = 1.0
    lidos = 0
    for linha in dados:
        try:
            taxa = float(str(linha["valor"]).replace(",", "."))
        except (KeyError, ValueError, TypeError):
            continue
        acumulado *= 1.0 + taxa / 100.0
        lidos += 1
    if not lidos:
        return None
    return (acumulado - 1.0) * 100.0


def valor_renda_fixa(valor_aplicado, pct_cdi, data_apl):
    """Valor estimado hoje de um CDB/LCI a X% do CDI, pro rata die."""
    if valor_aplicado is None or valor_aplicado <= 0:
        return None
    if data_apl is None:
        return None
    try:
        if data_apl != data_apl:  # NaT
            return None
    except Exception:
        pass
    dias = (agora_br().date() - data_apl.date()).days
    if dias < 1:
        return None
    cdi = cdi_do_periodo(dias)
    if cdi is None:
        return None
    return valor_aplicado * (1.0 + (cdi / 100.0) * (pct_cdi / 100.0))


def cdi_ultima_taxa():
    """Taxa do CDI do dia, em % (informativo)."""
    try:
        r = requests.get(f"{URL_CDI}/dados/ultimos/1",
                         params={"formato": "json"},
                         headers=CABECALHO, timeout=15)
        if r.status_code != 200:
            return None
        dados = r.json()
        if not dados:
            return None
        return float(str(dados[-1]["valor"]).replace(",", "."))
    except Exception:
        return None


@st.cache_data(ttl=1800, show_spinner=False)
def dolar_fechamento():
    """Dolar comercial: fechamento do ultimo pregao e a data dele."""
    info = cotacoes_fechamento(("USDBRL=X",))
    bloco = info.get("USDBRL=X")
    if bloco and bloco.get("fech"):
        return {"valor": bloco["fech"], "data": bloco["data"],
                "var": bloco.get("var", 0.0)}
    return None


def cotacao_dolar():
    """So o numero do dolar, para quem nao precisa da data."""
    info = dolar_fechamento()
    return info["valor"] if info else None
