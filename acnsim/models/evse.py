import numpy as np

BASIC = 'BASIC'
AV = 'AeroVironment'
CC = 'ClipperCreek'


def get_EVSE_by_type(station_id, evse_type):
    """ Factory to produce EVSEs of a given type.

    Args:
        station_id (str): Unique identifier of the EVSE.
        evse_type (str): Type of the EVSE. Currently supports 'BASIC', 'AeroVironment', and 'ClipperCreek'.

    Returns:
        EVSE: an EVSE of the specified type and with the specified id.
    """
    if evse_type == BASIC:
        return EVSE(station_id)
    elif evse_type == AV:
        allowable_rates = [0]
        allowable_rates.extend(i for i in range(6, 33))
        return FiniteRatesEVSE(station_id, allowable_rates)
    elif evse_type == CC:
        allowable_rates = [0, 8, 16, 24, 32]
        return FiniteRatesEVSE(station_id, allowable_rates)


class InvalidRateError(Exception):
    pass


class StationOccupiedError(Exception):
    pass


class EVSE:
    """ Class to model Electric Vehicle Supply Equipment (charging station).

    This base class allows for charging in a continuous range from min_rate to max_rate.

    Attributes;
        station_id (str): Unique identifier of the EVSE.
        ev (EV): EV currently connected the the EVSE.
        max_rate (float): Maximum charging current allowed by the EVSE.
        min_rate (float): Minimum charging current allowed by the EVSE.
        current_pilot (float): Pilot signal for the current time step. [acnsim units]
    """
    def __init__(self, station_id, max_rate=float('inf'), min_rate=0):
        self._station_id = station_id
        self._ev = None
        self._max_rate = max_rate
        self._min_rate = min_rate
        self._current_pilot = 0

    @property
    def station_id(self):
        return self._station_id

    @property
    def ev(self):
        return self._ev

    @property
    def max_rate(self):
        return self._max_rate

    @property
    def min_rate(self):
        return self._min_rate

    @property
    def current_pilot(self):
        return self._current_pilot

    def set_pilot(self, pilot):
        """ Apply a new pilot signal to the EVSE.

        Before applying the new pilot, this method first checks if the pilot is allowed. If it is not, an
        InvalidRateError is raised. If the rate is valid, it is forwarded on to the attached EV if one is present.
        This method is also where EV charging is triggered. Thus it must be called in every time time period where the
        attached EV should receive charge.

        Args:
            pilot (float): New pilot (control signal) to be sent to the attached EV.

        Returns:
            None.

        Raises:
            InvalidRateError: Exception raised when pilot is not allowed by the EVSE.
        """
        if self._valid_rate(pilot):
            self._current_pilot = pilot
            if self._ev is not None:
                self._ev.charge(pilot)
        else:
            raise InvalidRateError('Pilot {0} A is not valid for for station {1}'.format(pilot, self.station_id))

    def _valid_rate(self, pilot):
        """ Check if pilot is in the valid set.

        Args:
            pilot (float): Proposed pilot signal.

        Returns:
            bool: True if the proposed pilot signal is valid. False otherwise.
        """
        return self.min_rate <= pilot <= self.max_rate

    def plugin(self, ev):
        """ Method to attach an EV to the EVSE.

        Args:
            ev (EV): EV which should be attached to the EVSE.

        Returns:
            None.

        Raises:
            StationOccupiedError: Exception raised when plugin is called by an EV is already attached to the EVSE.
        """
        if self.ev is None:
            self._ev = ev
        else:
            raise StationOccupiedError('Station {0} is occupied with ev {1}'.format(self._station_id,
                                                                                    self._ev.session_id))

    def unplug(self):
        """ Method to remove an EV currently attached to the EVSE.

        Sets ev to None and current_pilot to 0.

        Returns:
            None
        """
        self._ev = None
        self._current_pilot = 0


class FiniteRatesEVSE(EVSE):
    """ Subclass of EVSE which allows for finite allowed rate sets.

    Most functionality remains the same except those differences noted below.

    Attributes:
        allowable_rates (iterable): Iterable of rates which are allowed by the EVSE.

    """
    def __init__(self, station_id, allowable_rates):
        super().__init__(station_id, max(allowable_rates))
        self.allowable_rates = allowable_rates

    def _valid_rate(self, pilot, atol=1e-3):
        """ Overrides super class method. Checks if pilot is close to being in the allowable set.

        Args:
            pilot: Proposed pilot signal.
            atol: Absolute tolerance used when determining if a pilot belongs to the allowable rates set.

        Returns:
            bool: True if the proposed pilot signal is valid. False otherwise.
        """
        return np.any(np.isclose(pilot, self.allowable_rates, atol=1e-3))
