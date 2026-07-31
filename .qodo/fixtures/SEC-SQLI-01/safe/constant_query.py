COUNT_ALL = "SELECT COUNT(*) FROM accounts"

def total(conn):
    cur = conn.cursor()
    cur.execute(COUNT_ALL)
    return cur.fetchone()[0]
