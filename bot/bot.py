import math
import random
from functools import reduce
import itertools
import sys

from move.move import Move
from move.move_type import MoveType
from field.point import Point


class Bot:

    def __init__(self):
        random.seed()  # set seed here if needed

        self.block = [
            ['l', 'l'],
            ['l', 'l'],
        ]

        self.tub = [
            ['.', 'l', '.'],
            ['l', '.', 'l'],
            ['.', 'l', '.'],
        ]

        self.beehive = [
            ['.', 'l', 'l', '.'],
            ['l', '.', '.', 'l'],
            ['.', 'l', 'l', '.'],
        ]


    def make_move(self, game):
        """
        Performs a Birth or a Kill move, currently returns a random move.
        Implement this method to make the bot smarter.
        """
        self.cell_map = game.field.get_cell_mapping()
        self.field = game.field
        self.cells = game.field.cells
        self.my_id = game.me.id
        self.enemy_id = '1' if game.me.id == '0' else '0'
        self.pattern_cells = set()

        self.actions = {
            'expand_tub': {
                'utility': 2,
                'coordinate': None,
                'type': MoveType.BIRTH,
            },
            'expand_beehive': {
                'utility': 3,
                'coordinate': None,
                'type': MoveType.BIRTH,
            },
            'kill_enemy_block': {
                'utility': 3,
                'coordinate': None,
                'type': MoveType.BIRTH,
            },
            'convert_block': {
                'utility': 1.5,
                'coordinate': None,
                'type': MoveType.KILL,
            },
            'kill_enemy_tub': {
                'utility': 2,
                'coordinate': None,
                'type': MoveType.KILL,
            },
            'kill_enemy_beehive': {
                'utility': 3,
                'coordinate': None,
                'type': MoveType.KILL,
            },
            'pass': {
                'utility': 0,
                'coordinate': None,
                'type': MoveType.PASS,
            }
        }

        moveFunctions = {}
        moveFunctions[MoveType.BIRTH] = self.birth_move
        moveFunctions[MoveType.KILL] = self.kill_move
        moveFunctions[MoveType.PASS] = self.pass_move

        self.acceptable_sacrifices = []

        self.analyze_blocks()
        self.analyze_tubs()
        self.analyze_beehives()

        #Decrease utility of birth actions if safe sacrifices are not available
        if len(self.acceptable_sacrifices) < 2:
            birth_penalty = (2 - len(self.acceptable_sacrifices)) / 2
            for action in [action for name, action in self.actions.items() if action['type'] == MoveType.BIRTH]:
                action['utility'] -= birth_penalty

        #Disallow birth actions if doing so would force a stable pattern to be disrupted
        self.acceptable_sacrifices.extend(self.get_non_pattern_cells())
        if len(self.acceptable_sacrifices) < 2:
            for key, value in self.actions.items():
                if value['type'] == MoveType.BIRTH:
                    self.actions.pop(key, None)

        available_actions = [action for name, action in self.actions.items()]

        best_action = max(available_actions, key=lambda action: action['utility'])
        return moveFunctions[best_action['type']](best_action['coordinate'])


    def analyze_blocks(self):
        block_occurrences = self.find_pattern_occurrences(self.block)

        #Find block cells that can be sacrificed
        my_blocks = list(filter(self.my_ownership_filter, block_occurrences))
        random.shuffle(my_blocks)

        for block in my_blocks:
            self.acceptable_sacrifices.append(self.find_cell_in_pattern(self.my_id, block))

        #Don't sacrifice two cells from the same block
        sacrifices_to_remove = set()
        for i in range(0, len(self.acceptable_sacrifices)):
            for j in range(1, len(self.acceptable_sacrifices)):
                if self.is_adjacent(self.acceptable_sacrifices[i], self.acceptable_sacrifices[j]):
                    sacrifices_to_remove.add(self.acceptable_sacrifices[i])

        self.acceptable_sacrifices = list(filter(lambda p: p not in sacrifices_to_remove, self.acceptable_sacrifices))

        enemy_blocks = list(filter(self.enemy_ownership_filter, block_occurrences))
        if len(enemy_blocks) == 0:
            self.actions.pop('kill_enemy_block', None)
        else:
            surrounding_empty_cells = list(itertools.chain(*[self.find_surrounding_cells('.', block) for block in enemy_blocks]))
            if len(surrounding_empty_cells) == 0:
                self.actions.pop('kill_enemy_block', None)
            else:
                self.actions['kill_enemy_block']['coordinate'] = surrounding_empty_cells.pop()

        convertable_blocks = list(filter(self.convertable_block_filter, block_occurrences))
        if len(convertable_blocks) == 0:
            self.actions.pop('convert_block', None)
        else:
            self.actions['convert_block']['coordinate'] = self.find_cell_in_pattern(self.enemy_id, convertable_blocks.pop())

    def is_adjacent(self, a, b):
        return math.sqrt((a.x - b.x)**2 + (a.y - b.y)**2) <= math.sqrt(2)

    def analyze_tubs(self):
        tub_occurences = self.find_pattern_occurrences(self.tub)

        enemy_tubs = list(filter(self.enemy_ownership_filter, tub_occurences))
        if len(enemy_tubs) == 0:
            self.actions.pop('kill_enemy_tub', None)
        else:
            self.actions['kill_enemy_tub']['coordinate'] = self.find_cell_in_pattern(self.enemy_id, enemy_tubs.pop())

        my_tubs = list(filter(self.my_ownership_filter, tub_occurences))
        if len(my_tubs) == 0:
            self.actions.pop('expand_tub', None)
        else:
            self.actions['expand_tub']['coordinate'] = self.find_cell_in_pattern('.', my_tubs.pop())

    def analyze_beehives(self):
        beehive_occurrences = self.find_pattern_occurrences(self.beehive)

        enemy_beehives = list(filter(self.enemy_ownership_filter, beehive_occurrences))
        if len(enemy_beehives) == 0:
            self.actions.pop('kill_enemy_beehive', None)
        else:
            self.actions['kill_enemy_beehive']['coordinate'] = self.find_cell_in_pattern(self.enemy_id, enemy_beehives.pop())

        my_beehives = list(filter(self.my_ownership_filter, beehive_occurrences))
        if len(my_beehives) == 0:
            self.actions.pop('expand_beehive', None)
        else:
            self.actions['expand_beehive']['coordinate'] = self.find_cell_in_pattern(self.enemy_id, my_beehives.pop())

    def find_surrounding_cells(self, cell, pattern_occurrence):
        pos = pattern_occurrence['position']
        pattern = pattern_occurrence['pattern']

        horizontal_borders = [Point(x, y)
                       for x in range(pos.x - 1, pos.x + len(pattern) + 1)
                       for y in [pos.y, pos.y + len(pattern[0])]]

        vertical_borders = [Point(x, y)
                       for y in range(pos.y, pos.y + len(pattern[0]))
                       for x in [pos.x, pos.x + len(pattern)]]

        return list(filter(lambda point: self.within_bounds(point.x, point.y)
                           and self.cells[point.x][point.y] == cell, horizontal_borders + vertical_borders))


    def find_cell_in_pattern(self, cell, pattern_occurrence):
        pos = pattern_occurrence['position']
        pattern = pattern_occurrence['pattern']

        pattern_cells = [Point(pos.x + x, pos.y + y)
                         for x in range(0, len(pattern))
                         for y in range(0, len(pattern[x]))
                         if self.cells[pos.x + x][pos.y + y] == cell]

        if len(pattern_cells) > 0:
            return pattern_cells.pop()

        return None

    def convertable_block_filter(self, pattern):
        if self.my_id == '0':
            return pattern['ownership'] <= -2
        else:
            return pattern['ownership'] >= 2

    def enemy_ownership_filter(self, pattern):
        if self.my_id == '0':
            return pattern['ownership'] > 0
        else:
            return pattern['ownership'] < 0

    def my_ownership_filter(self, pattern):
        if self.my_id == '0':
            return pattern['ownership'] < 0
        else:
            return pattern['ownership'] > 0

    def find_pattern_occurrences(self, pattern):
        occurrences = [o for o in [{
            'position': Point(x, y),
            'ownership': self.check_pattern_at_location(x, y, pattern),
            'pattern': pattern,
        }
        for x in range(self.field.width)
        for y in range(self.field.height)] if o['ownership'] is not None]

        return occurrences

    def check_pattern_at_location(self, x, y, pattern):
        p_width = len(pattern)
        p_height = len(pattern[0])
        matching_points = [(x + i, y + j)
                          for i in range(p_width) for j in range(p_height)
                          if self.within_bounds(x + i, y + j)
                          if (pattern[i][j] == 'l' and self.cells[x + i][y + j] != '.')
                           or pattern[i][j] == self.cells[x + i][y + j]]

        matching_cells = [self.cells[p[0]][p[1]] for p in matching_points]

        if len(matching_cells) != len(pattern) * len(pattern[0]):
            return None

        for p in matching_points:
            self.pattern_cells.add(p)

        cell_ownership_vals = {
            '0': -1,
            '1': 1,
            '.': 0,
        }

        return sum([cell_ownership_vals[cell] for cell in matching_cells])

    def within_bounds(self, x, y):
        return x >= 0 and x < self.field.width and y >= 0 and y < self.field.height

    def get_non_pattern_cells(self):
        return [Point(x, y)
                for x in range(self.field.width)
                for y in range(self.field.height)
                if (x, y) not in self.pattern_cells
                and self.cells[x][y] == self.my_id]

    def kill_move(self, point):
        return Move(MoveType.KILL, point)

    def birth_move(self, point):
        if len(self.acceptable_sacrifices) < 2:
            return Move(MoveType.PASS)
        sys.stderr.write(str(self.acceptable_sacrifices))
        return Move(MoveType.BIRTH, point, self.acceptable_sacrifices[:2])

    def pass_move(self, point):
        return Move(MoveType.PASS)
