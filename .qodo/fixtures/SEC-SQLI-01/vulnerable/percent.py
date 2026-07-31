def get(conn, aid):
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts WHERE id = '%s'" % aid)
    return cur.fetchone()
