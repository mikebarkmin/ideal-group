"""Simulated annealing algorithm for student grouping optimization."""

import random
import math
from copy import deepcopy
from typing import Callable

from .models import Project, Group, Student, ConstraintType


def calculate_likes_score(project: Project, group: Group) -> float:
    """Calculate score based on how many liked students are in the same group."""
    score = 0.0
    student_ids_set = set(group.student_ids)
    
    for student_id in group.student_ids:
        student = project.get_student_by_id(student_id)
        if student:
            # Count liked students in same group
            likes_in_group = len(set(student.liked) & student_ids_set)
            score += likes_in_group
    
    return score


def calculate_dislikes_score(project: Project, group: Group) -> float:
    """Calculate penalty based on how many disliked students are in the same group."""
    penalty = 0.0
    student_ids_set = set(group.student_ids)
    
    for student_id in group.student_ids:
        student = project.get_student_by_id(student_id)
        if student:
            # Count disliked students in same group (this is bad)
            dislikes_in_group = len(set(student.disliked) & student_ids_set)
            penalty += dislikes_in_group
    
    return penalty


def check_hard_constraints(project: Project) -> tuple[bool, list[str]]:
    """Check if all hard constraints are satisfied. Returns (valid, violations)."""
    violations = []
    
    # Build characteristic -> student mapping
    char_students: dict[str, set[int]] = {}
    for student in project.students:
        for char_name, value in student.characteristics.items():
            if value is True:
                if char_name not in char_students:
                    char_students[char_name] = set()
                char_students[char_name].add(student.id)
    
    for group in project.groups:
        group_ids = set(group.student_ids)
        
        # Check size constraint
        if len(group.student_ids) > group.max_size:
            violations.append(f"{group.name}: exceeds max size ({len(group.student_ids)} > {group.max_size})")
        
        for constraint in group.constraints:
            char_name = constraint.characteristic
            students_with_char = char_students.get(char_name, set())
            students_with_char_in_group = students_with_char & group_ids
            
            if constraint.constraint_type == ConstraintType.ALL:
                # All students with this characteristic must be in this group
                missing = students_with_char - group_ids
                if missing:
                    violations.append(f"{group.name}: ALL constraint violated for {char_name}, missing {len(missing)} students")
            
            elif constraint.constraint_type == ConstraintType.MAX:
                # Maximum number of students with this characteristic
                if len(students_with_char_in_group) > constraint.value:
                    violations.append(f"{group.name}: MAX constraint violated for {char_name} ({len(students_with_char_in_group)} > {constraint.value})")
    
    return len(violations) == 0, violations


def calculate_constraint_penalty(project: Project) -> float:
    """Calculate penalty for constraint violations."""
    return calculate_constraint_penalty_details(project)[0]


def calculate_constraint_penalty_details(project: Project) -> tuple[float, list[tuple[str, float, str]]]:
    """Calculate penalty for constraint violations with details.
    
    Pinned students are exempt from constraint penalties - they are where the user
    explicitly placed them, so no penalty applies.
    
    Returns:
        Tuple of (total_penalty, list of (group_name, penalty_amount, reason))
    """
    penalty = 0.0
    details: list[tuple[str, float, str]] = []
    
    # Collect all pinned students and which group they're pinned to
    pinned_students: dict[int, str] = {}  # student_id -> group_name
    for group in project.groups:
        for sid in group.pinned_student_ids:
            pinned_students[sid] = group.name
    
    # Build characteristic -> non-pinned student mapping
    char_students: dict[str, set[int]] = {}
    for student in project.students:
        # Skip pinned students - they're exempt from constraints
        if student.id in pinned_students:
            continue
        for char_name, value in student.characteristics.items():
            if value is True:
                if char_name not in char_students:
                    char_students[char_name] = set()
                char_students[char_name].add(student.id)
    
    for group in project.groups:
        group_ids = set(group.student_ids)
        pinned_in_group = set(group.pinned_student_ids)
        non_pinned_in_group = group_ids - pinned_in_group
        
        # Size violation penalty (pinned students still count toward size)
        if len(group.student_ids) > group.max_size:
            p = (len(group.student_ids) - group.max_size) * 100
            penalty += p
            details.append((group.name, p, f"Size exceeded: {len(group.student_ids)}/{group.max_size}"))
        
        for constraint in group.constraints:
            char_name = constraint.characteristic
            # Only consider non-pinned students for constraint violations
            students_with_char = char_students.get(char_name, set())
            students_with_char_in_group = students_with_char & non_pinned_in_group
            
            if constraint.constraint_type == ConstraintType.ALL:
                # Missing = students with this char who are not in this group (and not pinned elsewhere)
                missing = students_with_char - group_ids
                if missing:
                    p = len(missing) * 50
                    penalty += p
                    details.append((group.name, p, f"ALL {char_name}: {len(missing)} missing"))
            
            elif constraint.constraint_type == ConstraintType.MAX:
                # Only count non-pinned students toward MAX
                if constraint.value and len(students_with_char_in_group) > constraint.value:
                    p = (len(students_with_char_in_group) - constraint.value) * 50
                    penalty += p
                    details.append((group.name, p, f"MAX {char_name}: {len(students_with_char_in_group)} > {constraint.value}"))
            
            elif constraint.constraint_type == ConstraintType.SOME:
                # Check if there are any students with this char (pinned or not)
                all_with_char_in_group = set()
                for sid in group.student_ids:
                    student = project.get_student_by_id(sid)
                    if student and student.characteristics.get(char_name) is True:
                        all_with_char_in_group.add(sid)
                if len(all_with_char_in_group) == 0:
                    p = 25
                    penalty += p
                    details.append((group.name, p, f"SOME {char_name}: none in group"))
    
    return penalty, details


def calculate_group_score(project: Project, group: Group) -> float:
    """Calculate the score for a single group."""
    likes = calculate_likes_score(project, group)
    dislikes = calculate_dislikes_score(project, group)
    
    score = (likes * project.weights.likes_weight) - (dislikes * project.weights.dislikes_weight)
    return score


def calculate_total_score(project: Project) -> float:
    """Calculate the total score for the current assignment."""
    total = 0.0
    
    for group in project.groups:
        total += calculate_group_score(project, group)
    
    # Subtract constraint penalties
    total -= calculate_constraint_penalty(project)
    
    return total


def get_student_score_in_group(student: Student, group: Group, project: Project) -> dict:
    """Get detailed score info for a student in a group."""
    group_ids = set(group.student_ids)
    
    likes_in_group = [sid for sid in student.liked if sid in group_ids]
    dislikes_in_group = [sid for sid in student.disliked if sid in group_ids]
    
    return {
        "likes_satisfied": len(likes_in_group),
        "likes_total": len(student.liked),
        "dislikes_in_group": len(dislikes_in_group),
        "dislikes_total": len(student.disliked),
        "likes_ids": likes_in_group,
        "dislikes_ids": dislikes_in_group
    }


def initial_assignment(project: Project) -> Project:
    """Create an initial assignment respecting hard constraints and pinned students."""
    result = deepcopy(project)
    
    # Collect pinned students (they stay in their groups)
    pinned_students = set()
    for group in result.groups:
        for sid in group.pinned_student_ids:
            pinned_students.add(sid)
    
    # Clear existing assignments but keep pinned students
    for group in result.groups:
        group.student_ids = [sid for sid in group.student_ids if sid in group.pinned_student_ids]
    
    # Get unassigned students (not pinned)
    assigned_ids = set()
    for group in result.groups:
        assigned_ids.update(group.student_ids)
    
    unassigned = [s for s in result.students if s.id not in assigned_ids]
    random.shuffle(unassigned)
    
    # First pass: handle ALL constraints (skip pinned students - they're already handled)
    for group in result.groups:
        for constraint in group.constraints:
            if constraint.constraint_type == ConstraintType.ALL:
                char_name = constraint.characteristic
                to_add = [s for s in unassigned 
                         if s.characteristics.get(char_name) is True]
                for student in to_add:
                    if len(group.student_ids) < group.max_size:
                        group.student_ids.append(student.id)
                        unassigned.remove(student)
    
    # Second pass: handle SOME constraints
    for group in result.groups:
        for constraint in group.constraints:
            if constraint.constraint_type == ConstraintType.SOME:
                char_name = constraint.characteristic
                max_count = constraint.value if constraint.value else 1
                current = sum(1 for sid in group.student_ids 
                            if result.get_student_by_id(sid).characteristics.get(char_name) is True)
                
                to_add = [s for s in unassigned 
                         if s.characteristics.get(char_name) is True]
                
                for student in to_add[:max_count - current]:
                    if len(group.student_ids) < group.max_size:
                        group.student_ids.append(student.id)
                        unassigned.remove(student)
    
    # Third pass: distribute remaining students
    group_idx = 0
    for student in unassigned:
        # Find next group with space
        attempts = 0
        while attempts < len(result.groups):
            group = result.groups[group_idx]
            if len(group.student_ids) < group.max_size:
                # Check MAX constraints
                can_add = True
                for constraint in group.constraints:
                    if constraint.constraint_type == ConstraintType.MAX:
                        char_name = constraint.characteristic
                        if student.characteristics.get(char_name) is True:
                            current = sum(1 for sid in group.student_ids 
                                        if result.get_student_by_id(sid).characteristics.get(char_name) is True)
                            if current >= constraint.value:
                                can_add = False
                                break
                
                if can_add:
                    group.student_ids.append(student.id)
                    break
            
            group_idx = (group_idx + 1) % len(result.groups)
            attempts += 1
        else:
            # Fallback: add to first group with space
            for group in result.groups:
                if len(group.student_ids) < group.max_size:
                    group.student_ids.append(student.id)
                    break
        
        group_idx = (group_idx + 1) % len(result.groups)
    
    return result


def swap_students(project: Project) -> Project:
    """Create a neighbor solution by swapping two students between groups."""
    result = deepcopy(project)
    
    # Filter to groups with movable (non-pinned) students
    def get_movable_students(group):
        pinned = set(group.pinned_student_ids)
        return [sid for sid in group.student_ids if sid not in pinned]
    
    groups_with_movable = [(g, get_movable_students(g)) for g in result.groups]
    groups_with_movable = [(g, m) for g, m in groups_with_movable if m]
    
    if len(groups_with_movable) < 2:
        return result
    
    # Pick two different groups
    (g1, movable1), (g2, movable2) = random.sample(groups_with_movable, 2)
    
    # Pick a movable student from each
    s1_id = random.choice(movable1)
    s2_id = random.choice(movable2)
    
    # Swap
    g1.student_ids.remove(s1_id)
    g2.student_ids.remove(s2_id)
    g1.student_ids.append(s2_id)
    g2.student_ids.append(s1_id)
    
    return result


def move_student(project: Project) -> Project:
    """Create a neighbor solution by moving a student to a different group."""
    result = deepcopy(project)
    
    # Filter to groups with movable (non-pinned) students
    def get_movable_students(group):
        pinned = set(group.pinned_student_ids)
        return [sid for sid in group.student_ids if sid not in pinned]
    
    groups_with_movable = [(g, get_movable_students(g)) for g in result.groups]
    groups_with_movable = [(g, m) for g, m in groups_with_movable if m]
    
    if not groups_with_movable:
        return result
    
    # Pick source group and movable student
    source, movable = random.choice(groups_with_movable)
    student_id = random.choice(movable)
    
    # Pick target group (different, with space)
    targets = [g for g in result.groups 
               if g != source and len(g.student_ids) < g.max_size]
    if not targets:
        return result
    
    target = random.choice(targets)
    
    # Move
    source.student_ids.remove(student_id)
    target.student_ids.append(student_id)
    
    return result


def simulated_annealing(
    project: Project,
    initial_temp: float = 100.0,
    cooling_rate: float = 0.997,
    min_temp: float = 0.1,
    max_iterations: int = 15000,
    progress_callback: Callable[[int, float, float], None] | None = None
) -> Project:
    """
    Optimize group assignments using simulated annealing.
    
    Args:
        project: The project with groups and constraints defined
        initial_temp: Starting temperature
        cooling_rate: Temperature multiplier each iteration
        min_temp: Stop when temperature reaches this
        max_iterations: Maximum iterations
        progress_callback: Called with (iteration, temperature, score)
    
    Returns:
        Project with optimized assignments
    """
    # Start with initial assignment
    current = initial_assignment(project)
    current_score = calculate_total_score(current)
    
    best = deepcopy(current)
    best_score = current_score
    
    temperature = initial_temp
    iteration = 0
    
    while temperature > min_temp and iteration < max_iterations:
        # Generate neighbor
        if random.random() < 0.5:
            neighbor = swap_students(current)
        else:
            neighbor = move_student(current)
        
        neighbor_score = calculate_total_score(neighbor)
        
        # Decide whether to accept
        delta = neighbor_score - current_score
        
        if delta > 0:
            # Better solution, always accept
            current = neighbor
            current_score = neighbor_score
        else:
            # Worse solution, accept with probability
            prob = math.exp(delta / temperature)
            if random.random() < prob:
                current = neighbor
                current_score = neighbor_score
        
        # Track best
        if current_score > best_score:
            best = deepcopy(current)
            best_score = current_score
        
        # Cool down
        temperature *= cooling_rate
        iteration += 1
        
        # Progress callback
        if progress_callback and iteration % 100 == 0:
            progress_callback(iteration, temperature, best_score)
    
    return best


def optimize_with_restarts(
    project: Project,
    num_restarts: int = 5,
    initial_temp: float = 100.0,
    cooling_rate: float = 0.997,
    min_temp: float = 0.1,
    max_iterations: int = 15000,
    progress_callback: Callable[[int, float, float, int], None] | None = None
) -> Project:
    """
    Run simulated annealing multiple times and return the best result.
    
    Args:
        project: The project with groups and constraints defined
        num_restarts: Number of times to run the optimization
        initial_temp: Starting temperature for each run
        cooling_rate: Temperature multiplier each iteration
        min_temp: Stop when temperature reaches this
        max_iterations: Maximum iterations per run
        progress_callback: Called with (iteration, temperature, score, restart_num)
    
    Returns:
        Project with the best optimized assignments across all runs
    """
    overall_best = None
    overall_best_score = float('-inf')
    
    for restart in range(num_restarts):
        def restart_callback(iteration, temp, score):
            if progress_callback:
                # Adjust iteration to show overall progress
                total_iter = restart * max_iterations + iteration
                progress_callback(total_iter, temp, score, restart + 1)
        
        result = simulated_annealing(
            project,
            initial_temp=initial_temp,
            cooling_rate=cooling_rate,
            min_temp=min_temp,
            max_iterations=max_iterations,
            progress_callback=restart_callback
        )
        
        score = calculate_total_score(result)
        if score > overall_best_score:
            overall_best = result
            overall_best_score = score
    
    return overall_best
