#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2025 Alex PB <chozabu@gmail.com>
#
# This file is part of SixCells.
"""
Hexcells Level Generator for SixCells
Generates procedural Hexcells levels with automatic clue minimization
"""

import random
from typing import List, Tuple, Optional

import common
from common import *
from solver import *


class HexCell:
    """Represents a single hexagonal cell"""
    def __init__(self, x, y, is_blue=False, info_type='+'):
        self.x = x
        self.y = y
        self.is_blue = is_blue
        self.revealed = False
        self.info_type = info_type  # '.', '+', 'c', 'n'
        
    def to_string(self):
        """Convert to 2-character level format"""
        if self.is_blue:
            cell_char = 'X' if self.revealed else 'x'
        else:
            cell_char = 'O' if self.revealed else 'o'
        return cell_char + self.info_type


class ColumnHint:
    """Represents a column/line hint"""
    def __init__(self, x, y, direction, consecutive=None):
        self.x = x
        self.y = y
        self.direction = direction  # '\\', '|', '/'
        self.consecutive = consecutive  # None, 'c', or 'n'
        
    def to_string(self):
        """Convert to 2-character level format"""
        info = '+'
        if self.consecutive == 'c':
            info = 'c'
        elif self.consecutive == 'n':
            info = 'n'
        return self.direction + info


# Direction deltas: (dx, dy) for moving in a column hint's direction
direction_deltas = {
    '\\': (1, 1),  # diagonal down-right
    '|': (0, 2),  # straight down
    '/': (-1, 1)  # diagonal down-left
}

#============================== from player.py

class Cell(common.Cell):
    def __init__(self):
        common.Cell.__init__(self)

        self.flower = False
        self.hidden = False
        self.guess = None
        self._display = Cell.unknown

    def upd(self, first=False):
        common.Cell.upd(self, first)
        if self.guess:
            self.setBrush(Color.blue_border if self.guess == Cell.full else Color.black_border)

    @setter_property
    def display(self, value):
        rem = 0
        try:
            if self.display is not Cell.full and value is Cell.full:
                rem = -1
            if self.display is Cell.full and value is not Cell.full:
                rem = 1
        except AttributeError:
            pass
        yield value
        if rem and self.placed:
            self.scene().remaining += rem
        self.guess = None
        self.flower = False
        self.extra_text = ''

    def reset_cache(self):
        pass


class Column(common.Column):
    def reset_cache(self):
        pass





class Scene(common.Scene):

    def __init__(self):
        common.Scene.__init__(self)

        self.swap_buttons = False

        self.remaining = 0
        self.mistakes = 0

        self.solving = 0

        self.undo_history = []
        
    def prepare(self):
        remaining = 0
        for i, cell in enumerate(self.all(Cell)):
            cell.id = i
            if cell.kind is Cell.full and not cell.revealed:
                remaining += 1
            cell._display = cell.kind if cell.revealed else Cell.unknown
        for i, col in enumerate(self.all(Column)):
            col.id = i
        self.remaining = remaining
        self.mistakes = 0

        self.full_upd()


    @cached_property
    def all_cells(self):
        return list(self.all(Cell))

    @cached_property
    def all_columns(self):
        return list(self.all(Column))

    def reset_cache(self):
        for attr in ['all_cells', 'all_columns']:
            try:
                delattr(self, attr)
            except AttributeError:
                pass

    def solve_step(self):
        """Derive everything that can be concluded from the current state.
        Return whether progress has been made."""
        if self.solving:
            print("already solving")
            return

        self.confirm_guesses()
        self.solving += 1
        app.processEvents()
        progress = False
        undo_step = []
        for cell, value in solve(self):
            assert cell.kind is value
            cell.guess = value
            cell.upd()
            progress = True
            undo_step.append(cell)
        self.undo_history.append(undo_step)
        self.solving -= 1

        return progress

    def solve_complete(self):
        """Continue solving until stuck.
        Return whether the entire level could be uncovered."""
        self.solving = 1
        while self.solving:
            self.confirm_guesses()

            progress = True
            while progress:
                progress = False
                for cell, value in solve_simple(self):
                    progress = True
                    assert cell.kind is value
                    cell.display = cell.kind
                    cell.upd()
            self.solving -= 1
            if not self.solve_step():
                break
            self.solving += 1

        self.solving = 0
        # If it identified all blue cells, it'll have the rest uncovered as well
        return self.remaining == 0

    def clear_guesses(self):
        for cell in self.all(Cell):
            if cell.guess:
                cell.guess = None
                cell.upd()

    def confirm_guesses(self, opposite=False):
        correct = []
        for cell in self.all(Cell):
            if cell.guess and cell.display is Cell.unknown:
                if (cell.kind == cell.guess) ^ opposite:
                    cell.display = cell.kind
                    cell.upd()
                    correct.append(cell)
                else:
                    self.mistakes += 1
        self.undo_history.append(correct)



#============================


class GeneratedLevel:
    """Internal representation of a generated level"""
    def __init__(self):
        self.grid = [[None for _ in range(33)] for _ in range(33)]
        self.column_hints = []
        self.title = "Generated Level"
        self.author = "Generator"

    def get_neighbors(self, x, y) -> List[Tuple[int, int]]:
        """Get hexagonal neighbors of a cell using the game's coordinate system"""
        # These are the 6 immediate neighbors in the game's hex layout
        # From common.py: _neighbors_deltas = [(0, -2), (1, -1), (1, 1), (0, 2), (-1, 1), (-1, -1)]
        offsets = [(0, -2), (1, -1), (1, 1), (0, 2), (-1, 1), (-1, -1)]

        neighbors = []
        for dx, dy in offsets:
            nx, ny = x + dx, y + dy
            if 0 <= nx < 33 and 0 <= ny < 33:
                neighbors.append((nx, ny))
        return neighbors

    def are_neighbors(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> bool:
        """Check if two positions are neighbors"""
        return pos2 in self.get_neighbors(pos1[0], pos1[1])

    def all_grouped(self, positions: set) -> bool:
        """Check if all positions form one connected group"""
        if not positions:
            return True

        # Start with one position
        grouped = {next(iter(positions))}
        anything_to_add = True

        while anything_to_add:
            anything_to_add = False
            for pos in positions - grouped:
                if any(self.are_neighbors(pos, grouped_pos) for grouped_pos in grouped):
                    anything_to_add = True
                    grouped.add(pos)

        return len(grouped) == len(positions)

    def get_line_cells(self, x, y, direction) -> List[Tuple[int, int]]:
        """Get all cells in a line from a given position and direction

        Returns positions of all non-None cells (both HexCells and ColumnHints).
        This is needed for check_consecutive to properly calculate indices.
        """
        cells = []

        delta = direction_deltas.get(direction)
        if not delta:
            print("Invalid direction:", direction)
            return cells

        dx, dy = delta

        cx, cy = x, y

        # Move forward collecting all non-None cells
        while 0 <= cx < 33 and 0 <= cy < 33:
            if self.grid[cy][cx]:
                cells.append((cx, cy))
            cx += dx
            cy += dy

        return cells

    def get_hex_cells_in_line(self, x, y, direction) -> List[Tuple[int, int]]:
        """Get only HexCell positions in a line (filters out ColumnHints)"""
        line_cells = self.get_line_cells(x, y, direction)
        return [(cx, cy) for cx, cy in line_cells
                if isinstance(self.grid[cy][cx], HexCell)]
    
    def to_level_string(self) -> str:
        """Convert to Hexcells level format"""
        lines = [
            "Hexcells level v1",
            self.title,
            self.author,
            "",
            ""
        ]
        # Build 33x33 grid
        for y in range(33):
            row = ""
            for x in range(33):
                cell = self.grid[y][x]
                if cell:
                    row += cell.to_string()
                else:
                    row += ".."
            lines.append(row)
        return "\n".join(lines)

    def set_black_cell_info_types(self):
        """Set info_type (c/n) for black cells based on their blue neighbors"""
        for y in range(33):
            for x in range(33):
                cell = self.grid[y][x]
                if not isinstance(cell, HexCell) or cell.is_blue or cell.info_type == '.':
                    continue

                # Get all blue neighbors
                blue_neighbors = set()
                for nx, ny in self.get_neighbors(x, y):
                    neighbor = self.grid[ny][nx]
                    if isinstance(neighbor, HexCell) and neighbor.is_blue:
                        blue_neighbors.add((nx, ny))

                # If there are multiple blue neighbors, check if they're consecutive
                if len(blue_neighbors) > 1:
                    if self.all_grouped(blue_neighbors):
                        cell.info_type = 'c'
                    else:
                        cell.info_type = 'n'

class LevelGenerator:
    """Main generator class"""

    def __init__(self,
                 width=10,
                 height=10,
                 constrain_by_radius=True,
                 blue_density=0.4,
                 cell_spawn_chance=0.95,
                 column_hint_chance=0.6,
                 min_columns_removed=0,
                 max_columns_removed=2,
                 reveal_density=7,
                 blue_info_weight_plus=0.3,
                 blue_info_weight_none=0.7,
                 clue_removal_ratio=0.95):
        """Initialize the level generator with configuration parameters

        Args:
            width: Width of the pattern (max 30)
            height: Height of the pattern (max ~31)
            constrain_by_radius: Whether to constrain cells to a circular radius
            blue_density: Probability of a cell being blue (0.0-1.0)
            cell_spawn_chance: Probability of a cell spawning in valid positions (0.0-1.0)
            column_hint_chance: Probability of adding a column hint per cell (0.0-1.0)
            min_columns_removed: Minimum number of column hints to remove
            max_columns_removed: Maximum number of column hints to remove
            reveal_density: Divisor for revealed cell density (1/reveal_density cells revealed)
            blue_info_weight_plus: Weight for '+' info type on blue cells
            blue_info_weight_none: Weight for '.' info type on blue cells
            clue_removal_ratio: Ratio of clues to attempt removing (0.0-1.0, lower=easier, higher=harder)
        """
        self.width = width
        self.height = height
        self.constrain_by_radius = constrain_by_radius
        self.blue_density = blue_density
        self.cell_spawn_chance = cell_spawn_chance
        self.column_hint_chance = column_hint_chance
        self.min_columns_removed = min_columns_removed
        self.max_columns_removed = max_columns_removed
        self.reveal_density = reveal_density
        self.blue_info_weight_plus = blue_info_weight_plus
        self.blue_info_weight_none = blue_info_weight_none
        self.clue_removal_ratio = clue_removal_ratio

    def generate(self, max_attempts=20) -> Optional[GeneratedLevel]:
        """Generate a complete level with minimized clues"""
        for attempt in range(max_attempts):
            print(f"Generation attempt {attempt + 1}/{max_attempts}...")
            level = self.create_pattern()

            if self.is_solvable(level):
                print("Pattern is solvable, minimizing clues...")
                self.minimize_clues(level)
                print(f"Generated level with {self.count_clues(level)} clues")
                self._set_level_metadata(level)
                return level
            print("Pattern not solvable, retrying...")

        print(f"Failed to generate solvable level after {max_attempts} attempts, returning None")
        return None

    def _set_level_metadata(self, level: GeneratedLevel):
        """Set the level title and author based on generation parameters"""
        # Default values for comparison
        defaults = {
            'width': 10, 'height': 10, 'constrain_by_radius': True,
            'blue_density': 0.4, 'cell_spawn_chance': 0.95,
            'column_hint_chance': 0.6, 'min_columns_removed': 0,
            'max_columns_removed': 2, 'reveal_density': 7,
            'blue_info_weight_plus': 0.3, 'blue_info_weight_none': 0.7,
            'clue_removal_ratio': 0.75
        }

        # Build title from non-default size parameters
        title_parts = []
        if self.width != defaults['width'] or self.height != defaults['height']:
            title_parts.append(f"{self.width}x{self.height}")
        if not self.constrain_by_radius:
            title_parts.append("Rect")

        # Build author from non-default gameplay parameters
        author_parts = []
        if self.blue_density != defaults['blue_density']:
            author_parts.append(f"blue:{self.blue_density:.2f}")
        if self.cell_spawn_chance != defaults['cell_spawn_chance']:
            author_parts.append(f"spawn:{self.cell_spawn_chance:.2f}")
        if self.column_hint_chance != defaults['column_hint_chance']:
            author_parts.append(f"hints:{self.column_hint_chance:.2f}")
        if (self.min_columns_removed != defaults['min_columns_removed'] or
            self.max_columns_removed != defaults['max_columns_removed']):
            author_parts.append(f"rm:{self.min_columns_removed}-{self.max_columns_removed}")
        if self.reveal_density != defaults['reveal_density']:
            author_parts.append(f"reveal:1/{self.reveal_density}")
        if (self.blue_info_weight_plus != defaults['blue_info_weight_plus'] or
            self.blue_info_weight_none != defaults['blue_info_weight_none']):
            author_parts.append(f"info:{self.blue_info_weight_plus:.1f}/{self.blue_info_weight_none:.1f}")
        if self.clue_removal_ratio != defaults['clue_removal_ratio']:
            author_parts.append(f"clue_rm:{self.clue_removal_ratio:.2f}")

        # Set title and author
        level.title = " ".join(title_parts) if title_parts else "Generated Level"
        level.author = " ".join(author_parts) if author_parts else "Generator"
    
    def create_pattern(self) -> GeneratedLevel:
        """Create a properly aligned hex pattern of blue/black cells"""
        level = GeneratedLevel()
        grid_width, grid_height = 33, 33

        width, height = self.width, self.height
        center_x, center_y = grid_width // 2, grid_height // 2
        radius = min(width, height) // 2

        for tx in range(0, width, 2):
            for ty in range(height):
                x = tx + (-width // 2) + grid_width // 2
                y = ty + (-height // 2) + grid_height // 2
                # Offset every other row (hex staggering)
                grid_x = x + (y % 2)
                grid_y = y

                dx = grid_x - center_x
                dy = grid_y - center_y
                dist = math.sqrt(dx * dx + dy * dy)

                # Apply radius constraint if enabled
                radius_check = (dist <= radius * 1.0) if self.constrain_by_radius else True

                if radius_check and random.random() < self.cell_spawn_chance:
                    is_blue = random.random() < self.blue_density
                    info_type = '+'
                    if is_blue:
                        info_type = random.choices(['+', '.'],
                                                  weights=[self.blue_info_weight_plus,
                                                          self.blue_info_weight_none])[0]
                    level.grid[grid_y][grid_x] = HexCell(grid_x, grid_y, is_blue, info_type=info_type)




        # Reveal a few random non-blue cells
        all_cells = [cell for row in level.grid for cell in row if cell is not None and not cell.is_blue]
        num_to_reveal = max(1, len(all_cells) // self.reveal_density)
        for cell in random.sample(all_cells, num_to_reveal):
            cell.revealed = True



        self.add_column_hints(level)
        self.remove_random_column_hint(level)

        self.recheck_hints(level)

        # Set info types for black cells (c/n based on blue neighbor grouping)
        level.set_black_cell_info_types()

        return level

    def recheck_hints(self, level: 'GeneratedLevel'):
        """Recheck and fix column hints after cells have been removed"""
        hints_to_remove = []

        for hint in level.column_hints:
            # Get all cells in this line
            hex_cells = level.get_hex_cells_in_line(hint.x, hint.y, hint.direction)

            # Check if the column still has any members
            has_members = len(hex_cells) > 0

            if not has_members:
                # Remove hint from grid and mark for removal from list
                level.grid[hint.y][hint.x] = None
                hints_to_remove.append(hint)
                continue

            # Try to move hint into empty space in its direction
            dx, dy = direction_deltas[hint.direction]

            # Try moving the hint up to 3 times
            hint_removed = False
            for _ in range(3):
                new_x, new_y = hint.x + dx, hint.y + dy
                if not (0 <= new_x < 33 and 0 <= new_y < 33):
                    break

                if level.grid[new_y][new_x] is None:
                    # Move the hint
                    level.grid[hint.y][hint.x] = None
                    hint.x = new_x
                    hint.y = new_y
                    level.grid[new_y][new_x] = hint
                elif isinstance(level.grid[new_y][new_x], ColumnHint):
                    # Collision with another hint, remove this one
                    level.grid[hint.y][hint.x] = None
                    hints_to_remove.append(hint)
                    hint_removed = True
                    break
                else:
                    # Cell is occupied by something else, stop trying to move
                    break

            if hint_removed:
                continue

            # Recalculate blue cells and consecutive info
            blue_cells = [(cx, cy) for cx, cy in hex_cells
                         if level.grid[cy][cx].is_blue]

            # Recalculate consecutive/non-consecutive
            if len(blue_cells) <= 1:
                # Single cell or no cells - no togetherness info needed
                hint.consecutive = None
            else:
                # Check if blue cells are consecutive
                hint.consecutive = self.check_consecutive(hex_cells, blue_cells, level)

        # Remove hints that fail checks above
        for hint in hints_to_remove:
            level.column_hints.remove(hint)


    def add_column_hints(self, level: 'GeneratedLevel'):
        """Add column/line hints above each HexCell if there is space (up+left, up two spaces, up+right)."""
        height = len(level.grid)
        width = len(level.grid[0]) if height > 0 else 0
        # Directions: (dx, dy, direction symbol)
        directions = [
            (-1, -1, '\\'),  # up+left
            (0, -2, '|'),      # up two
            (1, -1, '/'),      # up+right
        ]
        for y in range(height):
            for x in range(width):
                cell = level.grid[y][x]
                if not (cell and isinstance(cell, HexCell)):
                    continue
                if random.random() < self.column_hint_chance:
                    continue
                for dx, dy, direction in directions:
                    hx, hy = x + dx, y + dy
                    if 0 <= hx < width and 0 <= hy < height:
                        if level.grid[hy][hx] is None:
                            hint = ColumnHint(hx, hy, direction, consecutive=None)
                            level.column_hints.append(hint)
                            level.grid[hy][hx] = hint

    def check_consecutive(self, line_cells, blue_cells, level) -> Optional[str]:
        """Check if blue cells in a line are consecutive"""
        if not blue_cells:
            return None
        blue_indices = []
        for i, (cx, cy) in enumerate(line_cells):
            cell = level.grid[cy][cx]
            if isinstance(cell, HexCell) and cell.is_blue:
                blue_indices.append(i)
        if not blue_indices:
            return None
        # Check if consecutive
        is_consecutive = all(blue_indices[i] + 1 == blue_indices[i + 1]
                            for i in range(len(blue_indices) - 1))
        if len(blue_indices) > 1:
            return 'c' if is_consecutive else 'n'
        return None

    def remove_random_column_hint(self, level: 'GeneratedLevel'):
        """Remove random column hints and all their members from the grid"""

        if not level.column_hints:
            return
        removenum = random.randint(self.min_columns_removed, self.max_columns_removed)
        for r in range(removenum):
            if not level.column_hints:
                return
            # Pick a random column hint
            hint = random.choice(level.column_hints)

            # Get all cells in this line
            line_cells = level.get_line_cells(hint.x, hint.y, hint.direction)

            # Remove all cells in the line from the grid
            for cx, cy in line_cells:
                level.grid[cy][cx] = None

            # Remove the hint itself from the grid
            level.grid[hint.y][hint.x] = None

            # Remove the hint from the column_hints list
            level.column_hints.remove(hint)

    def minimize_clues(self, level: GeneratedLevel):
        """Remove redundant clues while maintaining solvability"""
        clues = []
        # Collect column hints and flower hints
        for i in enumerate(level.column_hints):
            clues.append(('column', i[0]))
        for y in range(33):
            for x in range(33):
                cell = level.grid[y][x]
                if isinstance(cell, HexCell) and cell.info_type != '.':
                    clues.append(('flower' if cell.is_blue else 'blackcell', x, y))

        # Shuffle for random removal order
        random.shuffle(clues)
        clues = clues[:int(len(clues) * self.clue_removal_ratio)]  # limit number of clues to try removing
        
        # Try removing each clue
        removed_count = 0
        for clue in clues:
            # Temporarily remove
            backup = self.remove_clue(level, clue)

            # Check if still solvable
            if self.is_solvable(level):
                removed_count += 1
                #print("+++ removal successful: ", clue)
            else:
                # Restore clue
                self.restore_clue(level, clue, backup)
                #print("--- removal failed, clue restored: ", clue)
        print(f"Removed {removed_count} redundant clues")
    
    def remove_clue(self, level: GeneratedLevel, clue) -> any:
        """Temporarily remove a clue and return backup. For column hints, also remove from grid."""
        if clue[0] == 'flower' or clue[0] == 'blackcell':
            _, x, y = clue
            cell = level.grid[y][x]
            backup = cell.info_type
            cell.info_type = '.'
            return backup
        elif clue[0] == 'column':
            _, idx = clue
            if idx < len(level.column_hints):
                backup = level.column_hints[idx]
                if backup is not None:
                    # Remove from grid as well
                    level.grid[backup.y][backup.x] = None
                level.column_hints[idx] = None
                return backup
        return None
    
    def restore_clue(self, level: GeneratedLevel, clue, backup):
        """Restore a previously removed clue. For column hints, also restore to grid."""
        if backup is None:
            return
        if clue[0] == 'flower' or clue[0] == 'blackcell':
            _, x, y = clue
            cell = level.grid[y][x]
            cell.info_type = backup
        elif clue[0] == 'column':
            _, idx = clue
            if idx < len(level.column_hints):
                level.column_hints[idx] = backup
                if backup is not None:
                    # Restore to grid as well
                    level.grid[backup.y][backup.x] = backup

    def count_clues(self, level: GeneratedLevel) -> int:
        """Count total number of clues in level"""
        count = 0
        for y in range(33):
            for x in range(33):
                cell = level.grid[y][x]
                if isinstance(cell, HexCell) and cell.info_type != '.':
                    count += 1
        count += sum(1 for h in level.column_hints if h is not None)
        return count

    def is_solvable(self, level: GeneratedLevel):
        """Check if a level is solvable using the same logic as solve_complete in player.py"""
        try:
            from solver import solve, solve_simple
        except ImportError:
            print("Warning: solver module not available, assuming solvable")
            return True

        # Create a scene from the generated level
        scene = Scene()
        level_string = level.to_level_string()
        common.load(level_string, scene, Cell=Cell, Column=Column)
        scene.prepare()
        result = scene.solve_complete()
        return result

def main():
    """Command-line interface for the generator"""
    import argparse
    import os

    parser = argparse.ArgumentParser(description='Generate Hexcells levels')
    parser.add_argument('--count', type=int, default=1,
                       help='Number of levels to generate (default: 1)')
    parser.add_argument('--width', type=int, default=10,
                       help='Width of the pattern (default: 10, max: 30)')
    parser.add_argument('--height', type=int, default=10,
                       help='Height of the pattern (default: 10, max: ~31)')
    parser.add_argument('--no-radius', action='store_true',
                       help='Disable radius constraint (fills rectangular area)')
    parser.add_argument('--blue-density', type=float, default=0.4,
                       help='Probability of a cell being blue (default: 0.4)')
    parser.add_argument('--cell-spawn-chance', type=float, default=0.95,
                       help='Probability of a cell spawning (default: 0.95)')
    parser.add_argument('--column-hint-chance', type=float, default=0.6,
                       help='Probability of adding column hints (default: 0.6)')
    parser.add_argument('--min-columns-removed', type=int, default=0,
                       help='Minimum column hints to remove (default: 0)')
    parser.add_argument('--max-columns-removed', type=int, default=2,
                       help='Maximum column hints to remove (default: 2)')
    parser.add_argument('--reveal-density', type=int, default=7,
                       help='Reveal 1/N non-blue cells (default: 7)')
    parser.add_argument('--blue-info-plus', type=float, default=0.3,
                       help='Weight for + info type on blue cells (default: 0.3)')
    parser.add_argument('--blue-info-none', type=float, default=0.7,
                       help='Weight for no info type on blue cells (default: 0.7)')
    parser.add_argument('--clue-removal-ratio', type=float, default=0.75,
                       help='Ratio of clues to attempt removing, lower=easier (default: 0.75)')
    parser.add_argument('--name', type=str, default='generated',
                       help='Base name for generated files (default: generated)')
    parser.add_argument('--output-dir', type=str, default='generated_levels',
                       help='Output directory for generated levels (default: generated_levels)')

    args = parser.parse_args()

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Print generation parameters
    print("=" * 60)
    print("LEVEL GENERATION PARAMETERS")
    print("=" * 60)
    print(f"Count:                  {args.count}")
    print(f"Width:                  {args.width}")
    print(f"Height:                 {args.height}")
    print(f"Constrain by radius:    {not args.no_radius}")
    print(f"Blue density:           {args.blue_density}")
    print(f"Cell spawn chance:      {args.cell_spawn_chance}")
    print(f"Column hint chance:     {args.column_hint_chance}")
    print(f"Columns removed:        {args.min_columns_removed}-{args.max_columns_removed}")
    print(f"Reveal density:         1/{args.reveal_density}")
    print(f"Blue info weights:      +:{args.blue_info_plus}, .:{args.blue_info_none}")
    print(f"Clue removal ratio:     {args.clue_removal_ratio} (lower=easier)")
    print(f"Output directory:       {args.output_dir}")
    print(f"Base name:              {args.name}")
    print("=" * 60)

    generator = LevelGenerator(
        width=args.width,
        height=args.height,
        constrain_by_radius=not args.no_radius,
        blue_density=args.blue_density,
        cell_spawn_chance=args.cell_spawn_chance,
        column_hint_chance=args.column_hint_chance,
        min_columns_removed=args.min_columns_removed,
        max_columns_removed=args.max_columns_removed,
        reveal_density=args.reveal_density,
        blue_info_weight_plus=args.blue_info_plus,
        blue_info_weight_none=args.blue_info_none,
        clue_removal_ratio=args.clue_removal_ratio
    )

    for i in range(args.count):
        print(f"\n=== Generating level {i+1}/{args.count} ===")
        level = generator.generate()
        if level:
            filename = os.path.join(args.output_dir, f"{args.name}_{i+1}.hexcells")
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(level.to_level_string())
            print(f"Saved to {filename}", " title  ", level.title, " by ", level.author)
        else:
            print(f"Failed to generate level {i+1}")

    print(f"\n{'=' * 60}")
    print(f"Generation complete! Levels saved to: {args.output_dir}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()