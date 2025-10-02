#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
    def __init__(self, x, y, is_blue=False):
        self.x = x
        self.y = y
        self.is_blue = is_blue
        self.revealed = False
        self.info_type = '+'  # '.', '+', 'c', 'n'
        self.number = 0
        
    def to_string(self):
        """Convert to 2-character level format"""
        if self.is_blue:
            cell_char = 'X' if self.revealed else 'x'
        else:
            cell_char = 'O' if self.revealed else 'o'
        return cell_char + self.info_type


class ColumnHint:
    """Represents a column/line hint"""
    def __init__(self, x, y, direction, number, consecutive=None):
        self.x = x
        self.y = y
        self.direction = direction  # '\\', '|', '/'
        self.number = number
        self.consecutive = consecutive  # None, 'c', or 'n'
        
    def to_string(self):
        """Convert to 2-character level format"""
        info = '.'
        if self.consecutive == 'c':
            info = 'c'
        elif self.consecutive == 'n':
            info = 'n'
        elif self.number is not None:
            info = '+'
        return self.direction + info


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
        print("remaning", self.remaining)
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
        
    def get_line_cells(self, x, y, direction) -> List[Tuple[int, int]]:
        """Get all cells in a line from a given position and direction"""
        cells = []
        
        if direction == '|':  # vertical
            for ny in range(33):
                if self.grid[ny][x]:
                    cells.append((x, ny))
        elif direction == '\\':  # diagonal \
            # Move along the diagonal
            dx, dy = x, y
            while dx >= 0 and dy >= 0:
                dx -= 1
                dy -= 1
            dx += 1
            dy += 1
            while dx < 33 and dy < 33:
                if self.grid[dy][dx]:
                    cells.append((dx, dy))
                dx += 1
                dy += 1
        elif direction == '/':  # diagonal /
            dx, dy = x, y
            while dx >= 0 and dy < 33:
                dx -= 1
                dy += 1
            dx += 1
            dy -= 1
            while dx < 33 and dy >= 0:
                if self.grid[dy][dx]:
                    cells.append((dx, dy))
                dx += 1
                dy -= 1
                
        return cells
    
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

class LevelGenerator:
    """Main generator class"""

    def generate(self, max_attempts=1) -> Optional[GeneratedLevel]:
        """Generate a complete level with minimized clues"""
        for attempt in range(max_attempts):
            print(f"Generation attempt {attempt + 1}/{max_attempts}...")
            level = self.create_pattern()

            if self.is_solvable(level):
                print("Pattern is solvable, minimizing clues...")
                self.minimize_clues(level)
                print(f"Generated level with {self.count_clues(level)} clues")
                return level
            print("Pattern not solvable, retrying...")

        print(f"Failed to generate solvable level after {max_attempts} attempts, returning anyway")
        return level
    
    def create_pattern(self) -> GeneratedLevel:
        """Create a properly aligned hex pattern of blue/black cells"""
        level = GeneratedLevel()

        width, height = 8, 8  # smaller starter board
        center_x, center_y = 33 // 2, 33 // 2
        radius = min(width, height) // 2

        for ty in range(width):
            for tx in range(height):
                x=tx+(33 - width*3)//2
                y=ty+(33 - height*3)//2
                # Offset every other row (hex staggering)
                grid_x = x * 2 + (y % 2)
                grid_y = y

                # axial-style hex distance
                dx = x - center_x
                dy = y - center_y
                dz = -dx - dy
                dist = max(abs(dx), abs(dy), abs(dz))

                if dist <= radius*10:
                    is_blue = random.random() < 0.4#density of blue cells
                    level.grid[grid_y][grid_x] = HexCell(grid_x, grid_y, is_blue)

        # Reveal a few random non-blue cells
        all_cells = [cell for row in level.grid for cell in row if cell is not None and not cell.is_blue]
        num_to_reveal = max(1, len(all_cells) // 7)  # reveal set density of non-blue cells
        for cell in random.sample(all_cells, num_to_reveal):
            cell.revealed = True

        self.add_column_hints(level)

        return level
    
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
                for dx, dy, direction in directions:
                    hx, hy = x + dx, y + dy
                    if 0 <= hx < width and 0 <= hy < height:
                        if level.grid[hy][hx] is None:
                            # Count blue cells in this line (including this one)
                            line_cells = level.get_line_cells(x, y, direction)
                            blue_cells = [c for c in line_cells if level.grid[c[1]][c[0]] and isinstance(level.grid[c[1]][c[0]], HexCell) and level.grid[c[1]][c[0]].is_blue]
                            consecutive = self.check_consecutive(line_cells, blue_cells, level)
                            hint = ColumnHint(hx, hy, direction, len(blue_cells), consecutive)
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
    
    def minimize_clues(self, level: GeneratedLevel):
        """Remove redundant clues while maintaining solvability"""
        clues = []
        # Collect column hints and flower hints
        for i in enumerate(level.column_hints):
            clues.append(('column', i[0]))
        for y in range(33):
            for x in range(33):
                cell = level.grid[y][x]
                if isinstance(cell, HexCell) and cell.info_type == '+':
                    clues.append(('flower', x, y))

        # Shuffle for random removal order
        random.shuffle(clues)
        
        # Try removing each clue
        removed_count = 0
        cluelen = len(clues)
        cluecount = 0
        for clue in clues:
            print("=======================")
            print("clue no: ", cluecount, "/", cluelen)
            cluecount += 1
            print("trying to remove clue: ", clue)
            # Temporarily remove
            backup = self.remove_clue(level, clue)

            # Check if still solvable
            if self.is_solvable(level):
                removed_count += 1
                print("+++ removal successful")
            else:
                # Restore clue
                self.restore_clue(level, clue, backup)
                print("--- removal failed, clue restored")
            print("=======================")
        print(f"Removed {removed_count} redundant clues")
    
    def remove_clue(self, level: GeneratedLevel, clue) -> any:
        """Temporarily remove a clue and return backup. For column hints, also remove from grid."""
        if clue[0] == 'flower':
            _, x, y = clue
            cell = level.grid[y][x]
            backup = (cell.info_type, cell.number)
            cell.info_type = '.'
            cell.number = 0
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
        if clue[0] == 'flower':
            _, x, y = clue
            cell = level.grid[y][x]
            cell.info_type, cell.number = backup
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
                if isinstance(cell, HexCell) and cell.info_type == '+':
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
    generator = LevelGenerator()
    for i in range(1):
        print(f"\n=== Generating level {i+1}/{1} ===")
        level = generator.generate()
        levelname = "generated"
        if level:
            filename = f"{levelname}_{i+1}.hexcells"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(level.to_level_string())
            print(f"Saved to {filename}")
        else:
            print(f"Failed to generate level {i+1}")


if __name__ == '__main__':
    main()