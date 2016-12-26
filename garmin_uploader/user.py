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
        try:
            self.session = api.authenticate(self.username, self.password)
            logger.info('Login Successful.')
        except Exception as e:
            logger.critical('Login Failure: {}'.format(e))
            return False

        return True
