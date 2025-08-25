# app.py (finálna verzia 2.3 - integrácia Resend)

import os
import psycopg2
import resend # Nový import
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

# === NOVÁ FUNKCIA NA ODOSIELANIE EMAILOV CEZ RESEND ===
def odosli_objednavku_emailom(data, subor):
    try:
        resend.api_key = os.environ.get("RESEND_API_KEY")
        admin_email = os.environ.get("ADMIN_EMAIL")

        prilohy = []
        if subor:
            prilohy.append({
                "filename": subor.filename,
                "content": subor.read()
            })

        html_telo = f"""
        <html><body>
            <h2>Nová objednávka na MimaRehab.sk</h2>
            <p><strong>Dátum a čas:</strong> {data['datum']} o {data['cas']}</p>
            <p><strong>Procedúra:</strong> {data['procedura_nazov']} ({data['procedura_cena']} €)</p><hr>
            <h3>Detaily klienta:</h3>
            <p><strong>Meno dieťaťa:</strong> {data['meno_dietata']}</p>
            <p><strong>Meno rodiča:</strong> {data['meno_rodica']}</p>
            <p><strong>Telefón:</strong> {data['telefon']}</p>
            <p><strong>Email:</strong> {data['email']}</p>
            <p><strong>Diagnóza:</strong> {data.get('diagnoza', 'N/A')}</p>
            <p><strong>Ako sa o nás dozvedeli:</strong> {data.get('zdroj_info', 'N/A')}</p><hr>
        </body></html>
        """
        
        params = {
            "from": "MimaRehab Objednávky <onboarding@resend.dev>", # DÔLEŽITÉ: Na bezplatnom pláne Resend musí byť odosielateľ táto adresa
            "to": [admin_email],
            "subject": f"Nová objednávka: {data['procedura_nazov']} - {data['meno_dietata']}",
            "html": html_telo,
            "attachments": prilohy,
        }
        
        email = resend.Emails.send(params)
        print(f"Email o objednávke úspešne odoslaný cez Resend: {email}")
        return True

    except Exception as e:
        print(f"Chyba pri odosielaní emailu cez Resend: {e}")
        return False

# Všetky ostatné funkcie zostávajú rovnaké, len vkladáme novú emailovú funkciu
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
        # Zavoláme našu novú Resend funkciu
        odosli_objednavku_emailom(data, subor)
        return jsonify({'status': 'success', 'message': 'Objednávka úspešne vytvorená'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/terminy', methods=['GET'])
def ziskaj_terminy():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT datum, cas FROM objednavky")
    vsetky_objednavky = cursor.fetchall()
    cursor.close()
    conn.close()
    zoznam_objednavok = [{'datum': o[0], 'cas': o[1]} for o in vsetky_objednavky]
    return jsonify(zoznam_objednavok)

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

@app.route('/api/admin/zmazat/<int_objednavka_id>', methods=['POST'])
def zmaz_objednavku(objednavka_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM objednavky WHERE id = %s", (objednavka_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'status': 'success', 'message': 'Objednávka zmazaná'})