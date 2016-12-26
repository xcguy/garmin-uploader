import os.path
import ConfigParser
from garmin_uploader import logger, CONFIG_FILE
from garmin_uploader.api import GarminAPI


class User(object):
    """
    Garmin Connect user model
    Authenticates through web api as a browser
    """
    def __init__(self, username=None, password=None):
        # Authenticated API session
        self.session = None

        # ---- GC login credential order of precedence ----
        # 1) Credentials given on command line
        # 2) Credentials given in config file in current working directory
        # 3) Credentials given in config file in user's home directory
        #
        # Command line overrides all, config in cwd overrides config in home dir
        #
        configCurrentDir = os.path.abspath(os.path.normpath('./' + CONFIG_FILE))
        configHomeDir = os.path.expanduser(os.path.normpath('~/' + CONFIG_FILE))

        if username and password:
            logger.debug('Using credentials from command line.')
            self.username = username
            self.password = password
        elif os.path.isfile(configCurrentDir):
            logger.debug('Using credentials from \'%s\'.' % configCurrentDir)
            config = ConfigParser.RawConfigParser()
            config.read(configCurrentDir)
            self.username = config.get('Credentials', 'username')
            self.password = config.get('Credentials', 'password')
        elif os.path.isfile(configHomeDir):
            logger.debug('Using credentials from \'%s\'.' % configHomeDir)
            config = ConfigParser.RawConfigParser()
            config.read(configHomeDir)
            self.username = config.get('Credentials', 'username')
            self.password = config.get('Credentials', 'password')
        else:
            cwd = os.path.abspath(os.path.normpath('./'))
            homepath = os.path.expanduser(os.path.normpath('~/'))
            msg = '\'%s\' file does not exist in current directory (%s) or home directory (%s).  Use -l option.' % (CONFIG_FILE, cwd, homepath)
            logger.critical(msg)
            raise IOError(msg)

    def authenticate(self):
        """
        Authenticate on Garmin API
        """
        logger.info('Try to login on GarminConnect...')
        logger.debug('Username: {}'.format(self.username))
        logger.debug('Password: {}'.format('*'*len(self.password)))

        api = GarminAPI()
        self.session = api.authenticate(self.username, self.password)
        if self.session:
            logger.info('Login Successful.')
        else:
            msg = 'LOGIN FAILED - please verify your login credentials'
            logger.critical(msg)
            raise(IOError(msg))

    def upload(self, activity):
        """
        Upload an activity once authenticated
        """
        assert self.session is not None

        api = GarminAPI()
        status, id_msg = api.upload_file(self.session, activity.filename)
        nstat = 'N/A'
        tstat = 'N/A'
        if status == 'SUCCESS':
            # Set activity name if specified
            if activity.name:
                if api.set_activity_name(self.session, id_msg, activity.name):
                    nstat = activity.name
                else:
                    nstat = 'FAIL!'
            # Set activity type if specified
            if activity.type:
                if api.set_activity_type(self.session, id_msg, activity.type):
                    tstat =  activity.type
                else:
                    tstat =  'FAIL!'

        print 'File: %s    ID: %s    Status: %s    Name: %s    Type: %s' % \
              (activity.filename, id_msg, status, nstat, tstat)
