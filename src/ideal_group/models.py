"""Core data models for the Ideal Group application."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ConstraintType(Enum):
    """Type of constraint for group assignment."""
    ALL = "all"      # All students with this characteristic must be in this group
    SOME = "some"    # Some students with this characteristic should be in this group
    MAX = "max"      # Maximum number of students with this characteristic


@dataclass
class Constraint:
    """A constraint on a group."""
    characteristic: str
    constraint_type: ConstraintType
    value: Optional[int] = None  # For MAX constraints, the maximum count
    
    def to_dict(self) -> dict:
        return {
            "characteristic": self.characteristic,
            "constraint_type": self.constraint_type.value,
            "value": self.value
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Constraint":
        return cls(
            characteristic=data["characteristic"],
            constraint_type=ConstraintType(data["constraint_type"]),
            value=data.get("value")
        )


@dataclass
class Student:
    """A student with characteristics and preferences."""
    id: int
    name: str
    characteristics: dict[str, any] = field(default_factory=dict)
    liked: list[int] = field(default_factory=list)
    disliked: list[int] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "characteristics": self.characteristics,
            "liked": self.liked,
            "disliked": self.disliked
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Student":
        return cls(
            id=data["id"],
            name=data["name"],
            characteristics=data.get("characteristics", {}),
            liked=data.get("liked", []),
            disliked=data.get("disliked", [])
        )


@dataclass
class Group:
    """A group of students with constraints."""
    name: str
    max_size: int
    constraints: list[Constraint] = field(default_factory=list)
    student_ids: list[int] = field(default_factory=list)
    pinned_student_ids: list[int] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "max_size": self.max_size,
            "constraints": [c.to_dict() for c in self.constraints],
            "student_ids": self.student_ids,
            "pinned_student_ids": self.pinned_student_ids
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Group":
        return cls(
            name=data["name"],
            max_size=data["max_size"],
            constraints=[Constraint.from_dict(c) for c in data.get("constraints", [])],
            student_ids=data.get("student_ids", []),
            pinned_student_ids=data.get("pinned_student_ids", [])
        )


@dataclass
class ColumnMapping:
    """Mapping from Excel columns to required fields."""
    id_column: str = ""
    name_column: str = ""
    firstname_column: str = ""  # Optional: if set, use firstname + lastname
    lastname_column: str = ""   # Optional: if set, use firstname + lastname
    use_separate_name_columns: bool = False  # Whether to use firstname/lastname
    liked_column: str = ""
    disliked_column: str = ""
    characteristic_columns: dict[str, str] = field(default_factory=dict)  # name -> column
    
    def to_dict(self) -> dict:
        return {
            "id_column": self.id_column,
            "name_column": self.name_column,
            "firstname_column": self.firstname_column,
            "lastname_column": self.lastname_column,
            "use_separate_name_columns": self.use_separate_name_columns,
            "liked_column": self.liked_column,
            "disliked_column": self.disliked_column,
            "characteristic_columns": self.characteristic_columns
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ColumnMapping":
        return cls(
            id_column=data.get("id_column", ""),
            name_column=data.get("name_column", ""),
            firstname_column=data.get("firstname_column", ""),
            lastname_column=data.get("lastname_column", ""),
            use_separate_name_columns=data.get("use_separate_name_columns", False),
            liked_column=data.get("liked_column", ""),
            disliked_column=data.get("disliked_column", ""),
            characteristic_columns=data.get("characteristic_columns", {})
        )


@dataclass
class Weights:
    """Weights for the scoring algorithm."""
    likes_weight: float = 1.0
    dislikes_weight: float = 2.0
    characteristic_weights: dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "likes_weight": self.likes_weight,
            "dislikes_weight": self.dislikes_weight,
            "characteristic_weights": self.characteristic_weights
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Weights":
        return cls(
            likes_weight=data.get("likes_weight", 1.0),
            dislikes_weight=data.get("dislikes_weight", 2.0),
            characteristic_weights=data.get("characteristic_weights", {})
        )


@dataclass
class Project:
    """The complete project state."""
    excel_path: str = ""
    column_mapping: ColumnMapping = field(default_factory=ColumnMapping)
    students: list[Student] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    weights: Weights = field(default_factory=Weights)
    
    def to_dict(self) -> dict:
        return {
            "excel_path": self.excel_path,
            "column_mapping": self.column_mapping.to_dict(),
            "students": [s.to_dict() for s in self.students],
            "groups": [g.to_dict() for g in self.groups],
            "weights": self.weights.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        return cls(
            excel_path=data.get("excel_path", ""),
            column_mapping=ColumnMapping.from_dict(data.get("column_mapping", {})),
            students=[Student.from_dict(s) for s in data.get("students", [])],
            groups=[Group.from_dict(g) for g in data.get("groups", [])],
            weights=Weights.from_dict(data.get("weights", {}))
        )
    
    def get_student_by_id(self, student_id: int) -> Optional[Student]:
        """Get a student by their ID."""
        for student in self.students:
            if student.id == student_id:
                return student
        return None
    
    def get_unassigned_students(self) -> list[Student]:
        """Get all students not assigned to any group."""
        assigned_ids = set()
        for group in self.groups:
            assigned_ids.update(group.student_ids)
        return [s for s in self.students if s.id not in assigned_ids]
