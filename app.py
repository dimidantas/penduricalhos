# app.py
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="IRPF x Judiciário — Comparador",
    page_icon="⚖️",
    layout="wide",
)

CSV_PATH = "base_dashboard_irpf_2020_2023.csv"
OCUP_JUD = "Membro do Poder Judiciário e de Tribunal de Contas"
ANO_MIN = 2021  # remove 2020

# =========================
# ESTILO (leve, bonito, sem exagero)
# =========================
st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; padding-bottom: 2.5rem; }
      h1, h2, h3 { letter-spacing: -0.02em; }
      .bigline {
        font-size: 34px;
        font-weight: 800;
        line-height: 1.08;
        margin: 0.2rem 0 0.6rem 0;
      }
      .subline {
        font-size: 14px;
        opacity: 0.75;
        margin-top: -0.2rem;
      }
      .card {
        padding: 16px 18px;
        border: 1px solid rgba(0,0,0,0.08);
        border-radius: 16px;
        background: rgba(255,255,255,0.7);
        box-shadow: 0 2px 10px rgba(0,0,0,0.04);
      }
      .muted { opacity: 0.75; }
      .kpi {
        font-size: 44px;
        font-weight: 900;
        letter-spacing: -0.02em;
        margin: 0;
      }
      .kpi_label {
        font-size: 14px;
        opacity: 0.78;
        margin-top: -6px;
      }
      .note {
        font-size: 12px;
        opacity: 0.7;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# HELPERS
# =========================
def fmt_moeda(x):
    if pd.isna(x):
        return "—"
    return "R$ " + f"{x:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_pct(x, casas=1):
    if pd.isna(x):
        return "—"
    return f"{x*100:.{casas}f}%"

def fmt_x(x, casas=1):
    if pd.isna(x) or np.isinf(x):
        return "—"
    return f"{x:.{casas}f}x"

def safe_div(a, b):
    return np.nan if (b is None or b == 0 or pd.isna(b)) else a / b

# =========================
# LOAD
# =========================
@st.cache_data
def load_data(path):
    df = pd.read_csv(path)
    df["ano_base"] = df["ano_base"].astype(int)
    df["uf"] = df["uf"].astype(str)
    df["ocupacao_principal"] = df["ocupacao_principal"].astype(str)
    return df

try:
    df = load_data(CSV_PATH)
except Exception as e:
    st.error(f"Não consegui ler o arquivo {CSV_PATH}. Erro: {e}")
    st.stop()

# Remove 2020
df = df[df["ano_base"] >= ANO_MIN].copy()

# =========================
# HEADER
# =========================
st.title("⚖️ IRPF x Judiciário — Comparador por UF e Ocupação")
st.markdown(
    '<div class="subline">Compare sua ocupação com <b>membros do Judiciário</b> na mesma UF, usando dados agregados do IRPF (2021–2023).</div>',
    unsafe_allow_html=True
)

# =========================
# SIDEBAR CONTROLS
# =========================
ufs = sorted(df["uf"].unique().tolist())
ocupacoes = sorted(df["ocupacao_principal"].unique().tolist())

with st.sidebar:
    st.header("Filtros")
    uf_sel = st.selectbox("UF", ufs, index=ufs.index("São Paulo") if "São Paulo" in ufs else 0)

    # ocupações disponíveis na UF escolhida
    ocup_uf = sorted(df.loc[df["uf"] == uf_sel, "ocupacao_principal"].unique().tolist())
    # remover a ocupação do judiciário da lista do usuário (para evitar comparar judiciário vs judiciário)
    ocup_uf_user = [o for o in ocup_uf if o != OCUP_JUD]

    ocup_sel = st.selectbox("Sua ocupação", ocup_uf_user, index=0)

    anos_disponiveis = sorted(df["ano_base"].unique().tolist())
    anos_sel = st.multiselect("Anos (para 'em média')", anos_disponiveis, default=anos_disponiveis)

    st.markdown("---")
    st.caption("Obs.: 2020 foi removido por outliers/estranhezas na série.")

# =========================
# DATA FILTERED
# =========================
d = df[(df["uf"] == uf_sel) & (df["ano_base"].isin(anos_sel))].copy()

d_user = d[d["ocupacao_principal"] == ocup_sel].copy()
d_jud  = d[d["ocupacao_principal"] == OCUP_JUD].copy()

if d_user.empty:
    st.warning("Não encontrei dados para essa ocupação/UF/anos selecionados.")
    st.stop()
if d_jud.empty:
    st.warning(f"Não encontrei dados do Judiciário para UF={uf_sel} nos anos selecionados.")
    st.stop()

# =========================
# AGREGAR "EM MÉDIA" (ponderado)
# - renda média por contribuinte: soma(rend_total) / soma(contribuintes)
# - % isento: soma(isento) / soma(rend_total)
# - alíquota efetiva paga: soma(imposto_pago)/soma(rend_total)
# =========================
def agregados_ponderados(df_part):
    tot_contrib = df_part["qtde_contribuintes"].sum()
    tot_rend = df_part["rend_total"].sum()
    tot_isento = df_part["rend_isentos_e_nao_tributaveis"].sum()
    tot_pago = df_part["imposto_pago"].sum()
    tot_devido = df_part["imposto_devido_total"].sum()

    renda_media = safe_div(tot_rend, tot_contrib)
    pct_isento = safe_div(tot_isento, tot_rend)
    aliq_paga = safe_div(tot_pago, tot_rend)
    aliq_devida = safe_div(tot_devido, tot_rend)

    return {
        "tot_contrib": tot_contrib,
        "tot_rend": tot_rend,
        "tot_isento": tot_isento,
        "tot_pago": tot_pago,
        "tot_devido": tot_devido,
        "renda_media": renda_media,
        "pct_isento": pct_isento,
        "aliq_paga": aliq_paga,
        "aliq_devida": aliq_devida,
        "isento_medio": (renda_media * pct_isento) if (not pd.isna(renda_media) and not pd.isna(pct_isento)) else np.nan
    }

agg_user = agregados_ponderados(d_user)
agg_jud  = agregados_ponderados(d_jud)

ratio_renda = safe_div(agg_jud["renda_media"], agg_user["renda_media"])
dif_aliq_paga_pp = (agg_jud["aliq_paga"] - agg_user["aliq_paga"]) * 100 if (not pd.isna(agg_jud["aliq_paga"]) and not pd.isna(agg_user["aliq_paga"])) else np.nan

# =========================
# KPI SECTION
# =========================
colA, colB = st.columns([1.15, 0.85], gap="large")

with colA:
    st.markdown('<div class="card">', unsafe_allow_html=True)

    st.markdown(
        f'<div class="bigline">Um juiz recebeu <span style="text-decoration: underline;">{fmt_x(ratio_renda, 1)}</span> mais que você</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        f'<div class="subline">Média anual por contribuinte (anos selecionados), UF: <b>{uf_sel}</b></div>',
        unsafe_allow_html=True
    )

    k1, k2, k3 = st.columns(3)

    with k1:
        st.markdown(f'<div class="kpi">{fmt_moeda(agg_user["renda_media"])}</div>', unsafe_allow_html=True)
        st.markdown('<div class="kpi_label">Sua renda média</div>', unsafe_allow_html=True)

    with k2:
        st.markdown(f'<div class="kpi">{fmt_moeda(agg_jud["renda_media"])}</div>', unsafe_allow_html=True)
        st.markdown('<div class="kpi_label">Renda média do Judiciário</div>', unsafe_allow_html=True)

    with k3:
        st.markdown(f'<div class="kpi">{fmt_moeda(agg_jud["isento_medio"])}</div>', unsafe_allow_html=True)
        st.markdown('<div class="kpi_label">Isento médio do Judiciário</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

with colB:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="bigline">Comparação tributária</div>', unsafe_allow_html=True)
    st.markdown('<div class="subline">Alíquota efetiva paga e parcela isenta</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Sua alíquota efetiva paga", fmt_pct(agg_user["aliq_paga"], 1))
        st.metric("Sua % de renda isenta", fmt_pct(agg_user["pct_isento"], 1))

    with c2:
        st.metric("Alíquota efetiva paga (Judiciário)", fmt_pct(agg_jud["aliq_paga"], 1), delta=f"{dif_aliq_paga_pp:.1f} p.p." if not pd.isna(dif_aliq_paga_pp) else None)
        st.metric("% de renda isenta (Judiciário)", fmt_pct(agg_jud["pct_isento"], 1))

    st.markdown(
        '<div class="note">* Alíquotas efetivas são calculadas como imposto pago / rendimentos totais (agregado).</div>',
        unsafe_allow_html=True
    )
    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# SERIES (ano a ano)
# =========================
# juntar user + jud por ano
series_cols = ["ano_base", "rend_total_por_contrib", "pct_isento", "aliq_efetiva_paga"]

u = d_user[series_cols].rename(columns={
    "rend_total_por_contrib": "renda_media",
    "pct_isento": "pct_isento",
    "aliq_efetiva_paga": "aliq_paga"
}).copy()
u["grupo"] = ocup_sel

j = d_jud[series_cols].rename(columns={
    "rend_total_por_contrib": "renda_media",
    "pct_isento": "pct_isento",
    "aliq_efetiva_paga": "aliq_paga"
}).copy()
j["grupo"] = "Judiciário"

s = pd.concat([u, j], ignore_index=True).sort_values(["ano_base", "grupo"])

# pivot para razão anual (Jud / User)
pivot = s.pivot_table(index="ano_base", columns="grupo", values="renda_media", aggfunc="mean").reset_index()
if "Judiciário" in pivot.columns and ocup_sel in pivot.columns:
    pivot["vezes_mais"] = pivot["Judiciário"] / pivot[ocup_sel]
else:
    pivot["vezes_mais"] = np.nan

# =========================
# CHARTS
# =========================
st.markdown("## 📈 Séries temporais (UF selecionada)")

cL, cR = st.columns(2, gap="large")

with cL:
    # gráfico 1: quantas vezes mais
    fig1 = px.line(
        pivot,
        x="ano_base",
        y="vezes_mais",
        markers=True,
        title="Quantas vezes o Judiciário recebeu mais (média por contribuinte)"
    )
    fig1.update_layout(xaxis_title="Ano-base", yaxis_title="Vezes (Judiciário / Você)")
    st.plotly_chart(fig1, use_container_width=True)

with cR:
    # gráfico 2: % isento (duas linhas)
    fig2 = px.line(
        s,
        x="ano_base",
        y="pct_isento",
        color="grupo",
        markers=True,
        title="% da renda isenta (Você vs Judiciário)"
    )
    fig2.update_layout(xaxis_title="Ano-base", yaxis_title="% isento")
    fig2.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig2, use_container_width=True)

# =========================
# TABELA (opcional, útil para transparência)
# =========================
with st.expander("Ver tabela ano a ano (transparência)"):
    # montar tabela amigável
    t = s.copy()
    t["renda_media"] = t["renda_media"].map(lambda x: fmt_moeda(x))
    t["pct_isento"] = t["pct_isento"].map(lambda x: fmt_pct(x, 1))
    t["aliq_paga"] = t["aliq_paga"].map(lambda x: fmt_pct(x, 1))
    t = t.rename(columns={"ano_base": "Ano", "grupo": "Grupo", "renda_media": "Renda média", "pct_isento": "% isento", "aliq_paga": "Alíquota paga"})
    st.dataframe(t[["Ano", "Grupo", "Renda média", "% isento", "Alíquota paga"]], use_container_width=True)

st.markdown(
    """
    <div class="note">
      ⚠️ Observação metodológica: os dados são agregados por UF e ocupação. “Rendimentos isentos” incluem várias naturezas
      e não identificam, individualmente, verbas indenizatórias específicas.
    </div>
    """,
    unsafe_allow_html=True
)
