"""Translation support for the application."""

from typing import Callable

# Current language
_current_language = "en"

# Translation dictionaries
_translations = {
    "de": {
        # Main window
        "Ideal Group - Student Grouping Optimizer": "Ideal Group - Schülergruppen-Optimierer",
        "File": "Datei",
        "New Project": "Neues Projekt",
        "Open Project...": "Projekt öffnen...",
        "Save Project": "Projekt speichern",
        "Save Project As...": "Projekt speichern unter...",
        "Import Excel...": "Excel importieren...",
        "Export Excel...": "Excel exportieren...",
        "Quit": "Beenden",
        "Algorithm": "Algorithmus",
        "Run Optimization": "Optimierung starten",
        "Check Constraints": "Einschränkungen prüfen",
        "Ready": "Bereit",
        "Groups": "Gruppen",
        "Weights": "Gewichtungen",
        "Info": "Info",
        
        # Import dialog
        "Import Excel File": "Excel-Datei importieren",
        "No file selected": "Keine Datei ausgewählt",
        "Browse...": "Durchsuchen...",
        "Preview": "Vorschau",
        "Column Mapping": "Spaltenzuordnung",
        "ID Column:": "ID-Spalte:",
        "Name Column:": "Name-Spalte:",
        "Single column": "Eine Spalte",
        "Firstname + Lastname": "Vorname + Nachname",
        "Name:": "Name:",
        "Firstname:": "Vorname:",
        "Lastname:": "Nachname:",
        "Liked Column:": "Beliebt-Spalte:",
        "Disliked Column:": "Unbeliebt-Spalte:",
        "Characteristics (select columns to use)": "Merkmale (Spalten auswählen)",
        "Cancel": "Abbrechen",
        "Import": "Importieren",
        
        # Group config
        "Add Group": "Gruppe hinzufügen",
        "Remove Group": "Gruppe entfernen",
        "Constraints for Selected Group": "Einschränkungen für ausgewählte Gruppe",
        "Add Constraint": "Einschränkung hinzufügen",
        "Remove Constraint": "Einschränkung entfernen",
        "Name": "Name",
        "Max Size": "Max. Größe",
        "Constraints": "Einschränkungen",
        "Characteristic": "Merkmal",
        "Type": "Typ",
        "Value": "Wert",
        "Add Constraint": "Einschränkung hinzufügen",
        "Edit Constraint": "Einschränkung bearbeiten",
        "Characteristic:": "Merkmal:",
        "Constraint Type:": "Einschränkungstyp:",
        "ALL - All must be in group": "ALLE - Alle müssen in der Gruppe sein",
        "SOME - Some should be in group": "EINIGE - Einige sollen in der Gruppe sein",
        "MAX - Maximum count in group": "MAX - Maximale Anzahl in der Gruppe",
        "Maximum count:": "Maximale Anzahl:",
        "Target count:": "Zielanzahl:",
        "No Characteristics": "Keine Merkmale",
        "Import data first to define characteristics.": "Importieren Sie zuerst Daten, um Merkmale zu definieren.",
        
        # Weights
        "Base Weights": "Basis-Gewichtungen",
        "Likes Weight:": "Gewichtung Beliebt:",
        "Dislikes Weight:": "Gewichtung Unbeliebt:",
        "Characteristic Weights": "Merkmal-Gewichtungen",
        "Score Formula": "Punkte-Formel",
        "Where:": "Wobei:",
        "likes = number of liked students in same group": "beliebt = Anzahl beliebter Schüler in derselben Gruppe",
        "dislikes = number of disliked students in same group": "unbeliebt = Anzahl unbeliebter Schüler in derselben Gruppe",
        "Constraint violations add penalties (50-100 points each)": "Einschränkungsverletzungen führen zu Abzügen (je 50-100 Punkte)",
        
        # Kanban
        "Unassigned": "Nicht zugewiesen",
        "students": "Schüler",
        "Score:": "Punkte:",
        "No constraints": "Keine Einschränkungen",
        "Sort": "Sortieren",
        "No sorting": "Keine Sortierung",
        "Likes": "Beliebt",
        "Dislikes": "Unbeliebt",
        "constraint violations": "Einschränkungsverletzungen",
        "Pin to group": "An Gruppe anheften",
        "Unpin from group": "Von Gruppe lösen",
        
        # Messages
        "No Data": "Keine Daten",
        "Please import student data first.": "Bitte importieren Sie zuerst Schülerdaten.",
        "No Groups": "Keine Gruppen",
        "Please create groups first.": "Bitte erstellen Sie zuerst Gruppen.",
        "Optimization Runs": "Optimierungsdurchläufe",
        "Number of optimization runs (more = better results, slower):": "Anzahl der Durchläufe (mehr = bessere Ergebnisse, langsamer):",
        "Optimizing group assignments...": "Optimiere Gruppenzuweisungen...",
        "Run": "Durchlauf",
        "Optimization complete.": "Optimierung abgeschlossen.",
        "Kept current result": "Aktuelles Ergebnis beibehalten",
        "Optimization canceled": "Optimierung abgebrochen",
        "Constraints Check": "Einschränkungsprüfung",
        "All constraints are satisfied!": "Alle Einschränkungen sind erfüllt!",
        "Constraint violations:": "Einschränkungsverletzungen:",
        "Error": "Fehler",
        "Failed to load file:": "Datei konnte nicht geladen werden:",
        "Failed to open project:": "Projekt konnte nicht geöffnet werden:",
        "Failed to save project:": "Projekt konnte nicht gespeichert werden:",
        "Failed to import:": "Import fehlgeschlagen:",
        "New project created": "Neues Projekt erstellt",
        "Opened:": "Geöffnet:",
        "Saved:": "Gespeichert:",
        "Imported": "Importiert",
        "students from": "Schüler aus",
        "Total score:": "Gesamtpunktzahl:",
        "Total:": "Gesamt:",
        "Groups:": "Gruppen:",
        "Penalties:": "Abzüge:",
        "Iteration": "Iteration",
        "Score": "Punkte",
        
        # Info widget
        "Score Summary": "Punkte-Zusammenfassung",
        "Groups Sum:": "Gruppen-Summe:",
        "Total Score:": "Gesamtpunktzahl:",
        "Group Scores": "Gruppen-Punkte",
        "Group": "Gruppe",
        "Penalty Details": "Abzugs-Details",
        "Penalty": "Abzug",
        "Reason": "Grund",
        "No constraint violations": "Keine Einschränkungsverletzungen",
        
        # Export dialog
        "Export to Excel": "Nach Excel exportieren",
        "Column Names": "Spaltennamen",
        "Use separate firstname/lastname columns": "Separate Vorname/Nachname-Spalten verwenden",
        "Firstname Column:": "Vorname-Spalte:",
        "Lastname Column:": "Nachname-Spalte:",
        "Group Column:": "Gruppen-Spalte:",
        "Output File": "Ausgabedatei",
        "Select output file...": "Ausgabedatei auswählen...",
        "Export": "Exportieren",
        "Please select an output file.": "Bitte wählen Sie eine Ausgabedatei.",
        "Export failed:": "Export fehlgeschlagen:",
        "Exported to:": "Exportiert nach:",
        
        # Toolbar
        "📂 Import Excel": "📂 Excel importieren",
        "▶️ Run Optimization": "▶️ Optimierung starten",
        "✓ Check Constraints": "✓ Einschränkungen prüfen",
        "🔗 Relationship Graph": "🔗 Beziehungsgraph",
        
        # View menu and relationship graph
        "View": "Ansicht",
        "Relationship Graph": "Beziehungsgraph",
        "Student Relationships": "Schülerbeziehungen",
        "Liked by": "Gemocht von",
        "Disliked by": "Abgelehnt von",
        
        # Results dialog
        "Select Optimization Result": "Optimierungsergebnis auswählen",
        "Select a result to apply. Results are sorted by total score (best first).": "Wählen Sie ein Ergebnis aus. Ergebnisse sind nach Gesamtpunktzahl sortiert (beste zuerst).",
        "Results": "Ergebnisse",
        "Apply Selected": "Ausgewähltes anwenden",
        "Optimization produced no results": "Optimierung hat keine Ergebnisse erzeugt",
        "Switch Result...": "Ergebnis wechseln...",
        "No Results": "Keine Ergebnisse",
        "Run optimization first to generate results.": "Führen Sie zuerst eine Optimierung durch, um Ergebnisse zu erzeugen.",
    }
}


def set_language(lang: str):
    """Set the current language."""
    global _current_language
    _current_language = lang


def get_language() -> str:
    """Get the current language."""
    return _current_language


def tr(text: str) -> str:
    """Translate a string to the current language."""
    if _current_language == "en":
        return text
    
    translations = _translations.get(_current_language, {})
    return translations.get(text, text)


def available_languages() -> list[tuple[str, str]]:
    """Get list of available languages as (code, name) tuples."""
    return [
        ("en", "English"),
        ("de", "Deutsch"),
    ]
