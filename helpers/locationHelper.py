from json import loads
from urllib.request import urlopen

from common.log import logUtils as log
from objects import glob


def getCountry(ip: str) -> str:
    """
    Get country from IP address using geoip api

    :param ip: IP address
    :return: country code. XX if invalid.
    """
    try:
        # Try to get country from Pikolo Aul's Go-Sanic ip API
        result = loads(urlopen(f'{glob.conf.config["localize"]["ipapiurl"]}/{ip}', timeout=3).read().decode())["country"]
        return result.upper()
    except:
        log.error("Error in get country")
        return "XX"

def getLocation(ip: str) -> tuple[float]:
    """
    Get latitude and longitude from IP address using geoip api

    :param ip: IP address
    :return: (latitude, longitude)
    """
    try:
        # Try to get position from Pikolo Aul's Go-Sanic ip API
        result = loads(urlopen(f'{glob.conf.config["localize"]["ipapiurl"]}/{ip}', timeout=3).read().decode())["loc"].split(",")
        return float(result[0]), float(result[1])
    except:
        log.error("Error in get position")
        return 0, 0

def getGeoloc(ip: str) -> tuple[str, tuple[float, float]]:
    # both functions in one cuz why are they even split lol
    try:
        result = loads(urlopen(f'{glob.conf.config["localize"]["ipapiurl"]}/{ip}', timeout=3).read().decode())
        country = result['country']
        loc = result['loc'].split(',')
        return (country, (float(loc[0]), float(loc[1]))) # lat, lon
    except:
        return ('XX', (0.0, 0.0))
