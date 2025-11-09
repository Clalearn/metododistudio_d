from flask import Flask, request, jsonify, render_template_string
import numpy as np
import json

app = Flask(__name__)

# --- Logica di Business (Invariata) ---

def scala_griglia_ottimizzata(griglia_orig_list, giorni_nuovi, ore_giornaliere):
    try:
        griglia_iniziale = np.array(griglia_orig_list)
        if griglia_iniziale.size == 0:
            return np.full((ore_giornaliere, giorni_nuovi), ' ')
        
        ore_orig, giorni_orig = griglia_iniziale.shape

        indici_giorni = np.linspace(0, giorni_orig - 1, giorni_nuovi).astype(int)
        griglia_giorni_scalati = griglia_iniziale[:, indici_giorni]

        indici_ore = np.linspace(0, ore_orig - 1, ore_giornaliere).astype(int)
        nuova_griglia = griglia_giorni_scalati[indici_ore, :]
        
        return nuova_griglia
        
    except Exception as e:
        print(f"Errore durante lo scaling: {e}")
        return np.full((ore_giornaliere, giorni_nuovi), 'ERR')

def calcola_stampa(nuova_griglia, totale_pagine):
    totale_s = int((nuova_griglia == 'S').sum())
    
    if totale_s == 0:
        return {"pagine_per_s": 0, "totale_s": 0, "simulazione": []}

    pagine_per_s = totale_pagine / totale_s
    simulazione = []
    pagine_stampate_cumulative = 0
    contatore_s = 0
    num_ore, num_giorni = nuova_griglia.shape

    for g in range(num_giorni):
        for h in range(num_ore):
            if nuova_griglia[h, g] == 'S':
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

# --- Endpoint API per FlutterFlow (Invariato) ---

@app.route('/processa-griglia', methods=['POST'])
def handle_processing():
    try:
        data = request.get_json()
        required_keys = ['griglia_iniziale', 'giorni_nuovi', 'ore_giornaliere', 'totale_pagine']
        if not all(key in data for key in required_keys):
            return jsonify({"errore": "Dati di input mancanti"}), 400
        
        griglia_list = data['griglia_iniziale']
        giorni_nuovi = int(data['giorni_nuovi'])
        ore_giornaliere = int(data['ore_giornaliere'])
        totale_pagine = float(data['totale_pagine'])

        nuova_griglia_np = scala_griglia_ottimizzata(griglia_list, giorni_nuovi, ore_giornaliere)
        risultati_stampa = calcola_stampa(nuova_griglia_np, totale_pagine)
        nuova_griglia_list = nuova_griglia_np.tolist()
        
        return jsonify({
            "messaggio": "Elaborazione completata",
            "nuova_griglia": nuova_griglia_list,
            "risultati_stampa": risultati_stampa
        }), 200

    except Exception as e:
        return jsonify({"errore": f"Errore interno del server: {str(e)}"}), 500

# --- NUOVA SEZIONE: Interfaccia Web Semplice ---

# Definiamo l'HTML per la pagina web
# Usiamo render_template_string per non dover creare file HTML separati
HTML_INTERFACCIA = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Griglia API</title>
    <style>
        body { font-family: sans-serif; margin: 20px; background: #f4f4f4; }
        .container { max-width: 900px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .input-group { display: flex; flex-direction: column; }
        label { font-weight: bold; margin-bottom: 5px; }
        input, textarea { padding: 8px; border-radius: 4px; border: 1px solid #ccc; }
        textarea { height: 150px; font-family: monospace; }
        button { background: #007bff; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; margin-top: 20px; }
        button:hover { background: #0056b3; }
        h2 { border-bottom: 2px solid #eee; padding-bottom: 5px; }
        pre { background: #eee; padding: 10px; border-radius: 4px; white-space: pre-wrap; word-wrap: break-word; }
        #risultato-griglia { font-family: monospace; line-height: 1.4; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔧 Test API Griglia</h1>
        <p>Usa questo form per testare l'endpoint <code>/processa-griglia</code>.</p>
        
        <div class="form-grid">
            <div class="input-group">
                <label for="giorni_nuovi">Giorni Nuovi</label>
                <input type="number" id="giorni_nuovi" value="15">
            </div>
            <div class="input-group">
                <label for="ore_giornaliere">Ore Giornaliere</label>
                <input type="number" id="ore_giornaliere" value="4">
            </div>
            <div class="input-group">
                <label for="totale_pagine">Totale Pagine</label>
                <input type="number" id="totale_pagine" value="1000">
            </div>
        </div>
        
        <div class="input-group" style="margin-top: 20px;">
            <label for="griglia_iniziale">Griglia Iniziale (in formato JSON)</label>
            <textarea id="griglia_iniziale">
[["P", "P", "S", "S", "S", "R", "R"],
["P", "S", "S", "S", "S", "R", "R"],
["S", "S", "S", "S", "S", "E", "E"],
["S", "E", "E", "R", "E", "E", "E"]]
            </textarea>
        </div>

        <button id="submitBtn">Esegui Elaborazione</button>

        <h2>Risultati</h2>
        <h3>Nuova Griglia (ore x giorni)</h3>
        <pre id="risultato-griglia">...</pre>
        <h3>Simulazione Stampa</h3>
        <pre id="risultato-stampa">...</pre>
    </div>

    <script>
        document.getElementById('submitBtn').addEventListener('click', async () => {
            // Pulisci risultati vecchi
            document.getElementById('risultato-griglia').textContent = 'Elaboro...';
            document.getElementById('risultato-stampa').textContent = '...';

            let grigliaJSON;
            try {
                // Prendi il testo e convertilo in JSON
                grigliaJSON = JSON.parse(document.getElementById('griglia_iniziale').value.trim());
            } catch (e) {
                document.getElementById('risultato-griglia').textContent = "ERRORE: La griglia iniziale non è un JSON valido. Assicurati che le virgolette siano doppie (\\") e che non ci siano virgole finali.";
                return;
            }

            const payload = {
                giorni_nuovi: parseInt(document.getElementById('giorni_nuovi').value),
                ore_giornaliere: parseInt(document.getElementById('ore_giornaliere').value),
                totale_pagine: parseFloat(document.getElementById('totale_pagine').value),
                griglia_iniziale: grigliaJSON
            };

            try {
                // Chiama l'endpoint API /processa-griglia (sullo stesso server)
                const response = await fetch('/processa-griglia', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.errore || 'Errore sconosciuto');
                }

                // Formatta la griglia per una visualizzazione leggibile
                // La griglia è (ore x giorni), quindi ogni sotto-array è un'ora
                const grigliaFormattata = data.nuova_griglia.map(rigaOra => rigaOra.join('  ')).join('\\n');
                
                document.getElementById('risultato-griglia').textContent = grigliaFormattata;
                document.getElementById('risultato-stampa').textContent = JSON.stringify(data.risultati_stampa, null, 2);

            } catch (err) {
                document.getElementById('risultato-griglia').textContent = `ERRORE: ${err.message}`;
            }
        });
    </script>
</body>
</html>
"""

# Questo è l'endpoint per la pagina web (il "sito")
@app.route('/', methods=['GET'])
def index():
    """Mostra la pagina web di test."""
    # render_template_string prende la stringa HTML e la invia al browser
    return render_template_string(HTML_INTERFACCIA)

# --- Avvio (Invariato) ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)


