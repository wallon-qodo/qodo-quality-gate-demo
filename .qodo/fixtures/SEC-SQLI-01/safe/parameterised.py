def get(conn, aid):
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts WHERE id = ?", (aid,))
    return cur.fetchone()
