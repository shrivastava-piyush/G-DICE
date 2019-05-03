from gym_pomdps import POMDP


from enum import Enum

import numpy as np
from gym import Env
from gym.spaces import Discrete
from gym.utils import seeding

from functools import partial

from gym_pomdp.envs.coord import Grid, Coord
from gym_pomdp.envs.gui import ShipGui

# Battleship
# 1 agent
# Discount: 1
# Obs: 0 (miss), 1 (hit)
# Actions: 100 (10x10 firing)
#   Not preferred: Remove taken actions
#   Preferred: Remove useless actions as well (diagonal from hits)
# State of each cell: 0 (empty), 1 (empty, visited), 2 (empty, diagonal), 3 (occupied), 4 (occupied, visited),

class BattleshipPOMDP(POMDP):
    def __init__(self, boardSize=10, seed=None):
        self.seed(seed)
        self.boardSize = boardSize
        self.observation_space = Discrete(2)  # Miss or hit
        self.action_space = Discrete(boardSize ** 2)  # Fire on any square
        self.actionMap = partial(np.unravel_index, dims=(boardSize, boardSize))  # Function to get flat indices from tuple
        self.actionUnMap = partial(np.ravel_multi_index, dims=(boardSize, boardSize))  # Function to get tuple indices from flat

    # Seed the RNG
    def seed(self, seed):
        self.np_random, seed_ = seeding.np_random(seed)
        return [seed_]

    def reset(self):
        self.grid = np.zeros(self.boardSize ** 2, dtype=np.uint8)  # Grid (as flat)
        self.legalMoves = np.ones(self.boardSize ** 2, dtype=bool)  # Which squares have been fired on? Mark those as false
        self.preferredMoves = np.ones(self.boardSize ** 2, dtype=bool)  # Additionally prune squares diagonal to hit
        self._initShips()

    # Place a valid configuration of ships on the board
    def _initShips(self):
        shipLengths = [5, 4, 3, 3, 2]  # Carrier, battleship, cruiser, sub, destroyer
        positions = self.actionMap(np.arange(self.boardSize ** 2))  # Flat indices 0-100
        directions = np.arange(4)  # Directions
        permutations = np.array(np.meshgrid(positions, directions)).reshape(2, -1).swapaxes(0, 1)
        for ship in shipLengths:
            shuffleInd = self.np_random.permutation(directions.size * positions.size)  # Shuffle permutations
            perm = permutations[shuffleInd, :]
            for pos, dir in perm:
                if not self._collide(pos, dir, ship):
                    self._placeShip(pos, dir, ship)
                    break

    # Does placing this new ship collide with previous ships? Or with the grid?
    # shipPos is flat index
    # shipDir is 0 (N), 1 (E), 2 (W), 3 (S)
    def _collide(self, shipPos, shipDir, shipLength):
        posAsTuple = self.actionUnMap(shipPos)
        allPosAsTuple = [posAsTuple]


        return False

    def _placeShip(self, shipPos, shipDir, shipLength):
        allPos = 0



# TODO fix state
class Compass(Enum):
    North = Coord(0, 1)
    East = Coord(1, 0)
    South = Coord(0, -1)
    West = Coord(-1, 0)
    Null = Coord(0, 0)
    NorthEast = Coord(1, 1)
    SouthEast = Coord(1, -1)
    SouthWest = Coord(-1, -1)
    NorthWest = Coord(-1, 1)

    @staticmethod
    def get_coord(idx):
        return list(Compass)[idx].value


class Obs(Enum):
    NULL = 0
    HIT = 1


class Ship(object):
    def __init__(self, coord, length):
        self.pos = coord
        self.direction = np.random.randint(4)
        self.length = length


class ShipState(object):
    def __init__(self):
        self.ships = []
        self.total_remaining = 0


class Cell(object):
    def __init__(self):
        self.occupied = False
        self.visited = False
        self.diagonal = False


class BattleGrid(Grid):
    def __init__(self, board_size):
        super().__init__(*board_size)

    def build_board(self, value=0):
        self.board = []
        for idx in range(self.n_tiles):
            self.board.append(Cell())
        self.board = np.asarray(self.board).reshape((self.x_size, self.y_size))


class BattleShipEnv(Env):
    metadata = {"render.modes": ["human", "ansi"]}

    def __init__(self, board_size=(5, 5), max_len=3):
        self.grid = BattleGrid(board_size)
        self.action_space = Discrete(self.grid.n_tiles)
        self.observation_space = Discrete(len(Obs))
        self.num_obs = 2
        self._reward_range = self.action_space.n / 4.
        self._discount = 1.
        self.total_remaining = max_len - 1
        self.max_len = max_len + 1

    def seed(self, seed=None):
        np.random.seed(seed)

    def _compute_prob(self, action, next_state, ob):

        action_pos = self.grid.get_coord(action)
        cell = self.grid[action_pos]
        if ob == Obs.NULL.value and cell.visited:
            return 1
        elif ob == Obs.HIT.value and cell.occupied:
            return 1
        else:
            return int(ob == Obs.NULL.value)

    def step(self, action):

        assert self.done is False
        assert self.action_space.contains(action)
        assert self.total_remaining > 0
        self.last_action = action
        self.t += 1
        action_pos = self.grid.get_coord(action)
        # cell = self.grid.get_value(action_pos)
        cell = self.grid[action_pos]
        reward = 0
        if cell.visited:
            reward -= 10
            obs = Obs.NULL.value
        else:
            if cell.occupied:
                reward -= 1
                obs = 1
                self.state.total_remaining -= 1

                for d in range(4, 8):
                    if self.grid[action_pos + Compass.get_coord(d)]:
                        self.grid[action_pos + Compass.get_coord(d)].diagonal = False
            else:
                reward -= 1
                obs = Obs.NULL.value
            cell.visited = True
        if self.state.total_remaining == 0:
            reward += self.grid.n_tiles
            self.done = True
        self.tot_rw += reward
        return obs, reward, self.done, {"state": self.state}

    def _set_state(self, state):
        self.reset()
        self.state = state

    def close(self):
        return

    def reset(self):
        self.done = False
        self.tot_rw = 0
        self.t = 0
        self.last_action = -1
        self.state = self._get_init_state()
        return Obs.NULL.value

    def render(self, mode='human', close=False):
        if close:
            return
        if mode == 'human':
            if not hasattr(self, "gui"):
                obj_pos = []
                for ship in self.state.ships:
                    pos = ship.pos
                    obj_pos.append(self.grid.get_index(pos))
                    for i in range(ship.length):
                        pos += Compass.get_coord(ship.direction)
                        obj_pos.append(self.grid.get_index(pos))
                self.gui = ShipGui(board_size=self.grid.get_size, obj_pos=obj_pos)
            if self.t > 0:
                msg = "A: " + str(self.grid.get_coord(self.last_action)) + "T: " + str(self.t) + "Rw :" + str(
                    self.tot_rw)
                self.gui.render(state=self.last_action, msg=msg)

    def _generate_legal(self):
        # assert self.state.total_remaining > 0
        actions = []
        for action in range(self.action_space.n):
            action_pos = self.grid.get_coord(action)
            if not self.grid[action_pos].visited:
                actions.append(action)
        # assert len(actions) > 0
        return actions

    def _get_init_state(self):
        bsstate = ShipState()
        self.grid.build_board()

        for length in reversed(range(2, self.max_len)):
            # num_ships = 1
            # for idx in range(num_ships):
            while True:  # add one ship of each kind
                ship = Ship(coord=self.grid.sample(), length=length)
                if not self.collision(ship, self.grid, bsstate):
                    break
            self.mark_ship(ship, self.grid, bsstate)
            bsstate.ships.append(ship)
        return bsstate

    @staticmethod
    def mark_ship(ship, grid, state):

        pos = ship.pos  # .copy()

        for i in range(ship.length):
            cell = grid[pos]
            assert not cell.occupied
            cell.occupied = True
            if not cell.visited:
                state.total_remaining += 1
            pos += Compass.get_coord(ship.direction)

    @staticmethod
    def collision(ship, grid, state):

        pos = ship.pos  # .copy()
        for i in range(ship.length):
            if not grid.is_inside(pos + Compass.get_coord(ship.direction)):
                return True
            # cell = grid.get_value(pos)
            cell = grid[pos]
            if cell.occupied:
                return True
            for adj in range(8):
                coord = pos + Compass.get_coord(adj)
                if grid.is_inside(coord) and grid[coord].occupied:
                    return True
            pos += Compass.get_coord(ship.direction)
        return False