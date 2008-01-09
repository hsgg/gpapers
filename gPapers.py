#!/usr/bin/env python

#    gPapers
#    Copyright (C) 2007 Derek Anderson
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License along
#    with this program; if not, write to the Free Software Foundation, Inc.,
#    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import commands, dircache, getopt, math, pwd, os, string, sys, thread, threading, traceback
import desktop, openanything, schema_upgrades
from datetime import datetime
from time import strptime
#from BeautifulSoup 
import BeautifulSoup

RUN_FROM_DIR = os.path.abspath(os.path.dirname(sys.argv[0])) + '/'
PROGRAM = 'gPapers'
VERSION = 'v0.0.0'
GPL = open( RUN_FROM_DIR + 'GPL.txt', 'r' ).read()

# GUI imports
try:
    import gconf
    import pygtk
    pygtk.require("2.0")
    import gobject
    import gtk
    import gtk.glade
    import gnome
    import gnome.ui
    gobject.threads_init()
    gtk.gdk.threads_init()
except:
    traceback.print_exc()
    sys.exit()

# backend imports
try:
    import sqlite3 as sqlite
except:
    from pysqlite2 import dbapi2 as sqlite

def html_strip(s):
    return str(s).replace('&nbsp;', ' ').strip()

class Paper:
    
    title = None
    doi = None
    source = {}
    authors = []
    sponsors = []
    abstract = None
    references = []
    
    def __str__(self):
        return '\n\t'.join( [ self.doi, self.title, str(self.source), str(self.authors), str(self.sponsors), self.abstract, str(self.references) ] )

class DB:

    def get_or_create_db(self):
        base_dir = os.path.join( os.path.expanduser("~"),'.gPapers' )
        papers_dir = os.path.join( base_dir,'papers' )
        if not os.path.isdir( base_dir ):
            os.mkdir(base_dir)
        if not os.path.isdir( papers_dir ):
            os.mkdir(papers_dir)
        
        conn = sqlite.connect( os.path.join( base_dir, 'papers_db.sqlite3' ) )
        c = conn.cursor()
        
        # get our current schema version
        try:
            c.execute("select value from meta where key='schema_version'")
            schema_version = int(c.fetchone()[0])
            print 'schema_version', schema_version
        except sqlite.OperationalError:
            schema_version = 0
            
        while True:
            best_available_upgrade = None
            best_available_upgrade_version = 0
            
            for version, upgrade in schema_upgrades.UPGRADES_SQLITE3.iteritems():
                if version[0]!=schema_version:
                    continue
                if version[1] > best_available_upgrade_version:
                    best_available_upgrade_version = version[1]
                    best_available_upgrade = upgrade
                    
            if best_available_upgrade:
                print 'upgrading db from v%i to v%i' % (schema_version, best_available_upgrade_version)
                for cmd in best_available_upgrade:
                    print '\t', cmd
                    c.execute(cmd)
                conn.commit()
                schema_version = best_available_upgrade_version
            else:
                break
        return conn
    
    def __init__(self):
        self.get_or_create_db()
        
    def fetch_citation_via_url(self, url):
        t = thread.start_new_thread( self.import_citation, (url,) )
        
    def import_citation(self, url):
        params = openanything.fetch(url)
        if params['status']!=200 and params['status']!=302 :
            gtk.gdk.threads_enter()
            error = gtk.MessageDialog( type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK, flags=gtk.DIALOG_MODAL )
            error.connect('response', lambda x,y: error.destroy())
            error.set_markup('<b>Unable to Download</b>\n\nHTTP Error code: %i' % params['status'])
            error.show()
            gtk.gdk.threads_leave()
            return
        if params['url'].startswith('http://portal.acm.org/citation'):
            self.import_acm_citation(params)
            return
        gtk.gdk.threads_enter()
        error = gtk.MessageDialog( type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK, flags=gtk.DIALOG_MODAL )
        error.connect('response', lambda x,y: error.destroy())
        error.set_markup('<b>Unknown Source</b>\n\nThis URL is from an unknown citation source.')
        error.show()
        gtk.gdk.threads_leave()
        
    

    def import_acm_citation(self, params):
        BASE_URL = 'http://portal.acm.org'
        print thread.get_ident(), 'downloading acm citation:', params['url']
        try:
            print thread.get_ident(), 'parsing...'
            paper = Paper()
            soup = BeautifulSoup.BeautifulSoup( params['data'] )
            paper.title = html_strip(soup.find('title').string)
            paper.doi = str(soup.find('form', attrs={'name':'popbinder'}).nextSibling.table.findAll('tr')[-1].findAll('td')[-1].a.string)
            node = soup.find('strong', text='Source').parent.parent.nextSibling.nextSibling
            paper.source = {
                'name': html_strip(node.contents[1].string),
                'issue': html_strip(node.contents[6].string),
                'toc_url': BASE_URL +'/'+ node.contents[8]['href'],
                'location': html_strip(node.contents[11].string),
                'session': html_strip(node.contents[13].contents[0]).replace('SESSION: ',''),
                'pages': html_strip(node.contents[15].string).replace('Pages: ',''),
                'publication_date': html_strip(node.contents[17].string).replace('Year of Publication: ',''),
                'publisher': html_strip( soup.find('div', attrs={'class':'publishers'}).contents[0] ),
            }
            for node in soup.find('div', attrs={'class':'authors'}).findAll('tr'):
                td1, td2 = node.findAll('td')
                org_and_location = td2.find('small').string
                paper.authors.append( {
                    'name': html_strip( td1.find('a').string ),
                    'organization': html_strip( org_and_location[0:org_and_location.index(',')] ),
                    'location': html_strip( org_and_location[org_and_location.index(',')+1:] ),
                } )
            for node in soup.find('div', attrs={'class':'sponsors'}).contents:
                if isinstance( node, BeautifulSoup.NavigableString ):
                    sponsor = html_strip( node.replace(':','') )
                    if sponsor:
                        paper.sponsors.append( sponsor )
            paper.abstract = html_strip( soup.find('p', attrs={'class':'abstract'}).string )
            for node in soup.find('a', attrs={'name':'references'}).parent.findNextSibling('table').findAll('tr'):
                node = node.findAll('td')[2].div
                if node.string:
                    paper.references.append( {
                        'ref': html_strip(node.string),
                        'doi': None,
                    } )
                else:
                    title = None
                    doi = None
                    for a in node.findAll('a'):
                        if a['href'].startswith('citation'):
                            title = a.string
                        if a['href'].startswith('http://dx.doi.org'):
                            doi = a.string
                    paper.references.append( {
                        'ref': html_strip(title),
                        'doi': html_strip(doi),
                    } )
            
            print thread.get_ident(), 'paper =', paper
        except:
            traceback.print_exc()
        
        print thread.get_ident(), 'done'
    

class MainGUI:
    
    def import_url(self, o):
        dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_OK_CANCEL, flags=gtk.DIALOG_MODAL )
        #dialog.connect('response', lambda x,y: dialog.destroy())
        dialog.set_markup('<b>Import URL...</b>\n\nEnter the URL you would like to import:')
        entry = gtk.Entry()
        entry.set_activates_default(True)
        dialog.vbox.pack_start(entry)
        dialog.show_all()
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self.db.fetch_citation_via_url( entry.get_text() )
        dialog.destroy()
    
    def __init__(self):
        self.db = DB()
        gnome.init(PROGRAM, VERSION)
        self.ui = gtk.glade.XML(RUN_FROM_DIR + 'ui.glade')
        main_window = self.ui.get_widget('main_window')
        main_window.connect("delete-event", gtk.main_quit )
        main_window.show()
        self.init_menu()

    def init_menu(self):
        self.ui.get_widget('menuitem_quit').connect('activate', gtk.main_quit)
        self.ui.get_widget('menuitem_import_url').connect('activate', self.import_url)
        



if __name__ == "__main__":
    MainGUI()
    gtk.main()
        
