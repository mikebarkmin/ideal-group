# Ideal Group

A student grouping optimization tool that uses heuristic algorithms to form balanced groups based on preferences and characteristics.

> This project was mostly coded with Claude Opus 4.5.

## Overview

There is no such thing as an ideal group, but this project tries to get as close as possible. It uses simulated annealing to form groups of students by maximizing overall satisfaction while ensuring diversity and balance.

## Features

### Data Import
- Import student data from Excel (.xlsx) files
- Map columns to required fields (ID, name, liked, disliked)
- Define characteristics from additional columns (numerical or boolean)

### Group Configuration
- Create groups with configurable maximum sizes
- Set constraints per group:
  - ALL: All students with a characteristic must be in this group
  - SOME: At least some students with a characteristic should be in this group
  - MAX: Limit the maximum count of students with a characteristic

### Optimization
- Configure weights for likes, dislikes, and characteristics
- Run multi-restart simulated annealing optimization
- View scores and constraint violations in real-time

### Kanban Board
- Visual drag-and-drop interface for manual adjustments
- Student cards showing characteristics and relationship counts
- Group columns with size indicators and scores
- Pin students to groups to lock their assignment

### Relationship Graph
- Separate window with force-directed graph visualization
- Nodes represent students, colored by group assignment
- Green arrows for likes, red arrows for dislikes
- Click a node to highlight connections and view student details
- Automatic layout recalculation on window resize

### Export
- Export final assignments to Excel

## Input Format

The Excel file should contain:

| Column | Description |
|--------|-------------|
| ID | Unique identifier for each student |
| Name | Student name (or separate firstname/lastname columns) |
| Liked | Comma-separated list of IDs this student likes |
| Disliked | Comma-separated list of IDs this student dislikes |
| Other columns | Characteristics (e.g., gender, skill level, inclusion status) |

## Algorithm

The optimization uses simulated annealing to find good group assignments.

### Process

1. Start with an initial assignment respecting hard constraints
2. Iterate thousands of times, making small random changes
3. Accept improvements, but occasionally accept worse changes to escape local optima
4. Gradually reduce temperature to converge on a solution

### Moves

Each iteration randomly selects one of:
- SWAP: Exchange two students between different groups
- MOVE: Transfer one student to a different group

### Scoring

```
Score = sum(likes_in_group * likes_weight)
      - sum(dislikes_in_group * dislikes_weight)
      - constraint_penalties
```

### Constraint Penalties

| Violation | Penalty |
|-----------|---------|
| Group size exceeded | 100 points per extra student |
| ALL constraint violated | 50 points per missing student |
| MAX constraint violated | 50 points per extra student |
| SOME constraint violated | 25 points if zero students |

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Initial temperature | 100 | Higher values increase early exploration |
| Cooling rate | 0.997 | Lower values mean slower, more thorough cooling |
| Minimum temperature | 0.1 | Algorithm stops when reached |
| Max iterations | 15,000 | Hard limit per restart |
| Number of restarts | 5 | Best result across all restarts is kept |

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd ideal-group

# Install dependencies
uv sync

# Run the application
uv run python main.py
```

## Building

```bash
./build.sh
```

The executable will be created in the `dist/` directory.

## Releasing

The project uses GitHub Actions to automatically build and release binaries for Windows and Linux.

To create a new release:

```bash
git tag v1.0.0
git push --tags
```

This will trigger the workflow to:
1. Build the application on Windows (.exe) and Linux
2. Create a GitHub release with both binaries attached
3. Generate release notes automatically

## License

MIT
