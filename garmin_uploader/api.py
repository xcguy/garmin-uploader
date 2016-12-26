# Copyright (c) David Lotton 02/2014
#
# License: Apache 2.0
#
# Information: 2/26/2014
# Complete redesign of UploadGarmin.py due to major changes in the Garmin
# Connect authorization scheme which rolled out in late Feb 2014. License has
# change from previous version of this file to comply with licence of the work
# from which this work was derived.
#
# THE COPYRIGHT HOLDERS AND/OR OTHER PARTIES PROVIDE THE PROGRAM
# 'AS IS' WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESSED OR
# IMPLIED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE. THE
# ENTIRE RISK AS TO THE QUALITY AND PERFORMANCE OF THE PROGRAM
# IS WITH YOU. SHOULD THE PROGRAM PROVE DEFECTIVE, YOU ASSUME
# THE COST OF ALL NECESSARY SERVICING, REPAIR OR CORRECTION.
#

import requests
import re
from urllib import urlencode
import json
import os.path
from garmin_uploader import logger, VALID_GARMIN_FILE_EXTENSIONS, BINARY_FILE_FORMATS

# TODO: Clean
URL_HOSTNAME = 'https://connect.garmin.com/gauth/hostname'
URL_LOGIN = 'https://sso.garmin.com/sso/login'
URL_POST_LOGIN = 'https://connect.garmin.com/post-auth/login'
URL_CHECK_LOGIN = 'https://connect.garmin.com/user/username'
URL_HOST_SSO = 'sso.garmin.com'
URL_HOST_CONNECT = 'connect.garmin.com'


class GarminAPI:
    """
    Low level Garmin Connect api connector
    """

    def authenticate(self, username, password):
        """
        That's where the magic happens !
        Try to mimick a browser behavior trying to login
        on Garmin Connect as closely as possible
        Outputs a Requests session, loaded with precious cookies
        """
        # Use a valid Browser user agent
        # TODO: use several UA picked randomly
        session = requests.Session()
        session.headers.update({
            'User-Agent' :  'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:48.0) Gecko/20100101 Firefox/50.0',
        })

        # Request sso hostname
        sso_hostname = None
        resp = session.get(URL_HOSTNAME)
        if not resp.ok:
            raise Exception('Invalid SSO first request status code {}'.format(resp.status_code))

        sso_hostname = resp.json().get('host', None).rstrip('.garmin.com')
        # Load login page to get login ticket
        params = {
              'clientId' : 'GarminConnect',
              'webhost' : sso_hostname,

              # Full parameters from Firebug
              # Fuck this shit. Who needs mandatory urls in a request parameters !
              'consumeServiceTicket' : 'false',
              'createAccountShown' : 'true',
              'cssUrl' : 'https://static.garmincdn.com/com.garmin.connect/ui/css/gauth-custom-v1.2-min.css',
              'displayNameShown' : 'false',
              'embedWidget' : 'false',
              'gauthHost' : 'https://sso.garmin.com/sso',
              'generateExtraServiceTicket' : 'false',
              'globalOptInChecked': 'false',
              'globalOptInShown': 'false',
              'id' : 'gauth-widget',
              'initialFocus' : 'true',
              'locale' : 'fr',
              'openCreateAlcount' : 'false',
              'redirectAfterAccountCreationUrl' : 'https://connect.garmin.com/post-auth/login',
              'redirectAfterAccountLoginUrl' : 'https://connect.garmin.com/post-auth/login',
              'rememberMeChecked' : 'false',
              'rememberMeShown' : 'true',
              'service' : 'https://connect.garmin.com/post-auth/login',
              'source' : 'https://connect.garmin.com/fr-FR/signin',
              'usernameShown' : 'false',
        }
        res = session.get(URL_LOGIN, params=params)
        if res.status_code != 200:
              raise Exception('No login form')

        # Get the login ticket value
        regex = '<input\s+type="hidden"\s+name="lt"\s+value="(?P<lt>\w+)"\s+/>'
        res = re.search(regex, res.text)
        if not res:
              raise Exception('No login ticket')
        login_ticket = res.group('lt')
        logger.debug('Found login ticket %s', login_ticket)

        # Login/Password with login ticket
        data = {
          # All parameters are needed
          '_eventId' : 'submit',
          'displayNameRequired' : 'false',
          'embed' : 'true',
          'lt' : login_ticket,
          'username' : username,
          'password' : password,
        }
        headers = {
          'Host' : URL_HOST_SSO,
        }
        res = session.post(URL_LOGIN, params=params, data=data, headers=headers)
        if res.status_code != 200:
            raise Exception('Authentification failed.')

        # Try to find the full post login url in response
        regex = 'var response_url(\s+)= \'.*?ticket=(?P<ticket>[\w\-]+)\''
        params = {}
        matches = re.search(regex, res.text)
        if not matches:
            raise Exception('Missing service ticket')
        params['ticket'] = matches.group('ticket')
        logger.debug('Found service ticket %s', params['ticket'])

        # Second auth step
        # Needs a service ticket from previous response
        # Currently gives 3 302 redirects until a 404 :/
        headers = {
            'Host' : URL_HOST_CONNECT,
        }
        res = session.get(URL_POST_LOGIN, params=params, headers=headers)
        if res.status_code != 200 and not res.history:
            raise Exception('Second auth step failed.')

        # Check login
        res = session.get(URL_CHECK_LOGIN)
        garmin_user = res.json()
        if not garmin_user.get('username', None):
              raise Exception("Login check failed.")
        logger.info('Logged in as %s' % (garmin_user['username']))

        return session


    def upload_file(self, session, uploadFile):

        extension = os.path.splitext(uploadFile)[1].lower()

        # Valid File extensions are .tcx, .fit, and .gpx
        if extension not in VALID_GARMIN_FILE_EXTENSIONS:
            raise Exception("Invalid File Extension")

        if extension in BINARY_FILE_FORMATS:
            mode = 'rb'
        else:
            mode = 'r'

        # Garmin Connect web site does not comply with RFC 2231.
        # urllib3 (used by the requests module) automatically detects non-ascii
        # characters in filenames and generates the filename* header parameter
        # (with asterisk - signifying that the filename has non-ascii characters)
        # instead of the filename (without asterisk) header parameter.  Garmin
        # Connect does not accept the asterisked version of filename and there
        # is no way to tell urllib3 to not generate it.  The work-around for
        # Garmin's noncompliant behavior (sending non-ascii characters with the
        # non-asterisked filename parameter) is to always send an ascii encodable
        # filename.  This is achieved by parsing out the non-ascii characters.
        try:
          uploadFileName = uploadFile.encode('ascii')
        except UnicodeEncodeError:
          uploadFileName = uploadFile.decode('ascii', 'ignore')

        files = {"data": (uploadFileName, open(uploadFile, mode))}
        url = "https://connect.garmin.com/proxy/upload-service-1.1/json/upload/%s" % extension
        res = session.post(url, files=files)
        if not res.ok:
            raise Exception('Failed to upload {}'.format(uploadFile))
        res = res.json()["detailedImportResult"]

        if len(res["successes"]) == 0:
            if len(res["failures"]) > 0:
                if res["failures"][0]["messages"][0]['code'] == 202:
                    return ['EXISTS', res["failures"][0]["internalId"]]
                else:
                    return ['FAIL', res["failures"][0]["messages"]]
            else:
                return ['FAIL', 'Unknown error']
        else:
            # Upload was successsful
            return ['SUCCESS', res["successes"][0]["internalId"]]

    def set_activity_name(self, session, activity_id, activity_name):
        encoding_headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"} # GC really, really needs this part, otherwise it throws obscure errors like "Invalid signature for signature method HMAC-SHA1"
        #data = {"value": activity_name}
        data = urlencode({"value": activity_name}).encode("UTF-8")
        res = session.post('https://connect.garmin.com/proxy/activity-service-1.0/json/name/%d' % (activity_id), data=data, headers=encoding_headers)

        if res.status_code == 200:
            res = res.json()["display"]["value"]
            if res == activity_name:
                logger.info("activity name set: %s" % activity_name)
                return True
            else:
                logger.error('activity name not set: %s' % res)
                return False
        else:
            logger.error('activity name not set')
            return False


    def _check_activity_type(self, activity_type):
        ''' Fetch valid activity types from Garmin Connect,  compare the given
            activity_type against the 'key' and 'display' values in the dictionary
            of valid activities provided by the GC web site.  Returns the 'key'
            which is used to set activity type throught the web API.
        '''
        # TODO: simplify & cache this as a dict
        rawHierarchy = requests.get("https://connect.garmin.com/proxy/activity-service-1.2/json/activity_types").text
        activityHierarchy = json.loads(rawHierarchy)["dictionary"]

        for activity in activityHierarchy:
            if activity_type.lower() in (activity['key'], activity['display'].lower()):
                logger.info('Activity type found.  Using \'%s\' activity key.' % activity['key'])
                return activity['key']
        logger.error("Activity type not found")
        return False

    def set_activity_type(self, session, activity_id, activity_type):
        activity_key = self._check_activity_type(activity_type)
        if activity_key is None:
            logger.error("Activity type \'%s\' not valid" % activity_type)
            return False

        #data = {"value": activity_type.encode("UTF-8")}
        res = session.post("https://connect.garmin.com/proxy/activity-service-1.2/json/type/" + str(activity_id), data={"value": activity_key})

        if res.status_code == 200:
            res = res.json()
            if "activityType" not in res or res["activityType"]["key"] != activity_key:
                logger.error("Activity type not set")
                return False
            else:
                logger.info("Activity type set")
                return True
        else:
            return False
