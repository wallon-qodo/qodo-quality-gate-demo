def get(conn, aid):
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts WHERE id = :aid", {"aid": aid})
    return cur.fetchone()
