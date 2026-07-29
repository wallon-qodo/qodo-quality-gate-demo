"""Account lookup. Baseline uses parameterised SQL."""
import sqlite3


def get_account(conn: sqlite3.Connection, account_id: str) -> dict:
    cur = conn.cursor()
    cur.execute("SELECT id, name, balance FROM accounts WHERE id = ?", (account_id,))
    row = cur.fetchone()
    return {"id": row[0], "name": row[1], "balance": row[2]} if row else {}
