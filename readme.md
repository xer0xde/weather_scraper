# Wetter-Datensammler

## Was ist das hier?

Ein kleines Python-Skript, das Wetterdaten sammelt - quasi dein persönlicher Wetter-Paparazzi. Es holt alle Infos von einer lokalen Wetterstation und macht daraus eine schön strukturierte JSON-Datei.

## Was kann das Ding?

- Temperatur tracken (kalt oder warm?)
- Luftfeuchtigkeit checken
- Niederschlag messen
- Globalstrahlung aufzeichnen
- Blattnässe dokumentieren (ja, das gibt's wirklich!)

## Brauchst du dafür?

- Python 3.8 oder neuer
- Ein paar Python-Bibliotheken:
  ```
  pip install requests beautifulsoup4 urllib3
  ```

## Wie startest du es?

Ganz einfach:
```bash
python main.py
```

Das Skript läuft dann im Hintergrund und sammelt alle 5 Minuten neue Daten. Die Ergebnisse landen in `weather_data.json` und alle Aktivitäten werden in `weather_station.log` protokolliert.

## Was genau passiert hier?

Das Skript ist wie ein fleißiger Assistent, der:
- Alle wichtigen Wetterdaten sammelt
- Die Daten schön säuberlich in JSON organisiert
- Alles protokolliert, was passiert
- Immer up to date bleibt

## Wichtig zu wissen

- Es ist auf eine spezifische Wetterstation zugeschnitten (ID: 161)
- Keine Sorge wegen SSL-Warnungen - die werden unterdrückt
- Fehler werden netterweise abgefangen

## Möchtest du mitmachen?

Klar! Fork das Repo, mach deine Änderungen und meld dich mit einem Pull Request. Gemeinsam machen wir das Skript noch besser!

## Lizenz & Disclaimer

Benutz es, wie du möchtest - aber denk dran: Es ist für Bildungs- und Forschungszwecke gedacht. Stelle sicher, dass du die Daten legal sammelst.

**Viel Spaß beim Wetter-Spionieren!** 🌦️🕵️‍♀️
