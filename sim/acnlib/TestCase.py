import pickle
from datetime import timedelta
import math
from acnlib.EV import EV
from acnlib.SimulationOutput import SimulationOutput, Event
import config


class TestCase:
    '''
    TestCase represents charging sessions over a certain simulation time.
    Stores the data of the test case when the simulation is run.
    '''
    def __init__(self, EVs, start_timestamp,voltage=220, max_rate=32, period=1):
        self.voltage = voltage
        self.max_rate = max_rate
        self.period = period
        self.start_timestamp = start_timestamp
        self.EVs = EVs

        self.simulation_output = SimulationOutput(start_timestamp, period, max_rate, voltage)
        self.actual_charging_rates = {}

        self.charging_data = {}
        self.network_data = []
        self.clear_data()

    def step(self, pilot_signals, iteration):
        '''
        Updates the states of the EVs connected the system and stores the relevant data.

        :param pilot_signals: A dictionary where key is the EV id and the value is a number with the charging rate
        :type pilot_signals: dict
        :param iteration: The current time stamp of the simulation
        :type iteration: int
        :return: None
        '''
        self.actual_charging_rates = {} # reset the last actual charging rates
        active_EVs = self.get_active_EVs(iteration)
        total_current = 0
        for ev in active_EVs:
            if ev.arrival == iteration:
                self.simulation_output.submit_event(Event('INFO',
                                                          iteration,
                                                          'EV arrived at station {}'.format(ev.station_id),
                                                          ev.session_id))
            charge_rate = ev.charge(pilot_signals[ev.session_id], tail=True)
            if charge_rate > self.max_rate:
                # If charging rate was exceeded output an error
                self.simulation_output.submit_event(Event('ERROR',
                                                          iteration,
                                                          'Max charging rate exceeded: {}A'.format(charge_rate),
                                                          ev.session_id))
            if charge_rate == 0:
                # If charging rate is set to 0A before EV finished charging output a warning
                self.simulation_output.submit_event(Event('WARNING',
                                                          iteration,
                                                          'Charging rate is set to 0A before EV finished charging',
                                                          ev.session_id))
            self.actual_charging_rates[ev.session_id] = charge_rate
            total_current = total_current + charge_rate
            sample = {'time': iteration,
                      'charge_rate': charge_rate,
                      'pilot_signal': pilot_signals[ev.session_id],
                      'remaining_demand': ev.remaining_demand}
            self.simulation_output.submit_charging_data(ev.session_id, sample)
            self.charging_data[ev.session_id].append(sample)
            if ev.fully_charged:
                ev.finishing_time = iteration
                self.simulation_output.submit_event(Event('INFO',
                                                          iteration,
                                                          'EV finished charging at station {}'.format(ev.station_id),
                                                          ev.session_id))

        self.simulation_output.submit_network_data({'time': iteration,
                                                    'total_current' : total_current,
                                                    'nbr_active_EVs': len(active_EVs)})


    def get_active_EVs(self, iteration):
        '''
        Returns the EVs that is currently attached to the charging stations and
        has not had their energy demand met.

        :param iteration: The current time stamp of the simulation
        :type iteration: int
        :return: List of EVs currently plugged in and not finished charging
        :rtype: list
        '''
        active_EVs = []
        for ev in self.EVs:
            if not ev.fully_charged and ev.arrival <= iteration and ev.departure > iteration:
                active_EVs.append(ev)
        return active_EVs


    def get_charging_data(self):
        return self.charging_data

    def get_network_data(self):
        return self.network_data

    def get_actual_charging_rates(self):
        return self.actual_charging_rates

    def get_simulation_output(self):
        '''
        Compiles the last pieces of information to the simulation output object and then returns it

        :return: The simulation output
        :rtype: SimulationOutput
        '''
        self.simulation_output.submit_all_EVs(self.EVs)
        self.simulation_output.last_departure = self.last_departure
        self.simulation_output.last_arrival = self.last_arrival
        return self.simulation_output


    def event_occured(self, iteration):
        '''
        Tells if an event has happened during the specified time (period)

        :param iteration: The time to check
        :return: True if an event has occured, False if not
        :rtype: boolean
        '''
        for ev in self.EVs:
            if ev.arrival == iteration or ev.departure == iteration:
                return True
        return False

    def clear_data(self):
        for ev in self.EVs:
            self.charging_data[ev.session_id] = []
            ev.reset()

    @property
    def last_departure(self):
        last_departure = 0
        for ev in self.EVs:
            if ev.departure > last_departure:
                last_departure = ev.departure
        return last_departure

    @property
    def last_arrival(self):
        last_arrival = 0
        for ev in self.EVs:
            if ev.arrival > last_arrival:
                last_arrival = ev.arrival
        return last_arrival


def generate_test_case_local(file_name, start, end, voltage=220, max_rate=32, period=1):
    '''
    Generates a TestCase from real data. This test case will then be passed to the ``ACNsim`` to be simulated.

    :param string file_name: The file that holds the session data. This file should be a ``pickle`` file
        and located in the same folder as the simulation script.
    :param datetime start: When to start read the data from the file.
    :param datetime end: When to stop read the data from the file.
    :param float voltage: The voltage level of the power grid [V].
    :param float max_rate: The maximum rate the EVs can be charged with [A].
    :param int period: The length of one iteration in the simulation [minutes].
    :return: The test case generated from the file containing the session data.
    :rtype: TestCase
    '''
    sessions = pickle.load(open(file_name, 'rb'))
    EVs = []
    uid = 0
    min_arrival = None
    for s in sessions:
        if start <= s[0]-timedelta(hours=config.time_zone_diff_hour) and s[1]-timedelta(hours=config.time_zone_diff_hour) <= end and s[2] >= 0.5:
            arrival = s[0]-timedelta(hours=config.time_zone_diff_hour)
            departure = s[1]-timedelta(hours=config.time_zone_diff_hour)
            ev = EV(arrival.timestamp() // 60 // period,
                    (math.ceil(departure.timestamp() / 60 / period)),
                    ((s[2] * (60/period) * 1e3) / voltage),
                    max_rate,
                    s[3],
                    uid)
            if ev.departure - ev.arrival < ev.requested_energy / ev.max_rate:
                ev.departure = math.ceil(ev.requested_energy / ev.max_rate) + ev.arrival
            uid += 1
            if not min_arrival:
                min_arrival = ev.arrival
            elif min_arrival > ev.arrival:
                min_arrival = ev.arrival
            EVs.append(ev)

    for ev in EVs:
        ev.arrival -= min_arrival
        ev.departure -= min_arrival
    EVs.sort(key=lambda x: x.station_id)
    return TestCase(EVs, (min_arrival*60*period),voltage, max_rate, period)