from datetime import datetime, timedelta
from acnlib.Interface import Interface
from acnlib.Simulator import Simulator
from acnlib.Garage import Garage

class ACNsim:

    def __init__(self):
        pass

    def simulate(self, scheduler, garage):
        sim = Simulator(garage)
        interface = Interface(sim)
        scheduler.interface_setup(interface)
        sim.define_scheduler(scheduler)

        simulation_output = sim.run()
        return simulation_output

    def simulate_real(self, scheduler, test_case):
        garage = Garage()
        garage.set_test_case(test_case)
        return self.simulate(scheduler, garage)

    def simulate_model(self, scheduler, start=datetime.now(), end=(datetime.now() + timedelta(days=2)), period=1, voltage=220, max_rate = 32):
        garage = Garage()
        garage.generate_test_case(start, end, period, voltage, max_rate)
        return self.simulate(scheduler, garage)

