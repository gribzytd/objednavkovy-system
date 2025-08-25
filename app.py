# app.py (verzia pre Render s PostgreSQL)

import os
import sqlite3
import psycopg2
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- Inicializácia aplikácie ---
app = Flask(__name__)
CORS(app)

# --- Práca s databázou ---
def get_db_connection():
    """Vytvorí pripojenie k databáze."""
    # Render nám poskytne URL k databáze v "environment variable"
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        # Sme na serveri, pripájame sa na PostgreSQL
        conn = psycopg2.connect(db_url)
    else:
        # Sme lokálne, používame SQLite pre jednoduché testovanie
        conn = sqlite3.connect('terminy.db')
        conn.row_factory = sqlite3.Row # Umožní nám pristupovať k stĺpcom podľa mena
    return conn

def inicializuj_db():
    """
    Inicializuje databázu. Pre PostgreSQL to znamená vytvorenie tabuľky,
    pre SQLite vytvorí aj súbor.
    """
    conn = get_db_connection()
    # Rozdielne kurzory pre rôzne databázy
    if isinstance(conn, psycopg2.extensions.connection):
        cursor = conn.cursor()
        # Pre PostgreSQL použijeme SERIAL pre automatické inkrementovanie ID
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS objednavky (
                id SERIAL PRIMARY KEY,
                datum TEXT NOT NULL,
                cas TEXT NOT NULL,
                meno_klienta TEXT NOT NULL
            )
        ''')
    else: # Sme v SQLite
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS objednavky (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                datum TEXT NOT NULL,
                cas TEXT NOT NULL,
                meno_klienta TEXT NOT NULL
            )
        ''')
    
    conn.commit()
    cursor.close()
    conn.close()
    print("Databáza bola úspešne inicializovaná.")


# --- API Endpoints (zostávajú takmer rovnaké) ---

@app.route('/api/terminy', methods=['GET'])
def ziskaj_terminy():
    conn = get_db_connection()
    if isinstance(conn, psycopg2.extensions.connection):
        cursor = conn.cursor()
    else:
        cursor = conn.cursor()

    cursor.execute("SELECT datum, cas, meno_klienta FROM objednavky")
    vsetky_objednavky = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    zoznam_objednavok = [{'datum': o[0], 'cas': o[1], 'meno': o[2]} for o in vsetky_objednavky]
    return jsonify(zoznam_objednavok)

@app.route('/api/objednat', methods=['POST'])
def vytvor_objednavku():
    data = request.get_json()
    datum, cas, meno = data.get('datum'), data.get('cas'), data.get('meno')
    
    if not all([datum, cas, meno]):
        return jsonify({'status': 'error', 'message': 'Chýbajúce dáta'}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO objednavky (datum, cas, meno_klienta) VALUES (%s, %s, %s)", (datum, cas, meno))
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'status': 'success', 'message': 'Objednávka úspešne vytvorená'})

@app.route('/api/admin/zmazat', methods=['POST'])
def zmaz_objednavku():
    data = request.get_json()
    datum, cas = data.get('datum'), data.get('cas')

    if not all([datum, cas]):
        return jsonify({'status': 'error', 'message': 'Chýbajúce dáta na zmazanie'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM objednavky WHERE datum = %s AND cas = %s", (datum, cas))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'status': 'success', 'message': 'Objednávka zmazaná'})

# Táto časť je len pre lokálne testovanie, na Renderi sa nepoužije
if __name__ == '__main__':
    # Pred lokálnym spustením sa uistíme, že SQLite databáza je pripravená
    if not os.environ.get('DATABASE_URL'):
        inicializuj_db()
    app.run(debug=True, port=5000)