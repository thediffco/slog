import random
from mesa import Agent, Model
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector
import math


class Passenger(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.app_on = False

    def step(self):
        # Passenger moves randomly
        possible_steps = self.model.grid.get_neighborhood(self.pos, moore=True, include_center=False)
        new_position = self.random.choice(possible_steps)
        self.model.grid.move_agent(self, new_position)

class Driver(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.app_on = False

    def step(self):
        # Driver moves randomly
        possible_steps = self.model.grid.get_neighborhood(self.pos, moore=True, include_center=False)
        new_position = self.random.choice(possible_steps)
        self.model.grid.move_agent(self, new_position)

class RideshareModel(Model):
    def __init__(self, N_passengers, N_drivers, width, height):
        self.num_passengers = N_passengers
        self.num_drivers = N_drivers
        self.grid = MultiGrid(width, height, False)
        self.schedule = RandomActivation(self)
        self.running = True

        # Create passengers
        for i in range(self.num_passengers):
            x = self.random.randrange(self.grid.width)
            y = self.random.randrange(self.grid.height)
            passenger = Passenger(i, self)
            self.schedule.add(passenger)
            self.grid.place_agent(passenger, (x, y))

        # Create drivers
        for i in range(self.num_passengers, self.num_passengers + self.num_drivers):
            x = self.random.randrange(self.grid.width)
            y = self.random.randrange(self.grid.height)
            driver = Driver(i, self)
            self.schedule.add(driver)
            self.grid.place_agent(driver, (x, y))

    def step(self):
        self.schedule.step()

model = RideshareModel(10, 10, 100, 100)
for i in range(100):
    model.step()

def distance(agent1, agent2):
    x1, y1 = agent1.pos
    x2, y2 = agent2.pos
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
