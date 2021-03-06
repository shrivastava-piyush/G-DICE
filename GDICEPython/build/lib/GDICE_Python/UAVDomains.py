import gym
from gym import spaces
from gym.utils import seeding
import numpy as np
from enum import IntEnum

#   ######
#   #A   #
#   # #  #
#   #   T#
#   ######

# A - the agent (UAV)
# T - the target to be detected

# actions: n s e w
# observations: wall_left wall_right target_left target_right neither

# The default reward/penalty is -0.1
# If the target detected then the reward is 1

# Starting state: the UAV is located in the upper-left corner
# Episode termination:
#    The UAV detected the target
#    Episode length is greater than 50

class Action(IntEnum):
    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3

TRANSLATION_TABLE = [
    # [left, intended_direction, right]
    [Action.WEST, Action.NORTH, Action.EAST],
    [Action.NORTH, Action.EAST, Action.SOUTH],
    [Action.EAST, Action.SOUTH, Action.WEST],
    [Action.SOUTH, Action.WEST, Action.NORTH]
]

DIRECTIONS_TABLE = {  # First axis is the rows, second axis is the columns
    Action.NORTH: (-1, 0),
    Action.EAST: (0, 1),
    Action.SOUTH: (1, 0),
    Action.WEST: (0, -1)
}

class Observation(IntEnum):
    WALL_LEFT = 0
    WALL_RIGHT = 1
    WALL_TOP = 2
    WALL_BOTTOM = 3
    TARGET_LEFT = 4
    TARGET_RIGHT = 5
    TARGET_TOP = 6
    TARGET_BOTTOM = 7
    NEITHER = 8

# class Observation(IntEnum):
#     WALL_LEFT = 0
#     WALL_RIGHT = 1
#     TARGET_LEFT = 2
#     TARGET_RIGHT = 3
#     NEITHER = 4

class Cell(IntEnum):
    FREE = 0
    OBSTACLE = 1

class EnvSpec(object):
    pass


class UAVWithLocationSensorStaticTargetDomain(gym.Env):
    def __init__(self, n_rows=10, n_columns=10, obstacle_ratio=0.2, action_noise=0.2, obs_noise=0.2,
                 seed=None):
        self.episodic = True
        self.seed(seed)

        self.agents = 1
        self.discount = 0.99
        self.n_rows = n_rows
        self.n_columns = n_columns
        self.grid_size = self.n_rows * self.n_columns
        self.obstacle_ratio = obstacle_ratio
        self.action_noise = action_noise
        self.obs_noise = obs_noise
        uav_location = (0, 0)
        target_location = (self.n_rows - 1, self.n_columns - 1)

        self.state = (uav_location, target_location)
        self.create_env(uav_location, target_location)
        self.print_env(uav_location, target_location)

        self.action_space = spaces.Discrete(len(Action.__members__))
        self.observation_space = spaces.Discrete(self.grid_size)
        self.spec = EnvSpec()
        self.spec.id = "uav-single-static-target-v0"
        self.reset()

    def seed(self, seed=None):
        self.np_random, seed_ = seeding.np_random(seed)
        return [seed_]

    def create_env(self, uav_location, target_location):
        self.grid = np.zeros((self.n_rows, self.n_columns), dtype=np.uint8)

        # Generate an array of tuples of all possible cells
        cells = [(i, j) for i in range(self.n_rows - 1) for j in range(self.n_columns)]
        cells.remove(uav_location)
        n_obstacles = int(self.obstacle_ratio * self.grid_size)
        idx = self.np_random.choice(len(cells), n_obstacles)
        cells = np.array(cells)
        obstacle_locations = cells[idx]
        for location in obstacle_locations:
            self.grid[location[0], location[1]] = Cell.OBSTACLE

        # TODO: Check that there is a path from the UAV's initial location to the target

    def print_env(self, uav_location, target_location):
        for i in range(self.n_rows):
            for j in range(self.n_columns):
                if (i, j) == uav_location:
                    print('A', end='')
                elif (i, j) == target_location:
                    print('T', end='')
                elif self.grid[i][j] == Cell.OBSTACLE:
                    print('X', end='')
                else:
                    print('.', end='')
            print()
        print()

    def reset(self, printEnv=False):
        uav_location = (0, 0)
        target_location = (self.n_rows - 1, self.n_columns - 1)
        self.state = (uav_location, target_location)
        if printEnv:
            self.print_env(uav_location, target_location)

    def step(self, action, **kwargs):
        # The state argument allows us to simulate many states in parallel
        assert self.action_space.contains(action), "%r (%s) invalid" % (action, type(action))

        # In GDICE we simulate many states in parallel
        if 'state' in kwargs:
            state = kwargs['state']
        else:
            state = self.state

        # Extract the state components
        uav_location, target_location = state

        # Make a noisy movement and update the UAV location
        action = self.noisy_transition(action)
        direction = DIRECTIONS_TABLE[action]
        new_location = (uav_location[0] + direction[0], uav_location[1] + direction[1])

        # If the new location is out of boundary or hits an obstacle, then stay in place
        if new_location[0] >= 0 and new_location[0] < self.n_rows and \
            new_location[1] >= 0 and new_location[1] < self.n_columns and \
            self.grid[new_location[0], new_location[1]] == Cell.FREE:
            uav_location = new_location

        # Update the state
        new_state = (uav_location, target_location)
        if 'state' not in kwargs:
            self.state = new_state

        # Check if the UAV reached the target
        if uav_location == target_location:
            reward = 100
            done = True
        else:
            reward = -1
            done = False

        # Generate a new observation according to the UAV's location
        obs = self.generate_observation(uav_location)

        if 'printEnv' in kwargs:
            self.print_env(uav_location, target_location)

        return obs, reward, done, { 'new_state': new_state }

    def noisy_transition(self, action):
        p = self.np_random.rand()
        if p < self.action_noise / 2:
            action = TRANSLATION_TABLE[action][0]
        elif p < self.action_noise:
            action = TRANSLATION_TABLE[action][2]
        return action
        # Works two times slower
        # return TRANSLATION_TABLE[action][self.np_random.choice(3, p=[self.noise / 2, 1 - self.noise, self.noise / 2])]

    def generate_observation(self, uav_location):
        p = self.np_random.rand()

        curr_row, curr_col = uav_location
        if p < self.obs_noise:
            delta_i = self.np_random.choice((-1, 1))
            if curr_row + delta_i >= 0 and curr_row + delta_i < self.n_rows:
                curr_row += delta_i
            delta_j = self.np_random.choice((-1, 1))
            if curr_col + delta_j >= 0 and curr_col + delta_j < self.n_columns:
                curr_col += delta_j

        obs = curr_row * self.n_rows + curr_col
        return obs

# The actions, NSEW, have the expected result 80% of the time, and a transition in a direction perpendicular
# to the intended on with a 10% probability for each direction
class UAVWithProximitySensorStaticTargetDomain(gym.Env):
    def __init__(self, n_rows=10, n_columns=10, obstacle_ratio=0.2, noise=0.2,
                 seed=None):
        self.episodic = True
        self.seed(seed)

        self.agents = 1
        self.discount = 0.99
        self.n_rows = n_rows
        self.n_columns = n_columns
        self.grid_size = self.n_rows * self.n_columns
        self.obstacle_ratio = obstacle_ratio
        self.noise = noise
        uav_location = (0, 0)
        target_location = (self.n_rows - 1, self.n_columns - 1)

        self.state = (uav_location, target_location)
        self.create_env(uav_location, target_location)
        self.print_env(uav_location, target_location)

        self.action_space = spaces.Discrete(len(Action.__members__))
        self.observation_space = spaces.Discrete(len(Observation.__members__))
        self.spec = EnvSpec()
        self.spec.id = "uav-single-static-target-v0"
        self.reset()

    def seed(self, seed=None):
        self.np_random, seed_ = seeding.np_random(seed)
        return [seed_]

    def create_env(self, uav_location, target_location):
        self.grid = np.zeros((self.n_rows, self.n_columns), dtype=np.uint8)

        # Generate an array of tuples of all possible cells
        cells = [(i, j) for i in range(self.n_rows - 1) for j in range(self.n_columns)]
        cells.remove(uav_location)
        n_obstacles = int(self.obstacle_ratio * self.grid_size)
        idx = self.np_random.choice(len(cells), n_obstacles)
        cells = np.array(cells)
        obstacle_locations = cells[idx]
        for location in obstacle_locations:
            self.grid[location[0], location[1]] = Cell.OBSTACLE

        # TODO: Check that there is a path from the UAV's initial location to the target

    def print_env(self, uav_location, target_location):
        for i in range(self.n_rows):
            for j in range(self.n_columns):
                if (i, j) == uav_location:
                    print('A', end='')
                elif (i, j) == target_location:
                    print('T', end='')
                elif self.grid[i][j] == Cell.OBSTACLE:
                    print('X', end='')
                else:
                    print('.', end='')
            print()
        print()

    def reset(self, printEnv=False):
        uav_location = (0, 0)
        target_location = (self.n_rows - 1, self.n_columns - 1)
        self.state = (uav_location, target_location)
        if printEnv:
            self.print_env(uav_location, target_location)

    def step(self, action, **kwargs):
        # The state argument allows us to simulate many states in parallel
        assert self.action_space.contains(action), "%r (%s) invalid" % (action, type(action))

        # In GDICE we simulate many states in parallel
        if 'state' in kwargs:
            state = kwargs['state']
        else:
            state = self.state

        # Extract the state components
        uav_location, target_location = state

        # Make a noisy movement and update the UAV location
        action = self.noisy_transition(action)
        direction = DIRECTIONS_TABLE[action]
        new_location = (uav_location[0] + direction[0], uav_location[1] + direction[1])

        # If the new location is out of boundary or hits an obstacle, then stay in place
        if new_location[0] >= 0 and new_location[0] < self.n_rows and \
            new_location[1] >= 0 and new_location[1] < self.n_columns and \
            self.grid[new_location[0], new_location[1]] == Cell.FREE:
            uav_location = new_location

        # Update the state
        new_state = (uav_location, target_location)
        if 'state' not in kwargs:
            self.state = new_state

        # Check if the UAV reached the target
        if uav_location == target_location:
            reward = 100
            done = True
        else:
            reward = -1
            done = False

        # Generate a new observation according to the UAV's location
        if uav_location == (target_location[0], target_location[1] + 1):
            obs = Observation.TARGET_LEFT
        elif uav_location == (target_location[0], target_location[1] - 1):
            obs = Observation.TARGET_RIGHT
        elif uav_location == (target_location[0] + 1, target_location[1]):
            obs = Observation.TARGET_TOP
        elif uav_location == (target_location[0] - 1, target_location[1]):
            obs = Observation.TARGET_BOTTOM
        elif uav_location[1] == 0 or self.grid[uav_location[0], uav_location[1] - 1] == Cell.OBSTACLE:
            obs = Observation.WALL_LEFT
        elif uav_location[1] == self.n_columns - 1 or \
            self.grid[uav_location[0], uav_location[1] + 1] == Cell.OBSTACLE:
            obs = Observation.WALL_RIGHT
        elif uav_location[0] == 0 or self.grid[uav_location[0] - 1, uav_location[1]] == Cell.OBSTACLE:
            obs = Observation.WALL_TOP
        elif uav_location[0] == self.n_rows - 1 or \
            self.grid[uav_location[0] + 1, uav_location[1]] == Cell.OBSTACLE:
            obs = Observation.WALL_BOTTOM
        else:
            obs = Observation.NEITHER

        if 'printEnv' in kwargs:
            self.print_env(uav_location, target_location)

        return obs, reward, done, { 'new_state': new_state }

    def noisy_transition(self, action):
        p = self.np_random.rand()
        if p < self.noise / 2:
            action = TRANSLATION_TABLE[action][0]
        elif p < self.noise:
            action = TRANSLATION_TABLE[action][2]
        return action
        # Works two times slower
        # return TRANSLATION_TABLE[action][self.np_random.choice(3, p=[self.noise / 2, 1 - self.noise, self.noise / 2])]

class UAVSimpleDomain(gym.Env):
    def __init__(self, seed=None):
        self.episodic = True
        self.seed(seed)

        self.agents = 1
        self.discount = 0.99
        self.grid = np.array([[0, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 0]])
        self.n_rows = self.grid.shape[0]
        self.n_columns = self.grid.shape[1]

        self.action_space = spaces.Discrete(4)  # 4 actions
        self.observation_space = spaces.Discrete(5)  # 5 observations

        self.spec = EnvSpec()
        self.spec.id = "uav-simple-v0"
        self.reset()

    def seed(self, seed=None):
        self.np_random, seed_ = seeding.np_random(seed)
        return [seed_]

    def reset(self):
        uav_location = (0, 0)
        target_location = (2, 3)
        self.state = (uav_location, target_location)

    def step(self, action, state=None):
        # The state argument allows us to simulate many states in parallel
        assert self.action_space.contains(action), "%r (%s) invalid" % (action, type(action))

        # In GDICE we simulate many states in parallel
        if state is None:
            state = self.state

        # Extract the state components
        uav_location, target_location = state

        # Update the UAV location
        if action == Action.NORTH:
            new_location = (uav_location[0] - 1, uav_location[1])
        elif action == Action.SOUTH:
            new_location = (uav_location[0] + 1, uav_location[1])
        elif action == Action.EAST:
            new_location = (uav_location[0], uav_location[1] + 1)
        elif action == Action.WEST:
            new_location = (uav_location[0], uav_location[1] - 1)

        # If the new location is out of boundary, then stay in place
        if new_location[0] >= 0 and new_location[0] < self.n_rows and \
            new_location[1] >= 0 and new_location[1] < self.n_columns:
            uav_location = new_location

        # Update the state
        new_state = (uav_location, target_location)
        if state is None:
            self.state = new_state

        # Check if the UAV reached the target
        if uav_location == target_location:
            reward = 1.0
            done = True
        else:
            reward = -0.1
            done = False

        # Generate a new observation according to the UAV's location
        if uav_location[1] == 0 or (uav_location[1] > 0 and
            self.grid[uav_location[0], uav_location[1] - 1] == 1):
            obs = Observation.WALL_LEFT
        elif uav_location[1] == self.n_columns - 1 or (uav_location[1] < self.n_columns - 1 and
            self.grid[uav_location[0], uav_location[1] + 1] == 1):
            obs = Observation.WALL_RIGHT
        elif uav_location[0] == target_location[0] and \
            uav_location[1] == target_location[1] + 1:
            obs = Observation.TARGET_LEFT
        elif uav_location[0] == target_location[0] and \
            uav_location[1] == target_location[1] - 1:
            obs = Observation.TARGET_RIGHT
        else:
            obs = Observation.NEITHER

        return obs, reward, done, { 'new_state': new_state }
