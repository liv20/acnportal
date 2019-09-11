import json
from acnportal import acnsim

def from_json(in_json, typ='simulator', **kwargs):
	""" Load object of type given by typ from a given in_file using JSON

    Args:
        in_json (JSON str): JSON string from which to read JSON.
        typ (str): type of object to be read, default simulator. Options:
            {'simulator', 'network', 'event_queue', 'ev', 'event', 'evse'}

    Returns: Type returned depends on value of typ. Possibile return types:
        {Simulator, ChargingNetwork, BaseAlgorithm, EventQueue, EV, Event, EVSE, Battery}
    """
    # Check that the object type being decoded is valid
    decoder_func = '_{0}_from_json_dict'.format(typ)
    if decoder_func not in locals():
		raise InvalidJSONError('Attempting to decode unrecognized object: {0}.'.format(typ))
    
    json_dict = json.loads(in_json)
    
    # Check that json file is of the correct object type
    try:
        real_typ = json_dict['obj_type']
    except KeyError:
        raise InvalidJSONError('Unable to read object of type {0} from file.'.format(typ))
    if typ != real_typ:
        raise InvalidJSONError('Expected object of type {0}, got {1}.'.format(typ, real_typ))

    if typ == 'simulator':
        json_dict['scheduler'] = kwargs

    return locals()[decoder_func]()(json_dict)

def to_json(obj, typ, additional_fields=None):
	""" Returns a JSON-serializable representation of the object obj if possible
	
	Args:
		obj (Object): Object to be converted into JSON-serializable form.
        typ (str): Supertype of object to be serialized. Possible inputs:
            {'simulator', 'network', 'event_queue', 'event', 'ev', 'evse', 'battery'} 
        additional_fields (List[str]): Additional field names to serialize. Each field given must be
            JSON serializable

	Returns:
        JSON serializable
	"""
    encoder_func = '_{0}_to_json'.format(typ)
	
    if encoder_func not in locals():
		raise InvalidJSONError('Attempting to encode unrecognized object: {0}'.format(typ))
	
    json_dict = locals()[encoder_func](copy.deepcopy(obj), {'obj_type' : typ})

    return json.dumps(json_dict)

###-------------Encoders-------------###

def _simulator_to_json(obj, json_dict):
	json_dict['network'] = obj.network.to_json()
    json_dict['event_queue'] = obj.event_queue.to_json()

    json_dict['start'] = obj.start
    json_dict['period'] = obj.period
    json_dict['max_recompute'] = obj.max_recompute
    json_dict['verbose'] = obj.verbose
    json_dict['_iteration'] = obj.iteration

    json_dict['pilot_signals'] = obj.pilot_signals.to_list()
    json_dict['charging_rates'] = obj.charging_rates.to_list()

    json_dict['ev_history'] = {session_id : ev.to_json() for session_id, ev in obj.ev_history.items()}
    json_dict['event_history'] = [event.to_json() for event in obj.event_history]

    return json_dict

def _network_to_json(obj, json_dict):
    json_dict['_EVSEs'] = obj._EVSEs

    json_dict['constraint_matrix'] = obj.constraint_matrix.to_list()
    json_dict['magnitudes'] = obj.magnitudes.to_list()

    json_dict['constraint_index'] = obj.constraint_index

    json_dict['_voltages'] = np.array(obj._voltages)
    json_dict['_phase_angles'] = np.array(obj._phase_angles)

    return json_dict

def _event_queue_to_json(obj, json_dict):
	json_dict['_queue'] = [(ts, event.to_json()) for (ts, event) in obj._queue]
    json_dict['_timestep'] = obj._timestep
	
	return json_dict

def _event_to_json(obj, json_dict):
    json_dict['timestamp'] = obj.timestamp
    json_dict['type'] = obj.type
    json_dict['precedence'] = obj.precedence

    if obj.type == 'Unplug':
        json_dict['station_id'] = obj.station_id
        json_dict['session_id'] = obj.session_id
    elif obj.type == 'Plugin':
        json_dict['ev'] = obj.ev.to_json()

	return json_dict

def _evse_to_json(obj, json_dict):
	for field in ['station_id', 'max_rate', 'min_rate', 'current_pilot']:
        json_dict['_'+field] = obj.__dict__[field]

    if ev is not None:
        json_dict['_ev'] = obj.ev.to_json()
    else:
        json_dict['_ev'] = None

def _ev_to_json(obj, json_dict):
    for field in ['arrival', 'departure', 'estimated_departure', 'requested_energy',
        'session_id', 'station_id', 'energy_delivered', 'current_charging_rate']:
        json_dict['_'+field] = obj.__dict__[field]

	json_dict['_battery'] = obj.['_battery'].to_json()

	return json_dict

def _battery_to_json(obj, json_dict):
	json_dict['_max_power'] = obj.max_charging_power
    json_dict['_current_charging_power'] = obj.current_charging_power
    json_dict['_current_charge'] = obj._current_charge
    json_dict['_capacity'] = obj._capacity

###-------------Decoders-------------###

def _simulator_from_json_dict(in_dict, scheduler):
    network = _network_from_json_dict(in_dict['network'])
    events = _event_queue_from_json_dict(in_dict['event_queue'])

	out_obj = acnsim.Simulator(
        network,
        in_dict['scheduler'],
        events,
        in_dict['start'],
        period=in_dict['period'],
        max_recomp=in_dict['max_recompute'],
        verbose=in_dict['verbose']
    )

    out_obj._iteration = in_dict['_iteration']

    out_obj.pilot_signals = np.array(in_dict['pilot_signals'])
    out_obj.charging_rates = np.array(in_dict['charging_rates'])

    out_obj.ev_history = {session_id : _ev_from_json_dict(ev) for session_id, ev in in_dict['ev_history']}
    out_obj.event_history = [_event_from_json_dict(event) for event in in_dict['event_history']]

    return out_obj

def _network_from_json_dict(in_dict):
    out_obj = ChargingNetwork()
    out_obj._EVSEs = in_dict['_EVSEs']
    out_obj.constraint_matrix = np.array(in_dict['constraint_matrix'])
    out_obj.magnitudes = np.array(in_dict['magnitudes'])
    out_obj.constraint_index = in_dict['constraint_index']
    out_obj._voltages = np.array(in_dict['_voltages'].values())
    return out_obj

def _event_queue_from_json_dict(in_dict):
    event_list = [(ts, _event_from_json_dict(event_dict)) for (ts, event_dict) in in_dict['_queue']]
    out_obj = acnsim.events.EventQueue()
    out_obj._queue = event_list
    out_obj._timestep = in_dict['_timestep']
    return out_obj

def _event_from_json_dict(in_dict):
    if in_dict['type'] == 'Plugin':
        ev = _ev_from_json_dict(in_dict['_ev'])
        return acnsim.events.PluginEvent(
            in_dict['timestamp'],
            ev
        )
    elif in_dict['type'] == 'Unplug':
        station_id = in_dict['station_id']
        session_id = in_dict['session_id']
        return acnsim.events.UnplugEvent(
            in_dict['timestamp'],
            station_id,
            session_id
        )

def _evse_from_json_dict(in_dict):
    if in_dict['_ev'] is not None:
        ev = _ev_from_json_dict(in_dict['_ev'])
    else:
        ev = None

    out_obj = acnsim.models.EVSE(
        in_dict['_station_id']
        max_rate=in_dict['_max_rate']
        min_rate=in_dict['_min_rate']
    )

    out_obj._current_pilot = in_dict['_current_pilot']
    out_obj._ev = ev
    out_obj.is_continuous = True

    return out_obj

def _ev_from_json_dict(in_dict):
    battery = _battery_from_json_dict(in_dict['_battery'])

    out_obj = acnsim.models.EV(
        in_dict['_arrival'],
        in_dict['_departure'],
        in_dict['_requested_energy'],
        in_dict['_station_id'],
        in_dict['_session_id'],
        battery,
        estimated_departure=in_dict['estimated_departure']
    )

    return out_obj

def _battery_from_json_dict(in_dict):
    # Note second arg in below construction is a placeholder
    out_obj = acnsim.models.Battery(in_dict['_capacity'], 0, in_dict['_max_power'])

    out_obj._current_charging_power = in_dict['_current_charging_power']
    out_obj._current_charge = in_dict['_current_charge']

    return out_obj

class InvalidJSONError(Exception):
    """ Exception which is raised when trying to read a JSON file with contents that do not match
    the given type. """
    pass