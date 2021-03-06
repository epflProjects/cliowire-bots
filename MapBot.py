from clioServer import credentials, postPulses, cliowireUtils as cU
from mastodon import Mastodon
import sys, os, json, copy, io, re

#constants of the program
APP_NAME = 'MapBot'
DATA_FOLDER = 'data/'
HASH_MARKER = 'geocoding'
FINAL_PULSE = 'Today, {0} pulse(s) were geocoded and then added to the map of GeoPulses !'

GEOJSON_FILEPATH = DATA_FOLDER+'geopulses.json'

GEOJSON_PRE = "{\"type\": \"FeatureCollection\",\"generator\": \"overpass-turbo\",\"copyright\": \"2017, EPFL \",\"timestamp\": \"2017-11-20T13:03:02Z\",\"features\": ["

GEOJSON_POST = "]}"

#regex that is able to detect if a certain token is a correct coordinate hashtag or not.
coordReg = re.compile(r"\#pM?[0-9]{1,2}_[0-9]{1,4}_M?[0-9]{1,2}_[0-9]{1,4}")

class NoCoordsException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def main(args):

    bot_login, bot_pswd, last_id, file_name = None, None, None, None #BATMAAAAAAAN
    try:
        bot_login, bot_pswd, last_id = cU.retrieveBotsMetadata(args[1:])
    except Exception as exc:
        #print the error message for the user to understand what atrocity he did
        print('\n'+str(exc)+'\n')
        sys.exit(1)
    #this should not produce an index out of bound error, since it is checked in the try catch above.
    file_name = args[1]
    credentials.checkIfCredentials(file_name)

    cliowireConn = credentials.log_in(file_name, bot_login, bot_pswd)

    CWIter = cU.PulseIterator(cliowireConn, hashtag=HASH_MARKER, oldest_id=last_id)

    toWrite = ''

    #to determine wether new pulses were retrieved, and keep track of how much we're going to add to the map.
    nmbOfPulses = 0

    for geopulses in CWIter:
        for p in geopulses:
            cleanContent = cU.cleanHTTP(p.content)
            try:
                toWrite += jsonParse(cleanContent, int(p.id))
                toWrite += ','
                nmbOfPulses += 1
            except NoCoordsException:
                pass

    #need to update the id of the most recent pulse to allow statefull future computations
    last_id = CWIter.latest_id

    if nmbOfPulses == 0:
        print("No new geopulses were detected on the platform.\nNo actions were performed on the map.")
    else:
        #remove trailing commas
        toWrite = toWrite[:-1]
        f = writeGeoPulses(GEOJSON_FILEPATH, toWrite)
        f.close()
        #we need to save the last id that we have
        cU.updateBotsMetadata(file_name, last_id)
        postPulses.post_content(cliowireConn, [FINAL_PULSE.format(nmbOfPulses)])


def writeGeoPulses(filepath, pulsesToWrite):
    #first need to create the data folder if it is not already present.
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)

    if os.path.isfile(filepath):
        #this way of doing might not be feasible once the file gets too big.
        #really need a way to erase two last char of a JSON file.
        f = open(filepath, 'r')
        data = f.readlines()
        data[0] = data[0][:-len(GEOJSON_POST)]
        data[0] += ','
        data[0] += pulsesToWrite
        data[0] += GEOJSON_POST
        f.close()
        f = open(filepath, 'w')
        f.write(data[0])
        return f
    else:
        f = open(filepath, 'w+')
        f.write(GEOJSON_PRE+pulsesToWrite+GEOJSON_POST)
        return f


def contentBreakDown(content):
    '''
    takes the content of the pulse (cleaned from all the HTTP useless scraps), and produces
    the content without the hashtags refering to the geocoding part, then the list of entities
    and finally the tuples of geocoordinate (latitude and longitude)
    '''
    tokens = content.split(' ')
    filteredContent = []
    entities = []
    coordinates = []
    #to avoid pulses with the hashtag #geocoding without being a geopulse.
    hasCoords = False
    for t in tokens:
        if re.match(coordReg, t) != None:
            hasCoords = True
            removeP = t[2:]
            undSS = removeP.split('_')
            if len(undSS) != 4:
                raise Exception('The coordinate in this geocoded pulse : \"{}\" were malformed'.format(content))
            lng = coordToFloat(undSS[0], undSS[1])
            lat = coordToFloat(undSS[2], undSS[3])
            coordinates.append(lng)
            coordinates.append(lat)
        elif t.startswith('#') and not t == '#geocoding':
            entities.append(t[1:])
            filteredContent.append(t)
        elif t != '#geocoding':
            filteredContent.append(t)
    if not hasCoords:
        raise NoCoordsException('the hashtag geocoding was present but there were no coordinates in the pulse.')
    purifiedContent = ' '.join(filteredContent)
    return purifiedContent, entities, coordinates

def jsonParse(pulse, pulseId):
    content, entities, coordinates = contentBreakDown(pulse)
    #this below is the jsonGeoPulse format we're using. Coordinates must be a list/array of 2 floats, entities a list/array of string, everything else Strings.
    return json.dumps({
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": coordinates
        },
        "properties": {
            "pulseid": pulseId,
            "content": content,
            "entities": entities
        }
    })

def coordToFloat(decim, unit):
    res = 1
    if decim[0] == 'm' or decim[0] == 'M':
        res *= -1
        decim = decim[1:]
    return res * float(str(decim + '.' + unit))

main(sys.argv)
