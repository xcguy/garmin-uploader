"""
Upload Garmin

Handle the operation to upload to the Garmin Connect Website.

"""
#
#
# This version of UploadGarmin.py leverages heavily from work done in the
# tapiriik project (https://github.com/cpfair/tapiriik), particularly the new
# Garmin Connect user authentication using Jasig CAS.
#
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
import time
import re
import logging
from urllib import urlencode

try:
    import simplejson
except ImportError:
    import json as simplejson
import os.path

VALID_GARMIN_FILE_EXTENSIONS = ('.tcx', '.fit', '.gpx')
BINARY_FILE_FORMATS = ('.fit',)

activityTypes = ('running', 'cycling', 'mountain_biking', 'walking', 'hiking',
                 'resort_skiing_snowboarding', 'cross_country_skiing',
                 'skating', 'swimming', 'rowing', 'elliptical',
                 'fitness_equipment', 'other')

# TODO: Clean
URL_HOSTNAME = 'https://connect.garmin.com/gauth/hostname'
URL_LOGIN = 'https://sso.garmin.com/sso/login'
URL_POST_LOGIN = 'https://connect.garmin.com/post-auth/login'
URL_CHECK_LOGIN = 'https://connect.garmin.com/user/username'
URL_HOST_SSO = 'sso.garmin.com'
URL_HOST_CONNECT = 'connect.garmin.com'


class ServiceExceptionScope:
    Account = "account"
    Service = "service"

class ServiceException(Exception):
    def __init__(self, message, scope=ServiceExceptionScope.Service, block=False, user_exception=None):
        Exception.__init__(self, message)
        self.Message = message
        self.UserException = user_exception
        self.Block = block
        self.Scope = scope

    def __str__(self):
        return self.Message + " (user " + str(self.UserException) + " )"

class APIException(ServiceException):
    pass

class UserExceptionType:
    # Account-level exceptions (not a hardcoded thing, just to keep these seperate)
    Authorization = "auth"
    AccountFull = "full"
    AccountExpired = "expired"
    AccountUnpaid = "unpaid" # vs. expired, which implies it was at some point function, via payment or trial or otherwise.

    # Activity-level exceptions
    FlowException = "flow"
    Private = "private"
    NotTriggered = "notrigger"
    MissingCredentials = "credentials_missing" # They forgot to check the "Remember these details" box
    NotConfigured = "config_missing" # Don't think this error is even possible any more.
    StationaryUnsupported = "stationary"
    TypeUnsupported = "type_unsupported"
    DownloadError = "download"
    ListingError = "list" # Cases when a service fails listing, so nothing can be uploaded to it.
    UploadError = "upload"
    SanityError = "sanity"
    Corrupt = "corrupt" # Kind of a scary term for what's generally "some data is missing"
    Untagged = "untagged"
    LiveTracking = "live"
    UnknownTZ = "tz_unknown"
    System = "system"
    Other = "other"

class UserException:
    def __init__(self, type, extra=None, intervention_required=False, clear_group=None):
        self.Type = type
        self.Extra = extra # Unimplemented - displayed as part of the error message.
        self.InterventionRequired = intervention_required # Does the user need to dismiss this error?
        self.ClearGroup = clear_group if clear_group else type # Used to group error messages displayed to the user, and let them clear a group that share a common cause.


class UploadGarmin:
    """
    Upload Garmin

    Handle operation to open to Garmin
    """
    def __init__(self, logLevel = 30):
        self.rawHierarchy = requests.get("https://connect.garmin.com/proxy/activity-service-1.2/json/activity_types").text
        self.activityHierarchy = simplejson.loads(self.rawHierarchy)["dictionary"]
        self._last_req_start = None
        self.msgLogger = logging.getLogger(__name__)
        self.msgLogger.setLevel(level=logLevel)
        self.ch = logging.StreamHandler()
        self.ch.setLevel(level=logLevel)
        self.formatter = logging.Formatter('%(asctime)s::%(name)s::%(levelname)s::%(message)s')
        self.ch.setFormatter(self.formatter)
        self.msgLogger.addHandler(self.ch)
        #logging.basicConfig(level=logLevel)

        # Use same user agent in every request
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent' :  'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:48.0) Gecko/20100101 Firefox/50.0',
        })

        # Empty credentials
        self.username, self.password = None, None

    def _rate_limit(self):
        min_period = 1 # I appear to been banned from Garmin Connect while determining this.
        if not self._last_req_start:
            self._last_req_start = 0.0

        wait_time = max(0, min_period - (time.time() - self._last_req_start))
        time.sleep(wait_time)

        self._last_req_start = time.time()
        self.msgLogger.info("Rate limited for %f" % wait_time)


    def login(self, username, password):
        self.username = username
        self.password = password
        return self.authenticate()

    def authenticate(self):
        # Only try once
        if self.session.cookies:
            return True

        # Request sso hostname
        sso_hostname = None
        resp = self.session.get(URL_HOSTNAME)
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
        res = self.session.get(URL_LOGIN, params=params)
        if res.status_code != 200:
              raise Exception('No login form')

        # Get the login ticket value
        regex = '<input\s+type="hidden"\s+name="lt"\s+value="(?P<lt>\w+)"\s+/>'
        res = re.search(regex, res.text)
        if not res:
              raise Exception('No login ticket')
        login_ticket = res.group('lt')
        self.msgLogger.debug('Found login ticket %s', login_ticket)

        # Login/Password with login ticket
        data = {
          # All parameters are needed
          '_eventId' : 'submit',
          'displayNameRequired' : 'false',
          'embed' : 'true',
          'lt' : login_ticket,
          'username' : self.username,
          'password' : self.password,
        }
        headers = {
          'Host' : URL_HOST_SSO,
        }
        res = self.session.post(URL_LOGIN, params=params, data=data, headers=headers)
        if res.status_code != 200:
            raise Exception('Authentification failed.')

        # Try to find the full post login url in response
        regex = 'var response_url(\s+)= \'.*?ticket=(?P<ticket>[\w\-]+)\''
        params = {}
        matches = re.search(regex, res.text)
        if not matches:
            raise Exception('Missing service ticket')
        params['ticket'] = matches.group('ticket')
        self.msgLogger.debug('Found service ticket %s', params['ticket'])

        # Second auth step
        # Needs a service ticket from previous response
        # Currently gives 3 302 redirects until a 404 :/
        headers = {
            'Host' : URL_HOST_CONNECT,
        }
        res = self.session.get(URL_POST_LOGIN, params=params, headers=headers)
        if res.status_code != 200 and not res.history:
            raise Exception('Second auth step failed.')

        # Check login
        res = self.session.get(URL_CHECK_LOGIN)
        garmin_user = res.json()
        if not garmin_user.get('username', None):
              raise Exception("Login check failed.")
        self.msgLogger.info('Logged in as %s' % (garmin_user['username']))

        return True


    def upload_file(self, uploadFile):

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
        self.authenticate()
        self._rate_limit()
        url = "https://connect.garmin.com/proxy/upload-service-1.1/json/upload/%s" % extension
        res = self.session.post(url, files=files)
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

    def set_workout_name(self, workout_id, workout_name):
        encoding_headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"} # GC really, really needs this part, otherwise it throws obscure errors like "Invalid signature for signature method HMAC-SHA1"
        self.authenticate()
        #data = {"value": workout_name}
        data=urlencode({"value": workout_name}).encode("UTF-8")
        self._rate_limit()
        res = self.session.post('https://connect.garmin.com/proxy/activity-service-1.0/json/name/%d' % (workout_id), data=data, headers=encoding_headers)

        if res.status_code == 200:
            res = res.json()["display"]["value"]
            if res == workout_name:
                self.msgLogger.info("Workout name set: %s" % workout_name)
                return True
            else:
                self.msgLogger.error('Workout name not set: %s' % res)
                return False
        else:
            self.msgLogger.error('Workout name not set')
            return False

    # This for API backward compatability
    def name_workout(self, workout_id, workout_name):
        self.msgLogger.warning('name_workout method deprecated. Use set_workout_name instead.')
        return self.set_workout_name(workout_id, workout_name)


    def _check_activity_type(self, activity_type):
        ''' Fetch valid activity types from Garmin Connect,  compare the given
            activity_type against the 'key' and 'display' values in the dictionary
            of valid activities provided by the GC web site.  Returns the 'key'
            which is used to set activity type throught the web API.
        '''
        for activity in self.activityHierarchy:
            if activity_type.lower() in (activity['key'], activity['display'].lower()):
                self.msgLogger.info('Activity type found.  Using \'%s\' activity key.' % activity['key'])
                return activity['key']
        self.msgLogger.error("Activity type not found")
        return False

    def set_activity_type(self, workout_id, activity_type):
        activity_key = self._check_activity_type(activity_type)
        if activity_key is None:
            self.msgLogger.error("Activity type \'%s\' not valid" % activity_type)
            return False

        self.authenticate()
        #data = {"value": activity_type.encode("UTF-8")}
        self._rate_limit()
        res = self.session.post("https://connect.garmin.com/proxy/activity-service-1.2/json/type/" + str(workout_id), data={"value": activity_key})

        if res.status_code == 200:
            res = res.json()
            if "activityType" not in res or res["activityType"]["key"] != activity_key:
                self.msgLogger.error("Activity type not set")
                return False
            else:
                self.msgLogger.info("Activity type set")
                return True
        else:
            return False


if __name__ == '__main__':
    g = UploadGarmin()
    g.login("username", "password")
    wId = g.upload_tcx('/tmp/a.tcx')
    wInfo = g.upload_file('/tmp/a.tcx')
    g.name_workout(wId, "TestWorkout")
