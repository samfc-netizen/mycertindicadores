import re
import unicodedata
from io import BytesIO

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ============================================================
# DASHBOARD CRM CERTIFICADOS - MY CERT
# Upload de planilha Excel com colunas:
# Data, Nome, CPF/CNPJ, PARCEIRO, Modelo, Pedido, Valor, Vendedor, AGR, Origem
# ============================================================

st.set_page_config(
    page_title="Dashboard Certificados | CRM",
    page_icon="📊",
    layout="wide",
)

CUSTO_CERTIFICADO = 29.25

# Regras de valor para parceiros.
# Observação: CORPAD apareceu duas vezes na solicitação, com 65 e 50.
# Como a última regra enviada foi 50, o código considera CORPAD = 50.
VALORES_PARCEIROS = {
    "CORPAD SOLUCOES EMPRESARIAIS E INFORMATICA LTDA.": 50.00,
    "CONFIT INTELIGENCIA FISCAL E CONTABIL LTDA": 65.00,
    "BARUCCI CONTABILIDADE LTDA": 69.00,
    "SUPORT CONDOMINIOS - Alexandre Silva": 70.00,
    "VILA21 CONDOMINIOS LTDA": 70.00,
    "64.846.726 CINTIA ALBINO RODRIGUES LOPES": 70.00,
    "MOVIMA - ASSESSORIA & COPIAS IPAUSSUENSE LTDA": 70.00,
    "SOLUCOES ADMINISTRACAO E ASSESSORIA A CONDOMINIOS LTDA": 85.00,
    "SEVEN STARS SERVICOS LTDA": 89.00,
    "EDICLEIA BRITO DOS SANTOS": 89.92,
    "ENI ASSESSORIA EMPRESARIAL E CERTIFICACAO DIGITAL LTDA": 95.00,
    "GIGA COMERCIAL DE SOFTWARE LTDA": 105.00,
    "ADIPRON SERVICOS EM EQUIPAMENTOS DE INFORMATICA LTDA": 105.00,
    "LAVINIA DARA BARROS": 60.00,
    "M A B CAVALCANTE GS.DATA": 105.00,
}
PARCEIRO_FUNCEF = "FUNDACAO DOS ECONOMIARIOS FEDERAIS FUNCEF"

# -----------------------------
# Estilo visual
# -----------------------------
st.markdown(
    """
    <style>
    .main .block-container {padding-top: 1.3rem; padding-bottom: 2rem;}
    .hero {
        background: linear-gradient(120deg, #0f172a 0%, #1e3a8a 50%, #0369a1 100%);
        padding: 26px 30px;
        border-radius: 22px;
        color: white;
        margin-bottom: 20px;
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.18);
    }
    .hero h1 {margin: 0; font-size: 34px; font-weight: 850;}
    .hero p {margin: 8px 0 0 0; color: #dbeafe; font-size: 15px;}
    .info-card {
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 16px 18px;
        background: white;
        box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
        margin-bottom: 10px;
    }
    .info-card .label {font-size: 13px; color: #64748b; margin-bottom: 6px;}
    .info-card .value {font-size: 24px; font-weight: 800; color: #0f172a;}
    .info-card .small {font-size: 12px; color: #64748b; margin-top: 4px;}
    div[data-testid="stMetricValue"] {font-size: 26px; font-weight: 800;}
    div[data-testid="stMetricLabel"] {font-size: 14px; color: #475569;}
    .section-title {font-size: 22px; font-weight: 800; color: #0f172a; margin-top: 8px; margin-bottom: 8px;}
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Funções auxiliares
# -----------------------------
def normalize_text(value) -> str:
    if pd.isna(value):
        return ""
    s = str(value).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_key(value) -> str:
    s = normalize_text(value).upper()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_money(value) -> float:
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "null", "-"}:
        return 0.0
    s = s.replace("R$", "").replace("\u00a0", " ").strip()
    s = re.sub(r"[^0-9,.-]", "", s)
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def format_brl(value) -> str:
    try:
        return "R$ " + f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def format_pct(value) -> str:
    try:
        return f"{float(value) * 100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00%"


def find_header_row(raw: pd.DataFrame) -> int:
    required = {"data", "pedido", "valor", "origem"}
    for idx, row in raw.iterrows():
        vals = {normalize_key(x).lower() for x in row.tolist() if str(x).strip() != "nan"}
        if required.issubset(vals):
            return int(idx)
    # fallback: procura a linha que contenha Pedido
    for idx, row in raw.iterrows():
        vals = [normalize_key(x).lower() for x in row.tolist()]
        if "pedido" in vals:
            return int(idx)
    raise ValueError("Não encontrei a linha de cabeçalho. Verifique se a planilha possui a coluna Pedido.")


def split_nome_cpf_parceiro(valor):
    """Extrai Nome, CPF/CNPJ e Parceiro quando vêm juntos na mesma coluna Nome."""
    texto = normalize_text(valor)
    if not texto:
        return "", "", ""

    cpf_cnpj = ""
    parceiro = ""
    nome = texto

    # Ex.: Nome CPF/CNPJ: 00.000.000/0001-00Parceiro: ABC LTDA
    m_cpf = re.search(r"CPF\s*/\s*CNPJ\s*:\s*(.*?)(?=Parceiro\s*:|$)", texto, flags=re.I)
    if m_cpf:
        cpf_cnpj = normalize_text(m_cpf.group(1))
        nome = normalize_text(texto[:m_cpf.start()])

    m_parc = re.search(r"Parceiro\s*:\s*(.*)$", texto, flags=re.I)
    if m_parc:
        parceiro = normalize_text(m_parc.group(1))

    return nome, cpf_cnpj, parceiro


def _read_html_xls(uploaded_file) -> pd.DataFrame:
    """Lê relatórios .xls que são HTML disfarçado de Excel."""
    try:
        uploaded_file.seek(0)
    except Exception:
        pass
    tabelas = pd.read_html(uploaded_file)
    if not tabelas:
        raise ValueError("Nenhuma tabela encontrada no arquivo .xls/html.")
    df = tabelas[0].copy()

    # Se a primeira linha contém cabeçalhos reais, usa como cabeçalho.
    primeira = [normalize_text(x) for x in df.iloc[0].tolist()]
    if any(normalize_key(x) == "PEDIDO" for x in primeira) and any(normalize_key(x) == "DATA" for x in primeira):
        df.columns = primeira
        df = df.iloc[1:].reset_index(drop=True)
    return df


def _read_excel_normal(uploaded_file, sheet_name: str) -> pd.DataFrame:
    try:
        uploaded_file.seek(0)
    except Exception:
        pass
    raw = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=None)
    header_row = find_header_row(raw)
    cols = raw.iloc[header_row].tolist()
    df = raw.iloc[header_row + 1:].copy()
    df.columns = [normalize_text(c) for c in cols]
    return df


def read_excel_dashboard(uploaded_file, sheet_name: str | None = None, force_html: bool = False) -> pd.DataFrame:
    """
    Lê dois formatos:
    1) XLSX/Excel normal com colunas separadas: Data, Nome, CPF/CNPJ, PARCEIRO, Modelo, Pedido, Valor, Vendedor, AGR, Origem.
    2) XLS/HTML do sistema, onde a coluna Nome vem com Nome + CPF/CNPJ + Parceiro no mesmo texto.
    """
    if force_html:
        df = _read_html_xls(uploaded_file)
    else:
        try:
            df = _read_excel_normal(uploaded_file, sheet_name)
        except Exception:
            df = _read_html_xls(uploaded_file)

    df = df.dropna(how="all").copy()

    # Padroniza nomes de colunas por similaridade
    df.columns = [normalize_text(c) for c in df.columns]
    rename = {}
    for c in df.columns:
        nk = normalize_key(c)
        if nk == "DATA":
            rename[c] = "Data"
        elif nk in {"NOME", "CLIENTE"}:
            rename[c] = "Nome"
        elif nk in {"CPF CNPJ", "CPF", "CNPJ"}:
            rename[c] = "CPF/CNPJ"
        elif nk in {"PARCEIRO", "NOME PARCEIRO"}:
            rename[c] = "PARCEIRO"
        elif nk == "MODELO":
            rename[c] = "Modelo"
        elif nk in {"PEDIDO", "PROTOCOLO"}:
            rename[c] = "Pedido"
        elif nk == "VALOR":
            rename[c] = "Valor"
        elif nk == "VENDEDOR":
            rename[c] = "Vendedor"
        elif nk == "AGR":
            rename[c] = "AGR"
        elif nk == "ORIGEM":
            rename[c] = "Origem"
    df = df.rename(columns=rename)

    # Quando CPF/CNPJ e PARCEIRO estão dentro da coluna Nome, separa automaticamente.
    if "Nome" in df.columns and ("CPF/CNPJ" not in df.columns or "PARCEIRO" not in df.columns):
        extra = df["Nome"].apply(split_nome_cpf_parceiro)
        extra_df = pd.DataFrame(extra.tolist(), columns=["Nome_extra", "CPF_CNPJ_extra", "PARCEIRO_extra"], index=df.index)
        df["Nome"] = extra_df["Nome_extra"].where(extra_df["Nome_extra"].astype(str).str.strip() != "", df["Nome"])
        if "CPF/CNPJ" not in df.columns:
            df["CPF/CNPJ"] = extra_df["CPF_CNPJ_extra"]
        else:
            df["CPF/CNPJ"] = df["CPF/CNPJ"].fillna("").astype(str)
            df.loc[df["CPF/CNPJ"].str.strip().isin(["", "nan", "None"]), "CPF/CNPJ"] = extra_df["CPF_CNPJ_extra"]
        if "PARCEIRO" not in df.columns:
            df["PARCEIRO"] = extra_df["PARCEIRO_extra"]
        else:
            df["PARCEIRO"] = df["PARCEIRO"].fillna("").astype(str)
            df.loc[df["PARCEIRO"].str.strip().isin(["", "nan", "None"]), "PARCEIRO"] = extra_df["PARCEIRO_extra"]

    # Garante coluna Modelo para exportação, mesmo quando vier ausente.
    if "Modelo" not in df.columns:
        df["Modelo"] = ""

    required = ["Data", "Nome", "CPF/CNPJ", "PARCEIRO", "Pedido", "Valor", "AGR", "Origem"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError("Colunas obrigatórias não encontradas: " + ", ".join(missing))

    df["Data"] = pd.to_datetime(df["Data"], errors="coerce", dayfirst=True)
    df["Pedido"] = df["Pedido"].apply(lambda x: re.sub(r"\D", "", str(x).replace(".0", "")) if pd.notna(x) else "")
    df["Valor Original"] = df["Valor"].apply(parse_money)

    for col in ["Nome", "CPF/CNPJ", "PARCEIRO", "AGR", "Origem", "Modelo"]:
        df[col] = df[col].apply(normalize_text)

    df = df[(df["Pedido"] != "") & (df["Data"].notna())].copy()
    df["Origem"] = df["Origem"].str.strip().str.title()
    df.loc[~df["Origem"].isin(["Interno", "Parceiro"]), "Origem"] = df.loc[~df["Origem"].isin(["Interno", "Parceiro"]), "Origem"].replace("", "Não informado")

    return df

def read_partner_rules(uploaded_file) -> tuple[dict, set, pd.DataFrame]:
    """
    Lê a planilha de parceiros com as colunas PARCEIRO e VALOR.
    Quando VALOR vier como texto do tipo "CONSIDERA O VALOR QUE ESTÁ na coluna G",
    o app mantém o Valor Original da planilha principal para aquele parceiro.
    """
    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    try:
        df = pd.read_excel(uploaded_file, header=None)
    except Exception:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        df = pd.read_csv(uploaded_file, sep=None, engine="python", header=None)

    df = df.dropna(how="all").copy()
    if df.empty:
        raise ValueError("A planilha de parceiros está vazia.")

    # Procura a linha de cabeçalho com PARCEIRO e VALOR.
    header_row = None
    for idx, row in df.iterrows():
        vals = [normalize_key(x) for x in row.tolist()]
        if "PARCEIRO" in vals and "VALOR" in vals:
            header_row = int(idx)
            break

    if header_row is not None:
        cols = [normalize_text(c) for c in df.iloc[header_row].tolist()]
        df = df.iloc[header_row + 1:].copy()
        df.columns = cols
    else:
        # Fallback: considera as duas primeiras colunas como PARCEIRO e VALOR.
        df = df.iloc[:, :2].copy()
        df.columns = ["PARCEIRO", "VALOR"]

    rename = {}
    for c in df.columns:
        nk = normalize_key(c)
        if nk == "PARCEIRO":
            rename[c] = "PARCEIRO"
        elif nk == "VALOR":
            rename[c] = "VALOR"
    df = df.rename(columns=rename)

    if "PARCEIRO" not in df.columns or "VALOR" not in df.columns:
        raise ValueError("A planilha de parceiros precisa ter as colunas PARCEIRO e VALOR.")

    df = df[["PARCEIRO", "VALOR"]].dropna(how="all").copy()
    df["PARCEIRO"] = df["PARCEIRO"].apply(normalize_text)
    df["VALOR_TEXTO"] = df["VALOR"].apply(normalize_text)
    df = df[df["PARCEIRO"] != ""].copy()

    mapa_valores = {}
    parceiros_valor_original = set()
    linhas = []

    for _, row in df.iterrows():
        parceiro = row["PARCEIRO"]
        valor_texto = row["VALOR_TEXTO"]
        chave = normalize_key(parceiro)

        if "CONSIDERA" in normalize_key(valor_texto) or "COLUNA G" in normalize_key(valor_texto):
            parceiros_valor_original.add(chave)
            regra = "Valor original da planilha principal"
            valor_num = None
        else:
            valor_num = parse_money(valor_texto)
            mapa_valores[chave] = valor_num
            regra = "Valor fixo da planilha de parceiros"

        linhas.append({"PARCEIRO": parceiro, "VALOR": valor_num, "REGRA": regra})

    return mapa_valores, parceiros_valor_original, pd.DataFrame(linhas)


def valor_ajustado(row, mapa_parceiros: dict, parceiros_valor_original: set):
    origem = normalize_key(row.get("Origem", ""))
    parceiro = row.get("PARCEIRO", "")
    parceiro_norm = normalize_key(parceiro)
    valor_original = float(row.get("Valor Original", 0.0))

    if origem != "PARCEIRO":
        return valor_original, "Interno: valor da planilha"

    if parceiro_norm in parceiros_valor_original:
        return valor_original, "Parceiro cadastrado: valor da planilha"

    if parceiro_norm in mapa_parceiros:
        return float(mapa_parceiros[parceiro_norm]), "Parceiro: planilha de parceiros"

    return valor_original, "Parceiro sem regra: valor da planilha"


def preparar_base(df: pd.DataFrame, mapa_parceiros: dict, parceiros_valor_original: set) -> pd.DataFrame:
    d = df.copy()
    vals = d.apply(lambda row: valor_ajustado(row, mapa_parceiros, parceiros_valor_original), axis=1, result_type="expand")
    d["Faturamento Ajustado"] = vals[0].astype(float)
    d["Regra Valor"] = vals[1]
    d["Custo Certificado"] = CUSTO_CERTIFICADO
    d["Margem Bruta R$"] = d["Faturamento Ajustado"] - d["Custo Certificado"]
    d["Margem Bruta %"] = d.apply(lambda r: r["Margem Bruta R$"] / r["Faturamento Ajustado"] if r["Faturamento Ajustado"] else 0.0, axis=1)
    d["Dia"] = d["Data"].dt.date
    return d


def agg_resumo(base: pd.DataFrame, group_cols):
    if isinstance(group_cols, str):
        group_cols = [group_cols]
    out = base.groupby(group_cols, dropna=False).agg(
        Quantidade=("Pedido", "nunique"),
        Faturamento=("Faturamento Ajustado", "sum"),
        Custo=("Custo Certificado", "sum"),
        Margem=("Margem Bruta R$", "sum"),
    ).reset_index()
    out["Ticket Médio"] = out.apply(lambda r: r["Faturamento"] / r["Quantidade"] if r["Quantidade"] else 0.0, axis=1)
    out["Margem %"] = out.apply(lambda r: r["Margem"] / r["Faturamento"] if r["Faturamento"] else 0.0, axis=1)
    return out


def dataframe_download_excel(sheets: dict) -> BytesIO:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, df in sheets.items():
            safe_name = name[:31]
            df.to_excel(writer, index=False, sheet_name=safe_name)
            ws = writer.book[safe_name]
            for col in ws.columns:
                max_len = 0
                letter = col[0].column_letter
                for cell in col:
                    max_len = max(max_len, len(str(cell.value)) if cell.value is not None else 0)
                ws.column_dimensions[letter].width = min(max_len + 2, 45)
    output.seek(0)
    return output


def show_metric_card(label, value, small=""):
    st.markdown(
        f"""
        <div class='info-card'>
            <div class='label'>{label}</div>
            <div class='value'>{value}</div>
            <div class='small'>{small}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_table_money(df: pd.DataFrame, money_cols=None, pct_cols=None, int_cols=None):
    out = df.copy()
    for c in money_cols or []:
        if c in out.columns:
            out[c] = out[c].apply(format_brl)
    for c in pct_cols or []:
        if c in out.columns:
            out[c] = out[c].apply(format_pct)
    for c in int_cols or []:
        if c in out.columns:
            out[c] = out[c].fillna(0).astype(int)
    return out


def business_days_between(start_date, end_date, feriados=None):
    """Conta dias úteis de segunda a sexta entre duas datas, inclusive, desconsiderando feriados informados."""
    if start_date is None or end_date is None:
        return 0
    feriados = {pd.to_datetime(f).date() for f in (feriados or []) if pd.notna(f)}
    rng = pd.date_range(start=start_date, end=end_date, freq="D")
    return int(sum((d.weekday() < 5) and (d.date() not in feriados) for d in rng))


def parse_feriados(texto: str):
    """Lê feriados digitados como DD/MM/AAAA separados por vírgula, ponto e vírgula ou quebra de linha."""
    if not texto:
        return []
    partes = re.split(r"[,;\n]+", texto)
    datas = []
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        data = pd.to_datetime(parte, dayfirst=True, errors="coerce")
        if pd.notna(data):
            datas.append(data.date())
    return datas


def month_bounds(date_value):
    d = pd.Timestamp(date_value)
    first = d.replace(day=1).date()
    last = (d.replace(day=1) + pd.offsets.MonthEnd(0)).date()
    return first, last

# -----------------------------
# Cabeçalho
# -----------------------------
st.markdown(
    """
    <div class='hero'>
        <h1>Dashboard de Certificados | CRM</h1>
        <p>Upload da planilha, cálculo de faturamento ajustado por origem, parceiros, AGR, evolução diária e margem.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Upload e leitura
# -----------------------------
st.sidebar.header("Arquivo")
uploaded = st.sidebar.file_uploader("Anexe a planilha Excel do CRM", type=["xlsx", "xlsm", "xls"], key="crm")
parceiros_upload = st.sidebar.file_uploader("Anexe a planilha de parceiros", type=["xlsx", "xlsm", "xls", "csv"], key="parceiros")

if not uploaded:
    st.info("Anexe a planilha do CRM para carregar o dashboard.")
    st.stop()

if not parceiros_upload:
    st.info("Anexe também a planilha de parceiros com as colunas PARCEIRO e VALOR.")
    st.stop()

try:
    mapa_parceiros, parceiros_valor_original, df_regras_parceiros = read_partner_rules(parceiros_upload)
except Exception as e:
    st.error(f"Erro ao ler a planilha de parceiros: {e}")
    st.stop()

try:
    # Alguns relatórios .xls do sistema são HTML disfarçado de Excel.
    # Nesse caso, pd.ExcelFile pode falhar; o app cai automaticamente para pd.read_html.
    try:
        uploaded.seek(0)
        excel_file = pd.ExcelFile(uploaded)
        sheet = st.sidebar.selectbox("Aba", excel_file.sheet_names, index=0)
        df_raw = read_excel_dashboard(uploaded, sheet_name=sheet, force_html=False)
    except Exception:
        sheet = "Relatório HTML/XLS"
        df_raw = read_excel_dashboard(uploaded, sheet_name=None, force_html=True)
        st.sidebar.caption("Arquivo lido como relatório HTML/XLS.")

    df_base = preparar_base(df_raw, mapa_parceiros, parceiros_valor_original)
except Exception as e:
    st.error(f"Erro ao ler a planilha: {e}")
    st.stop()

if df_base.empty:
    st.warning("Nenhum pedido válido encontrado na planilha.")
    st.stop()

# -----------------------------
# Filtros
# -----------------------------
st.sidebar.header("Filtros")

# O dashboard trabalha com um mês de análise.
# A previsão de fechamento usa esse mês selecionado como referência.
df_base["MES_ANALISE"] = df_base["Data"].dt.to_period("M")
meses_disponiveis = sorted(df_base["MES_ANALISE"].dropna().unique().tolist())

def label_mes(periodo):
    meses = {
        1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
        7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"
    }
    return f"{meses.get(periodo.month, periodo.month)}/{periodo.year}"

mes_sel = st.sidebar.selectbox(
    "Mês de análise",
    meses_disponiveis,
    index=len(meses_disponiveis) - 1,
    format_func=label_mes,
    help="A previsão de fechamento será calculada considerando o mês selecionado aqui."
)

df_mes = df_base[df_base["MES_ANALISE"] == mes_sel].copy()
mes_inicio = mes_sel.to_timestamp().date()
mes_fim = (mes_sel.to_timestamp() + pd.offsets.MonthEnd(0)).date()

min_date = df_mes["Data"].min().date()
max_date = df_mes["Data"].max().date()

periodo = st.sidebar.date_input(
    "Período dentro do mês",
    value=(min_date, max_date),
    min_value=mes_inicio,
    max_value=mes_fim,
    format="DD/MM/YYYY",
    help="Use para analisar um intervalo específico dentro do mês selecionado."
)
if isinstance(periodo, tuple) and len(periodo) == 2:
    dt_ini, dt_fim = periodo
else:
    dt_ini, dt_fim = min_date, max_date

origens = sorted(df_base["Origem"].dropna().unique().tolist())
origem_sel = st.sidebar.multiselect("Origem", origens, default=origens)

agrs = sorted([x for x in df_base["AGR"].dropna().unique().tolist() if x])
agr_sel = st.sidebar.multiselect("AGR", agrs, default=agrs)

parceiros = sorted([x for x in df_base["PARCEIRO"].dropna().unique().tolist() if x])
parceiro_sel = st.sidebar.multiselect("Parceiro", parceiros, default=[])

st.sidebar.header("Meta")
meta_certificados = st.sidebar.number_input(
    "Meta de certificados do mês",
    min_value=0,
    value=0,
    step=1,
    help="Informe a meta mensal de certificados para acompanhar o realizado e a previsão de fechamento."
)

st.sidebar.header("Feriados")
feriados_texto = st.sidebar.text_area(
    "Feriados do mês",
    value="",
    placeholder="Ex.: 01/05/2026, 04/06/2026",
    help="Informe os feriados que devem ser desconsiderados da previsão, separados por vírgula, ponto e vírgula ou quebra de linha."
)
feriados_mes = [d for d in parse_feriados(feriados_texto) if mes_inicio <= d <= mes_fim]

base = df_mes[(df_mes["Data"].dt.date >= dt_ini) & (df_mes["Data"].dt.date <= dt_fim)].copy()
if origem_sel:
    base = base[base["Origem"].isin(origem_sel)].copy()
if agr_sel:
    base = base[base["AGR"].isin(agr_sel)].copy()
if parceiro_sel:
    base = base[base["PARCEIRO"].isin(parceiro_sel)].copy()

if base.empty:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")
    st.stop()

# -----------------------------
# Métricas gerais
# -----------------------------
qtd_geral = int(base["Pedido"].nunique())
fat_geral = float(base["Faturamento Ajustado"].sum())
custo_geral = float(base["Custo Certificado"].sum())
margem_geral = fat_geral - custo_geral
ticket_geral = fat_geral / qtd_geral if qtd_geral else 0.0

base_interno = base[base["Origem"] == "Interno"]
base_parceiro = base[base["Origem"] == "Parceiro"]

qtd_interno = int(base_interno["Pedido"].nunique())
qtd_parceiro = int(base_parceiro["Pedido"].nunique())
fat_interno = float(base_interno["Faturamento Ajustado"].sum())
fat_parceiro = float(base_parceiro["Faturamento Ajustado"].sum())
ticket_interno = fat_interno / qtd_interno if qtd_interno else 0.0
ticket_parceiro = fat_parceiro / qtd_parceiro if qtd_parceiro else 0.0

m1, m2, m3, m4 = st.columns(4)
with m1:
    show_metric_card("Certificados emitidos", f"{qtd_geral:,}".replace(",", "."), "Contagem por Pedido único")
with m2:
    show_metric_card("Faturamento geral", format_brl(fat_geral), "Valor ajustado pelas regras")
with m3:
    show_metric_card("Ticket médio geral", format_brl(ticket_geral), "Faturamento / certificados")
with m4:
    show_metric_card("Margem bruta geral", format_brl(margem_geral), f"{format_pct(margem_geral / fat_geral if fat_geral else 0)}")

m5, m6, m7, m8 = st.columns(4)
with m5:
    show_metric_card("Faturamento interno", format_brl(fat_interno), f"{qtd_interno} certificados | Ticket {format_brl(ticket_interno)}")
with m6:
    show_metric_card("Faturamento parceria", format_brl(fat_parceiro), f"{qtd_parceiro} certificados | Ticket {format_brl(ticket_parceiro)}")
with m7:
    show_metric_card(
        "Quantidade por origem",
        f"Geral: {qtd_geral} | Interno: {qtd_interno} | Parceria: {qtd_parceiro}",
        f"Parceria representa {format_pct(qtd_parceiro / qtd_geral if qtd_geral else 0)} da quantidade"
    )
with m8:
    show_metric_card(
        "Faturamento por origem",
        f"Geral: {format_brl(fat_geral)}",
        f"Interno: {format_brl(fat_interno)} | Parceria: {format_brl(fat_parceiro)}"
    )

# -----------------------------
# Meta e previsão de fechamento
# -----------------------------
st.markdown("<div class='section-title'>Meta e previsão de fechamento</div>", unsafe_allow_html=True)

temporal_previsao = base.groupby("Dia", as_index=False).agg(
    Quantidade=("Pedido", "nunique"),
    Faturamento=("Faturamento Ajustado", "sum"),
).sort_values("Dia")

# Previsão de fechamento:
# - Considera o mês de análise selecionado.
# - Dias úteis = segunda a sexta, menos os feriados informados na barra lateral.
# - Média = certificados realizados / dias úteis decorridos.
# - Previsão = média * dias úteis totais do mês.
mes_ini = mes_inicio
mes_fim_previsao = mes_fim
hoje = pd.Timestamp.today().date()

if mes_ini <= hoje <= mes_fim_previsao:
    data_corte_previsao = min(hoje, dt_fim, mes_fim_previsao)
elif hoje > mes_fim_previsao:
    data_corte_previsao = min(dt_fim, mes_fim_previsao)
else:
    data_corte_previsao = min(max_date, dt_fim, mes_fim_previsao)

dias_uteis_mes = business_days_between(mes_ini, mes_fim_previsao, feriados_mes)
dias_uteis_decorridos = business_days_between(mes_ini, data_corte_previsao, feriados_mes)

if data_corte_previsao >= mes_fim_previsao:
    media_qtd_dia = qtd_geral / dias_uteis_mes if dias_uteis_mes else 0
    previsao_qtd = qtd_geral
    status_previsao = "Mês fechado: previsão igual ao realizado."
else:
    media_qtd_dia = qtd_geral / dias_uteis_decorridos if dias_uteis_decorridos else 0
    previsao_qtd = int(round(media_qtd_dia * dias_uteis_mes, 0)) if dias_uteis_mes else 0
    qtd_feriados = len(feriados_mes)
    status_previsao = (
        f"Mês parcial: {dias_uteis_decorridos} dia(s) útil(eis) realizado(s) de {dias_uteis_mes}. "
        f"Feriados desconsiderados: {qtd_feriados}."
    )

atingimento_meta = qtd_geral / meta_certificados if meta_certificados else 0
previsao_vs_meta = previsao_qtd / meta_certificados if meta_certificados else 0

g1, g2 = st.columns([1.2, 1])
with g1:
    gauge_value = min(atingimento_meta * 100, 150) if meta_certificados else 0
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=gauge_value,
        number={"suffix": "%"},
        delta={"reference": 100},
        title={"text": "Atingimento da meta de certificados"},
        gauge={
            "axis": {"range": [0, 150]},
            "bar": {"thickness": 0.28},
            "steps": [
                {"range": [0, 70], "color": "#fee2e2"},
                {"range": [70, 100], "color": "#fef3c7"},
                {"range": [100, 150], "color": "#dcfce7"},
            ],
            "threshold": {"line": {"width": 4}, "thickness": 0.75, "value": 100},
        },
    ))
    fig_gauge.update_layout(height=280, margin=dict(l=20, r=20, t=55, b=10))
    if meta_certificados:
        st.plotly_chart(fig_gauge, use_container_width=True)
    else:
        st.info("Informe a meta mensal na barra lateral para exibir o velocímetro.")
with g2:
    show_metric_card("Meta informada", f"{int(meta_certificados)} certificados" if meta_certificados else "Sem meta", "Campo editável na barra lateral")
    show_metric_card("Previsão de fechamento", f"{previsao_qtd} certificados", f"Média: {media_qtd_dia:.2f}/dia útil | Dias úteis decorridos: {dias_uteis_decorridos}/{dias_uteis_mes}. {status_previsao}")
    if meta_certificados:
        show_metric_card("Previsão x Meta", format_pct(previsao_vs_meta), f"Realizado atual: {qtd_geral} certificados")

# -----------------------------
# Abas
# -----------------------------
tab_visao, tab_parceiros, tab_temporal, tab_agr, tab_margem, tab_base = st.tabs([
    "📌 Visão Geral",
    "🤝 Parceiros",
    "📅 Evolução diária",
    "🏆 AGR",
    "💰 Margem",
    "📄 Base tratada",
])

with tab_visao:
    st.markdown("<div class='section-title'>Faturamento por origem</div>", unsafe_allow_html=True)

    origem_tbl = agg_resumo(base, "Origem")
    origem_tbl["% Quantidade"] = origem_tbl["Quantidade"] / origem_tbl["Quantidade"].sum() if origem_tbl["Quantidade"].sum() else 0
    origem_tbl["% Faturamento"] = origem_tbl["Faturamento"] / origem_tbl["Faturamento"].sum() if origem_tbl["Faturamento"].sum() else 0

    c1, c2 = st.columns([1, 1])
    with c1:
        fig_origem_fat = px.pie(origem_tbl, names="Origem", values="Faturamento", title="Faturamento por Origem", hole=0.45)
        fig_origem_fat.update_traces(textinfo="percent+label")
        st.plotly_chart(fig_origem_fat, use_container_width=True)
    with c2:
        fig_origem_qtd = px.bar(origem_tbl, x="Origem", y="Quantidade", text="Quantidade", title="Quantidade de certificados por Origem")
        fig_origem_qtd.update_traces(textposition="outside")
        st.plotly_chart(fig_origem_qtd, use_container_width=True)

    origem_show = format_table_money(
        origem_tbl[["Origem", "Quantidade", "Faturamento", "% Quantidade", "% Faturamento", "Ticket Médio"]],
        money_cols=["Faturamento", "Ticket Médio"],
        pct_cols=["% Quantidade", "% Faturamento"],
        int_cols=["Quantidade"],
    )
    st.dataframe(origem_show, use_container_width=True, hide_index=True)

    st.info("Para parceiros com regra cadastrada, o faturamento é substituído pelo valor da tabela. Para FUNCEF e internos, o app usa o valor original da coluna Valor.")

with tab_parceiros:
    st.markdown("<div class='section-title'>Ranking e representatividade dos parceiros</div>", unsafe_allow_html=True)

    if base_parceiro.empty:
        st.info("Não há registros de parceiros nos filtros selecionados.")
    else:
        total_parceiros_qtd = base_parceiro["Pedido"].nunique()
        total_parceiros_fat = base_parceiro["Faturamento Ajustado"].sum()
        total_geral_qtd = base["Pedido"].nunique()
        total_geral_fat = base["Faturamento Ajustado"].sum()

        parceiro_tbl = agg_resumo(base_parceiro, "PARCEIRO")
        parceiro_tbl["% Qtd dentro Parceiros"] = parceiro_tbl["Quantidade"] / total_parceiros_qtd if total_parceiros_qtd else 0
        parceiro_tbl["% Qtd dentro Geral"] = parceiro_tbl["Quantidade"] / total_geral_qtd if total_geral_qtd else 0
        parceiro_tbl["% Fat dentro Parceiros"] = parceiro_tbl["Faturamento"] / total_parceiros_fat if total_parceiros_fat else 0
        parceiro_tbl["% Fat dentro Geral"] = parceiro_tbl["Faturamento"] / total_geral_fat if total_geral_fat else 0
        parceiro_tbl = parceiro_tbl.sort_values(["Faturamento", "Quantidade"], ascending=False)

        fig_tree = px.treemap(
            parceiro_tbl,
            path=["PARCEIRO"],
            values="Faturamento",
            color="Quantidade",
            title="Treemap de parceiros por faturamento ajustado",
            hover_data={"Quantidade": True, "Faturamento": ":.2f"},
        )
        st.plotly_chart(fig_tree, use_container_width=True)

        parceiro_show = format_table_money(
            parceiro_tbl[[
                "PARCEIRO", "Quantidade", "Faturamento", "Ticket Médio",
                "% Qtd dentro Parceiros", "% Qtd dentro Geral",
                "% Fat dentro Parceiros", "% Fat dentro Geral"
            ]],
            money_cols=["Faturamento", "Ticket Médio"],
            pct_cols=["% Qtd dentro Parceiros", "% Qtd dentro Geral", "% Fat dentro Parceiros", "% Fat dentro Geral"],
            int_cols=["Quantidade"],
        )
        st.dataframe(parceiro_show, use_container_width=True, hide_index=True)

        sem_regra = base_parceiro[base_parceiro["Regra Valor"] == "Parceiro sem regra: valor da planilha"]
        if not sem_regra.empty:
            st.warning(f"Existem {sem_regra['Pedido'].nunique()} certificado(s) de parceiro sem valor cadastrado. O app usou o valor original da planilha nesses casos.")
            st.dataframe(
                sem_regra[["Data", "Nome", "CPF/CNPJ", "PARCEIRO", "Pedido", "Valor Original", "Faturamento Ajustado", "AGR"]],
                use_container_width=True,
                hide_index=True,
            )

with tab_temporal:
    st.markdown("<div class='section-title'>Evolução diária de faturamento e emissões</div>", unsafe_allow_html=True)

    temporal = base.groupby("Dia", as_index=False).agg(
        Quantidade=("Pedido", "nunique"),
        Faturamento=("Faturamento Ajustado", "sum"),
    ).sort_values("Dia")

    top_fat = temporal.sort_values("Faturamento", ascending=False).head(3)
    top_qtd = temporal.sort_values("Quantidade", ascending=False).head(3)

    st.markdown("**Top 03 dias por faturamento**")
    cols = st.columns(3)
    for i, (_, row) in enumerate(top_fat.iterrows()):
        with cols[i]:
            show_metric_card(f"#{i+1} - {pd.to_datetime(row['Dia']).strftime('%d/%m/%Y')}", format_brl(row["Faturamento"]), f"{int(row['Quantidade'])} certificados")

    st.markdown("**Top 03 dias por quantidade de emissões**")
    cols = st.columns(3)
    for i, (_, row) in enumerate(top_qtd.iterrows()):
        with cols[i]:
            show_metric_card(f"#{i+1} - {pd.to_datetime(row['Dia']).strftime('%d/%m/%Y')}", f"{int(row['Quantidade'])} certificados", format_brl(row["Faturamento"]))

    fig_temp = make_subplots(specs=[[{"secondary_y": True}]])
    fig_temp.add_trace(go.Bar(x=temporal["Dia"], y=temporal["Quantidade"], name="Quantidade"), secondary_y=False)
    fig_temp.add_trace(go.Scatter(x=temporal["Dia"], y=temporal["Faturamento"], name="Faturamento", mode="lines+markers"), secondary_y=True)
    fig_temp.update_layout(title="Evolução diária: quantidade x faturamento", hovermode="x unified", legend=dict(orientation="h"))
    fig_temp.update_yaxes(title_text="Quantidade", secondary_y=False)
    fig_temp.update_yaxes(title_text="Faturamento (R$)", secondary_y=True)
    st.plotly_chart(fig_temp, use_container_width=True)

    temporal_show = format_table_money(temporal, money_cols=["Faturamento"], int_cols=["Quantidade"])
    st.dataframe(temporal_show, use_container_width=True, hide_index=True)

with tab_agr:
    st.markdown("<div class='section-title'>Ranking por AGR</div>", unsafe_allow_html=True)
    agr_tbl = agg_resumo(base, "AGR")
    agr_tbl["% Quantidade"] = agr_tbl["Quantidade"] / agr_tbl["Quantidade"].sum() if agr_tbl["Quantidade"].sum() else 0
    agr_tbl["% Faturamento"] = agr_tbl["Faturamento"] / agr_tbl["Faturamento"].sum() if agr_tbl["Faturamento"].sum() else 0
    agr_tbl = agr_tbl.sort_values(["Faturamento", "Quantidade"], ascending=False)

    c1, c2 = st.columns(2)
    with c1:
        fig_agr_fat = px.bar(agr_tbl.head(20), x="Faturamento", y="AGR", orientation="h", title="Top AGR por faturamento")
        fig_agr_fat.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig_agr_fat, use_container_width=True)
    with c2:
        fig_agr_qtd = px.bar(agr_tbl.head(20), x="Quantidade", y="AGR", orientation="h", title="Top AGR por quantidade")
        fig_agr_qtd.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig_agr_qtd, use_container_width=True)

    agr_show = format_table_money(
        agr_tbl[["AGR", "Quantidade", "Faturamento", "Ticket Médio", "% Quantidade", "% Faturamento"]],
        money_cols=["Faturamento", "Ticket Médio"],
        pct_cols=["% Quantidade", "% Faturamento"],
        int_cols=["Quantidade"],
    )
    st.dataframe(agr_show, use_container_width=True, hide_index=True)

with tab_margem:
    st.markdown("<div class='section-title'>Margem bruta por origem e parceiros</div>", unsafe_allow_html=True)
    st.caption(f"Custo fixo considerado: {format_brl(CUSTO_CERTIFICADO)} por certificado.")

    margem_origem = agg_resumo(base, "Origem").sort_values("Margem", ascending=False)
    margem_origem_show = format_table_money(
        margem_origem[["Origem", "Quantidade", "Faturamento", "Custo", "Margem", "Margem %"]],
        money_cols=["Faturamento", "Custo", "Margem"],
        pct_cols=["Margem %"],
        int_cols=["Quantidade"],
    )
    st.dataframe(margem_origem_show, use_container_width=True, hide_index=True)

    fig_margem = px.bar(margem_origem, x="Origem", y="Margem", text="Margem", title="Margem bruta por origem")
    fig_margem.update_traces(texttemplate="R$ %{text:,.2f}", textposition="outside")
    st.plotly_chart(fig_margem, use_container_width=True)

    if not base_parceiro.empty:
        st.markdown("**Margem por parceiro**")
        margem_parceiro = agg_resumo(base_parceiro, "PARCEIRO").sort_values("Margem", ascending=False)
        margem_parceiro_show = format_table_money(
            margem_parceiro[["PARCEIRO", "Quantidade", "Faturamento", "Custo", "Margem", "Margem %"]],
            money_cols=["Faturamento", "Custo", "Margem"],
            pct_cols=["Margem %"],
            int_cols=["Quantidade"],
        )
        st.dataframe(margem_parceiro_show, use_container_width=True, hide_index=True)

with tab_base:
    st.markdown("<div class='section-title'>Lista de certificados e base tratada</div>", unsafe_allow_html=True)
    base_lista = base[[
        "Data", "Nome", "CPF/CNPJ", "PARCEIRO", "Pedido", "Origem", "AGR",
        "Valor Original", "Faturamento Ajustado", "Regra Valor", "Custo Certificado", "Margem Bruta R$", "Margem Bruta %"
    ]].copy()
    base_lista["Data"] = base_lista["Data"].dt.strftime("%d/%m/%Y")

    st.dataframe(
        format_table_money(
            base_lista,
            money_cols=["Valor Original", "Faturamento Ajustado", "Custo Certificado", "Margem Bruta R$"],
            pct_cols=["Margem Bruta %"],
        ),
        use_container_width=True,
        hide_index=True,
    )

# -----------------------------
# Exportação Excel
# -----------------------------
origem_export = agg_resumo(base, "Origem")
agr_export = agg_resumo(base, "AGR").sort_values("Faturamento", ascending=False)
parceiro_export = agg_resumo(base_parceiro, "PARCEIRO").sort_values("Faturamento", ascending=False) if not base_parceiro.empty else pd.DataFrame()
temporal_export = base.groupby("Dia", as_index=False).agg(Quantidade=("Pedido", "nunique"), Faturamento=("Faturamento Ajustado", "sum")).sort_values("Dia")
base_export = base[[
    "Data", "Nome", "CPF/CNPJ", "PARCEIRO", "Modelo", "Pedido", "Origem", "AGR",
    "Valor Original", "Faturamento Ajustado", "Regra Valor", "Custo Certificado", "Margem Bruta R$", "Margem Bruta %"
]].copy()

excel_bytes = dataframe_download_excel({
    "Base tratada": base_export,
    "Resumo Origem": origem_export,
    "Ranking Parceiros": parceiro_export,
    "Ranking AGR": agr_export,
    "Temporal": temporal_export,
})

st.download_button(
    label="📥 Baixar análise em Excel",
    data=excel_bytes,
    file_name="dashboard_certificados_crm.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
