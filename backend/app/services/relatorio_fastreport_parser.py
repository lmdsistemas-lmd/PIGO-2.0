from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET
import html
import re
from datetime import date


def _get_attr(element: ET.Element, key: str) -> Optional[str]:
    value = element.attrib.get(key)
    if isinstance(value, str):
        return value.strip()
    return value


def _decode_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return value

    decoded = html.unescape(value)
    decoded = decoded.replace("\r\n", "\n").replace("\r", "\n")
    decoded = decoded.replace("#13;", "\n").replace("#10;", "\n")
    decoded = re.sub(r"\n{3,}", "\n\n", decoded)

    return decoded.strip()


def _limpar_sql_fastreport(sql_text: Optional[str]) -> Optional[str]:
    if not sql_text:
        return sql_text

    texto = sql_text.strip()

    # remove lixo/base64 no fim, quando existir
    lixo_match = re.search(r"\n[eE][A-Za-z0-9+/=]{40,}\s*$", texto)
    if lixo_match:
        texto = texto[:lixo_match.start()].rstrip()

    texto = re.sub(r"[ \t]*[eE][A-Za-z0-9+/=]{80,}\s*$", "", texto).rstrip()

    # remove ; finais
    while texto.endswith(";"):
        texto = texto[:-1].strip()

    return texto


def _is_band_tag(tag: str) -> bool:
    if not tag or not tag.startswith("Tfrx"):
        return False

    tag_lower = tag.lower()
    return "band" in tag_lower or tag_lower in {
        "tfrxreporttitle",
        "tfrxpageheader",
        "tfrxpagefooter",
        "tfrxcolumnheader",
        "tfrxcolumnfooter",
        "tfrxheader",
        "tfrxfooter",
        "tfrxmasterdata",
        "tfrxdetaildata",
        "tfrxgroupheader",
        "tfrxgroupfooter",
        "tfrxreportsummary",
        "tfrxchild",
        "tfrxoverlay",
    }


def _iter_non_band_descendants(element: ET.Element):
    for child in list(element):
        if _is_band_tag(child.tag):
            continue

        yield child

        for nested in _iter_non_band_descendants(child):
            yield nested


def _extract_memos_from_band(
    band: ET.Element,
    page_name: Optional[str],
    page_index: int,
    band_name: Optional[str],
    band_type: Optional[str],
) -> List[Dict[str, Any]]:
    memos: List[Dict[str, Any]] = []

    for node in _iter_non_band_descendants(band):
        if node.tag != "TfrxMemoView":
            continue

        memo_info = {
            "name": _get_attr(node, "Name"),
            "text": _decode_text(_get_attr(node, "Text")),
            "page_name": page_name,
            "page_index": page_index,
            "left": _get_attr(node, "Left"),
            "top": _get_attr(node, "Top"),
            "width": _get_attr(node, "Width"),
            "height": _get_attr(node, "Height"),
            "data_field": _get_attr(node, "DataField"),
            "data_set": _get_attr(node, "DataSet"),
            "h_align": _get_attr(node, "HAlign"),
            "v_align": _get_attr(node, "VAlign"),
            "font_name": _get_attr(node, "Font.Name"),
            "font_size": _get_attr(node, "Font.Size"),
            "font_style": _get_attr(node, "Font.Style"),
            "color": _get_attr(node, "Color"),
            "fill_color": _get_attr(node, "Fill.Color"),
            "border_color": _get_attr(node, "Frame.Color"),
            "border_width": _get_attr(node, "Frame.Width"),
            "band_name": band_name,
            "band_type": band_type,
        }

        memos.append(memo_info)

    return memos


def _extract_bands_from_node(
    node: ET.Element,
    page_name: Optional[str],
    page_index: int,
    bands: List[Dict[str, Any]],
    memos: List[Dict[str, Any]],
    parent_band_name: Optional[str] = None,
) -> None:
    for child in list(node):
        if not _is_band_tag(child.tag):
            _extract_bands_from_node(
                child,
                page_name,
                page_index,
                bands,
                memos,
                parent_band_name=parent_band_name,
            )
            continue

        band_name = _get_attr(child, "Name")
        band_type = child.tag

        band_info = {
            "name": band_name,
            "type": band_type,
            "page_name": page_name,
            "page_index": page_index,
            "parent_band_name": parent_band_name,
            "child_band_name": _get_attr(child, "Child"),
            "data_set": _get_attr(child, "DataSet"),
            "condition": _decode_text(_get_attr(child, "Condition")),
            "left": _get_attr(child, "Left"),
            "top": _get_attr(child, "Top"),
            "width": _get_attr(child, "Width"),
            "height": _get_attr(child, "Height"),
        }

        bands.append(band_info)

        memos.extend(
            _extract_memos_from_band(
                child,
                page_name=page_name,
                page_index=page_index,
                band_name=band_name,
                band_type=band_type,
            )
        )

        _extract_bands_from_node(
            child,
            page_name,
            page_index,
            bands,
            memos,
            parent_band_name=band_name,
        )


def _parse_layout_visual(root: ET.Element) -> Dict[str, Any]:
    pages: List[Dict[str, Any]] = []
    bands: List[Dict[str, Any]] = []
    memos: List[Dict[str, Any]] = []

    for page_index, page in enumerate(root.findall(".//TfrxReportPage")):
        page_name = _get_attr(page, "Name")

        pages.append(
            {
                "name": page_name,
                "width": _get_attr(page, "Width"),
                "height": _get_attr(page, "Height"),
            }
        )

        _extract_bands_from_node(
            page,
            page_name=page_name,
            page_index=page_index,
            bands=bands,
            memos=memos,
        )

    return {
        "pages": pages,
        "bands": bands,
        "memos": memos,
    }


def _infer_parameter_metadata(queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    today = date.today()
    first_day = today.replace(day=1)

    unique_params: Dict[str, Dict[str, Any]] = {}

    for query in queries:
        for param in query.get("parametros", []):
            original_name = (param.get("name") or "").strip()
            datatype = (param.get("datatype") or "").strip()

            if not original_name:
                continue

            key = original_name.upper()

            if key in unique_params:
                continue

            datatype_lower = datatype.lower()
            inferred_type = "str"
            semantic_key = key.lower()
            default_value: Any = ""

            if "date" in datatype_lower:
                inferred_type = "date"

                if "INICIAL" in key or "INICIO" in key or "INI" in key:
                    semantic_key = "data_inicial"
                    default_value = first_day.isoformat()
                elif "FINAL" in key or "FIM" in key:
                    semantic_key = "data_final"
                    default_value = today.isoformat()
                else:
                    semantic_key = "data"
                    default_value = today.isoformat()

            elif any(
                token in datatype_lower
                for token in ["integer", "smallint", "bigint", "int"]
            ):
                inferred_type = "int"
                default_value = 0

                if "EMPRESA" in key:
                    semantic_key = "empresa"
                    default_value = 1
                elif "VENDEDOR" in key:
                    semantic_key = "vendedor"
                elif "CLIENTE" in key:
                    semantic_key = "cliente"
                elif "NATUREZA" in key:
                    semantic_key = "natureza"
                elif "GRUPO" in key:
                    semantic_key = "grupo"
                elif "MARCA" in key:
                    semantic_key = "marca"
                elif "CIDADE" in key:
                    semantic_key = "cidade"
                elif "REGIAO" in key or "REGIÃO" in key:
                    semantic_key = "regiao"
                elif "FORNECEDOR" in key:
                    semantic_key = "fornecedor"
                elif "FILIAL" in key:
                    semantic_key = "filial"
                elif "PRODUTO" in key:
                    semantic_key = "produto"
                elif "ROTA" in key:
                    semantic_key = "rota"

            elif any(
                token in datatype_lower
                for token in ["numeric", "float", "double", "decimal"]
            ):
                inferred_type = "number"
                default_value = 0

            if key == "PANALISE":
                semantic_key = "analise"
                inferred_type = "str"
                default_value = "GRUPO"

            if key == "TIPODATA":
                semantic_key = "tipo_data"
                inferred_type = "str"
                default_value = "EMISSAO"

            unique_params[key] = {
                "original_name": original_name,
                "inferred_type": inferred_type,
                "semantic_key": semantic_key,
                "default_value": default_value,
            }

    return list(unique_params.values())


def _extract_sql_from_query_node(query: ET.Element) -> Optional[str]:
    """
    Tenta encontrar o SQL real do TfrxFDQuery em diferentes formatos.
    """
    sql_candidates: List[str] = []

    # 1. atributos que costumam carregar SQL
    for attr_name, attr_value in query.attrib.items():
        upper_name = attr_name.upper()
        if "SQL" in upper_name or "COMMAND" in upper_name:
            if attr_value:
                sql_candidates.append(attr_value)

    # 2. subnós que podem conter SQL
    possible_nodes = [
        "./SQL",
        "./CommandText",
        "./Command",
    ]

    for path in possible_nodes:
        for node in query.findall(path):
            node_text = "".join(node.itertext()).strip()
            if node_text:
                sql_candidates.append(node_text)

    # 3. fallback: texto completo do nó
    if not sql_candidates:
        text_content = "".join(query.itertext()).strip()
        if text_content:
            sql_candidates.append(text_content)

    if not sql_candidates:
        return None

    sql_text = "\n".join([item for item in sql_candidates if item]).strip()
    sql_text = _decode_text(sql_text)
    sql_text = _limpar_sql_fastreport(sql_text)

    return sql_text


def parse_fastreport_xml(xml_text: str) -> Dict[str, Any]:
    root = ET.fromstring(xml_text)

    datasets: List[Dict[str, Any]] = []
    variables: List[Dict[str, Any]] = []
    queries: List[Dict[str, Any]] = []
    observacoes: List[str] = []

    for item in root.findall(".//Datasets/item"):
        datasets.append(
            {
                "dataset": _get_attr(item, "DataSet"),
                "dataset_name": _get_attr(item, "DataSetName"),
            }
        )

    for item in root.findall(".//Variables/item"):
        variables.append(
            {
                "name": _get_attr(item, "Name"),
                "value": _get_attr(item, "Value"),
            }
        )

    fd_queries = root.findall(".//TfrxFDQuery")
    if fd_queries:
        observacoes.append("Foram encontradas queries TfrxFDQuery no relatório.")

    for query in fd_queries:
        parametros: List[Dict[str, Any]] = []
        sql_text: Optional[str] = None

        for p in query.findall("./Parameters/item"):
            parametros.append(
                {
                    "name": _get_attr(p, "Name"),
                    "datatype": _get_attr(p, "DataType"),
                }
            )

        sql_text = _extract_sql_from_query_node(query)

        queries.append(
            {
                "name": _get_attr(query, "Name"),
                "user_name": _get_attr(query, "UserName"),
                "sql_text": sql_text,
                "parametros": parametros,
            }
        )

    if not fd_queries:
        observacoes.append("Nenhuma TfrxFDQuery encontrada no relatório.")

    layout_visual = _parse_layout_visual(root)
    parameters_detected = _infer_parameter_metadata(queries)

    return {
        "datasets": datasets,
        "variables": variables,
        "queries": queries,
        "parameters_detected": parameters_detected,
        "observacoes": observacoes,
        "layout_visual": layout_visual,
    }