def get(conn, aid):
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts WHERE id = '{}'".format(aid))
    return cur.fetchone()
