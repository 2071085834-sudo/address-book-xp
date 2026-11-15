import re
from io import BytesIO
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from defusedxml.common import DefusedXmlException
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException

from contacts import MAX_METHODS, METHOD_LABELS, validate_contact


BASE_COLUMNS = {"姓名": "name", "单位": "organization", "备注": "note", "收藏": "favorite"}
METHOD_COLUMNS = {label: kind for kind, label in METHOD_LABELS.items()}
METHOD_HEADER = re.compile(r"(.+?)\s*([1-9][0-9]*)?")
MAX_ROWS = 5000
MAX_COLUMNS = len(BASE_COLUMNS) + MAX_METHODS * len(METHOD_LABELS)
MAX_UNCOMPRESSED = 32 * 1024 * 1024
CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def contact_values(contact, kind):
    return [item["value"] for item in contact["methods"] if item["kind"] == kind]


def make_workbook(contacts):
    counts = {
        kind: max(1, max((len(contact_values(item, kind)) for item in contacts), default=0))
        for kind in METHOD_LABELS
    }
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "联系人"
    headers = list(BASE_COLUMNS)
    for kind, label in METHOD_LABELS.items():
        headers.extend(f"{label}{number}" for number in range(1, counts[kind] + 1))
    sheet.append(headers)
    for contact in contacts:
        row = [
            contact["name"], contact["organization"], contact["note"],
            "是" if contact["favorite"] else "否",
        ]
        for kind, count in counts.items():
            values = contact_values(contact, kind)
            row.extend(values + [""] * (count - len(values)))
        sheet.append(row)
    for row in sheet.iter_rows():
        for cell in row:
            # Explicit text preserves leading zeroes and text starting with "=".
            cell.data_type = "s"
            cell.number_format = "@"
            if cell.row == 1:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="2C563E")
                cell.alignment = Alignment(vertical="center")
    sheet.row_dimensions[1].height = 25
    for index, header in enumerate(headers, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = 38 if header == "备注" else 23
    sheet.freeze_panes = "B2"
    sheet.auto_filter.ref = sheet.dimensions
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return stream


def read_workbook(stream):
    try:
        with ZipFile(stream) as archive:
            if sum(item.file_size for item in archive.infolist()) > MAX_UNCOMPRESSED:
                raise ValueError("Excel 解压后超过 32 MB，请拆分文件再导入。")
        stream.seek(0)
        workbook = load_workbook(stream, read_only=True, keep_links=False)
        try:
            if not workbook.worksheets:
                raise ValueError("文件中没有可读取的工作表。")
            return read_sheet(workbook.worksheets[0])
        finally:
            workbook.close()
    except (
        BadZipFile, InvalidFileException, ParseError, DefusedXmlException, KeyError, OSError,
        IndexError, TypeError,
    ) as error:
        raise ValueError("无法读取这个 Excel 文件，请使用有效的 .xlsx 文件。") from error


def read_sheet(sheet):
    if (sheet.max_row or 0) > MAX_ROWS + 1 or (sheet.max_column or 0) > MAX_COLUMNS:
        raise ValueError(f"每次导入最多 {MAX_ROWS} 行联系人和 {MAX_COLUMNS} 列。")
    rows = sheet.iter_rows(max_col=sheet.max_column or MAX_COLUMNS)
    columns = parse_headers(next(rows, ()))
    contacts = []
    for row_number, cells in enumerate(rows, start=2):
        if row_number > MAX_ROWS + 1:
            raise ValueError(f"每次导入最多 {MAX_ROWS} 行联系人。")
        if all(cell.value is None or not str(cell.value).strip() for cell in cells):
            continue
        try:
            contacts.append(parse_contact(columns, cells))
        except ValueError as error:
            raise ValueError(f"第 {row_number} 行：{error}") from error
    if not contacts:
        raise ValueError("表格里没有可导入的联系人。请从第 2 行开始填写。")
    return contacts


def parse_headers(cells):
    columns = []
    seen = set()
    for cell in cells:
        header = str(cell.value or "").strip()
        if not header:
            columns.append(None)
            continue
        if header in BASE_COLUMNS:
            key = (BASE_COLUMNS[header], 0)
        else:
            match = METHOD_HEADER.fullmatch(header)
            if not match or match[1] not in METHOD_COLUMNS:
                raise ValueError(f"无法识别列名「{header}」。请参考下载的模板。")
            if match[2] and (len(match[2]) > 2 or int(match[2]) > MAX_METHODS):
                raise ValueError(f"联系方式列的序号需在 1 到 {MAX_METHODS} 之间。")
            key = (METHOD_COLUMNS[match[1]], int(match[2] or 1))
        if key in seen:
            raise ValueError(f"列名「{header}」重复。")
        seen.add(key)
        columns.append(key)
    if ("name", 0) not in seen:
        raise ValueError("缺少「姓名」列。请按模板填写第一行表头。")
    return columns


def parse_contact(columns, cells):
    contact = {"name": "", "organization": "", "note": "", "favorite": False, "methods": []}
    methods = []
    for column, cell in zip(columns, cells):
        if cell.data_type in {"f", "e"}:
            raise ValueError("请将公式或错误值替换为文本。")
        value = "" if cell.value is None else str(cell.value).strip()
        if not value:
            continue
        if column is None:
            raise ValueError("有内容的列缺少表头。")
        field, order = column
        if order:
            methods.append((order, {"kind": field, "value": value}))
        elif field == "favorite":
            normalized = value.casefold()
            if normalized not in {"是", "否", "true", "false", "1", "0"}:
                raise ValueError("「收藏」请填写「是」或「否」。")
            contact["favorite"] = normalized in {"是", "true", "1"}
        else:
            contact[field] = value
    contact["methods"] = [item for _, item in sorted(methods, key=lambda entry: entry[0])]
    return validate_contact(contact)
