import os
import secrets
from pathlib import Path

import click
from flask import Flask, abort, redirect, render_template, request, send_file, session, url_for

from contacts import FIELD_LIMITS, MAX_METHODS, METHOD_LABELS, validate_contact
from excel import CONTENT_TYPE, MAX_ROWS, make_workbook, read_workbook
from store import all_contacts, database, init_storage, save_contact


MESSAGES = {
    "saved": "联系人已保存。",
    "deleted": "联系人已删除。",
    "favorite": "已添加到收藏。",
    "unfavorite": "已取消收藏。",
}


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("ADDRESS_BOOK_DB") or str(Path(app.instance_path) / "contacts.sqlite3"),
        SECRET_KEY=os.environ.get("ADDRESS_BOOK_SECRET") or secrets.token_hex(32),
        MAX_CONTENT_LENGTH=4 * 1024 * 1024,
    )
    app.config.update(config or {})
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    init_storage(app)

    @app.context_processor
    def form_context():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return dict(
            csrf=session["csrf"], labels=METHOD_LABELS, limits=FIELD_LIMITS,
            max_methods=MAX_METHODS,
        )

    @app.before_request
    def verify_form_token():
        if request.method == "POST":
            token = session.get("csrf")
            if not token or not secrets.compare_digest(
                token.encode(), request.form.get("csrf", "").encode()
            ):
                abort(400, "表单已失效。请返回通讯录，刷新后重新操作。")

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error_page(error):
        messages = {
            400: error.description,
            404: "没有找到这位联系人或页面。",
            413: "上传文件不能超过 4 MB。",
        }
        return render_template("error.html", message=messages[error.code]), error.code

    @app.get("/")
    def index():
        contacts = all_contacts()
        query = request.args.get("q", "").strip()
        favorites = request.args.get("view") == "favorites"
        selected_id = request.args.get("id", type=int)
        visible = [
            contact for contact in contacts
            if (not favorites or contact["favorite"]) and matches(contact, query)
        ]
        selected = next((item for item in visible if item["id"] == selected_id), None)
        if selected is None and visible:
            selected = visible[0]
        message = MESSAGES.get(request.args.get("status"))
        imported = request.args.get("imported", type=int)
        if imported is not None and 0 < imported <= MAX_ROWS:
            message = f"已导入 {imported} 位联系人。"
        return render_template(
            "index.html", contacts=visible, selected=selected, query=query,
            view="favorites" if favorites else "all", total=len(contacts),
            favorite_count=sum(contact["favorite"] for contact in contacts),
            message=message, error=None,
        )

    @app.route("/contacts/new", methods=["GET", "POST"])
    @app.route("/contacts/<int:contact_id>/edit", methods=["GET", "POST"])
    def edit(contact_id=None):
        contact = {
            "id": None, "name": "", "organization": "", "note": "",
            "favorite": False, "methods": [],
        }
        if contact_id is not None:
            contact = next((item for item in all_contacts() if item["id"] == contact_id), None)
            if contact is None:
                abort(404)
        if request.method == "GET":
            return render_template("edit.html", contact=contact)
        kinds = request.form.getlist("kind")
        values = request.form.getlist("value")
        contact.update(
            {field: request.form.get(field, "").strip() for field in ("name", "organization", "note")}
        )
        contact["methods"] = [
            {"kind": kind, "value": value.strip()}
            for kind, value in zip(kinds, values)
        ]
        try:
            if len(kinds) != len(values):
                raise ValueError("联系方式表单格式有误，请重新填写。")
            validate_contact(contact)
        except ValueError as error:
            return render_template("edit.html", contact=contact, error=str(error)), 400
        connection = database()
        with connection:
            saved_id = save_contact(connection, contact, contact_id)
        if saved_id is None:
            abort(404)
        return redirect(url_for("index", id=saved_id, status="saved"), code=303)

    @app.post("/contacts/<int:contact_id>/delete")
    def delete(contact_id):
        connection = database()
        with connection:
            result = connection.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
            if not result.rowcount:
                abort(404)
        return redirect(url_for("index", status="deleted"), code=303)

    @app.post("/contacts/<int:contact_id>/favorite")
    def favorite(contact_id):
        connection = database()
        with connection:
            result = connection.execute(
                "UPDATE contacts SET favorite = ? WHERE id = ?",
                (request.form.get("favorite") == "1", contact_id),
            )
            if not result.rowcount:
                abort(404)
        return redirect(url_for(
            "index", id=contact_id, view=request.form.get("view", "all"),
            q=request.form.get("q", ""),
            status="favorite" if request.form.get("favorite") == "1" else "unfavorite",
        ), code=303)

    @app.get("/excel/export")
    def export_excel():
        return send_file(
            make_workbook(all_contacts()), mimetype=CONTENT_TYPE,
            as_attachment=True, download_name="contacts.xlsx", max_age=0,
        )

    @app.get("/excel/template")
    def download_template():
        return send_file(
            make_workbook([]), mimetype=CONTENT_TYPE,
            as_attachment=True, download_name="contacts-template.xlsx", max_age=0,
        )

    @app.route("/excel/import", methods=["GET", "POST"])
    def import_excel():
        if request.method == "GET":
            return render_template("import.html")
        file = request.files.get("workbook")
        try:
            if file is None or not (file.filename or "").lower().endswith(".xlsx"):
                raise ValueError("请选择一个 .xlsx 文件。")
            contacts = read_workbook(file.stream)
        except ValueError as error:
            return render_template("import.html", error=str(error)), 400
        connection = database()
        with connection:
            for contact in contacts:
                save_contact(connection, contact)
        return redirect(url_for("index", imported=len(contacts)), code=303)

    @app.cli.command("seed-demo")
    def seed_demo():
        """Populate an empty database with fictional contacts for a demo."""
        connection = database()
        samples = [
            ("林知远", "软件工程学习小组", True,
             [("phone", "010-5550-0101"), ("email", "zhiyuan@example.test")],
             "负责整理课程项目的会议记录。"),
            ("周予安", "视觉设计社", False,
             [("email", "yuan@example.test"), ("social", "@yuan_demo")], ""),
            ("陈一禾", "软件工程学习小组", True,
             [("phone", "010-5550-0102"), ("phone", "010-5550-0103"),
              ("email", "yihe@example.test")], "两条示例电话用于演示 Excel 分列。"),
            ("许清禾", "读书会", False, [("address", "示例路 1 号")], ""),
        ]
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM contacts LIMIT 1").fetchone():
                raise click.ClickException("通讯录已有联系人，请使用新的演示数据库。")
            for name, organization, favorite, methods, note in samples:
                save_contact(connection, validate_contact(dict(
                    name=name, organization=organization, favorite=favorite, note=note,
                    methods=[dict(kind=kind, value=value) for kind, value in methods],
                )))
        click.echo("已添加 4 位虚构演示联系人。")

    return app


def matches(contact, query):
    texts = [contact[field] for field in ("name", "organization", "note")]
    texts.extend(item["value"] for item in contact["methods"])
    return any(query.casefold() in value.casefold() for value in texts)
