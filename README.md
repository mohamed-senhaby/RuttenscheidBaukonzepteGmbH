# 🏗️ Rüttenscheid Smart Kalkulation - Setup Guide

KI-gestützte Angebotserstellung für Bauprojekte mit Google Gemini AI

## 📋 Systemanforderungen

- **Betriebssystem:** Windows 10/11, macOS, oder Linux
- **Python:** Version 3.9 oder höher
- **RAM:** Mindestens 4 GB
- **Festplatte:** 500 MB freier Speicherplatz

## 🚀 Installation - Schritt für Schritt

### 1. Python installieren

**Windows:**
1. Besuche [python.org/downloads](https://www.python.org/downloads/)
2. Lade Python 3.9 oder höher herunter
3. Starte die Installation
4. ✅ **WICHTIG:** Aktiviere "Add Python to PATH" während der Installation
5. Klicke auf "Install Now"

**Überprüfung:**
```bash
python --version
```
Sollte anzeigen: `Python 3.9.x` oder höher

### 2. Projektdateien kopieren

Kopiere den gesamten Projektordner auf den neuen PC:
```
Laith/
├── main.py
├── requirements.txt
├── README.md
├── .streamlit/
│   └── secrets.toml
└── Data/
    └── Screenshot 2026-01-07 214122.png
```

### 3. Kommandozeile öffnen

**Windows:**
- Drücke `Win + R`
- Tippe `cmd` und drücke Enter
- Navigiere zum Projektordner:
  ```bash
  cd Pfad\zu\deinem\Projektordner\Laith
  ```

**Beispiel:**
```bash
cd C:\Users\IhrName\Desktop\Laith
```

### 4. Python-Pakete installieren

Installiere alle benötigten Bibliotheken:
```bash
pip install -r requirements.txt
```

**Bei Problemen:**
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Google Gemini API Key einrichten

#### 5.1 API Key erhalten

1. Besuche [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Melde dich mit deinem Google-Konto an
3. Klicke auf "Create API Key"
4. Kopiere den generierten API Key (sieht aus wie: `AIza...`)

#### 5.2 API Key konfigurieren

**Methode 1: Über secrets.toml (Empfohlen)**

1. Erstelle den Ordner `.streamlit` im Projektverzeichnis (falls nicht vorhanden)
2. Erstelle die Datei `secrets.toml` in diesem Ordner
3. Füge deinen API Key hinzu:

```toml
# .streamlit/secrets.toml
api_key = "DEIN_API_KEY_HIER"
```

**Beispiel:**
```toml
api_key = "AIzaSyB1234567890abcdefghijklmnopqrstuvw"
```

**Ordnerstruktur danach:**
```
Laith/
├── main.py
├── requirements.txt
├── .streamlit/
│   └── secrets.toml    ← Hier ist dein API Key
└── ...
```

### 6. Anwendung starten

Im Projektordner ausführen:
```bash
streamlit run main.py
```

**Alternative mit spezifischem Port:**
```bash
python -m streamlit run main.py --server.port 8501
```

Die App öffnet sich automatisch im Browser unter:
```
http://localhost:8501
```

## 🎯 Schnellstart-Anleitung (Nach Installation)

1. **Terminal öffnen** und zum Projektordner navigieren
2. **App starten:**
   ```bash
   streamlit run main.py
   ```
3. **Browser öffnet sich automatisch** - falls nicht: http://localhost:8501
4. **Dokument hochladen** (GAEB, PDF, Excel, Word)
5. **Analysieren** - KI extrahiert alle Positionen automatisch
6. **Bearbeiten** - Preise und Mengen anpassen
7. **Exportieren** - Als Excel oder PDF speichern

## 📁 Unterstützte Dateiformate

### GAEB-Dateien (Deutsch)
- D81, D82, D83, D84, D85, D86, D90
- X81, X82, X83, X84, X85, X86, X90
- P81, P82, P83, P84, P85, P86, P90

### Dokumente
- PDF (.pdf)
- Word (.docx, .doc)
- Excel (.xlsx, .xls)
- Text (.txt)

## ⚙️ Konfiguration

### API Key ändern

Bearbeite `.streamlit/secrets.toml`:
```toml
api_key = "NEUER_API_KEY"
```

### Firmenlogo ändern

Ersetze die Datei:
```
Data/Screenshot 2026-01-07 214122.png
```

### Firmenname ändern

In `main.py`, Zeile 18:
```python
COMPANY_NAME = "Ihr Firmenname hier"
```

## 🐛 Fehlerbehebung

### Problem: "Python wird nicht erkannt"
**Lösung:** Python wurde nicht zum PATH hinzugefügt
```bash
# Windows: Neuinstallation mit "Add to PATH" aktivieren
# Oder manuell hinzufügen: Systemeinstellungen → Umgebungsvariablen
```

### Problem: "pip wird nicht erkannt"
**Lösung:**
```bash
python -m ensurepip --upgrade
python -m pip install --upgrade pip
```

### Problem: "API Key fehlt"
**Lösung:** Prüfe `.streamlit/secrets.toml`:
- Datei existiert?
- API Key korrekt eingefügt?
- Keine Leerzeichen vor/nach dem Key?

### Problem: "503 - Model overloaded"
**Lösung:** Die App wechselt automatisch zwischen 5 verschiedenen Modellen. Warten Sie 1-2 Minuten und versuchen Sie es erneut.

### Problem: "429 - Quota exceeded"
**Lösung:** 
- Token-Limit: Warten Sie 1 Minute
- Tages-Limit: Neuen API Key erstellen oder bis morgen warten

### Problem: App startet nicht
**Lösung:**
```bash
# Überprüfe installierte Pakete
pip list

# Reinstalliere Streamlit
pip uninstall streamlit
pip install streamlit

# Neustart
streamlit run main.py
```

### Problem: Excel-Export funktioniert nicht
**Lösung:**
```bash
pip install --upgrade openpyxl pandas
```

## 📞 Support & Kontakt

**Rüttenscheid Baukonzepte GmbH**
- 📧 E-Mail: Moh@ruttenscheid-bau.de
- 📱 Mobil: +49 160 7901911
- ☎️ Tel: +49 0201 84850166
- 🌐 Web: www.ruttenscheid-bau.de

## 🔒 Sicherheitshinweise

⚠️ **WICHTIG:**
- **Niemals** deinen API Key öffentlich teilen
- `.streamlit/secrets.toml` NICHT in Git/GitHub hochladen
- API Key regelmäßig erneuern
- Quota-Limits im Google AI Studio überwachen

## 📦 Verwendete Technologien

- **Streamlit** - Web-Interface
- **Google Gemini AI** - KI-Analyse
- **Pandas** - Datenverarbeitung
- **FPDF** - PDF-Generierung
- **OpenPyXL** - Excel-Export

## 📄 Lizenz

© 2025-2026 Rüttenscheid Baukonzepte GmbH. Alle Rechte vorbehalten.

---

**Version:** 1.0  
**Letzte Aktualisierung:** Januar 2026
