#!/usr/bin/python
#
# Copyright (c) 2013 Dell, Inc.
#  by Matt Domsch <Matt_Domsch@dell.com>
# Licensed under the MIT/X11 license

# Environment Variables setable via Apache SetEnv directive:
# geoip_city.noreverseproxy
#  if set (to anything), do not look at X-Forwarded-For headers.  This
#  is used in environments that do not have a Reverse Proxy (HTTP
#  accelerator) in front of the application server running this WSGI,
#  to avoid looking "behind" the real client's own forward HTTP proxy.

from paste.wsgiwrappers import *
from iso3166 import countries
import geoip2.database
import geoip2.errors
import json

global gi
gi = geoip2.database.Reader("/usr/share/GeoIP/GeoLite2-City.mmdb")


def real_client_ip(xforwardedfor):
    """Only the last-most entry listed is the where the client
    connection to us came from, so that's the only one we can trust in
    any way."""
    return xforwardedfor.split(',')[-1].strip()

def get_client_ip(environ, request):
    client_ip = None
    request_data = request.GET

    if 'ip' in request_data:
        client_ip = request_data['ip'].strip()
    elif 'X-Forwarded-For' in request.headers and 'geoip_city.noreverseproxy' not in environ:
        client_ip = real_client_ip(request.headers['X-Forwarded-For'].strip())
    else:
        client_ip = request.environ['REMOTE_ADDR']

    return client_ip

def application(environ, start_response):
    request = WSGIRequest(environ)
    response = WSGIResponse()
    results = {}
    code = 500

    try:
        client_ip = get_client_ip(environ, request)
        if client_ip is None:
            code = 400
            raise Exception
        data = gi.city(client_ip)
        if data is None:
            code = 404
            raise Exception
    except geoip2.errors.AddressNotFoundError:
        response.status_code = 404
        return response(environ, start_response)
    except: 
        response.status_code=code
        return response(environ, start_response)

    results['ip'] = client_ip

    # map geoip2 data to a structure that matches the prior geoip format
    results['city']         = data.city.name
    results['region_name']  = data.subdivisions.most_specific.name
    results['region']       = data.subdivisions.most_specific.iso_code
    results['postal_code']  = data.postal.code
    results['country_name'] = data.country.name
    results['country_code'] = data.country.iso_code
    results['time_zone']    = data.location.time_zone
    results['latitude']     = data.location.latitude
    results['longitude']    = data.location.longitude
    results['metro_code']   = data.location.metro_code
    results['dma_code']     = data.location.metro_code

    # geoip2 no longer includes country_code3, so it has to be pulled
    # from iso3166.countries
    if data.country.iso_code in countries:
        results['country_code3'] = countries[data.country.iso_code].alpha3
    else:
        results['country_code3'] = None

    results = json.dumps(results)
    response.headers['Content-Length'] = str(len(results))
    response.write(results)
    return response(environ, start_response)


if __name__ == '__main__':
    from paste import httpserver
    httpserver.serve(application, host='127.0.0.1', port='8090')
