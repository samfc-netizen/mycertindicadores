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


MYCERT_LOGO_DATA_URI = "data:image/png;base64,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"

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


def normalizar_nome_avp(valor: object) -> str:
    """Normaliza nomes para casar AGR truncado/corrompido com o nome completo do AVP."""
    texto = normalizar_texto(valor)
    texto = texto.replace("�", "")
    texto = re.sub(r"[^A-Z0-9 ]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _mapa_nomes_avp_por_mes(mapa_avp: pd.DataFrame) -> dict[tuple[int, int], list[tuple[str, str, str]]]:
    """Lista nomes únicos de AVP por competência para o fallback por nome."""
    resultado: dict[tuple[int, int], list[tuple[str, str, str]]] = {}
    if mapa_avp.empty:
        return resultado

    base = mapa_avp[["Ano Arquivo", "Mes Arquivo", "Nome do AVP", "Arquivo AVP"]].drop_duplicates().copy()
    base["Nome Normalizado"] = base["Nome do AVP"].map(normalizar_nome_avp)
    base = base[base["Nome Normalizado"].str.len() >= 5]

    for (ano, mes), grupo in base.groupby(["Ano Arquivo", "Mes Arquivo"]):
        resultado[(int(ano), int(mes))] = [
            (row["Nome Normalizado"], str(row["Nome do AVP"]).strip(), str(row["Arquivo AVP"]).strip())
            for _, row in grupo.iterrows()
        ]
    return resultado


def _encontrar_avp_por_nome(agr_original: object, candidatos: list[tuple[str, str, str]]) -> tuple[str, str]:
    """Retorna o AVP quando o AGR é prefixo inequívoco do nome completo (ou vice-versa)."""
    agr_norm = normalizar_nome_avp(agr_original)
    if len(agr_norm) < 5:
        return "", ""

    matches = []
    for nome_norm, nome_completo, arquivo in candidatos:
        if agr_norm == nome_norm or nome_norm.startswith(agr_norm) or agr_norm.startswith(nome_norm):
            matches.append((nome_completo, arquivo))

    # Só corrige automaticamente se houver uma única pessoa possível.
    unicos = {(nome, arquivo) for nome, arquivo in matches}
    if len(unicos) == 1:
        return next(iter(unicos))
    return "", ""


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
    dados["AVP Encontrado Por"] = ""

    if mapa_avp.empty:
        dados["AVP Encontrado"] = False
        return dados

    # 1) Regra principal: protocolo + competência.
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

    encontrou_protocolo = dados["Nome do AVP"].astype(str).str.strip() != ""
    dados.loc[encontrou_protocolo, "AVP Encontrado Por"] = "Protocolo"

    # 2) Fallback: quando o protocolo não existe na planilha AGO/AGOSTO,
    # tenta recuperar o nome completo a partir do AGR truncado.
    # Não aplica em vendas de parceiro para evitar associação indevida.
    nomes_por_mes = _mapa_nomes_avp_por_mes(mapa_avp)
    origem_norm = dados.get("Origem Normalizada", pd.Series("", index=dados.index)).fillna("").astype(str)
    pendentes = (~encontrou_protocolo) & (~origem_norm.eq("PARCEIRO"))

    for idx in dados.index[pendentes]:
        try:
            chave = (int(dados.at[idx, "Ano Arquivo"]), int(dados.at[idx, "Mes Arquivo"]))
        except (TypeError, ValueError):
            continue
        nome, arquivo = _encontrar_avp_por_nome(dados.at[idx, "AGR Original"], nomes_por_mes.get(chave, []))
        if nome:
            dados.at[idx, "Nome do AVP"] = nome
            dados.at[idx, "Arquivo AVP"] = arquivo
            dados.at[idx, "AVP Encontrado Por"] = "Nome AGR"

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


def assinatura_pasta_dados(pasta: Path) -> tuple[tuple[str, int, int], ...]:
    """Assinatura barata da pasta para invalidar o cache apenas quando os arquivos mudarem."""
    extensoes = {".xls", ".xlsx", ".csv", ".html", ".htm"}
    assinatura = []
    try:
        for caminho in pasta.iterdir():
            if not caminho.is_file() or caminho.suffix.lower() not in extensoes:
                continue
            try:
                stat = caminho.stat()
                assinatura.append((caminho.name, stat.st_mtime_ns, stat.st_size))
            except OSError:
                continue
    except OSError:
        return tuple()
    return tuple(sorted(assinatura))


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

            .mycert-sidebar-logo {
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 10px 8px 18px 8px;
                margin-bottom: 4px;
            }
            .mycert-sidebar-logo img {
                width: 100%;
                max-width: 245px;
                height: auto;
                display: block;
            }
            .menu-label {
                color: #64748b;
                font-size: 11px;
                font-weight: 800;
                letter-spacing: .10em;
                margin: 2px 0 8px 2px;
            }
            .menu-divider {
                height: 1px;
                background: #e2e8f0;
                margin: 14px 0 8px 0;
            }
            section[data-testid="stSidebar"] div.stButton > button {
                min-height: 44px;
                border-radius: 10px;
                font-weight: 800;
                transition: all .15s ease;
            }
            section[data-testid="stSidebar"] div.stButton > button:hover {
                transform: translateY(-1px);
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

    @st.cache_data(show_spinner=False, max_entries=8)
    def carregar_dados_cacheado(pasta_str: str, assinatura):
        # A assinatura participa da chave do cache. Se qualquer arquivo mudar,
        # o Streamlit recarrega a base; em interacoes comuns, reutiliza a memoria.
        return carregar_dados(Path(pasta_str))

    st.set_page_config(page_title="Analise de Resultados My Cert", layout="wide")
    aplicar_estilo_dashboard(st)

    if "pagina_atual" not in st.session_state:
        st.session_state["pagina_atual"] = "Dashboard"

    def navegar_para(pagina: str):
        # Callback executado antes do rerun do Streamlit.
        # Isso elimina a sensacao de precisar clicar duas vezes no menu.
        st.session_state["pagina_atual"] = pagina

    with st.sidebar:
        st.markdown(
            f"""
            <div class="mycert-sidebar-logo">
                <img src="{MYCERT_LOGO_DATA_URI}" alt="MyCert">
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="menu-label">NAVEGAÇÃO</div>', unsafe_allow_html=True)
        dashboard_tipo = "primary" if st.session_state["pagina_atual"] == "Dashboard" else "secondary"
        simulacao_tipo = "primary" if st.session_state["pagina_atual"] == "SIMULAÇÃO" else "secondary"
        st.button(
            "Dashboard",
            key="menu_dashboard",
            type=dashboard_tipo,
            use_container_width=True,
            on_click=navegar_para,
            args=("Dashboard",),
        )
        st.button(
            "Simulação",
            key="menu_simulacao",
            type=simulacao_tipo,
            use_container_width=True,
            on_click=navegar_para,
            args=("SIMULAÇÃO",),
        )
        st.markdown('<div class="menu-divider"></div>', unsafe_allow_html=True)

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

    assinatura = assinatura_pasta_dados(pasta)
    with st.spinner("Carregando base..."):
        dados, precos = carregar_dados_cacheado(str(pasta.resolve()), assinatura)
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
