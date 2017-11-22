from clioServer import credentials, postPulses
from mastodon import Mastodon
import sys
import os
import json
import copy
import io
import re

APP_NAME = 'MapBot'
BOT_LOGIN = 'cedric.viaccoz@epfl.ch'
BOT_PSWD = 'reallygoodpassword'
HASH_MARKER = 'geoCoords'
FINAL_PULSE = 'Today, {0} pulses were geoparsed and then added to the map of GeoPulses !'

GEOJSON_FILEPATH = 'data/geopulses.json'

GEOJSON_PRE = "{\"type\": \"FeatureCollection\",\"generator\": \"overpass-turbo\",\"copyright\": \"2017, EPFL \",\"timestamp\": \"2017-11-20T13:03:02Z\",\"features\": ["

GEOJSON_POST = "]}"

def main(args):

    credentials.checkIfCredentials(APP_NAME)

    cliowireConn = credentials.log_in(APP_NAME, BOT_LOGIN, BOT_PSWD)

    geopulses = cliowireConn.timeline_hashtag(HASH_MARKER, local=True)

    toWrite = ''

    nmbOfPulses = len(geopulses)

    if nmbOfPulses > 0:
        for p in geopulses:
            cleanContent = cleanHTTP(p['content'])
            toWrite += jsonParse(cleanContent, p['id'])
            toWrite += ','

        #remove trailing comma
        toWrite = toWrite[:-1]
        f = writeGeoPulses(GEOJSON_FILEPATH, toWrite)
        f.close()

        postPulses.post_content(cliowireConn, [FINAL_PULSE.format(nmbOfPulses)])
    else:
        print("No new geopulses were detected on the platform.\nNo actions were performed on the map.")


def cleanHTTP(content):
    #Remove href balises, but keep the url
    cleanHref = re.compile('<a[^>]+href=\"(.*?)\"[^>]*>')
    #Remove every other http balises
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanHref, '', content)
    cleantext = re.sub(cleanr, '', cleantext)
    return cleantext

def writeGeoPulses(filepath, pulsesToWrite):
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
        Convention of the geoPulse : format (in regex like descritpion)
        "#geoCoords(<coord1>, <coord2>) <content>? [#GeoEntity <nameOfGeoEntity> | (<nameOfGeoEntity> <uriOfGeoEntity>)]+? <content>?"
        Example :
        "#geoCoords(12.3404, 45.4337) DHstudents went to #GeoEntity (Venice https://en.wikipedia.org/wiki/Venice)"
    '''
    tokens = content.split( )
    #will stoke processed version of the tokens, to reconstruct the original text
    purifiedContent = []
    ''' we take as principle that every content given in this function,
        is a content of a geoPulse, with all its convention respected.
        So the first two tokens should be the coordinates. If this is not
        the case, an exception is raised.'''
    if not tokens[0].startswith('#'+HASH_MARKER):
        raise Exception("MapBot received a pulse that was not geoparsed ! The operation was aborted.")
    lng = tokens[0][len(HASH_MARKER)+2:-1]
    lat = tokens[1][:-1]
    coordinates = [float(lng), float(lat)]
    tokens = tokens[2:]
    entities = []
    i = 1
    nmbToks = len(tokens)
    while i < nmbToks:
        currTok = copy.deepcopy(tokens[i])
        precedingTok = tokens[i-1]
        if precedingTok == '#GeoEntity':
            i += 1
            #if the geoEntity is also a named entities, need to remove the first open parenthesis.
            if currTok[0] == '(':
                currTok = currTok[1:]
                #We need to skip the uri as well.
                i += 1
            entities.append(currTok)
            purifiedContent.append(currTok)
        elif(precedingTok[0] == '(' and currTok.startswith('http')):
            #we encountered a named entities which did not trigger the geoparsing, need to add to entities list.
            purifiedContent.append(precedingTok[1:])
            entities.append(precedingTok[1:])
            i += 1
        else:
            #otherwise we just let the content as it is.
            purifiedContent.append(precedingTok)
            #with the weird way to scan all the tokey, those lines needed to be to avoid edge cases.
            if i == nmbToks - 1 and currTok != '#GeoEntity':
                purifiedContent.append(currTok)
        i += 1

    return ' '.join(purifiedContent), entities, coordinates

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

main(sys.argv)