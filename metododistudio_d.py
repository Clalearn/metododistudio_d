from flask import Flask, request, jsonify, render_template_string
import numpy as np
import json
from datetime import datetime, timedelta

app = Flask(__name__)

# --- Mappatura Giorni ---
GIORNI_SETTIMANA_MAP = {
    0: "Lun", 1: "Mar", 2: "Mer", 3: "Gio", 4: "Ven", 5: "Sab", 6: "Dom"
}

# Inverso per facilità
NOMI_GIORNI_INV = {v: k for k, v in GIORNI_SETTIMANA_MAP.items()}

# --- Logica di Business ---

def scala_griglia_con_giorni(griglia_orig_list, giorni_totali_programma, ore_giornaliere, giorni_consentiti, data_inizio_str):
    try:
        griglia_iniziale = np.array(griglia_orig_list)
        if griglia_iniziale.size == 0:
            return np.full((ore_giornaliere, giorni_totali_programma), ' ')
        
        # 1. Parsing della data di inizio
        try:
            # Accetta formato YYYY-MM-DD (standard JSON)
            data_inizio = datetime.strptime(data_inizio_str.split('T')[0], "%Y-%m-%d")
        except:
            # Fallback se la data è nulla o errata: assume Lunedì (0)
            data_inizio = datetime.now()

        # 2. Identifichiamo quali indici (0..N) sono giorni di studio
        indici_giorni_studio = []
        
        # Se la lista giorni_consentiti è vuota, assumiamo tutti i giorni
        if not giorni_consentiti:
            giorni_consentiti = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]

        for i in range(giorni_totali_programma):
            data_corrente = data_inizio + timedelta(days=i)
            giorno_sett_nome = GIORNI_SETTIMANA_MAP[data_corrente.weekday()]
            
            if giorno_sett_nome in giorni_consentiti:
                indici_giorni_studio.append(i)

        num_giorni_effettivi = len(indici_giorni_studio)

        # 3. Se non ci sono giorni disponibili (es. utente non seleziona nulla), ritorna tutto Riposo
        if num_giorni_effettivi == 0:
            return np.full((ore_giornaliere, giorni_totali_programma), 'Riposo')

        # 4. Scaliamo la griglia originale PER ADATTARLA AI SOLI GIORNI DI STUDIO
        #    Invece di spalmare su 'giorni_totali_programma', spalmiamo su 'num_giorni_effettivi'
        ore_orig, giorni_orig = griglia_iniziale.shape

        # Calcoliamo gli indici per interpolare la griglia originale sui giorni effettivi
        indici_cols_interpolati = np.linspace(0, giorni_orig - 1, num_giorni_effettivi).astype(int)
        
        # Stessa cosa per le ore (verticalmente)
        indici_rows_interpolati = np.linspace(0, ore_orig - 1, ore_giornaliere).astype(int)

        # Creiamo la "griglia concentrata" (solo giorni di studio)
        # Prende le colonne giuste dall'originale e le righe giuste per le nuove ore
        griglia_studio_concentrata = griglia_iniziale[:, indici_cols_interpolati][indici_rows_interpolati, :]

        # 5. Costruiamo la Griglia Finale (inserendo i giorni di riposo)
        griglia_finale = np.full((ore_giornaliere, giorni_totali_programma), 'Riposo', dtype='<U20')

        # Riempiamo solo le colonne che corrispondono ai giorni di studio
        for k, idx_giorno_reale in enumerate(indici_giorni_studio):
            griglia_finale[:, idx_giorno_reale] = griglia_studio_concentrata[:, k]
        
        return griglia_finale
        
    except Exception as e:
        print(f"Errore durante lo scaling: {e}")
        return np.full((ore_giornaliere, giorni_totali_programma), 'ERR')

def calcola_stampa(nuova_griglia, totale_pagine):
    # Conta solo le 'S' (o 'Studio') escludendo Riposo e Prestudio
    totale_s = int(np.sum((nuova_griglia == 'S') | (nuova_griglia == 'Studio')))
    
    if totale_s == 0:
        return {"pagine_per_s": 0, "totale_s": 0, "simulazione": []}

    pagine_per_s = totale_pagine / totale_s
    simulazione = []
    pagine_stampate_cumulative = 0
    contatore_s = 0
    num_ore, num_giorni = nuova_griglia.shape

    for g in range(num_giorni):
        for h in range(num_ore):
            att = nuova_griglia[h, g]
            # Consideriamo sia "S" che "Studio" come validi
            if att == 'S' or att == 'Studio':
                contatore_s += 1
                pagine_stampate_cumulative += pagine_per_s
                simulazione.append({
                    "giorno": g + 1, "ora": h + 1,
                    "s_count": contatore_s, "s_totali": totale_s,
                    "pagine_cumulative": round(pagine_stampate_cumulative, 2)
                })
                
    return {
        "pagine_per_s": round(pagine_per_s, 2), 
        "totale_s": totale_s,
        "simulazione": simulazione
    }

# --- Endpoint API per FlutterFlow ---

@app.route('/processa-griglia', methods=['POST'])
def handle_processing():
    try:
        data = request.get_json()
        
        # Parametri richiesti (aggiunti giorni_consentiti e data_inizio)
        # Nota: 'giorni_nuovi' qui rappresenta la DURATA TOTALE dell'esame in giorni solari
        required_keys = ['griglia_iniziale', 'giorni_nuovi', 'ore_giornaliere', 'totale_pagine']
        if not all(key in data for key in required_keys):
            return jsonify({"errore": "Dati di input mancanti"}), 400
        
        griglia_list = data['griglia_iniziale']
        giorni_nuovi = int(data['giorni_nuovi'])
        ore_giornaliere = int(data['ore_giornaliere'])
        totale_pagine = float(data['totale_pagine'])
        
        # Nuovi parametri opzionali (con default)
        giorni_consentiti = data.get('giorni_consentiti', []) # es. ["Lun", "Mar"]
        data_inizio = data.get('data_inizio', datetime.now().strftime("%Y-%m-%d")) # es. "2025-11-25"

        nuova_griglia_np = scala_griglia_con_giorni(
            griglia_list, 
            giorni_nuovi, 
            ore_giornaliere, 
            giorni_consentiti, 
            data_inizio
        )
        
        risultati_stampa = calcola_stampa(nuova_griglia_np, totale_pagine)
        nuova_griglia_list = nuova_griglia_np.tolist()
        
        return jsonify({
            "messaggio": "Elaborazione completata",
            "nuova_griglia": nuova_griglia_list,
            "risultati_stampa": risultati_stampa
        }), 200

    except Exception as e:
        return jsonify({"errore": f"Errore interno del server: {str(e)}"}), 500

# --- INTERFACCIA WEB (Aggiornata per testare i giorni) ---

HTML_INTERFACCIA = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Griglia API Avanzata</title>
    <style>
        body { font-family: sans-serif; margin: 20px; background: #f4f4f4; }
        .container { max-width: 900px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .input-group { display: flex; flex-direction: column; margin-bottom: 10px; }
        label { font-weight: bold; margin-bottom: 5px; }
        input, textarea, select { padding: 8px; border-radius: 4px; border: 1px solid #ccc; }
        textarea { height: 100px; font-family: monospace; }
        button { background: #007bff; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; margin-top: 20px; width: 100%; }
        button:hover { background: #0056b3; }
        pre { background: #eee; padding: 10px; border-radius: 4px; overflow-x: auto; }
        .days-checkboxes { display: flex; gap: 10px; flex-wrap: wrap; }
        .days-checkboxes label { font-weight: normal; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔧 Test API Griglia (Con Giorni)</h1>
        
        <div class="form-grid">
            <div class="input-group">
                <label>Durata Totale (Giorni Solari)</label>
                <input type="number" id="giorni_nuovi" value="14">
            </div>
            <div class="input-group">
                <label>Ore Studio (nei giorni attivi)</label>
                <input type="number" id="ore_giornaliere" value="4">
            </div>
            <div class="input-group">
                <label>Totale Pagine</label>
                <input type="number" id="totale_pagine" value="500">
            </div>
            <div class="input-group">
                <label>Data Inizio</label>
                <input type="date" id="data_inizio">
            </div>
        </div>

        <div class="input-group">
            <label>Giorni Consentiti</label>
            <div class="days-checkboxes">
                <label><input type="checkbox" name="day" value="Lun" checked> Lun</label>
                <label><input type="checkbox" name="day" value="Mar" checked> Mar</label>
                <label><input type="checkbox" name="day" value="Mer" checked> Mer</label>
                <label><input type="checkbox" name="day" value="Gio" checked> Gio</label>
                <label><input type="checkbox" name="day" value="Ven" checked> Ven</label>
                <label><input type="checkbox" name="day" value="Sab"> Sab</label>
                <label><input type="checkbox" name="day" value="Dom"> Dom</label>
            </div>
        </div>

        <div class="input-group">
            <label>Griglia Iniziale (JSON)</label>
            <textarea id="griglia_iniziale">
[["P","S","S","R"],
 ["S","S","S","R"],
 ["S","E","E","R"]]
            </textarea>
        </div>

        <button id="submitBtn">Calcola Programma</button>

        <h3>Risultato Griglia</h3>
        <pre id="risultato-griglia">...</pre>
        <h3>Statistiche Stampa</h3>
        <pre id="risultato-stampa">...</pre>
    </div>

    <script>
        // Imposta la data di oggi come default
        document.getElementById('data_inizio').valueAsDate = new Date();

        document.getElementById('submitBtn').addEventListener('click', async () => {
            const giorniNuovi = parseInt(document.getElementById('giorni_nuovi').value);
            const oreGiornaliere = parseInt(document.getElementById('ore_giornaliere').value);
            const totalePagine = parseFloat(document.getElementById('totale_pagine').value);
            const dataInizio = document.getElementById('data_inizio').value;
            
            // Raccogli i giorni selezionati
            const checkboxes = document.querySelectorAll('input[name="day"]:checked');
            const giorniConsentiti = Array.from(checkboxes).map(cb => cb.value);

            let grigliaJSON;
            try {
                grigliaJSON = JSON.parse(document.getElementById('griglia_iniziale').value);
            } catch (e) {
                alert("JSON Griglia non valido"); return;
            }

            const payload = {
                griglia_iniziale: grigliaJSON,
                giorni_nuovi: giorniNuovi,
                ore_giornaliere: oreGiornaliere,
                totale_pagine: totalePagine,
                giorni_consentiti: giorniConsentiti,
                data_inizio: dataInizio
            };

            try {
                const res = await fetch('/processa-griglia', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                
                // Formattazione per visualizzazione (Traspone per mostrare Giorni come colonne)
                const grigliaDisplay = data.nuova_griglia.map(row => row.map(cell => cell.padEnd(8)).join("|")).join("\\n");
                
                document.getElementById('risultato-griglia').textContent = grigliaDisplay;
                document.getElementById('risultato-stampa').textContent = JSON.stringify(data.risultati_stampa, null, 2);
            } catch (error) {
                document.getElementById('risultato-griglia').textContent = "Errore: " + error;
            }
        });
    </script>
</body>
</html>
"""

@app.route('/', methods=['GET'])
def index():
    return render_template_string(HTML_INTERFACCIA)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)



