import os, sys

RUN_FROM_DIR = os.path.abspath(os.path.dirname(sys.argv[0])) + '/'


def run_cmds(cmds):
  print
  for cmd in cmds:
    try:
      print '=== RUNNING:', cmd
      os.system(cmd)
    except:
      print '=== FAILED ===\n'
      sys.exit()
  print '=== SUCCESS ===\n'


try:
  import sqlite3
except:
  try:
    from pysqlite2 import dbapi2 as sqlite3
  except:
    #traceback.print_exc()
    print 'could not import required sqlite3 libraries.  try running:'
    print '\tfor ubuntu or debian: sudo apt-get install python-sqlite3'
    print '\tfor redhat: yum install python-sqlite3'
    print 'note that if your distro doesn\'t have python-sqlite3 yet, you can use pysqlite2'
    sys.exit()

try:
  from django.template import defaultfilters
  print 
  print 'note: django provides a web-based administrative tool for your database.  to use it, uncomment the commented-out lines under INSTALLED_APPS in settings.py and run the following:'
  print '     ./manage.py runserver'
  print '    then go to http://127.0.0.1:8000/admin/'
  print
except:
  #traceback.print_exc()
  cmds = [
    'tar -zxf ext/Django-1.0.2-final.tar.gz Django-1.0.2-final/django',
    'mv Django-1.0.2-final/django .',
    'rmdir Django-1.0.2-final',
  ]
  print 'could not import django [http://www.djangoproject.com/].  try to install ourselves? ',
  if sys.stdin.readline().strip().lower()=='yes':
    run_cmds(cmds)
  else:
    print 'try the following:'
    print '\n'.join(cmds)
    sys.exit()

try:
  import deseb
except:
  #traceback.print_exc()
  print 'could not import deseb [http://code.google.com/p/deseb/].  try running (from "%s"):' % RUN_FROM_DIR
  print '\tsvn checkout http://deseb.googlecode.com/svn/trunk/src/deseb'
  sys.exit()
  
try:
  import cairo
except:
  #traceback.print_exc()
  print 'could not import pycairo [http://cairographics.org/pycairo/].  try running (from "%s"):' % RUN_FROM_DIR
  print '\tsudo apt-get install python-cairo'

try:
  import poppler
except:
  cmds = [
    'sudo apt-get install build-essential libpoppler-dev libpoppler-glib-dev python-cairo-dev bzr gnome-common python-dev python-gnome2-dev python-gtk2-dev python-gobject-dev python-pyorbit-dev',
    'tar -zxf ext/pypoppler-0.8.1.tar.gz',
    'cd pypoppler-0.8.1 && sh configure',
    'cd pypoppler-0.8.1 && make',
    'cd pypoppler-0.8.1 && sudo make install',
  ]
  print 'could not import pypoppler.  try to install ourselves? ',
  if sys.stdin.readline().strip().lower()=='yes':
    run_cmds(cmds)
  else:
    print 'try the following:'
    print '\n'.join(cmds)
    sys.exit()


