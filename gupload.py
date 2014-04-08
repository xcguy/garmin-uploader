#!/usr/bin/python

###
# Copyright (c) David Lotton 01/2012 <yellow56@gmail.com>
#
# All rights reserved.
#
# License: GNU General Public License (GPL)
#
# THE COPYRIGHT HOLDERS AND/OR OTHER PARTIES PROVIDE THE PROGRAM 
# 'AS IS' WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESSED OR 
# IMPLIED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES 
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE. THE 
# ENTIRE RISK AS TO THE QUALITY AND PERFORMANCE OF THE PROGRAM 
# IS WITH YOU. SHOULD THE PROGRAM PROVE DEFECTIVE, YOU ASSUME 
# THE COST OF ALL NECESSARY SERVICING, REPAIR OR CORRECTION.
#
#
# Name: gupload.py
#
#   Brief:  gupload.py is a utility to upload Garmin fitness
#       GPS files to the connect.garmin.com web site.  
#       It requires that you have a user account on that
#       site.  See help (-h option) for more information.
###

# Make sure you have MultipartPostHandler.py in your path as well
import UploadGarmin
import argparse
import os.path
import ConfigParser
import logging
import platform
import string
import glob
import csv
from collections import namedtuple


workoutTuple = namedtuple('workoutTuple', ['filename', 'name', 'type'])

parser= argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description='A script to upload .TCX, .GPX, and .FIT files to the Garmin Connect web site.',
    epilog="""
    Status Output:
        The script will output a status for each upload file; Success, FAIL, or
	EXISTS.  Definitions are as follows: 

        SUCCESS = Garmin Connect indicated that the upload was successful.
        FAIL = Garmin Connect indicated there was a problem with the upload.
        EXISTS = Garmin Connect indicated that the workout already exists in
                 your account.

    Credentials:
        Username and password credentials may be placed in a configuration file 
        located either in the current working directory, or in the user's home
        directory.  WARNING, THIS IS NOT SECURE. USE THIS OPTION AT YOUR OWN
        RISK.  Username and password are stored as clear text in a file
        format that is consistent with Microsoft (r) INI files. 
    
        The configuration file must contain a [Credentials] section containing 
        'username' and 'password' entries.

        The name of the config file for non-windows platforms is '.guploadrc'
        for windows platforms the config file is named 'gupload.ini'.


        Example \'.guploadrc\' (or \'gupload.ini\' for windows):
            [Credentials]
            username=<myusername>
            password=<mypassword>

        Replace <myusername> and <mypassword> above with your own login 
        credentials.

    Priority of credentials:
        Command line credentials take priority over config files, current 
        directory config file takes priority over a config file in the user's
        home directory.

    CSV List Files:
        A CSV (comma separated values) file can be created to associate files 
        with filename and file type information.  Each record (line) in the csv
        file consists of three fields (filename, name, type).  Fields are 
        separated by commas, and text containing spaces or special characters
        is quoted with double quotes (\").  Empty fields may be left blank, but
        the field separators must be present.  THE FIRST LINE IN THE CSV FILE 
        DEFINES THE ORDER OF THE FIELDS AND *MUST* CONTAIN THE KEY WORDS
        \'filename\', \'name\', and \'type\'.  Most popular spreadsheet 
        programs can save files in CSV format, or files can be easily 
        constructed in your favorite text editor.
        
        Example \'file_list.csv\':
            filename, name, type
            file1.tcx, "10K race", running
            file2.fit, "Training Run", running
            file3.fit, , swimming
        
        Example \'file_list2.csv\' (note field order changed):
            name, filename, type
            "10K race", file1.tcx, running
            "Training Run", file2.fit, running
            , file3.fit, swimming
            
    Activity Types: 
        The following list of activity types should be valid for setting 
        your activity type on Garmin Connect...
        
        running, street_running, track_running, trail_running, 
        treadmill_running, cycling, cyclocross, downhill_biking, indoor_cycling,
        mountain_biking, recumbent_cycling, road_biking, track_cycling, 
        fitness_equipment, elliptical, , indoor_cardio, indoor_rowing, 
        stair_climbing, strength_training, hiking, swimming, lap_swimming, 
        open_water_swimming, walking, casual_walking, speed_walking, transition,
        swimToBikeTransition, bikeToRunTransition, runToBikeTransition, 
        motorcycling, other, backcountry_skiing_snowboarding, boating, 
        cross_country_skiing, driving_general, flying, golf, horseback_riding,
        inline_skating, mountaineering, paddling, resort_skiing_snowboarding, 
        rowing, sailing, skate_skiing, skating, snowmobiling, snow_shoe, 
        stand_up_paddleboarding, whitewater_rafting_kayaking, wind_kite_surfing.
        

    Examples:
        Upload file and set activty name:
            gupload.py -l myusername mypassword -a 'Run at park - 12/23' myfile.tcx

        Upload multiple files:
            gupload.py -l myusername mypassword myfile1.tcx myfile2.tcx myfile3.fit

        Upload multiple files and set activity type for all to running:
            gupload.py -l myusername mypassword -t "running" myfile1.tcx myfile2.tcx

        Upload files using config file for credentials and csv list file:
            gupload.py file_list.csv

        Upload file using config file for credentials, name file, verbose 
        output:
            gupload.py -v 1 -a 'Run at park - 12/23' myfile.tcx
    """)
parser.add_argument('filename', type=str, nargs='+', help='Path and name of file(s) to upload, list file name, or directory name containing fitness files.')
parser.add_argument('-a', type=str, nargs=1, help='Sets the activity name for the upload file. This option is ignored if multiple upload files are given.')
parser.add_argument('-t', type=str, nargs=1, help='Sets activity type for ALL files in filename list, except files described inside a csv list file.')
parser.add_argument('-l', type=str, nargs=2, help='Garmin Connect login credentials \'-l username password\'')
parser.add_argument('-v', type=int, nargs=1, default=[3], choices=[1, 2, 3, 4, 5] , help='Verbose - select level of verbosity. 1=DEBUG(most verbose), 2=INFO, 3=WARNING, 4=ERROR, 5= CRITICAL(least verbose). [default=3]')

myargs = parser.parse_args()
logLevel = myargs.v[0]*10


msgLogger = logging.getLogger(__name__)
msgLogger.setLevel(level=logLevel)
ch = logging.StreamHandler()
ch.setLevel(level=logLevel)
formatter = logging.Formatter('%(asctime)s::%(name)s::%(levelname)s::%(message)s')
ch.setFormatter(formatter)
msgLogger.addHandler(ch)


if myargs.t:
  activityType = myargs.t[0]
else:
  activityType = None

if myargs.a:
  activityName = myargs.a[0]
else:
  activityName = None



if platform.system() == 'Windows':
    configFile='gupload.ini'
else:
    configFile='.guploadrc'


# ----Login Credentials for Garmin Connect----
# If credentials are given on command line, use them.
# If no credentials are given on command line, look in 
# current directory for a .guploadrc file (or gupload.ini
# for windows).  If no .guploadrc/gupload.ini file exists
#  in the current directory look in the user's home directory.
configCurrentDir=os.path.abspath(os.path.normpath('./' + configFile))
configHomeDir=os.path.expanduser(os.path.normpath('~/' + configFile))

if myargs.l:
    msgLogger.debug('Using credentials from command line.')
    username=myargs.l[0]
    password=myargs.l[1]
elif os.path.isfile(configCurrentDir):
    msgLogger.debug('Using credentials from \'%s\'.' % configCurrentDir)
    config=ConfigParser.RawConfigParser()
    config.read(configCurrentDir)
    username=config.get('Credentials', 'username')
    password=config.get('Credentials', 'password')
elif os.path.isfile(configHomeDir):
    msgLogger.debug('Using credentials from \'%s\'.' % configHomeDir)
    config=ConfigParser.RawConfigParser()
    config.read(configHomeDir)
    username=config.get('Credentials', 'username')
    password=config.get('Credentials', 'password')
else:
    cwd = os.path.abspath(os.path.normpath('./'))
    homepath = os.path.expanduser(os.path.normpath('~/'))
    msgLogger.critical('\'%s\' file does not exist in current directory (%s) or home directory (%s).  Use -l option.' % (configFile, cwd, homepath))
    exit(1)

def obscurePassword(password):
    length=len(password)
    if length==1:
        return('*')
    elif length == 2:
        return(password[1] + '*')
    else:
        obscured=password[0]
        for _ in range(1, length-1):
            obscured=obscured+'*'
        obscured=obscured+password[length-1]
        return(obscured)


msgLogger.debug('Username: ' + username)
msgLogger.debug('Password: ' + obscurePassword(password))

def checkFile(filename):
    # checkFile - check to see if file exists, return True 
    # if exsists and file extension is good
    msgLogger.debug('Filename: %s' % filename)
    if os.path.isfile(filename):
        msgLogger.debug('File exists.')

        # Get file extension from name
        extension = os.path.splitext(filename)[1].lower()
        msgLogger.debug('File Extension: %s' % extension)

        # Valid file extensions are .tcx, .fit, and .gpx
        if extension in UploadGarmin.VALID_GARMIN_FILE_EXTENSIONS:
            msgLogger.debug('File \'%s\' extension \'%s\' is valid.' % (filename, extension))
            return True
        else: 
            msgLogger.warning('File \'%s\' extension \'%s\' is not valid. Skipping file...' % (filename, extension))
            return False
    else:
        msgLogger.warning('File \'%s\' does not exist. Skipping...' % filename)
        return False

def checkListFile(filename):
    # checkFile - check to see if file exists, return True 
    # if exsists and file extension is good
    extension = os.path.splitext(filename)[1].lower()
    if extension == '.csv' and os.path.isfile(filename):
        msgLogger.info('List file \'%s\' will be processed...' % filename)
        return True
    else:
        return False

fileArgs=myargs.filename

# Sort out file names given on command line.  Figure out if they are fitness
# file names, directory names containing fitness files, or names of csv file 
# lists.  Also, expand file name wildcards, if necessary.  Check to see if 
# files exist and if the file extension is valid.  Build lists of fitnes 
# filenames, directories # which will be further searched for files, and 
# list files.
filenames=[]
dirnames=[]
listfiles=[]
for fileArg in fileArgs:
    if os.path.isdir(fileArg):
        dirnames.append(os.path.abspath(fileArg))
    elif checkListFile(fileArg):
        listfiles.append(fileArg)
    else:
        if string.find(fileArg, '*') < 0:
            if checkFile(fileArg):
                filenames.append(fileArg)
        else:
            # For Windows we have to expand wildcards ourself
            # Ubuntu Linux appears to do the expansion
            wildcards=glob.glob(fileArg)
            for wildcard in wildcards:
                if checkFile(wildcard):
                    filenames.append(wildcard)

# Add files from directories given in filename list
for dirname in dirnames:
    for filename in os.listdir(dirname):
        extension = os.path.splitext(filename)[1].lower()
        filename = os.path.abspath(dirname + '/' + filename)
        if checkFile(filename):
            filenames.append(filename)
        elif checkListFile(filename):
            listfiles.append(filename)


# Activity name given on command line only applies if a single filename 
# is given.  Otherwise, ignore.
if len(filenames) != 1 and activityName:
    msgLogger.warning('-a option valid only when one fitness file given.  Ignoring -a option.')
    activityName = None

workouts = []

# Build workout tuples - a workoutTuple has a filename, name, and file type
for filename in filenames:
    workouts.append(workoutTuple(filename=filename, name=activityName, type=activityType))

# # Activity name given on command line only applies if a single filename 
# # is given.  Otherwise, ignore.
# if len(workouts)!=1 and activityName:
#     activityName=None
#     msgLogger.debug('Activity Name: %s' % activityName)

# Pull in file info from csv files and apend tuples to list
for listfile in listfiles:
    with open(listfile, 'rb') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if checkFile(row['filename']):
                workouts.append(workoutTuple(filename=row['filename'], name=row['name'], type=row['type']))

if len(workouts) == 0:
    msgLogger.critical('No valid Files.')
    raise(IOError('No valid files.'))


# Create object
g = UploadGarmin.UploadGarmin(logLevel=logLevel)

# LOGIN
if not g.login(username, password):
    msg = 'LOGIN FAILED - please verify your login credentials'
    msgLogger.critical(msg)
    raise(IOError(msg))
else:
    msgLogger.info('Login Successful.')


# UPLOAD files.  Set description and file type if specified.
for workout in workouts:
    status, id_msg = g.upload_file(workout.filename)
    nstat = 'N/A'
    tstat = 'N/A'
    if status == 'SUCCESS':
        if workout.name:
            if g.set_workout_name(id_msg, workout.name):
                nstat = workout.name
            else:
                nstat = 'FAIL!'

        if workout.type:
            if g.set_activity_type(id_msg, workout.type):
                tstat =  workout.type
            else:
                tstat =  'FAIL!'
        
    print 'File: %s    ID: %s    Status: %s    Name: %s    Type: %s' % \
                              (workout.filename, id_msg, status, nstat, tstat)

# # Name workout and/or set activity type. Only available for single file. 
# # Easier to name multiple files from the Garmin Connect site.
# if len(workouts) == 1 and status == 'SUCCESS':
#     if activityName:
#         if g.name_workout(id_msg, activityName):
#             msgLogger.info('Activity name \'%s\' written.' % activityName)
#         else:
#             msgLogger.error('Activity name not written')
#   
#     if activityType:
#         if g.set_activity_type(id_msg, activityType):
#             msgLogger.info('Activity type \'%s\' written.' % activityType)
#         else: 
#             msgLogger.error('Activity type not set')

exit()

