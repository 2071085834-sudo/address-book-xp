import re


METHOD_LABELS = {"phone": "电话", "email": "邮箱", "social": "社交账号", "address": "地址"}
MAX_METHODS = 30
FIELD_LIMITS = {"name": 100, "organization": 150, "note": 1000, "method": 300}
EXCEL_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def validate_contact(contact):
    if not contact["name"]:
        raise ValueError("请输入姓名。")
    for field, label in (("name", "姓名"), ("organization", "单位"), ("note", "备注")):
        value = contact[field]
        if len(value) > FIELD_LIMITS[field]:
            raise ValueError(f"{label}最多可输入 {FIELD_LIMITS[field]} 个字符。")
        if EXCEL_CONTROL.search(value):
            raise ValueError(f"{label}包含无法写入 Excel 的控制字符。")

    methods = []
    for number, method in enumerate(contact["methods"], start=1):
        value = method["value"]
        if not value:
            continue
        kind = method["kind"]
        label = METHOD_LABELS.get(kind)
        if label is None:
            raise ValueError(f"第 {number} 项联系方式：请选择有效的类型。")
        if len(value) > FIELD_LIMITS["method"]:
            raise ValueError(f"第 {number} 项{label}：最多可输入 {FIELD_LIMITS['method']} 个字符。")
        if EXCEL_CONTROL.search(value):
            raise ValueError(f"第 {number} 项{label}：请移除无法写入 Excel 的控制字符。")
        methods.append(method)
        if len(methods) > MAX_METHODS:
            raise ValueError(f"每位联系人最多可以保存 {MAX_METHODS} 项联系方式。")
    contact["methods"] = sorted(methods, key=lambda method: tuple(METHOD_LABELS).index(method["kind"]))
    return contact
