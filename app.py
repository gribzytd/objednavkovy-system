# app.py (verzia 2.0 s rozšíreným formulárom)

import os
import psycopg2
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def get_db_connection():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL nie je nastavená!")
    conn = psycopg2.connect(db_url)
    return conn

# !! DÔLEŽITÉ !! - Funkcia na úpravu databázy
# Túto funkciu budeme musieť jednorazovo spustiť, aby sme pridali nové stĺpce
def uprav_db_pre_v2():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Pridáme nové stĺpce do tabuľky 'objednavky'. Ak už existujú, príkaz neurobí nič.
    # Používame IF NOT EXISTS pre bezpečnosť
    cursor.execute('ALTER TABLE objednavky ADD COLUMN IF NOT EXISTS procedura_nazov TEXT;')
    cursor.execute('ALTER TABLE objednavky ADD COLUMN IF NOT EXISTS procedura_cena NUMERIC;')
    cursor.execute('ALTER TABLE objednavky ADD COLUMN IF NOT EXISTS meno_dietata TEXT;')
    cursor.execute('ALTER TABLE objednavky ADD COLUMN IF NOT EXISTS diagnoza TEXT;')
    cursor.execute('ALTER TABLE objednavky ADD COLUMN IF NOT EXISTS meno_rodica TEXT;')
    cursor.execute('ALTER TABLE objednavky ADD COLUMN IF NOT EXISTS telefon TEXT;')
    cursor.execute('ALTER TABLE objednavky ADD COLUMN IF NOT EXISTS email TEXT;')
    cursor.execute('ALTER TABLE objednavky ADD COLUMN IF NOT EXISTS zdroj_info TEXT;')
    cursor.execute('ALTER TABLE objednavky ADD COLUMN IF NOT EXISTS stav_platby TEXT DEFAULT \'čaká na platbu\';')
    
    # Premenujeme starý stĺpec pre lepšiu prehľadnosť
    # cursor.execute('ALTER TABLE objednavky RENAME COLUMN meno_klienta TO stary_udaj_meno;')

    conn.commit()
    cursor.close()
    conn.close()
    print("Databáza bola úspešne upravená pre v2.0.")


# --- API Endpoints ---

@app.route('/api/terminy', methods=['GET'])
def ziskaj_terminy():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Berieme len dátum a čas, aby sme vedeli určiť obsadenosť
    cursor.execute("SELECT datum, cas FROM objednavky")
    vsetky_objednavky = cursor.fetchall()
    cursor.close()
    conn.close()
    
    zoznam_objednavok = [{'datum': o[0], 'cas': o[1]} for o in vsetky_objednavky]
    return jsonify(zoznam_objednavok)

@app.route('/api/objednat', methods=['POST'])
def vytvor_objednavku():
    data = request.get_json()
    
    # Kontrola, či máme všetky potrebné dáta z nového formulára
    required_fields = ['datum', 'cas', 'procedura_nazov', 'procedura_cena', 'meno_dietata', 'meno_rodica', 'telefon', 'email']
    if not all(field in data for field in required_fields):
        return jsonify({'status': 'error', 'message': 'Chýbajú povinné polia'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Kontrola duplicitnej objednávky
    cursor.execute("SELECT id FROM objednavky WHERE datum = %s AND cas = %s", (data['datum'], data['cas']))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'status': 'error', 'message': 'Tento termín je už obsadený.'}), 409

    # Vloženie novej objednávky
    cursor.execute(
        """
        INSERT INTO objednavky (datum, cas, procedura_nazov, procedura_cena, meno_dietata, diagnoza, meno_rodica, telefon, email, zdroj_info)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            data['datum'], data['cas'], data['procedura_nazov'], data['procedura_cena'],
            data['meno_dietata'], data.get('diagnoza', ''), data['meno_rodica'],
            data['telefon'], data['email'], data.get('zdroj_info', '')
        )
    )
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'status': 'success', 'message': 'Objednávka úspešne vytvorená'})

# Admin panel teraz vracia všetky nové dáta
@app.route('/api/admin/vsetky-objednavky', methods=['GET'])
def ziskaj_vsetky_objednavky():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, datum, cas, procedura_nazov, procedura_cena, meno_dietata, diagnoza, meno_rodica, telefon, email, zdroj_info, stav_platby FROM objednavky ORDER BY datum, cas"
    )
    columns = [desc[0] for desc in cursor.description]
    objednavky = [dict(zip(columns, row)) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return jsonify(objednavky)


@app.route('/api/admin/zmazat/<int:objednavka_id>', methods=['POST'])
def zmaz_objednavku(objednavka_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM objednavky WHERE id = %s", (objednavka_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'status': 'success', 'message': 'Objednávka zmazaná'})