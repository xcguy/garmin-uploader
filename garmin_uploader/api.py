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
from garmin_uploader import logger

URL_HOSTNAME = 'https://connect.garmin.com/gauth/hostname'
URL_LOGIN = 'https://sso.garmin.com/sso/login'
URL_POST_LOGIN = 'https://connect.garmin.com/post-auth/login'
URL_CHECK_LOGIN = 'https://connect.garmin.com/user/username'
URL_HOST_SSO = 'sso.garmin.com'
URL_HOST_CONNECT = 'connect.garmin.com'
URL_UPLOAD = 'https://connect.garmin.com/proxy/upload-service-1.1/json/upload'
URL_ACTIVITY_NAME = 'https://connect.garmin.com/proxy/activity-service-1.0/json/name'
URL_ACTIVITY_TYPE = 'https://connect.garmin.com/proxy/activity-service-1.2/json/type'
URL_ACTIVITY_TYPES = 'https://connect.garmin.com/proxy/activity-service-1.2/json/activity_types'


class GarminAPIException(Exception):
    """
    An Exception occured in Garmin API
    """

class GarminAPI:
    """
    Low level Garmin Connect api connector
    """
    activity_types = None

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
            'User-Agent' : 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:48.0) Gecko/20100101 Firefox/50.0',
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


    def upload_activity(self, session, activity):
        """
        Upload an activity on Garmin
        Support multiple formats
        """
        assert activity.id is None

        files = {
            "data": (activity.filename, activity.open()),
        }
        url = '{}/{}'.format(URL_UPLOAD, activity.extension)
        res = session.post(url, files=files)
        if not res.ok:
            raise GarminAPIException('Failed to upload {}'.format(activity))

        if len(res["successes"]) == 0:
            if len(res["failures"]) > 0:
                if res["failures"][0]["messages"][0]['code'] == 202:
                    # Activity already exists
                    return res["failures"][0]["internalId"], False
                else:
                    return GarminAPIException(res["failures"][0]["messages"])
            else:
                raise GarminAPIException('Unknown error')
        else:
            # Upload was successsful
            return res["successes"][0]["internalId"], True

    def set_activity_name(self, session, activity):
        """
        Update the activity name
        """
        assert activity.id is not None
        assert activity.name is not None

        url = '{}/{}'.format(URL_ACTIVITY_NAME, activity.id)
        data = {
            'value' : activity.name,
        }
        res = session.post(url, data=data)
        if not res.ok:
            raise GarminAPIException('Activity name not set')

        new_name = res.json()["display"]["value"]
        if new_name != activity.name:
            raise GarminAPIException('Activity name not set: {}'.format(res.content))

    def load_activity_types(self):
        """
        Fetch valid activity types from Garmin Connect
        """
        # Only fetch once
        if self.activity_types:
            return self.activity_types

        logger.debug('Fecthing activity types')
        resp = requests.get(URL_ACTIVITY_TYPES)
        if not resp.ok:
            raise GarminAPIException('Failed to retrieve activity types')

        # Store as a clean dict, mapping keys and lower case common name
        types = resp.json()["dictionary"]
        out = [(t['key'], t['key']) for t in types]
        out += [(t['display'].lower(), t['key']) for t in types]
        out = dict(out)
        self.activity_types = out

        logger.debug('Fetched {} activity types'.format(len(self.activity_types)))
        return self.activity_types

    def set_activity_type(self, session, activity):
        """
        Update the activity type
        """
        assert activity.id is not None
        assert activity.type is not None

        # Load the corresponding type key on Garmin Connect
        types = self.load_activity_types()
        type_key = types.get(activity.type)
        if type_key is None:
            logger.error("Activity type '{}' not valid".format(activity.type))
            return False

        url = '{}/{}'.format(URL_ACTIVITY_NAME, activity.id)
        data = {
            'value' : type_key,
        }
        res = session.post(url, data)
        if not res.ok:
            raise GarminAPIException('Activity type not set')

        res = res.json()
        if "activityType" not in res or res["activityType"]["key"] != type_key:
            raise GarminAPIException('Activity type not set: {}'.format(res.content))
