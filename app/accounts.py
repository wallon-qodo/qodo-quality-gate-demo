"""Account lookup. Baseline uses parameterised SQL."""
import sqlite3

_SELECT_ACCOUNT = "SELECT id, name, balance FROM accounts WHERE id = ?"


def get_account(conn: sqlite3.Connection, account_id: str) -> dict:
    cur = conn.cursor()
    cur.execute(_SELECT_ACCOUNT, (account_id,))
    row = cur.fetchone()
    if row is None:
        return {}
    return {"id": row[0], "name": row[1], "balance": row[2]}
