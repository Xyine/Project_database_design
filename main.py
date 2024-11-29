import sqlite3

def connect_db():
    connection = sqlite3.connect('f1.db')
    cursor = connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print(cursor.fetchall())
    cursor.close()
    connection.close()

connect_db()
# test