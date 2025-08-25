# app.py (finálna verzia 4.0 - Úprava objednávok a SK sviatky)

import os
import psycopg2
import resend
import base64
import requests # Knižnica na sťahovanie dát z iných API
from datetime import date
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- Databázové a Emailové funkcie (zostávajú rovnaké) ---
def get_db_connection():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url: raise ValueError("DATABASE_URL nie je nastavená!")
    conn = psycopg2.connect(db_url)
    return conn

def odosli_objednavku_emailom(data, subor):
    # ... táto funkcia zostáva úplne rovnaká ako v predošlej verzii ...
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

# --- API Endpoints ---

@app.route('/api/dostupnost', methods=['GET'])
def ziskaj_dostupnost():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT datum, cas FROM objednavky")
    objednavky = cursor.fetchall()
    
    cursor.execute("SELECT datum FROM blokovane_dni")
    blokovane_dni_tuples = cursor.fetchall()
    
    cursor.close()
    conn.close()

    # --- NOVINKA: Načítanie SK sviatkov ---
    sviatky = []
    try:
        aktualny_rok = date.today().year
        # Použijeme verejné API pre sviatky Nager.Date
        response = requests.get(f"https://date.nager.at/api/v3/PublicHolidays/{aktualny_rok}/SK")
        if response.status_code == 200:
            sviatky = [sviatok['date'] for sviatok in response.json()]
            print(f"Úspešne načítaných {len(sviatky)} sviatkov pre rok {aktualny_rok}.")
    except Exception as e:
        print(f"Nepodarilo sa načítať sviatky: {e}")

    zoznam_objednavok = [{'datum': str(o[0]), 'cas': o[1]} for o in objednavky]
    zoznam_blokovanych_dni = [str(b[0]) for b in blokovane_dni_tuples]
    
    # Spojíme adminom blokované dni a štátne sviatky
    vsetky_blokovane_dni = list(set(zoznam_blokovanych_dni + sviatky))
    
    return jsonify({
        'objednavky': zoznam_objednavok,
        'blokovane_dni': vsetky_blokovane_dni
    })

# --- NOVÝ ENDPOINT PRE ÚPRAVU OBJEDNÁVKY ---
@app.route('/api/admin/upravit/<int:objednavka_id>', methods=['POST'])
def uprav_objednavku(objednavka_id):
    data = request.get_json()
    # Tu by sme mali overiť všetky dáta, ale pre jednoduchosť to preskočíme
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE objednavky SET
            datum = %s, cas = %s, procedura_nazov = %s, meno_dietata = %s,
            meno_rodica = %s, telefon = %s, email = %s, diagnoza = %s
        WHERE id = %s
        """,
        (
            data['datum'], data['cas'], data['procedura_nazov'], data['meno_dietata'],
            data['meno_rodica'], data['telefon'], data['email'], data['diagnoza'],
            objednavka_id
        )
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'status': 'success', 'message': 'Objednávka bola úspešne upravená.'})


# --- Ostatné funkcie zostávajú takmer rovnaké ---
@app.route('/api/objednat', methods=['POST'])
def vytvor_objednavku():
    # ... táto funkcia zostáva úplne rovnaká ako v predošlej verzii ...
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
            return jsonify({'status': 'error', 'message': 'Tento deň je zablokovaný.'}), 409
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

@app.route('/api/admin/blokovat-den', methods=['POST'])
def blokovat_den():
    # ... táto funkcia zostáva úplne rovnaká ...
    data = request.get_json()
    datum_str = data.get('datum')
    if not datum_str: return jsonify({'status': 'error', 'message': 'Chýba dátum'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM blokovane_dni WHERE datum = %s", (datum_str,))
    existuje = cursor.fetchone()
    if existuje:
        cursor.execute("DELETE FROM blokovane_dni WHERE id = %s", (existuje[0],))
        message = f"Dátum {datum_str} bol odblokovaný."
    else:
        cursor.execute("INSERT INTO blokovane_dni (datum) VALUES (%s)", (datum_str,))
        message = f"Dátum {datum_str} bol zablokovaný."
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'status': 'success', 'message': message})
    
@app.route('/api/admin/vsetky-objednavky', methods=['GET'])
def ziskaj_vsetky_objednavky():
    # ... táto funkcia zostáva úplne rovnaká ...
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
    # ... táto funkcia zostáva úplne rovnaká ...
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM objednavky WHERE id = %s", (objednavka_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'status': 'success', 'message': 'Objednávka zmazaná'})