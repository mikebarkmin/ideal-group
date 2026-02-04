"""Excel file import and parsing functionality."""

import pandas as pd
from pathlib import Path

from .models import Student, ColumnMapping


def read_excel_columns(path: str | Path) -> list[str]:
    """Read column names from an Excel file."""
    df = pd.read_excel(path, nrows=0)
    return list(df.columns)


def read_excel_preview(path: str | Path, rows: int = 5) -> pd.DataFrame:
    """Read a preview of the Excel file."""
    return pd.read_excel(path, nrows=rows)


def parse_id_list(value: str | None) -> list[int]:
    """Parse a comma-separated list of IDs."""
    if pd.isna(value) or not value:
        return []
    if isinstance(value, (int, float)):
        return [int(value)]
    parts = str(value).split(',')
    result = []
    for part in parts:
        part = part.strip()
        if part:
            try:
                result.append(int(float(part)))
            except ValueError:
                pass
    return result


def import_students(path: str | Path, mapping: ColumnMapping) -> list[Student]:
    """Import students from an Excel file using the given column mapping."""
    df = pd.read_excel(path)
    students = []
    
    for _, row in df.iterrows():
        # Parse basic fields
        student_id = int(row[mapping.id_column])
        
        # Parse name - either single column or firstname + lastname
        if mapping.use_separate_name_columns:
            firstname = str(row.get(mapping.firstname_column, "")).strip()
            lastname = str(row.get(mapping.lastname_column, "")).strip()
            name = f"{firstname} {lastname}".strip()
        else:
            name = str(row[mapping.name_column])
        
        # Parse liked/disliked
        liked = parse_id_list(row.get(mapping.liked_column))
        disliked = parse_id_list(row.get(mapping.disliked_column))
        
        # Parse characteristics
        characteristics = {}
        for char_name, col_name in mapping.characteristic_columns.items():
            value = row.get(col_name)
            if pd.isna(value):
                value = None
            elif isinstance(value, str):
                # Convert j/n, y/n, yes/no to boolean
                lower = value.lower().strip()
                if lower in ('j', 'y', 'yes', 'ja', 'true', '1'):
                    value = True
                elif lower in ('n', 'no', 'nein', 'false', '0'):
                    value = False
            characteristics[char_name] = value
        
        students.append(Student(
            id=student_id,
            name=name,
            characteristics=characteristics,
            liked=liked,
            disliked=disliked
        ))
    
    return students
