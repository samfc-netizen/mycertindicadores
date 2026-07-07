from __future__ import annotations

import argparse
import re
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
from lxml import html


CUSTO_CERTIFICADO = 29.25
MESES = {
    "JAN": 1,
    "JANEIRO": 1,
    "FEV": 2,
    "FEVEREIRO": 2,
    "MAR": 3,
    "MARCO": 3,
    "MARÇO": 3,
    "ABR": 4,
    "ABRIL": 4,
    "MAI": 5,
    "MAIO": 5,
    "JUN": 6,
    "JUNHO": 6,
    "JUL": 7,
    "JULHO": 7,
    "AGO": 8,
    "AGOSTO": 8,
    "SET": 9,
    "SETEMBRO": 9,
    "OUT": 10,
    "OUTUBRO": 10,
    "NOV": 11,
    "NOVEMBRO": 11,
    "DEZ": 12,
    "DEZEMBRO": 12,
}
PADRAO_MESES_ARQUIVO = (
    "JAN|JANEIRO|FEV|FEVEREIRO|MAR|MAR[CÇ]O|ABR|ABRIL|MAI|MAIO|"
    "JUN|JUNHO|JUL|JULHO|AGO|AGOSTO|SET|SETEMBRO|OUT|OUTUBRO|"
    "NOV|NOVEMBRO|DEZ|DEZEMBRO"
)
NOMES_MESES = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Marco",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


@dataclass(frozen=True)
class ArquivoMensal:
    caminho: Path
    mes: int
    ano: int
    mes_nome: str


def normalizar_texto(valor: object) -> str:
    texto = "" if pd.isna(valor) else str(valor)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"\s+", " ", texto).strip().upper()
    return texto


def moeda_para_float(valor: object) -> float:
    if pd.isna(valor):
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip()
    texto = texto.replace("R$", "").replace("\xa0", " ")
    texto = re.sub(r"[^0-9,.-]", "", texto)
    if not texto:
        return 0.0
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return 0.0


def formatar_moeda(valor: float) -> str:
    texto = f"R$ {valor:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_percentual(valor: float) -> str:
    return f"{valor:.1f}%".replace(".", ",")


def preparar_datas_para_tela(df: pd.DataFrame) -> pd.DataFrame:
    saida = df.copy()
    for col in saida.columns:
        if "data" in str(col).lower():
            saida[col] = pd.to_datetime(saida[col], errors="coerce").dt.date
    return saida


def mostrar_tabela(st, df: pd.DataFrame, **kwargs):
    df_tela = preparar_datas_para_tela(df)
    date_cols = [col for col in df_tela.columns if "data" in str(col).lower()]
    column_config = kwargs.pop("column_config", {})
    for col in date_cols:
        column_config[col] = st.column_config.DateColumn(col, format="DD/MM/YYYY")
    st.dataframe(df_tela, column_config=column_config, **kwargs)


def arquivo_mes_ano(caminho: Path) -> ArquivoMensal | None:
    nome = caminho.stem
    match = re.search(
        rf"\b({PADRAO_MESES_ARQUIVO})\b[\s_\-.]*(\d{{4}})\b",
        nome,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    mes_nome = normalizar_texto(match.group(1))
    ano = int(match.group(2))
    mes = MESES.get(mes_nome)
    if not mes:
        return None
    return ArquivoMensal(caminho=caminho, mes=mes, ano=ano, mes_nome=mes_nome)


def localizar_planilhas(pasta: Path) -> list[ArquivoMensal]:
    extensoes = {".xls", ".xlsx", ".html", ".htm"}
    arquivos: list[ArquivoMensal] = []
    for caminho in pasta.iterdir():
        if not caminho.is_file() or caminho.suffix.lower() not in extensoes:
            continue
        if normalizar_texto(caminho.stem).startswith("PARCEIROS"):
            continue
        info = arquivo_mes_ano(caminho)
        if info and not eh_planilha_avp(caminho):
            arquivos.append(info)
    return sorted(arquivos, key=lambda item: (item.ano, item.mes, item.caminho.name))



def normalizar_protocolo(valor: object) -> str:
    texto = "" if pd.isna(valor) else str(valor)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.strip().upper()
    texto = re.sub(r"\.0$", "", texto)
    texto = re.sub(r"[^A-Z0-9]", "", texto)
    return texto


def localizar_coluna_flexivel(df: pd.DataFrame, alternativas: Iterable[str]) -> str | None:
    mapa = {normalizar_texto(col): col for col in df.columns}
    alternativas_norm = [normalizar_texto(nome) for nome in alternativas]

    for nome in alternativas_norm:
        if nome in mapa:
            return mapa[nome]

    for col_norm, col_original in mapa.items():
        for nome in alternativas_norm:
            if nome and nome in col_norm:
                return col_original
    return None


def ler_tabela_generica(caminho: Path) -> pd.DataFrame:
    ext = caminho.suffix.lower()
    if ext == ".csv":
        try:
            return pd.read_csv(caminho, sep=None, engine="python")
        except Exception:
            return pd.read_csv(caminho)

    texto_inicial = caminho.read_bytes()[:256].decode("utf-8", errors="ignore").lower()
    if ext in {".html", ".htm"} or "<html" in texto_inicial or "<table" in texto_inicial:
        tabelas = pd.read_html(caminho)
        return tabelas[0] if tabelas else pd.DataFrame()

    bruto = pd.read_excel(caminho, header=None)
    if bruto.empty:
        return pd.DataFrame()

    for idx, row in bruto.iterrows():
        valores = [normalizar_texto(v) for v in row.tolist()]
        tem_protocolo = any("PROTOCOLO" == v or "PROTOCOLO" in v for v in valores)
        tem_avp = any(v in {"NOME DO AVP", "NOME AVP", "AVP"} or "AVP" in v for v in valores)
        if tem_protocolo and tem_avp:
            df = pd.read_excel(caminho, header=idx)
            df = df.dropna(how="all")
            df.columns = [str(c).strip() for c in df.columns]
            return df

    df = pd.read_excel(caminho)
    df = df.dropna(how="all")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def eh_planilha_avp(caminho: Path) -> bool:
    if normalizar_texto(caminho.stem).startswith("PARCEIROS"):
        return False
    try:
        df = ler_tabela_generica(caminho)
    except Exception:
        return False
    if df.empty:
        return False
    col_protocolo = localizar_coluna_flexivel(df, ["Protocolo"])
    col_avp = localizar_coluna_flexivel(df, ["Nome do AVP", "Nome AVP", "AVP"])
    return col_protocolo is not None and col_avp is not None


def localizar_planilhas_avp(pasta: Path) -> list[ArquivoMensal]:
    extensoes = {".xls", ".xlsx", ".csv", ".html", ".htm"}
    arquivos: list[ArquivoMensal] = []
    for caminho in pasta.iterdir():
        if not caminho.is_file() or caminho.suffix.lower() not in extensoes:
            continue
        info = arquivo_mes_ano(caminho)
        if info and eh_planilha_avp(caminho):
            arquivos.append(info)
    return sorted(arquivos, key=lambda item: (item.ano, item.mes, item.caminho.name))


def carregar_mapa_avp(pasta: Path) -> pd.DataFrame:
    frames = []
    for info in localizar_planilhas_avp(pasta):
        try:
            df = ler_tabela_generica(info.caminho)
            col_protocolo = localizar_coluna_flexivel(df, ["Protocolo"])
            col_avp = localizar_coluna_flexivel(df, ["Nome do AVP", "Nome AVP", "AVP"])
            if col_protocolo is None or col_avp is None:
                continue
            base = df[[col_protocolo, col_avp]].copy()
            base.columns = ["Protocolo", "Nome do AVP"]
            base["Protocolo Normalizado"] = base["Protocolo"].map(normalizar_protocolo)
            base["Nome do AVP"] = base["Nome do AVP"].fillna("").astype(str).str.strip()
            base = base[(base["Protocolo Normalizado"] != "") & (base["Nome do AVP"] != "")].copy()
            base["Ano Arquivo"] = info.ano
            base["Mes Arquivo"] = info.mes
            base["Arquivo AVP"] = info.caminho.name
            frames.append(base)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame(columns=["Ano Arquivo", "Mes Arquivo", "Protocolo Normalizado", "Nome do AVP", "Arquivo AVP"])
    mapa = pd.concat(frames, ignore_index=True)
    mapa = mapa.drop_duplicates(["Ano Arquivo", "Mes Arquivo", "Protocolo Normalizado"], keep="last")
    return mapa[["Ano Arquivo", "Mes Arquivo", "Protocolo Normalizado", "Nome do AVP", "Arquivo AVP"]]


def aplicar_avp_no_agr(dados: pd.DataFrame, pasta: Path) -> pd.DataFrame:
    if dados.empty:
        return dados
    mapa_avp = carregar_mapa_avp(pasta)
    dados = dados.copy()
    if "Protocolo" not in dados.columns:
        dados["Protocolo"] = dados.get("Pedido", "")
    dados["Protocolo Normalizado"] = dados["Protocolo"].map(normalizar_protocolo)
    dados["Nome do AVP"] = ""
    dados["Arquivo AVP"] = ""
    dados["AGR Original"] = dados.get("AGR", "")

    if mapa_avp.empty:
        return dados

    dados = dados.merge(
        mapa_avp,
        how="left",
        on=["Ano Arquivo", "Mes Arquivo", "Protocolo Normalizado"],
        suffixes=("", "_MAPA_AVP"),
    )
    if "Nome do AVP_MAPA_AVP" in dados.columns:
        dados["Nome do AVP"] = dados["Nome do AVP_MAPA_AVP"].fillna("").astype(str).str.strip()
        dados = dados.drop(columns=["Nome do AVP_MAPA_AVP"])
    else:
        dados["Nome do AVP"] = dados["Nome do AVP"].fillna("").astype(str).str.strip()

    if "Arquivo AVP_MAPA_AVP" in dados.columns:
        dados["Arquivo AVP"] = dados["Arquivo AVP_MAPA_AVP"].fillna("").astype(str).str.strip()
        dados = dados.drop(columns=["Arquivo AVP_MAPA_AVP"])
    else:
        dados["Arquivo AVP"] = dados["Arquivo AVP"].fillna("").astype(str).str.strip()

    usar_avp = dados["Nome do AVP"].astype(str).str.strip() != ""
    dados.loc[usar_avp, "AGR"] = dados.loc[usar_avp, "Nome do AVP"]
    dados["AVP Encontrado"] = usar_avp
    return dados


def extrair_registros_html(caminho: Path) -> pd.DataFrame:
    texto = caminho.read_text(encoding="utf-8-sig", errors="replace")
    doc = html.fromstring(texto)
    rows = doc.xpath("//table//tr")
    registros: list[dict[str, object]] = []
    for tr in rows[1:]:
        tds = tr.xpath("./td")
        if len(tds) < 8:
            continue
        nome_linhas = [x.strip() for x in tds[1].xpath(".//text()") if x.strip()]
        pedido_linhas = [x.strip() for x in tds[3].xpath(".//text()") if x.strip()]
        cpf_cnpj = ""
        parceiro = ""
        for linha in nome_linhas[1:]:
            linha_limpa = linha.strip()
            if linha_limpa.upper().startswith("CPF/CNPJ:"):
                cpf_cnpj = linha_limpa.split(":", 1)[1].strip()
            elif linha_limpa.upper().startswith("PARCEIRO:"):
                parceiro = linha_limpa.split(":", 1)[1].strip()

        registros.append(
            {
                "Data": tds[0].text_content().strip(),
                "Nome": nome_linhas[0] if nome_linhas else "",
                "CPF/CNPJ": cpf_cnpj,
                "Parceiro": parceiro,
                "Modelo": tds[2].text_content().strip(),
                "Pedido": pedido_linhas[0] if pedido_linhas else "",
                "Protocolo": pedido_linhas[0] if pedido_linhas else "",
                "Certificadora": pedido_linhas[1] if len(pedido_linhas) > 1 else "",
                "Valor Planilha": moeda_para_float(tds[4].text_content().strip()),
                "Vendedor": tds[5].text_content().strip(),
                "AGR": tds[6].text_content().strip(),
                "Origem": tds[7].text_content().strip(),
            }
        )
    return pd.DataFrame(registros)


def extrair_registros_excel(caminho: Path) -> pd.DataFrame:
    bruto = pd.read_excel(caminho, header=None)
    if bruto.empty:
        return pd.DataFrame()
    linha_cabecalho = None
    for idx, row in bruto.iterrows():
        valores = [normalizar_texto(v) for v in row.tolist()]
        if "DATA" in valores and "NOME" in valores and "VALOR" in valores:
            linha_cabecalho = idx
            break
    if linha_cabecalho is None:
        raise ValueError(f"Nao encontrei cabecalho na planilha {caminho.name}.")
    df = pd.read_excel(caminho, header=linha_cabecalho)
    df = df.dropna(how="all")
    df.columns = [str(c).strip() for c in df.columns]
    if "Valor" in df.columns:
        df["Valor Planilha"] = df["Valor"].map(moeda_para_float)
    elif "Valor Planilha" not in df.columns:
        df["Valor Planilha"] = 0.0
    col_protocolo = localizar_coluna_flexivel(df, ["Protocolo"])
    if col_protocolo and col_protocolo != "Protocolo":
        df["Protocolo"] = df[col_protocolo]
    for col in ["Data", "Nome", "Modelo", "Pedido", "Protocolo", "Vendedor", "AGR", "Origem", "Parceiro", "CPF/CNPJ"]:
        if col not in df.columns:
            df[col] = ""
    if df["Protocolo"].astype(str).str.strip().eq("").all():
        df["Protocolo"] = df["Pedido"]
    return df[
        ["Data", "Nome", "CPF/CNPJ", "Parceiro", "Modelo", "Pedido", "Protocolo", "Valor Planilha", "Vendedor", "AGR", "Origem"]
    ].copy()


def ler_arquivo_mensal(info: ArquivoMensal) -> pd.DataFrame:
    texto_inicial = info.caminho.read_bytes()[:128].decode("utf-8", errors="ignore").lower()
    if "<html" in texto_inicial or "<div" in texto_inicial or "<table" in texto_inicial:
        df = extrair_registros_html(info.caminho)
    else:
        df = extrair_registros_excel(info.caminho)
    if df.empty:
        return df
    df["Arquivo"] = info.caminho.name
    df["Ano Arquivo"] = info.ano
    df["Mes Arquivo"] = info.mes
    return df


def encontrar_planilha_parceiros(pasta: Path) -> Path | None:
    candidatos = []
    for caminho in pasta.iterdir():
        if caminho.is_file() and caminho.suffix.lower() in {".xls", ".xlsx", ".csv"}:
            if normalizar_texto(caminho.stem).startswith("PARCEIROS"):
                candidatos.append(caminho)
    return sorted(candidatos)[0] if candidatos else None


def carregar_precos_parceiros(pasta: Path) -> pd.DataFrame:
    caminho = encontrar_planilha_parceiros(pasta)
    if caminho is None:
        return pd.DataFrame(columns=["Parceiro", "Valor Parceiro", "Parceiro Normalizado"])
    if caminho.suffix.lower() == ".csv":
        df = pd.read_csv(caminho)
    elif caminho.suffix.lower() == ".xls":
        texto_inicial = caminho.read_bytes()[:128].decode("utf-8", errors="ignore").lower()
        if "<table" in texto_inicial or "<html" in texto_inicial:
            tabelas = pd.read_html(caminho)
            df = tabelas[0] if tabelas else pd.DataFrame()
        else:
            df = pd.read_excel(caminho)
    else:
        df = pd.read_excel(caminho)

    if df.empty or len(df.columns) < 2:
        return pd.DataFrame(columns=["Parceiro", "Valor Parceiro", "Parceiro Normalizado"])
    df = df.iloc[:, :2].copy()
    df.columns = ["Parceiro", "Valor Parceiro"]
    df = df.dropna(subset=["Parceiro"])
    df["Valor Parceiro"] = df["Valor Parceiro"].map(moeda_para_float)
    df["Parceiro Normalizado"] = df["Parceiro"].map(normalizar_texto)
    return df


def classificar_tipo(modelo: object, documento: object) -> str:
    texto_modelo = normalizar_texto(modelo)
    doc = re.sub(r"\D", "", "" if pd.isna(documento) else str(documento))
    if "CNPJ" in texto_modelo or len(doc) == 14:
        return "CNPJ"
    if "CPF" in texto_modelo or len(doc) == 11:
        return "CPF"
    if "PJ" in texto_modelo:
        return "CNPJ"
    return "Nao identificado"


def carregar_dados(pasta: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    arquivos = localizar_planilhas(pasta)
    frames = [ler_arquivo_mensal(info) for info in arquivos]
    dados = pd.concat([df for df in frames if not df.empty], ignore_index=True) if frames else pd.DataFrame()
    precos = carregar_precos_parceiros(pasta)
    if dados.empty:
        return dados, precos

    dados["Data"] = pd.to_datetime(dados["Data"], dayfirst=True, errors="coerce")
    dados = dados.dropna(subset=["Data"]).copy()
    dados["Ano"] = dados["Data"].dt.year
    dados["Mes"] = dados["Data"].dt.month
    dados["Mes Nome"] = dados["Mes"].map(NOMES_MESES)
    dados["Documento Limpo"] = dados["CPF/CNPJ"].astype(str).str.replace(r"\D", "", regex=True)
    dados["Parceiro"] = dados["Parceiro"].fillna("").replace("", "SEM INDICAÇÃO")
    dados["Origem"] = dados["Origem"].fillna("").str.strip().replace("", "Interno")
    dados["Origem Normalizada"] = dados["Origem"].map(normalizar_texto)
    dados["Parceiro Normalizado"] = dados["Parceiro"].map(normalizar_texto)
    dados["Valor Planilha"] = dados["Valor Planilha"].map(moeda_para_float)
    dados["Tipo"] = [classificar_tipo(m, d) for m, d in zip(dados["Modelo"], dados["CPF/CNPJ"])]
    dados = aplicar_avp_no_agr(dados, pasta)

    mapa_precos = precos.drop_duplicates("Parceiro Normalizado").set_index("Parceiro Normalizado")[
        "Valor Parceiro"
    ].to_dict()
    dados["Valor Parceiro"] = dados["Parceiro Normalizado"].map(mapa_precos)
    eh_parceiro = dados["Origem Normalizada"].eq("PARCEIRO")
    dados["Valor Considerado"] = dados["Valor Planilha"]
    dados.loc[eh_parceiro & dados["Valor Parceiro"].notna(), "Valor Considerado"] = dados.loc[
        eh_parceiro & dados["Valor Parceiro"].notna(), "Valor Parceiro"
    ]
    dados["Preco Parceiro Ausente"] = eh_parceiro & dados["Valor Parceiro"].isna()
    dados["Custo"] = CUSTO_CERTIFICADO
    dados["Margem Bruta"] = dados["Valor Considerado"] - dados["Custo"]
    dados["Margem %"] = dados["Margem Bruta"].where(dados["Valor Considerado"] != 0, 0) / dados[
        "Valor Considerado"
    ].replace(0, pd.NA)
    dados["Margem %"] = dados["Margem %"].fillna(0.0)
    return dados, precos


def aplicar_calculos_simulacao(dados: pd.DataFrame, precos: pd.DataFrame) -> pd.DataFrame:
    if dados.empty:
        return dados
    dados = dados.copy()
    dados["Data"] = pd.to_datetime(dados["Data"], dayfirst=True, errors="coerce")
    dados = dados.dropna(subset=["Data"]).copy()
    dados["Ano"] = dados["Data"].dt.year
    dados["Mes"] = dados["Data"].dt.month
    dados["Mes Nome"] = dados["Mes"].map(NOMES_MESES)
    dados["Documento Limpo"] = dados["CPF/CNPJ"].astype(str).str.replace(r"\D", "", regex=True)
    dados["Parceiro"] = dados["Parceiro"].fillna("").replace("", "SEM INDICAÇÃO")
    dados["Origem"] = dados["Origem"].fillna("").str.strip().replace("", "Interno")
    dados["Origem Normalizada"] = dados["Origem"].map(normalizar_texto)
    dados["Parceiro Normalizado"] = dados["Parceiro"].map(normalizar_texto)
    dados["Valor Planilha"] = dados["Valor Planilha"].map(moeda_para_float)
    dados["Tipo"] = [classificar_tipo(m, d) for m, d in zip(dados["Modelo"], dados["CPF/CNPJ"])]
    if "Protocolo" not in dados.columns:
        dados["Protocolo"] = dados.get("Pedido", "")
    dados["Protocolo Normalizado"] = dados["Protocolo"].map(normalizar_protocolo)
    dados["Nome do AVP"] = ""
    dados["AGR Original"] = dados.get("AGR", "")
    dados["AVP Encontrado"] = False

    if precos.empty:
        mapa_precos = {}
    else:
        mapa_precos = precos.drop_duplicates("Parceiro Normalizado").set_index("Parceiro Normalizado")[
            "Valor Parceiro"
        ].to_dict()
    dados["Valor Parceiro"] = dados["Parceiro Normalizado"].map(mapa_precos)
    eh_parceiro = dados["Origem Normalizada"].eq("PARCEIRO")
    dados["Valor Considerado"] = dados["Valor Planilha"]
    dados.loc[eh_parceiro & dados["Valor Parceiro"].notna(), "Valor Considerado"] = dados.loc[
        eh_parceiro & dados["Valor Parceiro"].notna(), "Valor Parceiro"
    ]
    dados["Preco Parceiro Ausente"] = eh_parceiro & dados["Valor Parceiro"].isna()
    dados["Custo"] = CUSTO_CERTIFICADO
    dados["Margem Bruta"] = dados["Valor Considerado"] - dados["Custo"]
    dados["Margem %"] = dados["Margem Bruta"].where(dados["Valor Considerado"] != 0, 0) / dados[
        "Valor Considerado"
    ].replace(0, pd.NA)
    dados["Margem %"] = dados["Margem %"].fillna(0.0)
    return dados


def carregar_planilha_upload(uploaded_file, precos: pd.DataFrame) -> pd.DataFrame:
    suffix = Path(uploaded_file.name).suffix or ".xls"
    info_nome = arquivo_mes_ano(Path(uploaded_file.name))
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        temp_path = Path(tmp.name)
    try:
        if info_nome:
            info = ArquivoMensal(temp_path, info_nome.mes, info_nome.ano, info_nome.mes_nome)
        else:
            info = ArquivoMensal(temp_path, 1, 1900, "UPLOAD")
        bruto = ler_arquivo_mensal(info)
        dados = aplicar_calculos_simulacao(bruto, precos)
        return dados
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass


def calcular_previsao_fechamento(dados: pd.DataFrame) -> dict[str, float | int | bool]:
    if dados.empty:
        return {
            "dias_uteis_total": 0,
            "dias_uteis_realizados": 0,
            "dias_uteis_restantes": 0,
            "media_qtd": 0.0,
            "media_faturamento": 0.0,
            "previsao_qtd": 0.0,
            "previsao_faturamento": 0.0,
            "mes_fechado": False,
        }
    data_ref = dados["Data"].max()
    ano = int(data_ref.year)
    mes = int(data_ref.month)
    inicio_mes = pd.Timestamp(year=ano, month=mes, day=1)
    fim_mes = inicio_mes + pd.offsets.MonthEnd(0)
    hoje = pd.Timestamp.today().normalize()
    dias_uteis_total = len(pd.bdate_range(inicio_mes, fim_mes))

    mes_fechado = hoje > fim_mes
    if mes_fechado:
        dias_uteis_realizados = dias_uteis_total
    elif hoje < inicio_mes:
        dias_uteis_realizados = 0
    else:
        dias_uteis_realizados = len(pd.bdate_range(inicio_mes, min(hoje, fim_mes)))

    qtd_realizada = len(dados)
    faturamento_realizado = dados["Valor Considerado"].sum()
    if mes_fechado or dias_uteis_realizados == 0:
        previsao_qtd = float(qtd_realizada)
        previsao_faturamento = float(faturamento_realizado)
        media_qtd = qtd_realizada / dias_uteis_total if dias_uteis_total else 0.0
        media_faturamento = faturamento_realizado / dias_uteis_total if dias_uteis_total else 0.0
    else:
        media_qtd = qtd_realizada / dias_uteis_realizados
        media_faturamento = faturamento_realizado / dias_uteis_realizados
        previsao_qtd = media_qtd * dias_uteis_total
        previsao_faturamento = media_faturamento * dias_uteis_total

    return {
        "dias_uteis_total": dias_uteis_total,
        "dias_uteis_realizados": dias_uteis_realizados,
        "dias_uteis_restantes": max(dias_uteis_total - dias_uteis_realizados, 0),
        "media_qtd": media_qtd,
        "media_faturamento": media_faturamento,
        "previsao_qtd": previsao_qtd,
        "previsao_faturamento": previsao_faturamento,
        "mes_fechado": mes_fechado,
    }


def resumir(df: pd.DataFrame, grupo: str | list[str]) -> pd.DataFrame:
    tabela = (
        df.groupby(grupo, dropna=False)
        .agg(
            Quantidade=("Pedido", "count"),
            Faturamento=("Valor Considerado", "sum"),
            Custo=("Custo", "sum"),
            Margem_Bruta=("Margem Bruta", "sum"),
        )
        .reset_index()
    )
    tabela["Margem_%"] = tabela["Margem_Bruta"] / tabela["Faturamento"].replace(0, pd.NA)
    tabela["Margem_%"] = tabela["Margem_%"].fillna(0.0)
    return tabela.sort_values(["Faturamento", "Quantidade"], ascending=False)


def filtrar_periodo(df: pd.DataFrame, anos: Iterable[int], meses: Iterable[int], inicio, fim) -> pd.DataFrame:
    filtrado = df[df["Ano"].isin(list(anos)) & df["Mes"].isin(list(meses))].copy()
    if inicio:
        filtrado = filtrado[filtrado["Data"] >= pd.to_datetime(inicio)]
    if fim:
        filtrado = filtrado[filtrado["Data"] <= pd.to_datetime(fim)]
    return filtrado


def lista_renovacoes(dados: pd.DataFrame, ano_base: int, meses_base: Iterable[int]) -> pd.DataFrame:
    meses_base = [int(mes) for mes in meses_base]
    base = dados[(dados["Ano"] == ano_base) & (dados["Mes"].isin(meses_base))].copy()
    prox = dados[(dados["Ano"] == ano_base + 1) & (dados["Documento Limpo"].astype(str).str.len() > 0)].copy()
    renovados = set(prox["Documento Limpo"].dropna())
    base["Status Renovacao"] = base["Documento Limpo"].map(
        lambda doc: "Renovou" if str(doc).strip() and doc in renovados else "Pendente"
    )
    primeira_renovacao = (
        prox.sort_values("Data").drop_duplicates("Documento Limpo").set_index("Documento Limpo")["Data"].to_dict()
    )
    base["Data Renovacao"] = pd.to_datetime(base["Documento Limpo"].map(primeira_renovacao), errors="coerce")
    base["Mes Base"] = base["Mes"].map(NOMES_MESES)
    base["Mes Renovacao"] = base["Data Renovacao"].dt.month.map(NOMES_MESES)
    colunas = [
        "Status Renovacao",
        "Mes Base",
        "Data",
        "Data Renovacao",
        "Mes Renovacao",
        "Nome",
        "CPF/CNPJ",
        "Parceiro",
        "Origem",
        "Modelo",
        "Vendedor",
        "AGR",
        "Nome do AVP",
        "Valor Considerado",
        "Margem Bruta",
    ]
    return base[colunas].sort_values(["Status Renovacao", "Data", "Nome"])


def resumo_renovacoes_periodo(dados: pd.DataFrame, anos: Iterable[int], meses: Iterable[int]) -> tuple[pd.DataFrame, int, int]:
    linhas = []
    total_base = 0
    total_renovou = 0
    anos_disponiveis = set(dados["Ano"].dropna().astype(int).unique())
    for ano in sorted(int(a) for a in anos):
        if ano + 1 not in anos_disponiveis:
            continue
        prox = dados[(dados["Ano"] == ano + 1) & (dados["Documento Limpo"].astype(str).str.len() > 0)]
        renovados = set(prox["Documento Limpo"].dropna())
        for mes in sorted(int(m) for m in meses):
            base = dados[(dados["Ano"] == ano) & (dados["Mes"] == mes)].copy()
            if base.empty:
                continue
            status = base["Documento Limpo"].map(lambda doc: bool(str(doc).strip()) and doc in renovados)
            qtd_base = len(base)
            qtd_renovou = int(status.sum())
            total_base += qtd_base
            total_renovou += qtd_renovou
            linhas.append(
                {
                    "Ano base": ano,
                    "Mes base": NOMES_MESES.get(mes, str(mes)),
                    "Base": qtd_base,
                    "Renovados": qtd_renovou,
                    "Pendentes": qtd_base - qtd_renovou,
                    "% Renovacao": 0 if qtd_base == 0 else qtd_renovou / qtd_base,
                }
            )
    return pd.DataFrame(linhas), total_base, total_renovou


def cli_check(pasta: Path) -> int:
    dados, precos = carregar_dados(pasta)
    print(f"Pasta analisada: {pasta}")
    print(f"Planilhas mensais encontradas: {len(localizar_planilhas(pasta))}")
    print(f"Planilhas AVP encontradas: {len(localizar_planilhas_avp(pasta))}")
    print(f"Registros carregados: {len(dados)}")
    print(f"Parceiros com preco cadastrado: {len(precos)}")
    if dados.empty:
        print("Nenhum dado encontrado. Confira se os arquivos seguem o padrao: JANEIRO 2025.xls")
        return 1
    print(f"Periodo dos dados: {dados['Data'].min().date()} a {dados['Data'].max().date()}")
    print(f"Faturamento total considerado: {formatar_moeda(dados['Valor Considerado'].sum())}")
    print(f"Quantidade total: {len(dados)}")
    print(f"Margem bruta total: {formatar_moeda(dados['Margem Bruta'].sum())}")
    ausentes = dados["Preco Parceiro Ausente"].sum()
    if ausentes:
        print(f"Atencao: {ausentes} vendas de parceiro estao sem preco na planilha PARCEIROS.")
    return 0


def exigir_streamlit():
    try:
        import plotly.express as px
        import plotly.graph_objects as go
        import streamlit as st

        return st, px, go
    except ModuleNotFoundError as exc:
        pacote = exc.name
        print(
            f"O pacote '{pacote}' nao esta instalado. Rode: pip install -r requirements.txt\n"
            "Depois abra o dashboard com: streamlit run analise_mycert.py",
            file=sys.stderr,
        )
        raise SystemExit(1)


def tabela_formatada(df: pd.DataFrame) -> pd.DataFrame:
    saida = df.copy()
    for col in ["Faturamento", "Custo", "Margem_Bruta", "Valor Considerado", "Margem Bruta"]:
        if col in saida.columns:
            saida[col] = saida[col].map(formatar_moeda)
    for col in ["Margem_%", "Margem %", "Atingimento %", "% Renovacao"]:
        if col in saida.columns:
            saida[col] = (saida[col].astype(float) * 100).map(formatar_percentual)
    return saida


def gauge(go, titulo: str, valor_atual: float, valor_meta: float):
    atingimento = 0.0 if valor_meta == 0 else min((valor_atual / valor_meta) * 100, 200)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=atingimento,
            number={"suffix": "%"},
            title={"text": titulo},
            gauge={
                "axis": {"range": [0, 150]},
                "bar": {"color": "#1f77b4"},
                "steps": [
                    {"range": [0, 70], "color": "#f8d7da"},
                    {"range": [70, 100], "color": "#fff3cd"},
                    {"range": [100, 150], "color": "#d1e7dd"},
                ],
                "threshold": {"line": {"color": "#198754", "width": 4}, "thickness": 0.75, "value": 100},
            },
        )
    )
    fig.update_layout(height=260, margin=dict(l=20, r=20, t=45, b=10))
    return fig


def aplicar_estilo_dashboard(st):
    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 1.4rem;
                padding-bottom: 2rem;
            }
            div[data-testid="stMetric"] {
                background: #ffffff;
                border: 1px solid #e6edf3;
                border-radius: 12px;
                padding: 16px 18px;
                box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
            }
            div[data-testid="stMetric"] label {
                color: #64748b;
                font-weight: 700;
            }
            div[data-testid="stMetricValue"] {
                color: #0f172a;
                font-weight: 800;
            }
            .dashboard-hero {
                background: linear-gradient(135deg, #020617 0%, #052e16 54%, #16a34a 100%);
                border-radius: 16px;
                padding: 22px 26px;
                color: #ffffff;
                margin-bottom: 18px;
                box-shadow: 0 12px 30px rgba(15, 23, 42, 0.18);
            }
            .dashboard-hero h1 {
                margin: 0;
                font-size: 30px;
                line-height: 1.15;
            }
            .dashboard-hero p {
                margin: 8px 0 0 0;
                color: rgba(255,255,255,0.82);
                font-size: 14px;
            }
            .kpi-card {
                background: #ffffff;
                border: 1px solid #e6edf3;
                border-radius: 14px;
                padding: 16px 18px;
                box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
                min-height: 122px;
            }
            .kpi-label {
                color: #64748b;
                font-size: 13px;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: .03em;
            }
            .kpi-value {
                color: #0f172a;
                font-size: 26px;
                font-weight: 850;
                margin-top: 8px;
                white-space: nowrap;
            }
            .kpi-sub {
                color: #475569;
                font-size: 13px;
                margin-top: 6px;
            }
            .section-title {
                font-size: 18px;
                font-weight: 850;
                color: #0f172a;
                margin: 8px 0 10px 0;
            }
            button[data-baseweb="tab"] {
                background: #f8fafc;
                border: 1px solid #d1fae5;
                border-radius: 10px 10px 0 0;
                padding: 12px 18px;
                margin-right: 5px;
                color: #052e16;
                font-weight: 850;
            }
            button[data-baseweb="tab"][aria-selected="true"] {
                background: #052e16;
                color: #ffffff;
                border-color: #052e16;
            }
            button[data-baseweb="tab"]:hover {
                background: #dcfce7;
                color: #052e16;
            }
            button[kind="primary"], div.stDownloadButton > button {
                background: #16a34a;
                border-color: #16a34a;
                color: #ffffff;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def card_kpi(st, titulo: str, valor: str, subtitulo: str):
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{titulo}</div>
            <div class="kpi-value">{valor}</div>
            <div class="kpi-sub">{subtitulo}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def dinheiro_plotly(fig, eixo: str = "y"):
    if eixo == "x":
        fig.update_xaxes(tickprefix="R$ ", separatethousands=True)
    else:
        fig.update_yaxes(tickprefix="R$ ", separatethousands=True)
    return fig


def app_simulacao(st, px, go, pasta_padrao: Path):
    st.markdown(
        """
        <div class="dashboard-hero">
            <h1>SIMULAÇÃO</h1>
            <p>Analise uma planilha avulsa, compare metas e projete o fechamento por dias uteis.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar.expander("Apoio da simulacao", expanded=True):
        pasta_txt = st.text_input("Pasta com PARCEIROS", value=str(pasta_padrao), key="sim_pasta_apoio")
        pasta = Path(pasta_txt).expanduser()
        if not pasta.exists():
            st.error("Pasta de apoio nao encontrada.")
            return

    precos = carregar_precos_parceiros(pasta)
    upload = st.file_uploader("Suba a planilha do mes para simular", type=["xls", "xlsx", "html", "htm"])
    if upload is None:
        st.info("Envie uma planilha mensal para iniciar a simulacao.")
        return

    try:
        dados_sim = carregar_planilha_upload(upload, precos)
    except Exception as exc:
        st.error(f"Nao consegui ler a planilha enviada: {exc}")
        return

    if dados_sim.empty:
        st.warning("A planilha enviada nao trouxe registros validos.")
        return

    periodo_txt = f"{dados_sim['Data'].min().date().strftime('%d/%m/%Y')} a {dados_sim['Data'].max().date().strftime('%d/%m/%Y')}"
    st.caption(f"Arquivo carregado: {upload.name} | Periodo identificado: {periodo_txt}")

    with st.expander("Metas da simulacao", expanded=True):
        m1, m2 = st.columns(2)
        meta_qtd = m1.number_input("Meta em quantidade de certificados", min_value=0, value=0, step=1)
        meta_valor = m2.number_input("Meta em faturamento (R$)", min_value=0.0, value=0.0, step=1000.0, format="%.2f")

    total_faturamento = dados_sim["Valor Considerado"].sum()
    total_qtd = len(dados_sim)
    margem = dados_sim["Margem Bruta"].sum()
    ticket = total_faturamento / total_qtd if total_qtd else 0
    parceiros = dados_sim[dados_sim["Origem Normalizada"].eq("PARCEIRO")]
    interno = dados_sim[dados_sim["Origem Normalizada"].ne("PARCEIRO")]

    previsao = calcular_previsao_fechamento(dados_sim)
    previsao_qtd = previsao["previsao_qtd"]
    previsao_fat = previsao["previsao_faturamento"]

    k1, k2, k3 = st.columns(3)
    with k1:
        card_kpi(
            st,
            "Realizado geral",
            formatar_moeda(total_faturamento),
            f"{total_qtd:,}".replace(",", ".") + f" certificados | ticket {formatar_moeda(ticket)}",
        )
    with k2:
        card_kpi(
            st,
            "Previsao fechamento",
            formatar_moeda(previsao_fat),
            f"{previsao_qtd:.0f} certificados | {previsao['dias_uteis_restantes']} dias uteis restantes",
        )
    with k3:
        card_kpi(
            st,
            "Margem bruta",
            formatar_moeda(margem),
            f"Custo unitario {formatar_moeda(CUSTO_CERTIFICADO)}",
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Faturamento parceiros", formatar_moeda(parceiros["Valor Considerado"].sum()), f"{len(parceiros)} certificados")
    c2.metric("Faturamento interno", formatar_moeda(interno["Valor Considerado"].sum()), f"{len(interno)} certificados")
    c3.metric("Dias uteis realizados", previsao["dias_uteis_realizados"])
    c4.metric("Media diaria faturamento", formatar_moeda(previsao["media_faturamento"]))

    st.markdown('<div class="section-title">Meta x realizado x previsao</div>', unsafe_allow_html=True)
    g1, g2 = st.columns(2)
    g1.plotly_chart(gauge(go, "Atingimento da meta de faturamento", total_faturamento, meta_valor), use_container_width=True)
    g2.plotly_chart(gauge(go, "Atingimento da meta de quantidade", total_qtd, meta_qtd), use_container_width=True)

    comp_meta = pd.DataFrame(
        [
            {
                "Indicador": "Faturamento",
                "Meta": formatar_moeda(meta_valor),
                "Realizado": formatar_moeda(total_faturamento),
                "Previsao fechamento": formatar_moeda(previsao_fat),
                "% Realizado": formatar_percentual((0 if meta_valor == 0 else total_faturamento / meta_valor) * 100),
                "% Previsto": formatar_percentual((0 if meta_valor == 0 else previsao_fat / meta_valor) * 100),
            },
            {
                "Indicador": "Quantidade",
                "Meta": f"{int(meta_qtd):,}".replace(",", "."),
                "Realizado": f"{total_qtd:,}".replace(",", "."),
                "Previsao fechamento": f"{previsao_qtd:.0f}",
                "% Realizado": formatar_percentual((0 if meta_qtd == 0 else total_qtd / meta_qtd) * 100),
                "% Previsto": formatar_percentual((0 if meta_qtd == 0 else previsao_qtd / meta_qtd) * 100),
            },
        ]
    )
    mostrar_tabela(st, comp_meta, use_container_width=True, hide_index=True)

    if previsao["mes_fechado"]:
        st.success("Mes fechado: a previsao de fechamento foi igualada ao realizado.")

    faltantes = dados_sim[dados_sim["Preco Parceiro Ausente"]]
    if not faltantes.empty:
        with st.expander("Parceiros sem preco encontrado", expanded=False):
            mostrar_tabela(st, tabela_formatada(resumir(faltantes, "Parceiro")), use_container_width=True, hide_index=True)

    tab_geral, tab_parceiros, tab_agr, tab_tipo, tab_dias, tab_dados = st.tabs(
        ["Geral", "Parceiros", "AGR", "CPF x CNPJ", "Dias", "Dados"]
    )

    with tab_geral:
        por_origem = resumir(dados_sim, "Origem")
        ctab1, ctab2 = st.columns([1, 1])
        with ctab1:
            mostrar_tabela(st, tabela_formatada(por_origem), use_container_width=True, hide_index=True)
        fig = px.bar(
            por_origem,
            x="Origem",
            y="Faturamento",
            text=por_origem["Faturamento"].map(formatar_moeda),
            color="Origem",
            color_discrete_sequence=["#16a34a", "#052e16", "#22c55e"],
        )
        fig.update_layout(yaxis_title="Faturamento", xaxis_title="", plot_bgcolor="#ffffff")
        dinheiro_plotly(fig, "y")
        ctab2.plotly_chart(fig, use_container_width=True)

    with tab_parceiros:
        if parceiros.empty:
            st.info("Sem vendas de parceiros na planilha enviada.")
        else:
            performance = resumir(parceiros, "Parceiro")
            mostrar_tabela(st, tabela_formatada(performance), use_container_width=True, hide_index=True, height=420)
            top_fat = performance.head(10).sort_values("Faturamento")
            fig = px.bar(
                top_fat,
                x="Faturamento",
                y="Parceiro",
                orientation="h",
                title="Top parceiros por faturamento",
                color_discrete_sequence=["#16a34a"],
            )
            fig.update_layout(plot_bgcolor="#ffffff")
            dinheiro_plotly(fig, "x")
            st.plotly_chart(fig, use_container_width=True)

    with tab_agr:
        ranking_agr = resumir(dados_sim, "AGR")
        mostrar_tabela(st, tabela_formatada(ranking_agr), use_container_width=True, hide_index=True, height=420)

    with tab_tipo:
        por_tipo = resumir(dados_sim, "Tipo")
        t1, t2 = st.columns([1, 1])
        with t1:
            mostrar_tabela(st, tabela_formatada(por_tipo), use_container_width=True, hide_index=True)
        t2.plotly_chart(px.pie(por_tipo, names="Tipo", values="Quantidade", title="Quantidade por tipo"), use_container_width=True)

    with tab_dias:
        dias = (
            dados_sim.groupby("Data")
            .agg(Quantidade=("Pedido", "count"), Faturamento=("Valor Considerado", "sum"))
            .reset_index()
            .sort_values("Data")
        )
        fig = px.line(dias, x="Data", y="Faturamento", markers=True, title="Faturamento por dia")
        fig.update_layout(plot_bgcolor="#ffffff")
        dinheiro_plotly(fig, "y")
        st.plotly_chart(fig, use_container_width=True)
        mostrar_tabela(st, tabela_formatada(dias), use_container_width=True, hide_index=True)

    with tab_dados:
        mostrar_tabela(st, dados_sim, use_container_width=True, hide_index=True)


def app_streamlit(pasta_padrao: Path):
    st, px, go = exigir_streamlit()
    st.set_page_config(page_title="Analise de Resultados My Cert", layout="wide")
    aplicar_estilo_dashboard(st)

    if "pagina_atual" not in st.session_state:
        st.session_state["pagina_atual"] = "Dashboard"

    with st.sidebar:
        st.markdown("### Menu")
        dashboard_tipo = "primary" if st.session_state["pagina_atual"] == "Dashboard" else "secondary"
        simulacao_tipo = "primary" if st.session_state["pagina_atual"] == "SIMULAÇÃO" else "secondary"
        if st.button("Dashboard", type=dashboard_tipo, use_container_width=True):
            st.session_state["pagina_atual"] = "Dashboard"
        if st.button("SIMULAÇÃO", type=simulacao_tipo, use_container_width=True):
            st.session_state["pagina_atual"] = "SIMULAÇÃO"

    if st.session_state["pagina_atual"] == "SIMULAÇÃO":
        app_simulacao(st, px, go, pasta_padrao)
        return

    st.markdown(
        """
        <div class="dashboard-hero">
            <h1>Analise de Resultados My Cert</h1>
            <p>Faturamento, margem, parceiros, AGR, renovacoes e comparativo ano -1 em uma visao executiva.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("Controles")
        mostrar_filtros = st.toggle("Exibir filtros", value=True)
        pasta_txt = st.text_input("Pasta das planilhas", value=str(pasta_padrao))
        pasta = Path(pasta_txt).expanduser()
        if not pasta.exists():
            st.error("Pasta nao encontrada.")
            st.stop()

    dados, precos = carregar_dados(pasta)
    qtd_avp = int(dados.get("AVP Encontrado", pd.Series(dtype=bool)).sum()) if not dados.empty else 0
    total_registros = len(dados) if not dados.empty else 0
    if total_registros:
        st.caption(f"AVP aplicado em {qtd_avp:,} de {total_registros:,} registros via Protocolo.".replace(",", "."))
    if dados.empty:
        st.warning("Nenhuma planilha mensal encontrada no padrao: JANEIRO 2025, FEVEREIRO 2025...")
        st.stop()

    anos_disponiveis = sorted(dados["Ano"].dropna().unique().tolist())
    meses_disponiveis = sorted(dados["Mes"].dropna().unique().tolist())
    data_min = dados["Data"].min().date()
    data_max = dados["Data"].max().date()
    origens_disponiveis = sorted(dados["Origem"].unique())
    tipos_disponiveis = sorted(dados["Tipo"].unique())

    anos = anos_disponiveis
    meses = meses_disponiveis
    inicio, fim = data_min, data_max
    origem = origens_disponiveis
    tipo = tipos_disponiveis

    if mostrar_filtros:
        with st.sidebar.expander("Filtros da analise", expanded=True):
            anos = st.multiselect("Ano", anos_disponiveis, default=anos_disponiveis)
            meses = st.multiselect(
                "Mes",
                meses_disponiveis,
                default=meses_disponiveis,
                format_func=lambda m: NOMES_MESES.get(int(m), str(m)),
            )
            periodo = st.date_input(
                "Periodo por data",
                value=(data_min, data_max),
                min_value=data_min,
                max_value=data_max,
            )
            if isinstance(periodo, tuple) and len(periodo) == 2:
                inicio, fim = periodo
            origem = st.multiselect("Origem", origens_disponiveis, default=origens_disponiveis)
            tipo = st.multiselect("Tipo", tipos_disponiveis, default=tipos_disponiveis)
    else:
        st.sidebar.caption("Filtros ocultos. Usando a base completa.")

    filtrado = filtrar_periodo(dados, anos, meses, inicio, fim)
    filtrado = filtrado[filtrado["Origem"].isin(origem) & filtrado["Tipo"].isin(tipo)].copy()

    if filtrado.empty:
        st.warning("Nenhum registro encontrado para os filtros selecionados.")
        st.stop()

    total_faturamento = filtrado["Valor Considerado"].sum()
    total_qtd = len(filtrado)
    margem = filtrado["Margem Bruta"].sum()
    margem_pct = 0 if total_faturamento == 0 else margem / total_faturamento

    parceiros = filtrado[filtrado["Origem Normalizada"].eq("PARCEIRO")].copy()
    interno = filtrado[filtrado["Origem Normalizada"].ne("PARCEIRO")].copy()
    fat_parceiros = parceiros["Valor Considerado"].sum()
    fat_interno = interno["Valor Considerado"].sum()
    margem_parceiros = parceiros["Margem Bruta"].sum()
    margem_interno = interno["Margem Bruta"].sum()
    ticket_geral = total_faturamento / total_qtd if total_qtd else 0
    ticket_parceiros = fat_parceiros / len(parceiros) if len(parceiros) else 0
    ticket_interno = fat_interno / len(interno) if len(interno) else 0

    k1, k2, k3 = st.columns(3)
    with k1:
        card_kpi(
            st,
            "Faturamento geral",
            formatar_moeda(total_faturamento),
            f"{total_qtd:,}".replace(",", ".")
            + f" certificados | ticket {formatar_moeda(ticket_geral)} | margem {formatar_moeda(margem)}",
        )
    with k2:
        card_kpi(
            st,
            "Faturamento parceiros",
            formatar_moeda(fat_parceiros),
            f"{len(parceiros):,}".replace(",", ".")
            + f" certificados | ticket {formatar_moeda(ticket_parceiros)} | margem {formatar_moeda(margem_parceiros)}",
        )
    with k3:
        card_kpi(
            st,
            "Faturamento interno",
            formatar_moeda(fat_interno),
            f"{len(interno):,}".replace(",", ".")
            + f" certificados | ticket {formatar_moeda(ticket_interno)} | margem {formatar_moeda(margem_interno)}",
        )

    c1, c2, c3 = st.columns(3)
    c1.metric("Margem bruta geral", formatar_moeda(margem), formatar_percentual(margem_pct * 100))
    c2.metric("Ticket medio", formatar_moeda(total_faturamento / total_qtd if total_qtd else 0))
    c3.metric("Custo unitario", formatar_moeda(CUSTO_CERTIFICADO))

    faltantes = filtrado[filtrado["Preco Parceiro Ausente"]]
    if not faltantes.empty:
        parceiros_faltantes = resumir(faltantes, "Parceiro")
        st.warning(
            f"{len(faltantes)} vendas de parceiro estao sem preco na planilha PARCEIROS. "
            "Atualize a planilha com os parceiros listados abaixo; enquanto isso, usei o valor da planilha mensal."
        )
        with st.expander("Ver parceiros nao encontrados na planilha PARCEIROS", expanded=True):
            mostrar_tabela(st, tabela_formatada(parceiros_faltantes), use_container_width=True, hide_index=True, height=240)
            st.download_button(
                "Baixar parceiros nao encontrados CSV",
                data=parceiros_faltantes.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                file_name="parceiros_nao_encontrados.csv",
                mime="text/csv",
            )

    tab_geral, tab_parceiros, tab_agr, tab_tipo, tab_dias, tab_renovacao, tab_comparativo, tab_dados = st.tabs(
        [
            "Geral",
            "Parceiros",
            "AGR",
            "CPF x CNPJ",
            "Dias",
            "Renovacao",
            "Ano -1",
            "Dados",
        ]
    )

    with tab_geral:
        st.markdown('<div class="section-title">Faturamento por origem</div>', unsafe_allow_html=True)
        por_origem = resumir(filtrado, "Origem")
        g1, g2 = st.columns([1, 1])
        with g1:
            mostrar_tabela(st, tabela_formatada(por_origem), use_container_width=True, hide_index=True)
        fig = px.bar(
            por_origem,
            x="Origem",
            y="Faturamento",
            text=por_origem["Faturamento"].map(formatar_moeda),
            color="Origem",
            color_discrete_sequence=["#16a34a", "#052e16", "#22c55e"],
        )
        fig.update_layout(yaxis_title="Faturamento", xaxis_title="", plot_bgcolor="#ffffff")
        dinheiro_plotly(fig, "y")
        g2.plotly_chart(fig, use_container_width=True)

    with tab_parceiros:
        if parceiros.empty:
            st.info("Sem vendas de parceiros no filtro selecionado.")
        else:
            performance = resumir(parceiros, "Parceiro")
            st.markdown('<div class="section-title">Tabela de performance dos parceiros</div>', unsafe_allow_html=True)
            mostrar_tabela(
                st,
                tabela_formatada(performance),
                use_container_width=True,
                hide_index=True,
                height=420,
            )
            p1, p2 = st.columns(2)
            top_qtd = performance.sort_values("Quantidade", ascending=False).head(10)
            fig_qtd = px.bar(
                top_qtd.sort_values("Quantidade"),
                x="Quantidade",
                y="Parceiro",
                orientation="h",
                title="Top parceiros por quantidade",
                color_discrete_sequence=["#052e16"],
            )
            fig_qtd.update_layout(plot_bgcolor="#ffffff")
            p1.plotly_chart(fig_qtd, use_container_width=True)
            top_fat = performance.sort_values("Faturamento", ascending=False).head(10)
            fig_fat = px.bar(
                top_fat.sort_values("Faturamento"),
                x="Faturamento",
                y="Parceiro",
                orientation="h",
                title="Top parceiros por faturamento",
                color_discrete_sequence=["#16a34a"],
            )
            fig_fat.update_layout(plot_bgcolor="#ffffff")
            dinheiro_plotly(fig_fat, "x")
            p2.plotly_chart(fig_fat, use_container_width=True)

    with tab_agr:
        st.markdown('<div class="section-title">Ranking dos AGR</div>', unsafe_allow_html=True)
        ranking_agr = resumir(filtrado, "AGR")
        mostrar_tabela(st, tabela_formatada(ranking_agr), use_container_width=True, hide_index=True, height=420)
        a1, a2 = st.columns(2)
        top_agr_fat = ranking_agr.head(20).sort_values("Faturamento")
        fig_agr_fat = px.bar(
            top_agr_fat,
            x="Faturamento",
            y="AGR",
            orientation="h",
            title="Top AGR por faturamento",
            color_discrete_sequence=["#16a34a"],
        )
        fig_agr_fat.update_layout(plot_bgcolor="#ffffff")
        dinheiro_plotly(fig_agr_fat, "x")
        a1.plotly_chart(fig_agr_fat, use_container_width=True)
        top_agr_qtd = ranking_agr.sort_values("Quantidade", ascending=False).head(20).sort_values("Quantidade")
        fig_agr_qtd = px.bar(
            top_agr_qtd,
            x="Quantidade",
            y="AGR",
            orientation="h",
            title="Top AGR por quantidade",
            color_discrete_sequence=["#052e16"],
        )
        fig_agr_qtd.update_layout(plot_bgcolor="#ffffff")
        a2.plotly_chart(fig_agr_qtd, use_container_width=True)

    with tab_tipo:
        st.markdown('<div class="section-title">CPF x CNPJ</div>', unsafe_allow_html=True)
        por_tipo = resumir(filtrado, "Tipo")
        t1, t2 = st.columns([1, 1])
        with t1:
            mostrar_tabela(st, tabela_formatada(por_tipo), use_container_width=True, hide_index=True)
        t2.plotly_chart(px.pie(por_tipo, names="Tipo", values="Quantidade", title="Quantidade por tipo"), use_container_width=True)
        tipo_drill = st.selectbox("Drill por tipo", sorted(filtrado["Tipo"].unique()))
        detalhe_tipo = filtrado[filtrado["Tipo"] == tipo_drill].copy()
        mostrar_tabela(
            st,
            detalhe_tipo[
                [
                    "Data",
                    "Nome",
                    "CPF/CNPJ",
                    "Modelo",
                    "Pedido",
                    "Origem",
                    "Parceiro",
                    "Vendedor",
                    "Valor Considerado",
                    "Margem Bruta",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    with tab_dias:
        st.markdown('<div class="section-title">Movimentacao diaria</div>', unsafe_allow_html=True)
        dias = (
            filtrado.groupby("Data")
            .agg(Quantidade=("Pedido", "count"), Faturamento=("Valor Considerado", "sum"))
            .reset_index()
            .sort_values("Data")
        )
        top5 = dias.nlargest(5, "Faturamento")
        fig = px.line(dias, x="Data", y="Faturamento", markers=True, title="Faturamento por dia")
        fig.add_trace(
            go.Scatter(
                x=top5["Data"],
                y=top5["Faturamento"],
                mode="markers+text",
                text=top5["Faturamento"].map(formatar_moeda),
                textposition="top center",
                marker=dict(size=12, color="#dc3545"),
                name="Top 5 dias",
            )
        )
        fig.update_layout(plot_bgcolor="#ffffff")
        dinheiro_plotly(fig, "y")
        st.plotly_chart(fig, use_container_width=True)
        fig_dias_qtd = px.bar(dias, x="Data", y="Quantidade", title="Quantidade por dia", color_discrete_sequence=["#052e16"])
        fig_dias_qtd.update_layout(plot_bgcolor="#ffffff")
        st.plotly_chart(fig_dias_qtd, use_container_width=True)
        mostrar_tabela(st, tabela_formatada(dias), use_container_width=True, hide_index=True)

    with tab_renovacao:
        st.markdown('<div class="section-title">Lista de renovacao</div>', unsafe_allow_html=True)
        anos_base = sorted([ano for ano in dados["Ano"].unique() if ano + 1 in set(dados["Ano"].unique())])
        if not anos_base:
            st.info("Para gerar renovacao, inclua planilhas de anos consecutivos, por exemplo 2025 e 2026.")
        else:
            st.caption("Esta aba usa filtros proprios e ignora o filtro lateral do dashboard.")
            r1, r2 = st.columns(2)
            ano_base = r1.selectbox("Ano base", anos_base, index=0)
            meses_base = sorted(dados.loc[dados["Ano"] == ano_base, "Mes"].unique())
            meses_base_sel = r2.multiselect(
                "Meses base",
                meses_base,
                default=meses_base,
                format_func=lambda m: NOMES_MESES.get(int(m), str(m)),
            )
            st.caption(
                "A lista considera como renovado qualquer CPF/CNPJ dos meses base que apareca em qualquer mes do ano seguinte."
            )
            if not meses_base_sel:
                st.info("Selecione pelo menos um mes base para gerar a lista.")
            else:
                resumo_renov, base_sel, renov_sel = resumo_renovacoes_periodo(dados, [int(ano_base)], meses_base_sel)
                pct_sel = 0 if base_sel == 0 else renov_sel / base_sel
                rsel1, rsel2, rsel3, rsel4 = st.columns(4)
                rsel1.metric("Base selecionada", f"{base_sel:,}".replace(",", "."))
                rsel2.metric("Renovados", f"{renov_sel:,}".replace(",", "."))
                rsel3.metric("Pendentes", f"{base_sel - renov_sel:,}".replace(",", "."))
                rsel4.metric("% renovacao", formatar_percentual(pct_sel * 100))
                with st.expander("Resumo de renovacao dos meses selecionados", expanded=False):
                    mostrar_tabela(st, tabela_formatada(resumo_renov), use_container_width=True, hide_index=True)

                renov = lista_renovacoes(dados, int(ano_base), meses_base_sel)
                qtd_renovou = (renov["Status Renovacao"] == "Renovou").sum()
                qtd_pendente = (renov["Status Renovacao"] == "Pendente").sum()
                rr1, rr2, rr3 = st.columns(3)
                rr1.metric("Base dos meses", len(renov))
                rr2.metric(f"Renovados em {int(ano_base) + 1}", qtd_renovou)
                rr3.metric("Lista para trabalhar", qtd_pendente)
                status = st.multiselect("Status", ["Pendente", "Renovou"], default=["Pendente", "Renovou"])
                renov_filtrada = renov[renov["Status Renovacao"].isin(status)]
                mostrar_tabela(st, renov_filtrada, use_container_width=True, hide_index=True)
                st.download_button(
                    "Baixar lista de renovacao CSV",
                    data=renov_filtrada.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                    file_name=f"lista_renovacao_meses_selecionados_{ano_base}.csv",
                    mime="text/csv",
                )

    with tab_comparativo:
        st.markdown('<div class="section-title">Comparativo com ano -1</div>', unsafe_allow_html=True)
        anos_filtro = sorted(filtrado["Ano"].unique())
        ano_atual = st.selectbox("Ano para comparar", anos_filtro, index=len(anos_filtro) - 1)
        meses_comp = sorted(filtrado.loc[filtrado["Ano"] == ano_atual, "Mes"].unique())
        atual = filtrado[(filtrado["Ano"] == ano_atual) & (filtrado["Mes"].isin(meses_comp))]
        anterior = dados[(dados["Ano"] == ano_atual - 1) & (dados["Mes"].isin(meses_comp))]
        fat_atual = atual["Valor Considerado"].sum()
        fat_anterior = anterior["Valor Considerado"].sum()
        qtd_atual = len(atual)
        qtd_anterior = len(anterior)
        comp = pd.DataFrame(
            [
                {
                    "Indicador": "Faturamento",
                    "Ano atual": fat_atual,
                    "Ano -1": fat_anterior,
                    "Atingimento %": 0 if fat_anterior == 0 else fat_atual / fat_anterior,
                },
                {
                    "Indicador": "Quantidade",
                    "Ano atual": qtd_atual,
                    "Ano -1": qtd_anterior,
                    "Atingimento %": 0 if qtd_anterior == 0 else qtd_atual / qtd_anterior,
                },
            ]
        )
        c1, c2 = st.columns(2)
        c1.plotly_chart(gauge(go, "Atingimento faturamento vs ano -1", fat_atual, fat_anterior), use_container_width=True)
        c2.plotly_chart(gauge(go, "Atingimento quantidade vs ano -1", qtd_atual, qtd_anterior), use_container_width=True)
        comp_fmt = pd.DataFrame(
            [
                {
                    "Indicador": "Faturamento",
                    "Ano atual": formatar_moeda(fat_atual),
                    "Ano -1": formatar_moeda(fat_anterior),
                    "Atingimento %": formatar_percentual((0 if fat_anterior == 0 else fat_atual / fat_anterior) * 100),
                },
                {
                    "Indicador": "Quantidade",
                    "Ano atual": f"{qtd_atual:,}".replace(",", "."),
                    "Ano -1": f"{qtd_anterior:,}".replace(",", "."),
                    "Atingimento %": formatar_percentual((0 if qtd_anterior == 0 else qtd_atual / qtd_anterior) * 100),
                },
            ]
        )
        mostrar_tabela(st, comp_fmt, use_container_width=True, hide_index=True)

    with tab_dados:
        st.subheader("Base filtrada")
        mostrar_tabela(st, filtrado, use_container_width=True, hide_index=True)
        st.download_button(
            "Baixar base filtrada CSV",
            data=filtrado.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
            file_name="base_filtrada_mycert.csv",
            mime="text/csv",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Dashboard de analise de resultados da My Cert.")
    parser.add_argument("--pasta", default=".", help="Pasta onde estao as planilhas mensais e a planilha PARCEIROS.")
    parser.add_argument("--check", action="store_true", help="Valida a leitura dos arquivos e mostra um resumo no CMD.")
    args = parser.parse_args()
    pasta = Path(args.pasta).expanduser().resolve()
    if args.check:
        return cli_check(pasta)
    app_streamlit(pasta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
