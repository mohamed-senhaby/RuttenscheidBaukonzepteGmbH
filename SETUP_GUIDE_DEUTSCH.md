# 🚀 Schnelle Installation - Schritt für Schritt

## Für jemanden ohne Programmierkenntnisse

### Schritt 1: Python installieren (5 Minuten)

1. **Download:**
   - Öffne deinen Browser
   - Gehe zu: https://www.python.org/downloads/
   - Klicke auf den großen gelben "Download Python" Button

2. **Installation:**
   - Öffne die heruntergeladene Datei
   - ⚠️ **SEHR WICHTIG:** Setze ein Häkchen bei "Add Python to PATH"
   - Klicke auf "Install Now"
   - Warte bis die Installation abgeschlossen ist
   - Klicke auf "Close"

3. **Testen:**
   - Drücke `Windows-Taste + R`
   - Tippe `cmd` und drücke Enter
   - Im schwarzen Fenster tippe: `python --version`
   - Du solltest sehen: `Python 3.x.x`
   - ✅ Python ist installiert!

### Schritt 2: Projektdateien kopieren (2 Minuten)

1. Kopiere den kompletten "Laith" Ordner auf den neuen PC
2. Am besten auf den Desktop oder in "Dokumente"
3. Merke dir den Pfad, z.B.: `C:\Users\DeinName\Desktop\Laith`

### Schritt 3: API Key besorgen (3 Minuten)

1. **Google AI Studio öffnen:**
   - Gehe zu: https://aistudio.google.com/app/apikey
   - Melde dich mit deinem Google-Konto an

2. **API Key erstellen:**
   - Klicke auf "Create API Key"
   - Wähle ein Google Cloud Projekt (oder erstelle ein neues)
   - Klicke nochmal auf "Create API Key"
   - **KOPIERE** den Key (er sieht so aus: `AIzaSyB1234567890...`)

3. **API Key speichern:**
   - Öffne den Ordner: `Laith\.streamlit\`
   - Falls der Ordner nicht existiert: Erstelle ihn
     - Rechtsklick im Laith-Ordner → Neu → Ordner
     - Name: `.streamlit` (mit Punkt am Anfang!)
   
   - Öffne Notepad/Editor
   - Schreibe hinein:
     ```
     api_key = "HIER_DEIN_API_KEY"
     ```
   - Ersetze `HIER_DEIN_API_KEY` mit deinem kopierten Key
   - Speichern als: `secrets.toml` 
   - Speicherort: `Laith\.streamlit\secrets.toml`
   - ⚠️ **WICHTIG:** Dateiendung muss `.toml` sein (nicht `.txt`)

### Schritt 4: Programm-Bibliotheken installieren (3 Minuten)

1. **Kommandozeile öffnen:**
   - Drücke `Windows-Taste + R`
   - Tippe `cmd` und drücke Enter

2. **Zum Projektordner navigieren:**
   ```
   cd C:\Users\DeinName\Desktop\Laith
   ```
   (Passe den Pfad an deinen Speicherort an!)

3. **Bibliotheken installieren:**
   ```
   pip install -r requirements.txt
   ```
   - Dies dauert 1-3 Minuten
   - Du siehst viel Text durchlaufen - das ist normal!
   - Warte bis es fertig ist (du siehst wieder `C:\...>`)

### Schritt 5: App starten! 🎉

1. **Im gleichen CMD-Fenster tippe:**
   ```
   streamlit run main.py
   ```

2. **Browser öffnet sich automatisch!**
   - Falls nicht, öffne: http://localhost:8501
   - Die App ist jetzt bereit!

---

## 📌 Checkliste - Ist alles fertig?

- [ ] Python installiert (`python --version` funktioniert)
- [ ] Projektordner kopiert
- [ ] API Key von Google erhalten
- [ ] Datei `.streamlit\secrets.toml` mit API Key erstellt
- [ ] `pip install -r requirements.txt` erfolgreich ausgeführt
- [ ] `streamlit run main.py` startet die App

---

## 🎯 Tägliche Nutzung

**Wenn du die App später wieder öffnen möchtest:**

1. Kommandozeile öffnen (`Win + R` → `cmd`)
2. Zum Projektordner navigieren:
   ```
   cd C:\Users\DeinName\Desktop\Laith
   ```
3. App starten:
   ```
   streamlit run main.py
   ```

**Optional: Desktop-Verknüpfung erstellen**

1. Erstelle eine neue Textdatei auf dem Desktop
2. Benenne sie um zu: `Start_Kalkulation.bat`
3. Rechtsklick → Bearbeiten
4. Füge ein:
   ```batch
   @echo off
   cd C:\Users\DeinName\Desktop\Laith
   streamlit run main.py
   pause
   ```
5. Speichern und schließen
6. Doppelklick auf `Start_Kalkulation.bat` startet die App!

---

## ❓ Probleme?

### "python wird nicht erkannt"
→ Python nicht richtig installiert oder nicht zu PATH hinzugefügt
→ Lösung: Python neu installieren, Häkchen bei "Add to PATH" setzen!

### "pip wird nicht erkannt"
→ Python nicht korrekt installiert
→ Lösung: Versuche: `python -m pip install -r requirements.txt`

### "API Key fehlt"
→ secrets.toml Datei nicht erstellt oder falscher Ort
→ Lösung: Überprüfe Pfad: `Laith\.streamlit\secrets.toml`

### "Address already in use"
→ App läuft bereits
→ Lösung: Schließe alle CMD-Fenster und Browser-Tabs, starte neu

### Andere Probleme
→ Screenshot machen und an Support senden!

---

## 📞 Hilfe benötigt?

**Rüttenscheid Baukonzepte GmbH**
- 📧 Moh@ruttenscheid-bau.de
- 📱 +49 160 7901911

Viel Erfolg! 🚀
