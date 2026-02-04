"""Simulated annealing algorithm for student grouping optimization - IMPROVED VERSION."""

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
    """Create an initial assignment respecting hard constraints and pinned students.
    
    IMPROVED: Better handling of students with preferences and fallback logic.
    """
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
    
    # IMPROVED: Sort by number of preferences (students with more preferences first)
    # This helps place highly-connected students in better positions
    unassigned.sort(key=lambda s: len(s.liked) + len(s.disliked), reverse=True)
    
    # IMPROVED: Add controlled randomness to prevent identical initial states
    for i in range(len(unassigned)):
        if random.random() < 0.3:  # 30% chance to shuffle each position
            j = random.randint(0, len(unassigned) - 1)
            unassigned[i], unassigned[j] = unassigned[j], unassigned[i]
    
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
                # SOME means at least 1, but respect value if provided
                min_count = 1
                max_count = constraint.value if constraint.value else 1
                
                current = sum(1 for sid in group.student_ids 
                            if result.get_student_by_id(sid).characteristics.get(char_name) is True)
                
                if current < min_count:
                    to_add = [s for s in unassigned 
                             if s.characteristics.get(char_name) is True]
                    
                    for student in to_add[:max_count - current]:
                        if len(group.student_ids) < group.max_size:
                            group.student_ids.append(student.id)
                            unassigned.remove(student)
    
    # Third pass: distribute remaining students
    group_idx = 0
    remaining_unassigned = []
    
    for student in unassigned:
        placed = False
        # Try to find a suitable group
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
                            if constraint.value and current >= constraint.value:
                                can_add = False
                                break
                
                if can_add:
                    group.student_ids.append(student.id)
                    placed = True
                    break
            
            group_idx = (group_idx + 1) % len(result.groups)
            attempts += 1
        
        if not placed:
            remaining_unassigned.append(student)
        
        group_idx = (group_idx + 1) % len(result.groups)
    
    # IMPROVED: Better fallback for students that couldn't be placed
    for student in remaining_unassigned:
        # First try: find any group with space
        placed = False
        for group in result.groups:
            if len(group.student_ids) < group.max_size:
                group.student_ids.append(student.id)
                placed = True
                break
        
        # IMPROVED: Ultimate fallback - place in smallest group even if over max_size
        if not placed:
            smallest = min(result.groups, key=lambda g: len(g.student_ids))
            smallest.student_ids.append(student.id)
    
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
    
    # Pick any different target group (allow over-capacity, penalties will handle it)
    targets = [g for g in result.groups if g != source]
    if not targets:
        return result
    
    target = random.choice(targets)
    
    # Move
    source.student_ids.remove(student_id)
    target.student_ids.append(student_id)
    
    return result


def smart_move_student(project: Project) -> Project:
    """Move a student toward liked peers or away from disliked peers."""
    result = deepcopy(project)
    
    # Find students with unsatisfied preferences
    candidates = []
    for group in result.groups:
        pinned = set(group.pinned_student_ids)
        group_ids = set(group.student_ids)
        
        for sid in group.student_ids:
            if sid in pinned:
                continue
            student = result.get_student_by_id(sid)
            if not student:
                continue
            
            # Count dislikes in current group (bad) and likes outside (missed opportunities)
            dislikes_here = len(set(student.disliked) & group_ids)
            likes_elsewhere = len(set(student.liked) - group_ids)
            
            if dislikes_here > 0 or likes_elsewhere > 0:
                candidates.append((sid, group, dislikes_here + likes_elsewhere))
    
    if not candidates:
        return move_student(result)  # Fallback to random move
    
    # Pick a candidate weighted by unhappiness
    candidates.sort(key=lambda x: x[2], reverse=True)
    # Take from top 30% of unhappy students
    top_candidates = candidates[:max(1, len(candidates) // 3)]
    student_id, source, _ = random.choice(top_candidates)
    
    student = result.get_student_by_id(student_id)
    
    # Find best target group (has liked students or fewer disliked)
    best_targets = []
    for group in result.groups:
        if group == source:
            continue
        group_ids = set(group.student_ids)
        likes_there = len(set(student.liked) & group_ids)
        dislikes_there = len(set(student.disliked) & group_ids)
        score = likes_there - dislikes_there
        best_targets.append((group, score))
    
    if not best_targets:
        return result
    
    # Sort by score and pick from top choices with some randomness
    best_targets.sort(key=lambda x: x[1], reverse=True)
    top_targets = best_targets[:max(1, len(best_targets) // 2)]
    target, _ = random.choice(top_targets)
    
    # Move
    source.student_ids.remove(student_id)
    target.student_ids.append(student_id)
    
    return result


def generate_neighbor(project: Project) -> Project:
    """Generate a neighbor solution using multiple strategies."""
    rand = random.random()
    
    if rand < 0.3:
        # 30% chance: swap two students
        return swap_students(project)
    elif rand < 0.6:
        # 30% chance: random move
        return move_student(project)
    elif rand < 0.9:
        # 30% chance: smart move (preference-based)
        return smart_move_student(project)
    else:
        # 10% chance: double move for bigger jumps
        temp = move_student(project)
        return move_student(temp)


def simulated_annealing(
    project: Project,
    initial_temp: float = 200.0,
    cooling_rate: float = 0.9995,
    min_temp: float = 0.01,
    max_iterations: int = 25000,
    progress_callback: Callable[[int, float, float], None] | None = None,
    verbose: bool = False,
    use_current_assignment: bool = False
) -> Project:
    """
    Optimize group assignments using simulated annealing.
    
    IMPROVED: Better temperature schedule, reheating, and adaptive cooling.
    
    Args:
        project: The project with groups and constraints defined
        initial_temp: Starting temperature (increased from 100 to 200)
        cooling_rate: Temperature multiplier each iteration
        min_temp: Stop when temperature reaches this
        max_iterations: Maximum iterations (increased from 15000 to 25000)
        progress_callback: Called with (iteration, temperature, score)
        verbose: Print diagnostic information
        use_current_assignment: If True, start from current assignment instead of generating new one
    
    Returns:
        Project with optimized assignments
    """
    # Start with current or new initial assignment
    if use_current_assignment:
        current = deepcopy(project)
    else:
        current = initial_assignment(project)
    current_score = calculate_total_score(current)
    initial_score = current_score
    
    best = deepcopy(current)
    best_score = current_score
    
    temperature = initial_temp
    iteration = 0
    
    # Track stagnation for reheating
    iterations_since_improvement = 0
    last_best_score = best_score
    
    # Diagnostic counters
    moves_accepted = 0
    moves_rejected = 0
    moves_improved = 0
    same_score_count = 0
    
    while temperature > min_temp and iteration < max_iterations:
        # Generate neighbor using diverse strategies
        neighbor = generate_neighbor(current)
        neighbor_score = calculate_total_score(neighbor)
        
        # Decide whether to accept
        delta = neighbor_score - current_score
        
        if delta == 0:
            same_score_count += 1
        
        if delta > 0:
            # Better solution, always accept
            current = neighbor
            current_score = neighbor_score
            moves_accepted += 1
            moves_improved += 1
        else:
            # Worse solution, accept with probability
            prob = math.exp(delta / temperature)
            if random.random() < prob:
                current = neighbor
                current_score = neighbor_score
                moves_accepted += 1
            else:
                moves_rejected += 1
        
        # Track best
        if current_score > best_score:
            best = deepcopy(current)
            best_score = current_score
            iterations_since_improvement = 0
        else:
            iterations_since_improvement += 1
        
        # IMPROVED: Adaptive cooling - cool slower when finding improvements
        if current_score > last_best_score:
            temperature *= (cooling_rate + 0.0003)  # Slower cooling
            last_best_score = current_score
        else:
            temperature *= cooling_rate  # Normal cooling
        
        # IMPROVED: Reheating to escape local optima
        if iterations_since_improvement > 2000 and iteration > 0:
            if verbose:
                print(f"  Reheating at iteration {iteration} (stagnant for {iterations_since_improvement} iters)")
            temperature = min(temperature * 3.0, initial_temp * 0.5)
            iterations_since_improvement = 0
        
        iteration += 1
        
        # Progress callback
        if progress_callback and iteration % 100 == 0:
            progress_callback(iteration, temperature, best_score)
    
    if verbose:
        print(f"  Final: iteration {iteration}/{max_iterations}, temp {temperature:.4f}")
        print(f"  Moves: {moves_accepted} accepted, {moves_rejected} rejected, {moves_improved} improved")
        print(f"  Same score moves: {same_score_count} ({100*same_score_count/max(1,iteration):.1f}%)")
        print(f"  Score: {initial_score:.1f} → {best_score:.1f} (Δ{best_score - initial_score:+.1f})")
        if iteration >= max_iterations:
            print("  (hit max iterations)")
    
    return best


def optimize_with_restarts(
    project: Project,
    num_restarts: int = 10,
    initial_temp: float = 200.0,
    cooling_rate: float = 0.9995,
    min_temp: float = 0.01,
    max_iterations: int = 25000,
    progress_callback: Callable[[int, float, float, int], None] | None = None,
    verbose: bool = True
) -> Project:
    """
    Run simulated annealing multiple times and return the best result.
    
    IMPROVED: Better tracking, diagnostics, and increased default restarts.
    
    Args:
        project: The project with groups and constraints defined
        num_restarts: Number of times to run the optimization (increased from 5 to 10)
        initial_temp: Starting temperature for each run
        cooling_rate: Temperature multiplier each iteration
        min_temp: Stop when temperature reaches this
        max_iterations: Maximum iterations per run
        progress_callback: Called with (iteration, temperature, score, restart_num)
        verbose: Print diagnostic information
    
    Returns:
        Project with the best optimized assignments across all runs
    """
    overall_best = None
    overall_best_score = float('-inf')
    
    scores = []  # Track all run scores for statistics
    
    if verbose:
        print(f"Starting optimization with {num_restarts} restarts...")
        print(f"  (restart 1 uses current assignment, others use random initial assignments)")
    
    for restart in range(num_restarts):
        if verbose:
            restart_type = "current" if restart == 0 else "random"
            print(f"\nRestart {restart + 1}/{num_restarts} ({restart_type}):")
        
        def restart_callback(iteration, temp, score):
            if progress_callback:
                # Adjust iteration to show overall progress
                total_iter = restart * max_iterations + iteration
                progress_callback(total_iter, temp, score, restart + 1)
        
        # First restart uses current assignment, subsequent ones generate new initial assignments
        use_current = (restart == 0)
        
        result = simulated_annealing(
            project,
            initial_temp=initial_temp,
            cooling_rate=cooling_rate,
            min_temp=min_temp,
            max_iterations=max_iterations,
            progress_callback=restart_callback,
            verbose=verbose,
            use_current_assignment=use_current
        )
        
        score = calculate_total_score(result)
        scores.append(score)
        
        if score > overall_best_score:
            overall_best = result
            overall_best_score = score
            if verbose:
                print(f"  >>> New best score: {score:.1f}")
        
        # If we found a better solution, use it as basis for some future restarts
        if overall_best is not None and restart == num_restarts // 2:
            # Midway through, update project to best found so far for more focused search
            project = deepcopy(overall_best)
    
    # Print statistics
    if verbose and len(scores) > 1:
        mean_score = sum(scores) / len(scores)
        variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
        std_dev = variance ** 0.5
        
        print(f"\n{'='*60}")
        print(f"Optimization Complete!")
        print(f"{'='*60}")
        print(f"Scores across {num_restarts} runs: {[f'{s:.1f}' for s in scores]}")
        print(f"Best:  {max(scores):.1f}")
        print(f"Worst: {min(scores):.1f}")
        print(f"Mean:  {mean_score:.1f}")
        print(f"StdDev: {std_dev:.1f}")
        print(f"Range: {max(scores) - min(scores):.1f}")
        print(f"{'='*60}")
        
        # Validate final result
        valid, violations = check_hard_constraints(overall_best)
        if not valid:
            print(f"⚠️  WARNING: Final result has constraint violations:")
            for v in violations:
                print(f"  - {v}")
        else:
            print(f"✓ All hard constraints satisfied")
    
    return overall_best
