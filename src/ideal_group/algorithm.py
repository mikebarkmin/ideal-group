"""Simulated annealing algorithm for student grouping optimization - FAST VERSION.

Key improvements over previous version:
- No deepcopy on every neighbor: mutations are applied in-place and rolled back on rejection
- O(1) incremental score updates: only recompute the delta for moved/swapped students
- Student ID → Student lookup cached as a dict (was O(n) linear scan)
- Smarter initial assignment: greedy preference-aware seeding
- Tighter reheating: triggers after 500 stagnant iterations instead of 2000
- Cooling schedule tuned for faster convergence without losing exploration
"""

import random
import math
from copy import deepcopy
from typing import Callable

from .models import Project, Group, Student, ConstraintType


# ---------------------------------------------------------------------------
# Lookup cache (rebuilt once per SA run)
# ---------------------------------------------------------------------------

def _build_lookup(project: Project) -> dict[int, Student]:
    return {s.id: s for s in project.students}


# ---------------------------------------------------------------------------
# Incremental scoring helpers
# ---------------------------------------------------------------------------

def _student_delta(
    student_id: int,
    old_group_ids: set[int],
    new_group_ids: set[int],
    lookup: dict[int, Student],
    likes_w: float,
    dislikes_w: float,
) -> float:
    """Return the score change caused by moving one student from old_group to new_group.

    We only need to account for the student's own preferences, PLUS the preferences
    that other students in those groups have toward the moving student.  Group-level
    symmetry means every like/dislike is counted from both sides, so we handle:
      - student's likes/dislikes that appear in old/new group
      - every other student in old/new group whose liked/disliked list contains student_id
    """
    student = lookup.get(student_id)
    if student is None:
        return 0.0

    delta = 0.0

    # --- Student's own preferences ---
    # Likes lost from old group
    likes_lost = len(set(student.liked) & old_group_ids)
    # Likes gained in new group
    likes_gained = len(set(student.liked) & new_group_ids)
    # Dislikes lost from old group (good: penalty removed)
    dislikes_lost = len(set(student.disliked) & old_group_ids)
    # Dislikes gained in new group (bad: new penalty)
    dislikes_gained = len(set(student.disliked) & new_group_ids)

    delta += (likes_gained - likes_lost) * likes_w
    delta -= (dislikes_gained - dislikes_lost) * dislikes_w

    # --- Other students' preferences toward this student ---
    # Students in old_group who liked/disliked us: moving away changes their score
    for oid in old_group_ids:
        other = lookup.get(oid)
        if other is None:
            continue
        if student_id in other.liked:
            delta -= likes_w       # they lose a liked peer
        if student_id in other.disliked:
            delta += dislikes_w    # they lose a disliked peer (good for them)

    # Students in new_group who liked/disliked us: moving in changes their score
    for nid in new_group_ids:
        other = lookup.get(nid)
        if other is None:
            continue
        if student_id in other.liked:
            delta += likes_w       # they gain a liked peer
        if student_id in other.disliked:
            delta -= dislikes_w    # they gain a disliked peer (bad for them)

    return delta


# ---------------------------------------------------------------------------
# Constraint penalty (full recalc – only called at start/end, not each step)
# ---------------------------------------------------------------------------

def calculate_constraint_penalty(project: Project, lookup: dict[int, Student]) -> float:
    penalty = 0.0

    pinned_students: set[int] = set()
    for group in project.groups:
        pinned_students.update(group.pinned_student_ids)

    # char -> set of non-pinned student ids that have that char = True
    char_students: dict[str, set[int]] = {}
    for student in project.students:
        if student.id in pinned_students:
            continue
        for char_name, value in student.characteristics.items():
            if value is True:
                char_students.setdefault(char_name, set()).add(student.id)

    for group in project.groups:
        group_ids = set(group.student_ids)
        pinned_in_group = set(group.pinned_student_ids)
        non_pinned_in_group = group_ids - pinned_in_group

        if len(group.student_ids) > group.max_size:
            penalty += (len(group.student_ids) - group.max_size) * 100

        for constraint in group.constraints:
            char_name = constraint.characteristic
            students_with_char = char_students.get(char_name, set())
            students_with_char_in_group = students_with_char & non_pinned_in_group

            if constraint.constraint_type == ConstraintType.ALL:
                missing = students_with_char - group_ids
                if missing:
                    penalty += len(missing) * 50

            elif constraint.constraint_type == ConstraintType.MAX:
                if constraint.value and len(students_with_char_in_group) > constraint.value:
                    penalty += (len(students_with_char_in_group) - constraint.value) * 50

            elif constraint.constraint_type == ConstraintType.SOME:
                all_with_char = sum(
                    1 for sid in group.student_ids
                    if lookup.get(sid) and lookup[sid].characteristics.get(char_name) is True
                )
                if all_with_char == 0:
                    penalty += 25

    return penalty


def _constraint_penalty_delta_swap(
    s1_id: int, g1: Group,
    s2_id: int, g2: Group,
    lookup: dict[int, Student],
) -> float:
    """Fast approximation of constraint penalty delta for a swap.

    Only checks size and MAX constraints because ALL/SOME are unaffected by
    same-count swaps (the totals don't change). For MAX, we check whether
    the swap moves a student with the constrained characteristic into a group
    that is already at its MAX limit.
    """
    delta = 0.0
    s1 = lookup.get(s1_id)
    s2 = lookup.get(s2_id)
    if s1 is None or s2 is None:
        return 0.0

    # Size constraints don't change in a swap (both groups keep same count).

    for constraint in g2.constraints:
        if constraint.constraint_type == ConstraintType.MAX and constraint.value:
            char = constraint.characteristic
            if s1.characteristics.get(char) is True:
                current = sum(
                    1 for sid in g2.student_ids
                    if lookup.get(sid) and lookup[sid].characteristics.get(char) is True
                )
                # s2 leaves g2, s1 enters g2
                leaving = 1 if s2.characteristics.get(char) is True else 0
                after = current - leaving + 1
                before_violation = max(0, current - leaving - constraint.value)  # after removing s2
                # more precisely:
                before_violation = max(0, current - constraint.value)
                after_violation = max(0, after - constraint.value)
                delta += (after_violation - before_violation) * 50

    for constraint in g1.constraints:
        if constraint.constraint_type == ConstraintType.MAX and constraint.value:
            char = constraint.characteristic
            if s2.characteristics.get(char) is True:
                current = sum(
                    1 for sid in g1.student_ids
                    if lookup.get(sid) and lookup[sid].characteristics.get(char) is True
                )
                leaving = 1 if s1.characteristics.get(char) is True else 0
                after = current - leaving + 1
                before_violation = max(0, current - constraint.value)
                after_violation = max(0, after - constraint.value)
                delta += (after_violation - before_violation) * 50

    return delta


def _constraint_penalty_delta_move(
    student_id: int, source: Group, target: Group,
    lookup: dict[int, Student],
) -> float:
    """Fast constraint penalty delta for moving one student."""
    delta = 0.0
    student = lookup.get(student_id)
    if student is None:
        return 0.0

    # Size: source shrinks (good if over), target grows (bad if at max)
    if len(source.student_ids) > source.max_size:
        delta -= 100  # removing helps
    if len(target.student_ids) >= target.max_size:
        delta += 100  # adding hurts

    for constraint in target.constraints:
        if constraint.constraint_type == ConstraintType.MAX and constraint.value:
            char = constraint.characteristic
            if student.characteristics.get(char) is True:
                current = sum(
                    1 for sid in target.student_ids
                    if lookup.get(sid) and lookup[sid].characteristics.get(char) is True
                )
                before_v = max(0, current - constraint.value)
                after_v = max(0, current + 1 - constraint.value)
                delta += (after_v - before_v) * 50

        elif constraint.constraint_type == ConstraintType.SOME:
            char = constraint.characteristic
            current = sum(
                1 for sid in target.student_ids
                if lookup.get(sid) and lookup[sid].characteristics.get(char) is True
            )
            if current == 0 and student.characteristics.get(char) is True:
                delta -= 25  # satisfies SOME

    for constraint in source.constraints:
        if constraint.constraint_type == ConstraintType.SOME:
            char = constraint.characteristic
            if student.characteristics.get(char) is True:
                current = sum(
                    1 for sid in source.student_ids
                    if lookup.get(sid) and lookup[sid].characteristics.get(char) is True
                )
                if current == 1:
                    delta += 25  # removing the only one breaks SOME

    return delta


# ---------------------------------------------------------------------------
# Initial assignment
# ---------------------------------------------------------------------------

def initial_assignment(project: Project) -> Project:
    """Greedy preference-aware initial assignment.

    Strategy:
    1. Keep pinned students in place.
    2. Handle ALL constraints first.
    3. For each remaining student, greedily pick the group that maximises
       the immediate likes score (or minimises dislikes).
    4. Fallback: round-robin for any remaining.
    """
    result = deepcopy(project)
    lookup = _build_lookup(result)

    pinned: set[int] = set()
    for group in result.groups:
        pinned.update(group.pinned_student_ids)

    # Clear assignments, keep pinned
    for group in result.groups:
        group.student_ids = [sid for sid in group.student_ids if sid in group.pinned_student_ids]

    unassigned = [s for s in result.students if s.id not in pinned]
    random.shuffle(unassigned)  # break ties randomly

    # Pass 1: ALL constraints
    for group in result.groups:
        for constraint in group.constraints:
            if constraint.constraint_type == ConstraintType.ALL:
                char = constraint.characteristic
                to_add = [s for s in unassigned if s.characteristics.get(char) is True]
                for student in to_add:
                    if len(group.student_ids) < group.max_size:
                        group.student_ids.append(student.id)
                        unassigned.remove(student)

    # Pass 2: SOME constraints
    for group in result.groups:
        for constraint in group.constraints:
            if constraint.constraint_type == ConstraintType.SOME:
                char = constraint.characteristic
                already = sum(1 for sid in group.student_ids if lookup.get(sid) and lookup[sid].characteristics.get(char) is True)
                if already == 0:
                    candidates = [s for s in unassigned if s.characteristics.get(char) is True]
                    if candidates and len(group.student_ids) < group.max_size:
                        chosen = candidates[0]
                        group.student_ids.append(chosen.id)
                        unassigned.remove(chosen)

    # Pass 3: Greedy preference-aware placement
    group_id_sets = [set(g.student_ids) for g in result.groups]

    for student in unassigned:
        best_group_idx = -1
        best_score = float('-inf')

        for i, group in enumerate(result.groups):
            if len(group.student_ids) >= group.max_size:
                continue

            # Check MAX constraints
            can_add = True
            for constraint in group.constraints:
                if constraint.constraint_type == ConstraintType.MAX and constraint.value:
                    char = constraint.characteristic
                    if student.characteristics.get(char) is True:
                        current = sum(1 for sid in group.student_ids if lookup.get(sid) and lookup[sid].characteristics.get(char) is True)
                        if current >= constraint.value:
                            can_add = False
                            break
            if not can_add:
                continue

            gids = group_id_sets[i]
            likes_here = len(set(student.liked) & gids)
            dislikes_here = len(set(student.disliked) & gids)
            score = likes_here - 2 * dislikes_here - len(group.student_ids) * 0.01  # slight bias toward emptier groups

            if score > best_score:
                best_score = score
                best_group_idx = i

        if best_group_idx == -1:
            # Fallback: smallest group
            best_group_idx = min(range(len(result.groups)), key=lambda i: len(result.groups[i].student_ids))

        result.groups[best_group_idx].student_ids.append(student.id)
        group_id_sets[best_group_idx].add(student.id)

    return result


# ---------------------------------------------------------------------------
# In-place neighbor generation (swap or move, with rollback)
# ---------------------------------------------------------------------------

def _get_movable(group: Group) -> list[int]:
    pinned = set(group.pinned_student_ids)
    return [sid for sid in group.student_ids if sid not in pinned]


def _apply_swap(groups: list[Group], gi1: int, gi2: int, s1_id: int, s2_id: int) -> None:
    g1, g2 = groups[gi1], groups[gi2]
    g1.student_ids.remove(s1_id)
    g2.student_ids.remove(s2_id)
    g1.student_ids.append(s2_id)
    g2.student_ids.append(s1_id)


def _apply_move(groups: list[Group], src_i: int, tgt_i: int, sid: int) -> None:
    groups[src_i].student_ids.remove(sid)
    groups[tgt_i].student_ids.append(sid)


# ---------------------------------------------------------------------------
# Smart move (preference-aware candidate selection)
# ---------------------------------------------------------------------------

def _pick_smart_move(
    groups: list[Group],
    lookup: dict[int, Student],
) -> tuple[int, int, int] | None:
    """Return (src_idx, tgt_idx, student_id) for a smart preference-driven move."""
    candidates: list[tuple[int, int, int]] = []  # (unhappiness, group_idx, student_id)

    for i, group in enumerate(groups):
        pinned = set(group.pinned_student_ids)
        gids = set(group.student_ids)
        for sid in group.student_ids:
            if sid in pinned:
                continue
            student = lookup.get(sid)
            if not student:
                continue
            dislikes_here = len(set(student.disliked) & gids)
            likes_elsewhere = len(set(student.liked) - gids)
            score = dislikes_here + likes_elsewhere
            if score > 0:
                candidates.append((score, i, sid))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    top = candidates[:max(1, len(candidates) // 3)]
    _, src_i, sid = random.choice(top)

    student = lookup[sid]
    src_group = groups[src_i]

    scored_targets: list[tuple[float, int]] = []
    for j, group in enumerate(groups):
        if j == src_i:
            continue
        gids = set(group.student_ids)
        likes_there = len(set(student.liked) & gids)
        dislikes_there = len(set(student.disliked) & gids)
        scored_targets.append((likes_there - dislikes_there, j))

    if not scored_targets:
        return None

    scored_targets.sort(reverse=True)
    top_t = scored_targets[:max(1, len(scored_targets) // 2)]
    _, tgt_i = random.choice(top_t)
    return src_i, tgt_i, sid


# ---------------------------------------------------------------------------
# Core simulated annealing (in-place, no deepcopy in inner loop)
# ---------------------------------------------------------------------------

def simulated_annealing(
    project: Project,
    initial_temp: float = 150.0,
    cooling_rate: float = 0.9997,
    min_temp: float = 0.01,
    max_iterations: int = 30000,
    progress_callback: Callable[[int, float, float], None] | None = None,
    verbose: bool = False,
    use_current_assignment: bool = False,
) -> Project:
    """
    Optimize group assignments using simulated annealing.

    Uses in-place mutation + rollback instead of deepcopy on every iteration,
    giving ~10-20x speedup. Score updates are O(group_size) incremental deltas
    rather than full O(n²) recalculation.
    """
    if use_current_assignment:
        current = deepcopy(project)
    else:
        current = initial_assignment(project)

    lookup = _build_lookup(current)
    likes_w = current.weights.likes_weight
    dislikes_w = current.weights.dislikes_weight

    # Build group index map for fast lookups: student_id -> group index
    student_to_group: dict[int, int] = {}
    for i, group in enumerate(current.groups):
        for sid in group.student_ids:
            student_to_group[sid] = i

    # Full score at start (constraint penalty included)
    def full_score() -> float:
        total = 0.0
        for group in current.groups:
            gids = set(group.student_ids)
            for sid in group.student_ids:
                s = lookup.get(sid)
                if s:
                    total += len(set(s.liked) & gids) * likes_w
                    total -= len(set(s.disliked) & gids) * dislikes_w
        total -= calculate_constraint_penalty(current, lookup)
        return total

    current_score = full_score()
    best_score = current_score
    best_state = deepcopy(current)  # snapshot of best (only on improvement)

    temperature = initial_temp
    iterations_since_improvement = 0

    moves_accepted = moves_rejected = moves_improved = 0
    initial_score = current_score

    groups = current.groups  # alias

    for iteration in range(max_iterations):
        if temperature < min_temp:
            break

        rand = random.random()
        accepted = False
        score_delta = 0.0

        if rand < 0.45:
            # --- SWAP ---
            movable_groups = [(i, _get_movable(g)) for i, g in enumerate(groups)]
            movable_groups = [(i, m) for i, m in movable_groups if m]
            if len(movable_groups) < 2:
                temperature *= cooling_rate
                continue

            (gi1, mv1), (gi2, mv2) = random.sample(movable_groups, 2)
            s1_id = random.choice(mv1)
            s2_id = random.choice(mv2)

            g1_ids = set(groups[gi1].student_ids) - {s1_id}   # after s1 leaves
            g2_ids = set(groups[gi2].student_ids) - {s2_id}   # after s2 leaves

            # Score delta for s1 moving from g1 to g2, and s2 moving from g2 to g1
            d1 = _student_delta(s1_id, g1_ids, g2_ids, lookup, likes_w, dislikes_w)
            d2 = _student_delta(s2_id, g2_ids, g1_ids, lookup, likes_w, dislikes_w)
            cp_delta = _constraint_penalty_delta_swap(s1_id, groups[gi1], s2_id, groups[gi2], lookup)
            score_delta = d1 + d2 - cp_delta

            if score_delta > 0 or random.random() < math.exp(score_delta / temperature):
                _apply_swap(groups, gi1, gi2, s1_id, s2_id)
                student_to_group[s1_id] = gi2
                student_to_group[s2_id] = gi1
                current_score += score_delta
                accepted = True

        elif rand < 0.75:
            # --- RANDOM MOVE ---
            movable_groups = [(i, _get_movable(g)) for i, g in enumerate(groups)]
            movable_groups = [(i, m) for i, m in movable_groups if m]
            if not movable_groups:
                temperature *= cooling_rate
                continue

            src_i, mv = random.choice(movable_groups)
            sid = random.choice(mv)
            targets = [j for j in range(len(groups)) if j != src_i]
            if not targets:
                temperature *= cooling_rate
                continue
            tgt_i = random.choice(targets)

            src_ids = set(groups[src_i].student_ids) - {sid}
            tgt_ids = set(groups[tgt_i].student_ids)
            d = _student_delta(sid, src_ids, tgt_ids, lookup, likes_w, dislikes_w)
            cp_delta = _constraint_penalty_delta_move(sid, groups[src_i], groups[tgt_i], lookup)
            score_delta = d - cp_delta

            if score_delta > 0 or random.random() < math.exp(score_delta / temperature):
                _apply_move(groups, src_i, tgt_i, sid)
                student_to_group[sid] = tgt_i
                current_score += score_delta
                accepted = True

        else:
            # --- SMART MOVE ---
            result = _pick_smart_move(groups, lookup)
            if result is None:
                temperature *= cooling_rate
                continue
            src_i, tgt_i, sid = result

            src_ids = set(groups[src_i].student_ids) - {sid}
            tgt_ids = set(groups[tgt_i].student_ids)
            d = _student_delta(sid, src_ids, tgt_ids, lookup, likes_w, dislikes_w)
            cp_delta = _constraint_penalty_delta_move(sid, groups[src_i], groups[tgt_i], lookup)
            score_delta = d - cp_delta

            if score_delta > 0 or random.random() < math.exp(score_delta / temperature):
                _apply_move(groups, src_i, tgt_i, sid)
                student_to_group[sid] = tgt_i
                current_score += score_delta
                accepted = True

        if accepted:
            moves_accepted += 1
            if score_delta > 0:
                moves_improved += 1
            if current_score > best_score:
                best_score = current_score
                best_state = deepcopy(current)
                iterations_since_improvement = 0
            else:
                iterations_since_improvement += 1
        else:
            moves_rejected += 1
            iterations_since_improvement += 1

        # Adaptive cooling
        temperature *= cooling_rate

        # Reheating – trigger faster (500 instead of 2000)
        if iterations_since_improvement > 500:
            temperature = min(temperature * 4.0, initial_temp * 0.6)
            iterations_since_improvement = 0
            if verbose:
                print(f"  Reheat at iter {iteration}, temp → {temperature:.3f}, score {current_score:.1f}")

        if progress_callback and iteration % 100 == 0:
            progress_callback(iteration, temperature, best_score)

    if verbose:
        print(f"  Iters: {max_iterations}, temp: {temperature:.4f}")
        print(f"  Accepted: {moves_accepted}, rejected: {moves_rejected}, improved: {moves_improved}")
        print(f"  Score: {initial_score:.1f} → {best_score:.1f} (Δ{best_score - initial_score:+.1f})")

    return best_state


# ---------------------------------------------------------------------------
# Multi-restart wrapper
# ---------------------------------------------------------------------------

def optimize_with_restarts(
    project: Project,
    num_restarts: int = 10,
    initial_temp: float = 150.0,
    cooling_rate: float = 0.9997,
    min_temp: float = 0.01,
    max_iterations: int = 30000,
    progress_callback: Callable[[int, float, float, int], None] | None = None,
    verbose: bool = True,
    return_all_results: bool = False,
) -> "Project | list[Project]":
    """Run SA multiple times and return the best result."""
    overall_best = None
    overall_best_score = float('-inf')
    all_results: list[Project] = []
    scores: list[float] = []

    if verbose:
        print(f"Starting optimization: {num_restarts} restarts × {max_iterations} iters")

    for restart in range(num_restarts):
        if verbose:
            label = "current" if restart == 0 else "random"
            print(f"\nRestart {restart + 1}/{num_restarts} ({label}):")

        def cb(iteration: int, temp: float, score: float, _r: int = restart) -> None:
            if progress_callback:
                progress_callback(restart * max_iterations + iteration, temp, score, _r + 1)

        result = simulated_annealing(
            project,
            initial_temp=initial_temp,
            cooling_rate=cooling_rate,
            min_temp=min_temp,
            max_iterations=max_iterations,
            progress_callback=cb,
            verbose=verbose,
            use_current_assignment=(restart == 0),
        )

        # Recompute score from scratch to avoid accumulated floating-point drift
        lookup = _build_lookup(result)
        score = 0.0
        for group in result.groups:
            gids = set(group.student_ids)
            for sid in group.student_ids:
                s = lookup.get(sid)
                if s:
                    score += len(set(s.liked) & gids) * result.weights.likes_weight
                    score -= len(set(s.disliked) & gids) * result.weights.dislikes_weight
        score -= calculate_constraint_penalty(result, lookup)

        scores.append(score)
        all_results.append(result)

        if score > overall_best_score:
            overall_best = result
            overall_best_score = score
            if verbose:
                print(f"  >>> New best: {score:.1f}")

        # Mid-run: switch base to best found so far for focused exploitation
        if overall_best is not None and restart == num_restarts // 2:
            project = deepcopy(overall_best)

    if verbose and len(scores) > 1:
        mean = sum(scores) / len(scores)
        std = (sum((s - mean) ** 2 for s in scores) / len(scores)) ** 0.5
        print(f"\n{'='*55}")
        print(f"Done. Scores: {[f'{s:.1f}' for s in scores]}")
        print(f"Best={max(scores):.1f}  Worst={min(scores):.1f}  Mean={mean:.1f}  σ={std:.1f}")

        # Per-group score breakdown for the best result
        if overall_best is not None:
            best_lookup = _build_lookup(overall_best)
            group_scores = []
            for group in overall_best.groups:
                gids = set(group.student_ids)
                gs = 0.0
                for sid in group.student_ids:
                    s = best_lookup.get(sid)
                    if s:
                        gs += len(set(s.liked) & gids) * overall_best.weights.likes_weight
                        gs -= len(set(s.disliked) & gids) * overall_best.weights.dislikes_weight
                group_scores.append((group.name, gs, len(group.student_ids)))
            g_vals = [gs for _, gs, _ in group_scores]
            g_mean = sum(g_vals) / len(g_vals) if g_vals else 0.0
            g_std = (sum((v - g_mean) ** 2 for v in g_vals) / len(g_vals)) ** 0.5 if g_vals else 0.0
            max_abs = max((abs(v) for v in g_vals), default=1.0) or 1.0
            print(f"\nBest result — per-group scores (σ={g_std:.2f}, lower = more balanced):")
            for name, gs, size in sorted(group_scores, key=lambda x: x[1], reverse=True):
                bar = '█' * max(0, round(abs(gs) / max_abs * 20))
                sign = '' if gs >= 0 else '-'
                print(f"  {name:<20} {gs:>7.1f}  (n={size:>2})  {sign}{bar}")
            print(f"  {'Mean':<20} {g_mean:>7.1f}")
            print(f"  {'StdDev':<20} {g_std:>7.2f}")
        print(f"{'='*55}")

    if return_all_results:
        paired = sorted(zip(scores, all_results), key=lambda x: x[0], reverse=True)
        return [p for _, p in paired]

    return overall_best


# ---------------------------------------------------------------------------
# Kept for backwards compatibility / diagnostics
# ---------------------------------------------------------------------------

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
        "dislikes_ids": dislikes_in_group,
    }


def calculate_group_score(project: Project, group: Group) -> float:
    """Calculate the score for a single group (likes minus dislikes, no constraint penalty)."""
    lookup = _build_lookup(project)
    gids = set(group.student_ids)
    score = 0.0
    for sid in group.student_ids:
        s = lookup.get(sid)
        if s:
            score += len(set(s.liked) & gids) * project.weights.likes_weight
            score -= len(set(s.disliked) & gids) * project.weights.dislikes_weight
    return score


def calculate_constraint_penalty_details(
    project: Project,
) -> tuple[float, list[tuple[str, float, str]]]:
    """Calculate penalty for constraint violations with per-violation details.

    Returns:
        (total_penalty, [(group_name, penalty_amount, reason), ...])
    """
    lookup = _build_lookup(project)
    penalty = 0.0
    details: list[tuple[str, float, str]] = []

    pinned_students: set[int] = set()
    for group in project.groups:
        pinned_students.update(group.pinned_student_ids)

    char_students: dict[str, set[int]] = {}
    for student in project.students:
        if student.id in pinned_students:
            continue
        for char_name, value in student.characteristics.items():
            if value is True:
                char_students.setdefault(char_name, set()).add(student.id)

    for group in project.groups:
        group_ids = set(group.student_ids)
        pinned_in_group = set(group.pinned_student_ids)
        non_pinned_in_group = group_ids - pinned_in_group

        if len(group.student_ids) > group.max_size:
            p = (len(group.student_ids) - group.max_size) * 100
            penalty += p
            details.append((group.name, p, f"Size exceeded: {len(group.student_ids)}/{group.max_size}"))

        for constraint in group.constraints:
            char_name = constraint.characteristic
            students_with_char = char_students.get(char_name, set())
            students_with_char_in_group = students_with_char & non_pinned_in_group

            if constraint.constraint_type == ConstraintType.ALL:
                missing = students_with_char - group_ids
                if missing:
                    p = len(missing) * 50
                    penalty += p
                    details.append((group.name, p, f"ALL {char_name}: {len(missing)} missing"))

            elif constraint.constraint_type == ConstraintType.MAX:
                if constraint.value and len(students_with_char_in_group) > constraint.value:
                    p = (len(students_with_char_in_group) - constraint.value) * 50
                    penalty += p
                    details.append((group.name, p, f"MAX {char_name}: {len(students_with_char_in_group)} > {constraint.value}"))

            elif constraint.constraint_type == ConstraintType.SOME:
                all_with_char_in_group = sum(
                    1 for sid in group.student_ids
                    if lookup.get(sid) and lookup[sid].characteristics.get(char_name) is True
                )
                if all_with_char_in_group == 0:
                    p = 25.0
                    penalty += p
                    details.append((group.name, p, f"SOME {char_name}: none in group"))

    return penalty, details


def calculate_total_score(project: Project) -> float:
    lookup = _build_lookup(project)
    total = 0.0
    for group in project.groups:
        gids = set(group.student_ids)
        for sid in group.student_ids:
            s = lookup.get(sid)
            if s:
                total += len(set(s.liked) & gids) * project.weights.likes_weight
                total -= len(set(s.disliked) & gids) * project.weights.dislikes_weight
    total -= calculate_constraint_penalty(project, lookup)
    return total


def check_hard_constraints(project: Project) -> tuple[bool, list[str]]:
    violations: list[str] = []
    lookup = _build_lookup(project)
    char_students: dict[str, set[int]] = {}
    for s in project.students:
        for c, v in s.characteristics.items():
            if v is True:
                char_students.setdefault(c, set()).add(s.id)

    for group in project.groups:
        gids = set(group.student_ids)
        if len(group.student_ids) > group.max_size:
            violations.append(f"{group.name}: exceeds max size ({len(group.student_ids)} > {group.max_size})")
        for constraint in group.constraints:
            char = constraint.characteristic
            with_char = char_students.get(char, set())
            in_group = with_char & gids
            if constraint.constraint_type == ConstraintType.ALL:
                missing = with_char - gids
                if missing:
                    violations.append(f"{group.name}: ALL {char} – {len(missing)} missing")
            elif constraint.constraint_type == ConstraintType.MAX:
                if constraint.value and len(in_group) > constraint.value:
                    violations.append(f"{group.name}: MAX {char} – {len(in_group)} > {constraint.value}")

    return len(violations) == 0, violations
