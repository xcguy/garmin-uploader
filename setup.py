#!/usr/bin/python

try:
	from ez_setup import use_setuptools
	use_setuptools()
except ImportError:
	pass

try:
	from setuptools import setup
except ImportError:
	from distutils.core import setup

setup(
	name = "GcpUploader",
	version = "2014.02.16",
	author = "David E. Lotton",
	author_email = "yellow56@gmail.com",
	description = "A tool to upload FIT, GPX, and TCX files to the Garmin Connect web site.",
	url = "http://sourceforge.net/projects/gcpuploader/",
	license = "GPL",
	keywords = "GARMIN CONNECT GPS TCX GPX FIT UPLOAD UPLOADER",

	package_dir = {'': 'lib'},
	scripts = ["gupload.py"],

	py_modules = ['ez_setup', 'UploadGarmin', 'MultipartPostHandler'],

	install_requires = [
		"logging",
		"simplejson",
	],

	classifiers = [
		"Development Status :: 3 - Alpha",
		"Environment :: Console",
		"Intended Audience :: End Users/Desktop",
		"License :: OSI Approved :: GNU General Public License (GPL)",
		"Programming Language :: Python",
		"Topic :: Utilities",
	],
)
