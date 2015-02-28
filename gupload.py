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

import UploadGarmin
import argparse
import os.path
import ConfigParser
import logging
import platform
import glob
import csv
from collections import namedtuple

workoutTuple = namedtuple('workoutTuple', ['filename', 'name', 'type'])


class gupload():
  ''' gupload - Does the work of sorting out command line arguments, building
                the a list of files, then uploading, naming, and setting type
                on the Garmin Connect web site.
  '''

  def __init__(self, myargs):
    ''' Init logger, parse command line arguments, parse config files
    '''
    self.myargs = myargs
  
    self.logLevel = myargs.v[0]*10
    
    self.msgLogger = logging.getLogger(__name__)
    self.msgLogger.setLevel(level=self.logLevel)
    self.ch = logging.StreamHandler()
    self.ch.setLevel(level=self.logLevel)
    self.formatter = logging.Formatter('%(asctime)s::%(name)s::%(levelname)s::%(message)s')
    self.ch.setFormatter(self.formatter)
    self.msgLogger.addHandler(self.ch)
    
    
    self.fileArgs=myargs.filename
    
    if myargs.t:
      self.activityType = myargs.t[0]
    else:
      self.activityType = None
    
    if myargs.a:
      self.activityName = myargs.a[0]
    else:
      self.activityName = None
    
    
    if platform.system() == 'Windows':
      configFile='gupload.ini'
    else:
      configFile='.guploadrc'
    
    
    # ---- GC login credential order of precedence ----
    # 1) Credentials given on command line with '-l' option
    # 2) Credentials given in config file in current working directory
    # 3) Credentials given in config file in user's home directory
    #
    # Command line overrides all, config in cwd overrides config in home dir
    #
    configCurrentDir=os.path.abspath(os.path.normpath('./' + configFile))
    configHomeDir=os.path.expanduser(os.path.normpath('~/' + configFile))
    
    if myargs.l:
      self.msgLogger.debug('Using credentials from command line.')
      self.username=myargs.l[0]
      self.password=myargs.l[1]
    elif os.path.isfile(configCurrentDir):
      self.msgLogger.debug('Using credentials from \'%s\'.' % configCurrentDir)
      config=ConfigParser.RawConfigParser()
      config.read(configCurrentDir)
      self.username=config.get('Credentials', 'username')
      self.password=config.get('Credentials', 'password')
    elif os.path.isfile(configHomeDir):
      self.msgLogger.debug('Using credentials from \'%s\'.' % configHomeDir)
      config=ConfigParser.RawConfigParser()
      config.read(configHomeDir)
      self.username=config.get('Credentials', 'username')
      self.password=config.get('Credentials', 'password')
    else:
      cwd = os.path.abspath(os.path.normpath('./'))
      homepath = os.path.expanduser(os.path.normpath('~/'))
      msg = '\'%s\' file does not exist in current directory (%s) or home directory (%s).  Use -l option.' % (configFile, cwd, homepath)
      self.msgLogger.critical(msg)
      raise IOError(msg)
  
  
  def obscurePassword(self, password):
    ''' Obscure password for the purpose of logging output '''
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


  def checkFile(self, filename):
    ''' checkFile - check to see if file exists and that the extension is a
        valid fitness file accepted by GC.
    '''
    self.msgLogger.debug('Filename: %s' % filename)
    if os.path.isfile(filename):
      self.msgLogger.debug('File exists.')

      # Get file extension from name
      extension = os.path.splitext(filename)[1].lower()
      self.msgLogger.debug('File Extension: %s' % extension)

      # Valid file extensions are .tcx, .fit, and .gpx
      if extension in UploadGarmin.VALID_GARMIN_FILE_EXTENSIONS:
        self.msgLogger.debug('File \'%s\' extension \'%s\' is valid.' % (filename, extension))
        return True
      else: 
        self.msgLogger.warning('File \'%s\' extension \'%s\' is not valid. Skipping file...' % (filename, extension))
        return False
    else:
      self.msgLogger.warning('File \'%s\' does not exist. Skipping...' % filename)
      return False

  def checkListFile(self, filename):
    ''' checkListFile - check to see if file exists and that the file 
        extension is .csv
    '''
    extension = os.path.splitext(filename)[1].lower()
    if extension == '.csv' and os.path.isfile(filename):
      self.msgLogger.info('List file \'%s\' will be processed...' % filename)
      return True
    else:
      return False

  def gupload(self):
    ''' gupload - This does the work, building a list of files to upload 
        based on command line filename args, wildcard expansion, and list file
        expansion.  It uploads files and sets activity name and activity type.
    '''
    self.msgLogger.debug('Username: ' + self.username)
    self.msgLogger.debug('Password: ' + self.obscurePassword(self.password))
    
    # Sort out file name args given on command line.  Figure out if they are fitness
    # file names, directory names containing fitness files, or names of csv file 
    # lists.  Also, expand file name wildcards, if necessary.  Check to see if 
    # files exist and if the file extension is valid.  Build lists of fitnes 
    # filenames, directories # which will be further searched for files, and 
    # list files.
    
    filenames=[]
    dirnames=[]
    listfiles=[]
    for fileArg in self.fileArgs:
      # Expand any wildcards that may have been passed in if the OS hasn't already
      wildcards = glob.glob(fileArg)
      for wildcard in wildcards:
        # Check for valid fitness file 
        if self.checkFile(fileArg):
          filenames.append(fileArg)
        # Check for valid list file 
        elif self.checkListFile(wildcard):
          listfiles.append(wildcard)
        # Check for directory - will search for files in directories next
        elif os.path.isdir(wildcard):
          dirnames.append(os.path.abspath(wildcard))
  
  
    # Add fitness files from directories given in in command line arg list.  
    # - Does not recursively drill into directories.  
    # - Does not search for csv files in directories. 
    for dirname in dirnames:
      for filename in os.listdir(dirname):
        #extension = os.path.splitext(filename)[1].lower()
        filename = os.path.join(dirname, filename)
        if self.checkFile(filename):
          filenames.append(filename)
    
    
    # Activity name given on command line only applies if a single filename 
    # is given.  Otherwise, ignore.
    if len(filenames) != 1 and self.activityName:
      self.msgLogger.warning('-a option valid only when one fitness file given.  Ignoring -a option.')
      self.activityName = None
    
    workouts = []
    
    # Build workout tuples - a workoutTuple has a filename, name, and file type
    for filename in filenames:
      workouts.append(workoutTuple(filename=filename, name=self.activityName, type=self.activityType))
    
    # Pull in file info from csv files and apend tuples to list
    for listfile in listfiles:
      with open(listfile, 'rb') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
          if self.checkFile(row['filename']):
            workouts.append(workoutTuple(filename=row['filename'], name=row['name'], type=row['type']))
  
  
    if len(workouts) == 0:
      self.msgLogger.critical('No valid Files.')
      raise(IOError('No valid files.'))
    
    
    # Create object
    g = UploadGarmin.UploadGarmin(logLevel=self.logLevel)
    
    # LOGIN
    if not g.login(self.username, self.password):
      msg = 'LOGIN FAILED - please verify your login credentials'
      self.msgLogger.critical(msg)
      raise(IOError(msg))
    else:
      self.msgLogger.info('Login Successful.')
    
    
    # UPLOAD files.  Set description and file type if specified.
    for workout in workouts:
      status, id_msg = g.upload_file(workout.filename)
      nstat = 'N/A'
      tstat = 'N/A'
      if status == 'SUCCESS':
        # Set workout name if specified
        if workout.name:
          if g.set_workout_name(id_msg, workout.name):
            nstat = workout.name
          else:
            nstat = 'FAIL!'
        # Set workout type if specified
        if workout.type:
          if g.set_activity_type(id_msg, workout.type):
            tstat =  workout.type
          else:
            tstat =  'FAIL!'
        
      print 'File: %s    ID: %s    Status: %s    Name: %s    Type: %s' % \
            (workout.filename, id_msg, status, nstat, tstat)


if __name__ == '__main__':
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
  parser.add_argument(
      'filename', 
      type=str, 
      nargs='+', 
      help='Path and name of file(s) to upload, list file name, or directory name containing fitness files.')
  parser.add_argument(
      '-a', 
      type=str, 
      nargs=1, 
      help='Sets the activity name for the upload file. This option is ignored if multiple upload files are given.')
  parser.add_argument(
      '-t', 
      type=str, 
      nargs=1, 
      help='Sets activity type for ALL files in filename list, except files described inside a csv list file.')
  parser.add_argument(
      '-l', 
      type=str, 
      nargs=2, 
      help='Garmin Connect login credentials \'-l username password\'')
  parser.add_argument(
      '-v', 
      type=int, 
      nargs=1, 
      default=[3], 
      choices=[1, 2, 3, 4, 5] , 
      help='Verbose - select level of verbosity. 1=DEBUG(most verbose), 2=INFO, 3=WARNING, 4=ERROR, 5= CRITICAL(least verbose). [default=3]')
  
  myargs = parser.parse_args()
  
  g = gupload(myargs)
  
  g.gupload()
  


