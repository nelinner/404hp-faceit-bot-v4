# db.py — база данных и миграция
import sqlite3, os
from datetime import datetime

DB_NAME = "faceit_data.db"
OLD_DB_NAME = "404hp_faceit.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables(conn):
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY, nick TEXT UNIQUE, pw TEXT, salt TEXT,
        elo INT DEFAULT 0, rank TEXT DEFAULT '🎯 Level 1',
        role TEXT DEFAULT 'player', matches INT DEFAULT 0,
        wins INT DEFAULT 0, losses INT DEFAULT 0, wr REAL DEFAULT 0,
        reg TEXT, banned INT DEFAULT 0, ban_till TEXT, prem_till TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT, creator INT, code TEXT,
        map TEXT, max INT DEFAULT 10, now INT DEFAULT 1,
        status TEXT DEFAULT 'open', msg_id INT, finished INT DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS room_players (
        room INT, pid INT, nick TEXT, role TEXT, pos INT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT, room INT, side TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS team_players (
        team INT, pid INT, nick TEXT, elo INT, pos INT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS bans (
        pid INT, till TEXT, reason TEXT, admin TEXT
    )""")
    # добавляем недостающие столбцы, если таблицы уже существовали
    try: c.execute("ALTER TABLE rooms ADD COLUMN finished INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE players ADD COLUMN prem_till TEXT")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE players ADD COLUMN ban_till TEXT")
    except sqlite3.OperationalError: pass
    conn.commit()

def migrate_old_db():
    if not os.path.exists(OLD_DB_NAME):
        return
    print("🔍 Найдена старая база, переношу игроков...")
    try:
        old_conn = sqlite3.connect(OLD_DB_NAME)
        old_conn.row_factory = sqlite3.Row
        old_players = old_conn.execute("SELECT * FROM players").fetchall()
        new_conn = get_db()
        create_tables(new_conn)
        for p in old_players:
            try:
                new_conn.execute("""
                    INSERT INTO players (id, nick, pw, salt, elo, rank, role, matches, wins, losses, wr, reg, banned, ban_till, prem_till)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    p['id'], p['nick'], p['pw'], p['salt'], p['elo'], p['rank'], p['role'],
                    p['matches'], p['wins'], p['losses'], p['wr'], p['reg'],
                    p['banned'], p.get('ban_till'), p.get('prem_till')
                ))
            except sqlite3.IntegrityError:
                pass  # уже есть такой игрок
        new_conn.commit()
        new_conn.close()
        old_conn.close()
        os.rename(OLD_DB_NAME, OLD_DB_NAME + ".backup")
        print("✅ Игроки перенесены, старая база переименована в .backup")
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")

def init_db():
    if os.path.exists(OLD_DB_NAME):
        migrate_old_db()
    else:
        conn = get_db()
        create_tables(conn)
        conn.close()
    print("✅ БД готова")
