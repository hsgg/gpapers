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
from datetime import date, datetime
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
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
from gPapers.models import *

def html_strip(s):
    return str(s).replace('&nbsp;', ' ').strip()

def set_model_from_list(cb, items, index=None):
    """Setup a ComboBox or ComboBoxEntry based on a list of strings, or a list of tuples with the index param."""           
    model = gtk.ListStore(str)
    for i in items:
        if index==None:
            model.append((i,))
        else:
            model.append((i[index],))
    cb.set_model(model)

def fetch_citation_via_url(url):
    t = thread.start_new_thread( import_citation, (url,) )
    
def import_citation(url):
    try:
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
            import_acm_citation(params)
            return
        if params['url'].startswith('http://ieeexplore.ieee.org'):
            if params['url'].find('search/wrapper.jsp')>-1:
                import_ieee_citation( openanything.fetch( params['url'].replace('search/wrapper.jsp','xpls/abs_all.jsp') ) )
            else:
                import_ieee_citation( params )
            return
    except:
        traceback.print_exc()
        gtk.gdk.threads_enter()
        error = gtk.MessageDialog( type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK, flags=gtk.DIALOG_MODAL )
        error.connect('response', lambda x,y: error.destroy())
        error.set_markup('<b>Unknown Error</b>\n\nUnable to download this resource.')
        error.show()
        gtk.gdk.threads_leave()

    gtk.gdk.threads_enter()
    error = gtk.MessageDialog( type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK, flags=gtk.DIALOG_MODAL )
    error.connect('response', lambda x,y: error.destroy())
    error.set_markup('<b>Unknown Source</b>\n\nThis URL is from an unknown citation source.')
    error.show()
    gtk.gdk.threads_leave()
    


def import_acm_citation(params):
    BASE_URL = 'http://portal.acm.org'
    print thread.get_ident(), 'downloading acm citation:', params['url']
    try:
        print thread.get_ident(), 'parsing...'
        soup = BeautifulSoup.BeautifulSoup( params['data'] )
        
        paper, created = Paper.objects.get_or_create(
            title = html_strip(soup.find('title').string),
            doi = str(soup.find('form', attrs={'name':'popbinder'}).nextSibling.table.findAll('tr')[-1].findAll('td')[-1].a.string),
        )
        if created: paper.save()
        else: 
            print thread.get_ident(), 'paper already imported'
            gtk.gdk.threads_enter()
            dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_OK_CANCEL, flags=gtk.DIALOG_MODAL )
            #dialog.connect('response', lambda x,y: dialog.destroy())
            dialog.set_markup('<b>Paper Already Exists</b>\n\nShould we continue the import, updating/overwriting the previous entry?')
            dialog.set_default_response(gtk.RESPONSE_OK)
            dialog.show_all()
            response = dialog.run()
            dialog.destroy()
            gtk.gdk.threads_leave()
            if response == gtk.RESPONSE_CANCEL:
                return

        publisher, created = Publisher.objects.get_or_create(
            name=html_strip( soup.find('div', attrs={'class':'publishers'}).contents[0] ),
        )
        if created: publisher.save()
            
        node = soup.find('strong', text='Source').parent.parent.nextSibling.nextSibling
        source, created = Source.objects.get_or_create(
            name = html_strip(node.contents[1].string),
            issue = html_strip(node.contents[6].string),
            acm_toc_url = BASE_URL +'/'+ node.contents[8]['href'],
            location = html_strip(node.contents[11].string),
            publication_date = date( int( html_strip(node.contents[17].string).replace('Year of Publication: ','') ), 1, 1 ),
            publisher = publisher,
        )
        if created: source.save()
        
        node = soup.find('strong', text='Source').parent.parent.nextSibling.nextSibling
        paper.source = source
        paper.source_session = html_strip(node.contents[13].contents[0]).replace('SESSION: ','')
        paper.source_pages = html_strip(node.contents[15].string).replace('Pages: ','')
        paper.abstract = html_strip( soup.find('p', attrs={'class':'abstract'}).string )
        paper.save()
        
        for node in soup.find('div', attrs={'class':'authors'}).findAll('tr'):
            td1, td2 = node.findAll('td')
            org_and_location = td2.find('small').string
            author, created = Author.objects.get_or_create(
                name = html_strip( td1.find('a').string ),
                organization = html_strip( org_and_location[0:org_and_location.index(',')] ),
                location = html_strip( org_and_location[org_and_location.index(',')+1:] ),
            )
            if created: author.save()
            paper.authors.add( author )
            
        for node in soup.find('div', attrs={'class':'sponsors'}).contents:
            if isinstance( node, BeautifulSoup.NavigableString ):
                sponsor_name = html_strip( node.replace(':','') )
                if sponsor_name:
                    sponsor, created = Sponsor.objects.get_or_create(
                        name = sponsor_name,
                    )
                    if created: sponsor.save()
                    paper.sponsors.add( sponsor )
                    
        for node in soup.find('a', attrs={'name':'references'}).parent.findNextSibling('table').findAll('tr'):
            node = node.findAll('td')[2].div
            if node.string:
                reference, created = Reference.objects.get_or_create(
                    line = html_strip(node.string),
                )
                if created: reference.save()
                paper.references.add( reference )
            else:
                line = ''
                doi = ''
                for a in node.findAll('a'):
                    if a['href'].startswith('citation'):
                        line = html_strip(a.string)
                    if a['href'].startswith('http://dx.doi.org'):
                        doi = html_strip(a.string)
                reference, created = Reference.objects.get_or_create(
                    line = line,
                    doi = doi,
                )
                if created: reference.save()
                paper.references.add( reference )
        
        print thread.get_ident(), 'paper =', paper
    except:
        traceback.print_exc()
    
    print thread.get_ident(), 'done'


def import_ieee_citation(params):
    BASE_URL = 'http://ieeexplore.ieee.org'
    print thread.get_ident(), 'downloading ieee citation:', params['url']
    try:
        print thread.get_ident(), 'parsing...'
        paper = Paper()
        soup = BeautifulSoup.BeautifulSoup( params['data'] )
        paper.title = html_strip(soup.find('span', attrs={'class':'headNavBlueXLarge2'}).string)
        paper.doi = str(soup.find('form', attrs={'name':'popbinder'}).nextSibling.table.findAll('tr')[-1].findAll('td')[-1].a.string)
        node = soup.find('strong', text='Source').parent.parent.nextSibling.nextSibling
        paper.source = Source()
        paper.source.name = html_strip(node.contents[1].string)
        paper.source.issue = html_strip(node.contents[6].string)
        paper.source.toc_url = BASE_URL +'/'+ node.contents[8]['href']
        paper.source.location = html_strip(node.contents[11].string)
        paper.source.publication_date = date( int( html_strip(node.contents[17].string).replace('Year of Publication: ','') ), 1, 1 )
        paper.source.publisher = html_strip( soup.find('div', attrs={'class':'publishers'}).contents[0] )
        paper.source_session = html_strip(node.contents[13].contents[0]).replace('SESSION: ','')
        paper.source_pages = html_strip(node.contents[15].string).replace('Pages: ','')
        for node in soup.find('div', attrs={'class':'authors'}).findAll('tr'):
            td1, td2 = node.findAll('td')
            org_and_location = td2.find('small').string
            author = Author()
            author.name = html_strip( td1.find('a').string )
            author.organization = html_strip( org_and_location[0:org_and_location.index(',')] )
            author.location = html_strip( org_and_location[org_and_location.index(',')+1:] )
            paper.authors.append( author )
        for node in soup.find('div', attrs={'class':'sponsors'}).contents:
            if isinstance( node, BeautifulSoup.NavigableString ):
                sponsor = html_strip( node.replace(':','') )
                if sponsor:
                    paper.sponsors.append( sponsor )
        paper.abstract = html_strip( soup.find('p', attrs={'class':'abstract'}).string )
        for node in soup.find('a', attrs={'name':'references'}).parent.findNextSibling('table').findAll('tr'):
            node = node.findAll('td')[2].div
            if node.string:
                reference = Reference()
                reference.line = html_strip(node.string)
                paper.references.append( reference )
            else:
                title = None
                doi = None
                for a in node.findAll('a'):
                    reference = Reference()
                    if a['href'].startswith('citation'):
                        reference.line = html_strip(a.string)
                    if a['href'].startswith('http://dx.doi.org'):
                        reference.doi = html_strip(a.string)
                paper.references.append( reference )
        
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
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.show_all()
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            fetch_citation_via_url( entry.get_text() )
        dialog.destroy()
    
    def import_doi(self, o):
        dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_OK_CANCEL, flags=gtk.DIALOG_MODAL )
        #dialog.connect('response', lambda x,y: dialog.destroy())
        dialog.set_markup('<b>Import via DOI...</b>\n\nEnter the DOI name (e.g., 10.1000/182) you would like to import:')
        entry = gtk.Entry()
        entry.set_activates_default(True)
        dialog.vbox.pack_start(entry)
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.show_all()
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            fetch_citation_via_url( 'http://dx.doi.org/'+ entry.get_text().strip() )
        dialog.destroy()
    
    def __init__(self):
        gnome.init(PROGRAM, VERSION)
        self.ui = gtk.glade.XML(RUN_FROM_DIR + 'ui.glade')
        main_window = self.ui.get_widget('main_window')
        main_window.connect("delete-event", gtk.main_quit )
        main_window.show()
        self.init_menu()
        self.init_search_box()

    def init_menu(self):
        self.ui.get_widget('menuitem_quit').connect('activate', gtk.main_quit)
        self.ui.get_widget('menuitem_import_url').connect('activate', self.import_url)
        self.ui.get_widget('menuitem_import_doi').connect('activate', self.import_doi)
        
    def init_search_box(self):
        set_model_from_list( self.ui.get_widget('search_source'), ['local','ACM','PubMed'] )
        self.ui.get_widget('search_source').set_active(0)



if __name__ == "__main__":
    MainGUI()
    gtk.main()
        
