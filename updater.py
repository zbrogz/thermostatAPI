from urllib import request
from urllib import parse
from state import state_table
from state import json

hvac_idle = {"heater": False, "ac": False, "fan": False}
hvac_vent = {"heater": False, "ac": False, "fan": True}
hvac_heat = {"heater": True, "ac": False, "fan": True}
hvac_cool = {"heater": False, "ac": True, "fan": True}


def send_next_hvac(hvac_url, hvac, next_hvac):
    if next_hvac.items() <= hvac.items():
        return
    data = json.dumps(next_hvac).encode('utf8')
    
    req = request.Request(
        url=hvac_url, data=data, method='PUT')
    resp = request.urlopen(req)
    print(resp.getcode())


def update_hvac(thermostat, off_time_increment):
    hvac = json.loads(request.urlopen(thermostat['hvac_url']).read())
    temp = json.loads(request.urlopen(thermostat['temperature_url']).read())
    temperature = temp['temperature']
    next_hvac = {}
    desired = thermostat['desired_temperature']
    eco_min = thermostat['eco_min_temperature']
    eco_max = thermostat['eco_max_temperature']

    print(thermostat)
    if thermostat['mode'] == "off":
        next_hvac = hvac_idle
        next_hvac['off_time'] = hvac['off_time'] + off_time_increment
    elif thermostat['mode'] == "eco":
        # Too cold
        if ((temperature < eco_min - thermostat['tolerance']) or
                (temperature < eco_min and hvac['heater'])):
            next_hvac = hvac_heat
            next_hvac['off_time'] = hvac['off_time'] + off_time_increment
        # Too hot
        elif (hvac['off_time'] >= hvac['min_off_time'] and (
                temperature > eco_max + thermostat['tolerance'] or (
                temperature > eco_max and hvac['ac']))):
            next_hvac = hvac_cool
            next_hvac['off_time'] = 0
        else:
            next_hvac = hvac_idle
            next_hvac['off_time'] = hvac['off_time'] + off_time_increment
    elif thermostat['mode'] == "normal":
        # Too cold
        if ((temperature < desired - thermostat['tolerance']) or
                (temperature < desired and hvac['heater'])):
            next_hvac = hvac_heat
            next_hvac['off_time'] = hvac['off_time'] + off_time_increment
        # Too hot
        elif (hvac['off_time'] >= hvac['min_off_time'] and (
                temperature > desired + thermostat['tolerance'] or (
                temperature > desired and hvac['ac']))):
            next_hvac = hvac_cool
            next_hvac['off_time'] = 0
        else:
            next_hvac = hvac_idle
            next_hvac['off_time'] = hvac['off_time'] + off_time_increment
    elif thermostat['mode'] == "heat":
        # Too cold
        if ((temperature < desired - thermostat['tolerance']) or
                (temperature < desired and hvac['heater'])):
            next_hvac = hvac_heat
        # Too hot
        else:
            next_hvac = hvac_idle
        next_hvac['off_time'] = hvac['off_time'] + off_time_increment
    elif thermostat['mode'] == "cool":
        # Too hot
        if (hvac['off_time'] >= hvac['min_off_time'] and (
                temperature > desired + thermostat['tolerance'] or (
                temperature > desired and hvac['ac']))):
            next_hvac = hvac_cool
            next_hvac['off_time'] = 0
        # Too cold
        else:
            next_hvac = hvac_idle
            next_hvac['off_time'] = hvac['off_time'] + off_time_increment
    else:
        raise Exception("Invalid thermostat mode")

    # Check fan
    if thermostat['fan'] == 'on':
        next_hvac['fan'] = True
    
    print(next_hvac)
    
    send_next_hvac(thermostat['hvac_url'], hvac, next_hvac)


def update_hvacs():
    thermostats = state_table().scan()['Items']
    for thermostat in thermostats:
        update_hvac(thermostat, off_time_increment=1)


def lambda_handler(event, context):
    # Add logic to determine if job sent by Chron or HTTP event
    update_hvacs()
