import re


METHOD_LABELS = {"phone": "电话", "email": "邮箱", "social": "社交账号", "address": "地址"}
MAX_METHODS = 30
FIELD_LIMITS = {"name": 100, "organization": 150, "note": 1000, "method": 300}


def validate_contact(contact):
    if not contact["name"]:
        raise ValueError("请输入姓名。")
    for field, label in (("name", "姓名"), ("organization", "单位"), ("note", "备注")):
        if len(contact[field]) > FIELD_LIMITS[field]:
            raise ValueError(f"{label}最多可输入 {FIELD_LIMITS[field]} 个字符。")
    if len(contact["methods"]) > MAX_METHODS:
        raise ValueError(f"每位联系人最多可以保存 {MAX_METHODS} 项联系方式。")
    for method in contact["methods"]:
        if method["kind"] not in METHOD_LABELS or not method["value"]:
            raise ValueError("请选择联系方式类型并填写内容。")
        if len(method["value"]) > FIELD_LIMITS["method"]:
            raise ValueError(f"联系方式最多可输入 {FIELD_LIMITS['method']} 个字符。")
    texts = [contact[field] for field in ("name", "organization", "note")]
    texts.extend(method["value"] for method in contact["methods"])
    if any(re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]", value) for value in texts):
        raise ValueError("内容包含无法写入 Excel 的控制字符。")
    contact["methods"].sort(key=lambda method: tuple(METHOD_LABELS).index(method["kind"]))
    return contact
