import sqlite3

def get(conn, aid):
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM accounts WHERE id = '{aid}'")
    return cur.fetchone()
