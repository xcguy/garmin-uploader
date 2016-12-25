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

import uploader
import argparse
import os.path
import ConfigParser
import glob
import csv
from collections import namedtuple
from . import logger, CONFIG_FILE

workoutTuple = namedtuple('workoutTuple', ['filename', 'name', 'type'])


class gupload():
  ''' gupload - Does the work of sorting out command line arguments, building
                the a list of files, then uploading, naming, and setting type
                on the Garmin Connect web site.
  '''

  def __init__(self, options):
    ''' Init logger, parse command line arguments, parse config files
    '''
    logger.setLevel(level=options.verbose * 10)

    self.activityType = options.type
    self.activityName = options.name


    self.workouts = self.load_activities(options.paths)


    # ---- GC login credential order of precedence ----
    # 1) Credentials given on command line
    # 2) Credentials given in config file in current working directory
    # 3) Credentials given in config file in user's home directory
    #
    # Command line overrides all, config in cwd overrides config in home dir
    #
    configCurrentDir = os.path.abspath(os.path.normpath('./' + CONFIG_FILE))
    configHomeDir = os.path.expanduser(os.path.normpath('~/' + CONFIG_FILE))

    if options.username and options.password:
      logger.debug('Using credentials from command line.')
      self.username = options.username
      self.password = options.password
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

  def load_activities(self, paths):
    """
    Load all activities files
    """
    # Sort out file name args given on command line.  Figure out if they are fitness
    # file names, directory names containing fitness files, or names of csv file
    # lists.  Also, expand file name wildcards, if necessary.  Check to see if
    # files exist and if the file extension is valid.  Build lists of fitnes
    # filenames, directories # which will be further searched for files, and
    # list files.

    def is_csv(filename):
      '''
      check to see if file exists and that the file
      extension is .csv
      '''
      extension = os.path.splitext(filename)[1].lower()
      return extension == '.csv' and os.path.isfile(filename)

    def is_activity(filename):
      '''
      check to see if file exists and that the extension is a
      valid activity file accepted by GC.
      '''
      if not os.path.isfile(filename):
        logger.warning("File '{}' does not exist. Skipping...".format(filename))
        return False

      # Get file extension from name
      extension = os.path.splitext(filename)[1].lower()
      logger.debug("File '{}' has extension '{}'".format(filename, extension))

      # Valid file extensions are .tcx, .fit, and .gpx
      if extension in uploader.VALID_GARMIN_FILE_EXTENSIONS:
        logger.debug("File '{}' extension '{}' is valid.".format(filename, extension))
        return True
      else:
        logger.warning("File '{}' extension '{}' is not valid. Skipping file...".format(filename, extension))
        return False

    filenames, listfiles = [], []
    for path in paths:
      path = os.path.realpath(path)
      if is_activity(path):
        # Use file directly
        filenames.append(path)

      elif is_csv(path):
        # Use file directly
        logger.info("List file '{}' will be processed...".format(path))
        filenames.append(path)

      elif os.path.isdir(path):
        # Use files in directory
        # - Does not recursively drill into directories.
        # - Does not search for csv files in directories.
        filenames += [f for f in glob.glob(os.path.join(path, '*')) if is_activity(f)]

    # Activity name given on command line only applies if a single filename
    # is given.  Otherwise, ignore.
    if len(filenames) != 1 and self.activityName:
      logger.warning('-a option valid only when one fitness file given.  Ignoring -a option.')
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
      logger.critical('No valid Files.')
      raise(IOError('No valid files.'))

    return workouts


  def gupload(self):
    ''' gupload - This does the work, building a list of files to upload
        based on command line filename args, wildcard expansion, and list file
        expansion.  It uploads files and sets activity name and activity type.
    '''
    logger.debug('Username: {}'.format(self.username))
    logger.debug('Password: {}'.format('*'*len(self.password)))

    # Create object
    g = uploader.UploadGarmin()

    # LOGIN
    if not g.login(self.username, self.password):
      msg = 'LOGIN FAILED - please verify your login credentials'
      logger.critical(msg)
      raise(IOError(msg))
    else:
      logger.info('Login Successful.')


    # UPLOAD files.  Set description and file type if specified.
    for workout in self.workouts:
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
  base_dir = os.path.realpath(os.path.dirname(__file__))
  parser= argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description='A script to upload .TCX, .GPX, and .FIT files to the Garmin Connect web site.',
    epilog=open(os.path.join(base_dir, 'help.txt')).read(),
  )

  parser.add_argument(
      'paths',
      type=str,
      nargs='+',
      help='Path and name of file(s) to upload, list file name, or directory name containing fitness files.')
  parser.add_argument(
      '-a',
      '--name',
      dest='name',
      type=str,
      help='Sets the activity name for the upload file. This option is ignored if multiple upload files are given.')
  parser.add_argument(
      '-t',
      '--type',
      dest='type',
      type=str,
      help='Sets activity type for ALL files in filename list, except files described inside a csv list file.')
  parser.add_argument(
      '-u',
      '--username',
      dest='username',
      type=str,
      help='Garmin Connect user login')
  parser.add_argument(
      '-p',
      '--password',
      dest='password',
      type=str,
      help='Garmin Connect user password')
  parser.add_argument(
      '-v',
      '--verbose',
      dest='verbose',
      type=int,
      default=3,
      choices=[1, 2, 3, 4, 5] ,
      help='Verbose - select level of verbosity. 1=DEBUG(most verbose), 2=INFO, 3=WARNING, 4=ERROR, 5= CRITICAL(least verbose). [default=3]')

  options = parser.parse_args()

  g = gupload(options)
  g.gupload()
