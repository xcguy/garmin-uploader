import logging
import platform


# Setup config file name
if platform.system() == 'Windows':
    CONFIG_FILE = 'gupload.ini'
else:
    CONFIG_FILE = '.guploadrc'


# Setup common logger
logger = logging.getLogger('garmin_uploader')
logger.setLevel(level=logging.WARNING)
channel = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s::%(name)s::%(levelname)s::%(message)s')
channel.setFormatter(formatter)
logger.addHandler(channel)
