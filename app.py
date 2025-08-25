# app.py (verzia 3.0 - Blokovanie termínov)

import os
import psycopg2
import resend
import base64
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

# === NOVÁ FUNKCIA PRE VYTVORENIE TABUĽKY NA BLOKOVANÉ DNI ===
def inicializuj_blokovanie_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blokovane_dni (
            id SERIAL PRIMARY KEY,
            datum DATE NOT NULL UNIQUE
        );
    """)
    conn.commit()
    cursor.close()
    conn.close()
    print("Tabuľka 'blokovane_dni' bola úspešne vytvorená/overená.")

# --- API Endpoints ---

@app.route('/api/dostupnost', methods=['GET'])
def ziskaj_dostupnost():
    """
    Nový, vylepšený endpoint, ktorý vráti ZÁROVEŇ objednávky aj blokované dni.
    Toto zjednoduší prácu pre front-end.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Získame všetky objednávky
    cursor.execute("SELECT datum, cas FROM objednavky")
    objednavky = cursor.fetchall()
    
    # Získame všetky blokované dni
    cursor.execute("SELECT datum FROM blokovane_dni")
    blokovane_dni_tuples = cursor.fetchall()
    
    cursor.close()
    conn.close()

    # Prevedieme dáta do lepšieho formátu
    zoznam_objednavok = [{'datum': str(o[0]), 'cas': o[1]} for o in objednavky]
    zoznam_blokovanych_dni = [str(b[0]) for b in blokovane_dni_tuples]
    
    return jsonify({
        'objednavky': zoznam_objednavok,
        'blokovane_dni': zoznam_blokovanych_dni
    })

@app.route('/api/admin/blokovat-den', methods=['POST'])
def blokovat_den():
    """
    Tento endpoint zablokuje alebo odblokuje daný deň.
    Funguje ako prepínač (toggle).
    """
    data = request.get_json()
    datum_str = data.get('datum')
    if not datum_str:
        return jsonify({'status': 'error', 'message': 'Chýba dátum'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Zistíme, či už je deň zablokovaný
    cursor.execute("SELECT id FROM blokovane_dni WHERE datum = %s", (datum_str,))
    existuje = cursor.fetchone()
    
    if existuje:
        # Ak existuje, zmažeme ho (odblokujeme deň)
        cursor.execute("DELETE FROM blokovane_dni WHERE id = %s", (existuje[0],))
        message = f"Dátum {datum_str} bol odblokovaný."
    else:
        # Ak neexistuje, pridáme ho (zablokujeme deň)
        cursor.execute("INSERT INTO blokovane_dni (datum) VALUES (%s)", (datum_str,))
        message = f"Dátum {datum_str} bol zablokovaný."
        
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'status': 'success', 'message': message})

# --- Ostatné funkcie (odosielanie emailov, pridávanie objednávok, atď.) zostávajú rovnaké ---
# ... (sem patrí celý zvyšok kódu z app.py verzie 2.4, nebudem ho tu opakovať, aby som ušetril miesto)
def odosli_objednavku_emailom(data, subor):
    try:
        resend.api_key = os.environ.get("RESEND_API_KEY")
        admin_email = os.environ.get("ADMIN_EMAIL")
        prilohy = []
        if subor:
            file_content = base64.b64encode(subor.read()).decode('utf-8')
            prilohy.append({"filename": subor.filename, "content": file_content})
        html_telo = f"<html><body><h2>Nová objednávka na MimaRehab.sk</h2><p><strong>Dátum a čas:</strong> {data['datum']} o {data['cas']}</p><p><strong>Procedúra:</strong> {data['procedura_nazov']} ({data['procedura_cena']} €)</p><hr><h3>Detaily klienta:</h3><p><strong>Meno dieťaťa:</strong> {data['meno_dietata']}</p><p><strong>Meno rodiča:</strong> {data['meno_rodica']}</p><p><strong>Telefón:</strong> {data['telefon']}</p><p><strong>Email:</strong> {data['email']}</p><p><strong>Diagnóza:</strong> {data.get('diagnoza', 'N/A')}</p><p><strong>Ako sa o nás dozvedeli:</strong> {data.get('zdroj_info', 'N/A')}</p><hr></body></html>"
        params = {"from": "MimaRehab Objednávky <onboarding@resend.dev>", "to": [admin_email], "subject": f"Nová objednávka: {data['procedura_nazov']} - {data['meno_dietata']}", "html": html_telo, "attachments": prilohy}
        resend.Emails.send(params)
        return True
    except Exception as e:
        print(f"Chyba pri odosielaní emailu cez Resend: {e}")
        return False
@app.route('/api/objednat', methods=['POST'])
def vytvor_objednavku():
    data = request.form
    subor = request.files.get('lekarsky_nalez')
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM objednavky WHERE datum = %s AND cas = %s", (data['datum'], data['cas']))
        if cursor.fetchone():
            return jsonify({'status': 'error', 'message': 'Tento termín je už obsadený.'}), 409
        cursor.execute("SELECT id FROM blokovane_dni WHERE datum = %s", (data['datum'],))
        if cursor.fetchone():
            return jsonify({'status': 'error', 'message': 'Tento deň je zablokovaný a nie je možné sa objednať.'}), 409
        cursor.execute(
            "INSERT INTO objednavky (datum, cas, procedura_nazov, procedura_cena, meno_dietata, diagnoza, meno_rodica, telefon, email, zdroj_info) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (data['datum'], data['cas'], data['procedura_nazov'], data['procedura_cena'], data['meno_dietata'], data.get('diagnoza', ''), data['meno_rodica'], data['telefon'], data['email'], data.get('zdroj_info', ''))
        )
        conn.commit()
        odosli_objednavku_emailom(data, subor)
        return jsonify({'status': 'success', 'message': 'Objednávka úspešne vytvorená'})
    finally:
        cursor.close()
        conn.close()
@app.route('/api/admin/vsetky-objednavky', methods=['GET'])
def ziskaj_vsetky_objednavky():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, datum, cas, procedura_nazov, procedura_cena, meno_dietata, diagnoza, meno_rodica, telefon, email, zdroj_info, stav_platby FROM objednavky ORDER BY datum DESC, cas")
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