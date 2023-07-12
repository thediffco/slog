import random
from mesa import Agent, Model
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector
import math
import matplotlib.pyplot as plt
from mesa.time import RandomActivation


class Passenger(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.app_on = False
        self.had_ride = False        

    def step(self):
        # Passenger moves randomly
        self.had_ride = False
        possible_steps = self.model.grid.get_neighborhood(self.pos, moore=True, include_center=False)
        new_position = self.random.choice(possible_steps)
        self.model.grid.move_agent(self, new_position)

        # If app is on and passenger didn't have a ride yet, passenger looks for driver
        if self.app_on and not self.had_ride:
            self.model.check_for_driver(self)


class Driver(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.app_on = False
        self.had_passenger = False

    def step(self):
        # Driver moves randomly
        self.had_passenger = False
        possible_steps = self.model.grid.get_neighborhood(self.pos, moore=True, include_center=False)
        new_position = self.random.choice(possible_steps)
        self.model.grid.move_agent(self, new_position)

class Company(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.funding = model.co_funding
        self.revenue_history = []
        self.cash_history = []
        self.budget_previous_step = self.funding
        self.revenue = 0
        self.rides_this_round = 0
        self.spending = 0
        self.pnl = 0

    def allocate_budget(self):
        # The company allocates half of its remaining budget, unless there are not enough inactive passengers/drivers.
        # The allocation is done in proportion to the failure rates of drivers and passengers.
        if self.funding < min(self.model.passenger_cac, self.model.driver_cac):
            self.model.running = False
        if self.funding < 0:
            self.model.running = False
        total_budget = self.funding / 2
        
        inactive_passengers = [p for p in self.model.schedule.agents if isinstance(p, Passenger) and not p.app_on]
        inactive_drivers = [d for d in self.model.schedule.agents if isinstance(d, Driver) and not d.app_on]
        
        failure_rate_passenger = len([p for p in self.model.schedule.agents if isinstance(p, Passenger) and not p.had_ride]) / self.model.num_passengers
        failure_rate_driver = len([d for d in self.model.schedule.agents if isinstance(d, Driver) and not d.had_passenger]) / self.model.num_drivers
        
        total_failure_rate = failure_rate_passenger + failure_rate_driver
        if total_failure_rate == 0:
            passenger_budget = 0
            driver_budget = 0
        else:
            passenger_share = failure_rate_passenger / total_failure_rate
            driver_share = 1 - passenger_share
            passenger_budget = min(total_budget * passenger_share,
                                   len(inactive_passengers) * self.model.passenger_cac)
            driver_budget = min(total_budget * driver_share,
                                len(inactive_drivers) * self.model.driver_cac)
        
        num_passengers_to_market = min(len(inactive_passengers), passenger_budget // self.model.passenger_cac)
        num_drivers_to_market = min(len(inactive_drivers), driver_budget // self.model.driver_cac)

        # if company's remaining budget is less than the lower of passenger_cac and driver_cac, end the simulation

        if passenger_budget +  driver_budget < 0:
            print("Negative budget! Abort.")
            self.model.running = False

        if len(self.cash_history) > 20:
            if self.cash_history[-1] > self.cash_history[-20]:
                print("Company achieved sustainable model, exiting now!")
                self.model.running = False
            
        return passenger_budget, driver_budget, num_passengers_to_market, num_drivers_to_market

    def step(self):
        passenger_budget, driver_budget, num_passengers_to_market, num_drivers_to_market = self.allocate_budget()
    
        # Convert these numbers to integers
        num_passengers_to_market = int(num_passengers_to_market)
        num_drivers_to_market = int(num_drivers_to_market)
    
        # Market to the passengers
        inactive_passengers = [p for p in self.model.schedule.agents if isinstance(p, Passenger) and not p.app_on]
        passengers_to_market = self.random.sample(inactive_passengers, num_passengers_to_market)
        for passenger in passengers_to_market:
            passenger.app_on = True
            
        # Market to the drivers
        inactive_drivers = [d for d in self.model.schedule.agents if isinstance(d, Driver) and not d.app_on]
        drivers_to_market = self.random.sample(inactive_drivers, num_drivers_to_market)
        for driver in drivers_to_market:
            driver.app_on = True

        # Update revenue and cash history
        self.revenue = self.model.profit_per_ride * self.rides_this_round
        self.funding += self.revenue
        self.funding -= passenger_budget + driver_budget
        self.revenue_history.append(self.revenue)
        self.cash_history.append(self.funding)
        self.rides_this_round = 0
        self.spending = passenger_budget + driver_budget
        self.pnl = self.revenue - self.spending

        
class RideshareModel(Model):
    def __init__(self, N_passengers,
                 N_drivers,
                 width,
                 height,
                 co_funding,
                 profit_per_ride,
                 passenger_cac,
                 driver_cac):
        self.num_passengers = N_passengers
        self.num_drivers = N_drivers
        self.grid = MultiGrid(width, height, False)
        self.schedule = RandomActivation(self)
        self.co_funding = co_funding
        self.profit_per_ride = profit_per_ride
        self.passenger_cac = passenger_cac
        self.driver_cac = driver_cac
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

        # create company
        self.company = Company(1, self)

    def check_for_driver(self, passenger):
        # Get list of drivers at passenger's location
        nearby_cells = []
        for dx in range(-10, 11):
            for dy in range(-10, 11):
                # Check if the cell is within the grid boundaries
                x, y = passenger.pos[0] + dx, passenger.pos[1] + dy
                if 0 <= x < self.grid.width and 0 <= y < self.grid.height:
                    nearby_cells.append((x, y))
        nearby_agents = [self.grid.get_cell_list_contents([pos]) for pos in nearby_cells]
        nearby_agents = [agent for sublist in nearby_agents for agent in sublist]
        drivers = [agent for agent in nearby_agents if type(agent) is Driver and agent.app_on]

        # If there's a driver here, a ride happens
        if drivers:
            passenger.had_ride = True
            driver = random.choice(drivers)
            driver.had_passenger = True
            driver.app_on = True
            passenger.app_on = True
            self.company.rides_this_round += 1

    def calculate_statistics(self):
        drivers = [agent for agent in self.schedule.agents if isinstance(agent, Driver)]
        passengers = [agent for agent in self.schedule.agents if isinstance(agent, Passenger)]
        company = self.company

        company_spending = company.spending
        company_revenue = len([p for p in passengers if p.had_ride]) * self.profit_per_ride
        company_cash = company.funding - company_spending
        company_pnl = company_revenue - company_spending
        percent_drivers_on = len([d for d in drivers if d.app_on]) / self.num_drivers * 100
        percent_passengers_on = len([p for p in passengers if p.app_on]) / self.num_passengers * 100
        success_rate_drivers = len([d for d in drivers if d.had_passenger]) / self.num_drivers * 100
        success_rate_passengers = len([p for p in passengers if p.had_ride]) / self.num_passengers * 100

        headers = "| {:>4} | {:>5} | {:>5} | {:>5} | {:>5} | {:>7} | {:>7} | {:>7} | {:>7} |".format(
            "Step", "Spend", "Rev", "Cash", "PnL", "D-Pen %", "P-Pen %", "D-Succ %", "P-Succ %")
        row_data = "| {:>4} | {:>5.1f} | {:>5.1f} | {:>5.1f} | {:>5.1f} | {:>7.1f} | {:>7.1f} | {:>7.1f} | {:>7.1f} |".format(
            self.schedule.steps, company_spending, company_revenue, company_cash, company_pnl, 
            percent_drivers_on, percent_passengers_on, success_rate_drivers, success_rate_passengers)

        if self.schedule.steps == 1:
            print(headers)
            print(row_data)
    
        company.budget_previous_step = company.funding

    def calculate_statistics(self):
        drivers = [agent for agent in self.schedule.agents if isinstance(agent, Driver)]
        passengers = [agent for agent in self.schedule.agents if isinstance(agent, Passenger)]
        company = self.company

        company_spending = company.spending
        company_revenue = len([p for p in passengers if p.had_ride]) * self.profit_per_ride
        company_cash = company.funding - company_spending
        company_pnl = company_revenue - company_spending
        percent_drivers_on = len([d for d in drivers if d.app_on]) / self.num_drivers * 100
        percent_passengers_on = len([p for p in passengers if p.app_on]) / self.num_passengers * 100
        success_rate_drivers = len([d for d in drivers if d.had_passenger]) / self.num_drivers * 100
        success_rate_passengers = len([p for p in passengers if p.had_ride]) / self.num_passengers * 100

        headers = "| Step | Spend | Rev | Cash | PnL | D-Pen % | P-Pen % | D-Succ % | P-Succ % |"
        row_data = "| {} | {:.1f} | {:.1f} | {:.1f} | {:.1f} | {:.1f} | {:.1f} | {:.1f} | {:.1f} |".format(
            self.schedule.steps, company_spending, company_revenue, company_cash, company_pnl, 
            percent_drivers_on, percent_passengers_on, success_rate_drivers, success_rate_passengers)

        if self.schedule.steps == 1:
            print(headers)
        print(row_data)
    
        company.budget_previous_step = company.funding
            
    def step(self):
        if not self.running:
            return
        self.company.step()  # The company performs its marketing activities
        self.schedule.step() # All agents move and potentially initiate rides
        self.calculate_statistics()  # Print out the statistics for this step
        for agent in self.schedule.agents:
            if isinstance(agent, Driver) and not agent.had_passenger and self.random.random() < 0.25:
                agent.app_on = False
            elif isinstance(agent, Passenger) and not agent.had_ride and self.random.random() < 0.25:
                agent.app_on = False


def run_model(N_passengers,
              N_drivers,
              width,
              height,
              co_funding,
              profit_per_ride,
              passenger_cac,
              driver_cac):
    model = RideshareModel(N_passengers, N_drivers, width, height, co_funding, profit_per_ride, passenger_cac, driver_cac)
    while model.running:
        model.step()

    fig, ax1 = plt.subplots()
    ax1.set_xlabel('Step')
    ax1.set_ylabel('Cash Reserves', color='tab:blue')
    ax1.plot(model.company.cash_history, color='tab:blue')
    ax1.tick_params(axis='y', labelcolor='tab:blue')

    ax2 = ax1.twinx()
    ax2.set_ylabel('Revenue', color='tab:red')  # we already handled the x-label with ax1
    ax2.plot(model.company.revenue_history, color='tab:red')
    ax2.tick_params(axis='y', labelcolor='tab:red')

    plt.show()

def distance(agent1, agent2):
    x1, y1 = agent1.pos
    x2, y2 = agent2.pos
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)


## Current test run: 
# run_model(100, 20, 50, 50, 2000, 2, 5, 10)
# For legibility: 

# run_model(N_passengers = 100,
#           N_drivers = 20,
#           width = 50 ,
#           height = 50,
#           co_funding = 200,
#           profit_per_ride = 2,
#           passenger_cac = 5,
#           driver_cac = 10)
