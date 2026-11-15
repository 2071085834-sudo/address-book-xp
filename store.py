import sqlite3

from flask import current_app, g


def database():
    if "database" not in g:
        g.database = sqlite3.connect(current_app.config["DATABASE"])
        g.database.row_factory = sqlite3.Row
        g.database.execute("PRAGMA foreign_keys = ON")
    return g.database


def init_storage(app):
    @app.teardown_appcontext
    def close_storage(error):
        connection = g.pop("database", None)
        if connection is not None:
            connection.close()

    with app.app_context():
        database().executescript("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                organization TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                favorite INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0, 1))
            );
            CREATE TABLE IF NOT EXISTS methods (
                id INTEGER PRIMARY KEY,
                contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                kind TEXT NOT NULL,
                value TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS methods_contact_id ON methods(contact_id);
        """)


def all_contacts():
    connection = database()
    with connection:
        connection.execute("BEGIN")
        contacts = {
            row["id"]: dict(row, methods=[])
            for row in connection.execute(
                "SELECT * FROM contacts ORDER BY name COLLATE NOCASE, id"
            )
        }
        for method in connection.execute("SELECT * FROM methods ORDER BY id"):
            contacts[method["contact_id"]]["methods"].append(
                {"kind": method["kind"], "value": method["value"]}
            )
    return list(contacts.values())


def save_contact(connection, contact, contact_id=None):
    fields = (contact["name"], contact["organization"], contact["note"])
    if contact_id is None:
        contact_id = connection.execute(
            "INSERT INTO contacts (name, organization, note, favorite) VALUES (?, ?, ?, ?)",
            (*fields, contact["favorite"]),
        ).lastrowid
    else:
        result = connection.execute(
            "UPDATE contacts SET name = ?, organization = ?, note = ? WHERE id = ?",
            (*fields, contact_id),
        )
        if not result.rowcount:
            return None
        connection.execute("DELETE FROM methods WHERE contact_id = ?", (contact_id,))
    connection.executemany(
        "INSERT INTO methods (contact_id, kind, value) VALUES (?, ?, ?)",
        [(contact_id, item["kind"], item["value"]) for item in contact["methods"]],
    )
    return contact_id
