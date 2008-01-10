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

import commands, dircache, getopt, math, pwd, os, re, string, sys, thread, threading, traceback
import desktop, openanything
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
    import pango
    gobject.threads_init()
    gtk.gdk.threads_init()
except:
    traceback.print_exc()
    sys.exit()

# backend imports
import settings
from django.template import defaultfilters
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
        
        title = []
        for node in soup.find('a', attrs={'name':'FullText'}).parent.parent.parent.find('td').findAll('strong'):
            title.append(node.string)
        paper, created = Paper.objects.get_or_create(
            title = html_strip(''.join(title)),
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
            location = html_strip(node.contents[11].string),
            publication_date = date( int( html_strip(node.contents[17].string).replace('Year of Publication: ','') ), 1, 1 ),
            publisher = publisher,
        )
        if created:
            source.acm_toc_url = BASE_URL +'/'+ node.contents[8]['href']
            source.save()
        
        node = soup.find('strong', text='Source').parent.parent.nextSibling.nextSibling
        paper.source = source
        paper.source_session = html_strip(node.contents[13].contents[0]).replace('SESSION: ','')
        paper.source_pages = html_strip(node.contents[15].string).replace('Pages: ','')
        paper.abstract = html_strip( soup.find('p', attrs={'class':'abstract'}).string )
        paper.save()
        
        for node in soup.find('div', attrs={'class':'authors'}).findAll('tr'):
            td1, td2 = node.findAll('td')
            org_and_location = td2.find('small')
            if org_and_location:
                author, created = Author.objects.get_or_create(
                    name = html_strip( td1.find('a').string ),
                    organization = html_strip( org_and_location.string[0:org_and_location.string.index(',')] ),
                    location = html_strip( org_and_location.string[org_and_location.string.index(',')+1:] ),
                )
            else:
                author, created = Author.objects.get_or_create(
                    name = html_strip( td1.find('a').string ),
                )
            if created: author.save()
            paper.authors.add( author )
            
        node = soup.find('div', attrs={'class':'sponsors'})
        if node:
            for node in node.contents:
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
                    paper = paper,
                )
                if created: reference.save()
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
                    paper = paper,
                )
                if created: reference.save()
        
        
        for node in soup.findAll('a', attrs={'name':'FullText'}):
            if node.contents[1]=='Pdf':
                file_url = BASE_URL +'/'+ node['href']
                print thread.get_ident(), 'downloading paper from', file_url
                params = openanything.fetch(file_url)
                if params['status']==200 or params['status']==302 :
                    ext = params['url'][ params['url'].rfind('.')+1:]
                    if not ext or len(ext)>5:
                        ext = 'pdf'
                    paper.save_full_text_file( defaultfilters.slugify(paper.doi) +'_'+ defaultfilters.slugify(paper.title) +'.'+ defaultfilters.slugify(ext), params['data'] )
                    paper.save()
                    break
                else:
                    print thread.get_ident(), 'error downloading paper:', params
        
        print thread.get_ident(), 'paper =', paper
    except:
        traceback.print_exc()
    
    print thread.get_ident(), 'done'


def import_ieee_citation(params):
    BASE_URL = 'http://portal.acm.org'
    print thread.get_ident(), 'downloading ieee citation:', params['url']
    try:
        print thread.get_ident(), 'parsing...'
        soup = BeautifulSoup.BeautifulSoup( params['data'] )
        print soup.prettify()
        
        print soup.find('span', attrs={'class':'headNavBlueXLarge2'})
        
        paper, created = Paper.objects.get_or_create(
            title = html_strip( soup.find('span', attrs={'class':'headNavBlueXLarge2'}).string ),
            doi = re.search( 'Digital Object Identifier: ([a-zA-Z0-9./]*)<br>', params['data'] ).group(1),
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
            location = html_strip(node.contents[11].string),
            publication_date = date( int( html_strip(node.contents[17].string).replace('Year of Publication: ','') ), 1, 1 ),
            publisher = publisher,
        )
        if created:
            source.acm_toc_url = BASE_URL +'/'+ node.contents[8]['href']
            source.save()
        
        node = soup.find('strong', text='Source').parent.parent.nextSibling.nextSibling
        paper.source = source
        paper.source_session = html_strip(node.contents[13].contents[0]).replace('SESSION: ','')
        paper.source_pages = html_strip(node.contents[15].string).replace('Pages: ','')
        paper.abstract = html_strip( soup.find('p', attrs={'class':'abstract'}).string )
        paper.save()
        
        for node in soup.find('div', attrs={'class':'authors'}).findAll('tr'):
            td1, td2 = node.findAll('td')
            org_and_location = td2.find('small')
            if org_and_location:
                author, created = Author.objects.get_or_create(
                    name = html_strip( td1.find('a').string ),
                    organization = html_strip( org_and_location.string[0:org_and_location.string.index(',')] ),
                    location = html_strip( org_and_location.string[org_and_location.string.index(',')+1:] ),
                )
            else:
                author, created = Author.objects.get_or_create(
                    name = html_strip( td1.find('a').string ),
                )
            if created: author.save()
            paper.authors.add( author )
            
        node = soup.find('div', attrs={'class':'sponsors'})
        if node:
            for node in node.contents:
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
                    paper = paper,
                )
                if created: reference.save()
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
                    paper = paper,
                )
                if created: reference.save()
        
        
        for node in soup.findAll('a', attrs={'name':'FullText'}):
            if node.contents[1]=='Pdf':
                file_url = BASE_URL +'/'+ node['href']
                print thread.get_ident(), 'downloading paper from', file_url
                params = openanything.fetch(file_url)
                if params['status']==200 or params['status']==302 :
                    ext = params['url'][ params['url'].rfind('.')+1:]
                    if not ext or len(ext)>5:
                        ext = 'pdf'
                    paper.save_full_text_file( defaultfilters.slugify(paper.doi) +'_'+ defaultfilters.slugify(paper.title) +'.'+ defaultfilters.slugify(ext), params['data'] )
                    paper.save()
                    break
                else:
                    print thread.get_ident(), 'error downloading paper:', params
        
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
        self.init_menu()
        self.init_search_box()
        self.init_left_pane()
        self.init_middle_top_pane()
        self.refresh_left_pane()        
        main_window.show()

    def init_menu(self):
        self.ui.get_widget('menuitem_quit').connect('activate', gtk.main_quit)
        self.ui.get_widget('menuitem_import_url').connect('activate', self.import_url)
        self.ui.get_widget('menuitem_import_doi').connect('activate', self.import_doi)
        
    def init_search_box(self):
        pass
#        set_model_from_list( self.ui.get_widget('search_source'), ['My Library','ACM','IEEE'] )
#        self.ui.get_widget('search_source').set_active(0)
        
    def init_left_pane(self):
        left_pane = self.ui.get_widget('left_pane')
        # name, icon
        self.left_pane_model = gtk.TreeStore( str, gtk.gdk.Pixbuf, )
        left_pane.set_model( self.left_pane_model )
        
        column = gtk.TreeViewColumn()
        left_pane.append_column(column)
        renderer = gtk.CellRendererPixbuf()
        column.pack_start(renderer, expand=False)
        column.add_attribute(renderer, 'pixbuf', 1)
        renderer = gtk.CellRendererText()
        column.pack_start(renderer, expand=True)
        column.add_attribute(renderer, 'markup', 0)
        
        left_pane.connect('cursor-changed', self.select_left_pane_item)
        
    def refresh_left_pane(self):
        left_pane = self.ui.get_widget('left_pane')
        self.left_pane_model.clear()
        self.left_pane_model.append( None, ( '<b>My Library</b>', left_pane.render_icon(gtk.STOCK_HOME, gtk.ICON_SIZE_MENU) ) )
#        self.left_pane_model.append( self.left_pane_model.get_iter((0,)), ( 'My Library', ) )
        self.left_pane_model.append( None, ( 'ACM', gtk.gdk.pixbuf_new_from_file( os.path.join( RUN_FROM_DIR, 'icons', 'favicon_acm.ico' ) ) ) )
        self.left_pane_model.append( None, ( 'IEEE', gtk.gdk.pixbuf_new_from_file( os.path.join( RUN_FROM_DIR, 'icons', 'favicon_ieee.ico' ) )  ) )
        self.left_pane_model.append( None, ( 'PubMed', gtk.gdk.pixbuf_new_from_file( os.path.join( RUN_FROM_DIR, 'icons', 'favicon_pubmed.ico' ) )  ) )

    def select_left_pane_item(self, treeview):
        selection = treeview.get_selection()
        liststore, rows = selection.get_selected_rows()
        print rows[0]
        print liststore[rows[0]][0]
        self.ui.get_widget('middle_pane_label').set_markup( liststore[rows[0]][0] )
        
        if rows[0]==(0,):
            self.refresh_middle_pane_from_my_library()

    def init_middle_top_pane(self):
        middle_top_pane = self.ui.get_widget('middle_top_pane')
        # id, authors, title, journal, year, rating
        self.middle_top_pane_model = gtk.ListStore( int, str, str, str, str, int )
        middle_top_pane.set_model( self.middle_top_pane_model )
        middle_top_pane.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        
        column = gtk.TreeViewColumn("Title", gtk.CellRendererText(), markup=2)
        column.set_min_width(256)
        column.set_expand(True)
        middle_top_pane.append_column( column )
        column = gtk.TreeViewColumn("Authors", gtk.CellRendererText(), markup=1)
        column.set_min_width(128)
        column.set_expand(True)
        middle_top_pane.append_column( column )
        column = gtk.TreeViewColumn("Journal", gtk.CellRendererText(), markup=3)
        column.set_min_width(128)
        column.set_expand(True)
        middle_top_pane.append_column( column )
        column = gtk.TreeViewColumn("Year", gtk.CellRendererText(), markup=4)
        column.set_min_width(48)
        column.set_expand(False)
        middle_top_pane.append_column( column )
        column = gtk.TreeViewColumn("Rating", gtk.CellRendererText(), markup=5)
        column.set_min_width(64)
        column.set_expand(False)
        middle_top_pane.append_column( column )
        
        for column in middle_top_pane.get_columns():
            column.set_resizable(True)
            column.set_clickable(True)
            #column.connect('clicked', self.sortRows)
            for renderer in column.get_cell_renderers():
                renderer.set_property( 'ellipsize', pango.ELLIPSIZE_END )
        
        middle_top_pane.connect('cursor-changed', self.select_middle_top_pane_item)
        
    def select_middle_top_pane_item(self, treeview):
        selection = treeview.get_selection()
        liststore, rows = selection.get_selected_rows()
        if len(rows)==0:
            self.ui.get_widget('paper_information_pane').get_buffer().set_text( 'nothing selected' )
        elif len(rows)==1:
            print rows[0]
            print liststore[rows[0]][0]
            paper = Paper.objects.get(id=liststore[rows[0]][0])
            description = []
            description.append( 'Title:  '+paper.title )
            description.append( 'Authors:  '+liststore[rows[0]][1] )
            description.append( 'Source:  %s %s (pages: %s)' % ( str(paper.source), paper.source_session, paper.source_pages ) )
            description.append( '' )
            description.append( 'Abstract:  '+paper.abstract )
            description.append( '' )
            description.append( 'References:' )
            for ref in paper.reference_set.all():
                description.append( ref.line )
            self.ui.get_widget('paper_information_pane').get_buffer().set_text( '\n'.join(description) )
            
        else:
            print 'selected', rows
            self.ui.get_widget('paper_information_pane').get_buffer().set_text( '%i papers selected' % len(rows) )

    def refresh_middle_pane_from_my_library(self):
        middle_top_pane = self.ui.get_widget('middle_top_pane')
        self.middle_top_pane_model.clear()
        for paper in Paper.objects.filter(full_text__isnull=False):
            authors = []
            for author in paper.authors.order_by('id'):
                authors.append( str(author.name) )
            self.middle_top_pane_model.append( ( paper.id, ', '.join(authors), paper.title, paper.source.name, paper.source.publication_date.year, paper.rating ) )
        middle_top_pane.columns_autosize()
       

if __name__ == "__main__":
    if not os.path.isdir( settings.MEDIA_ROOT ):
        os.mkdir( settings.MEDIA_ROOT )
    if not os.path.isdir( os.path.join( settings.MEDIA_ROOT, 'papers' ) ):
        os.mkdir( os.path.join( settings.MEDIA_ROOT, 'papers' ) )
    MainGUI()
    gtk.main()
        
