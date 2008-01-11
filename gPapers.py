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

import commands, dircache, getopt, math, pwd, os, re, string, sys, thread, threading, time, traceback
import desktop, openanything
from datetime import date, datetime
from time import strptime
#from BeautifulSoup 
import BeautifulSoup

RUN_FROM_DIR = os.path.abspath(os.path.dirname(sys.argv[0])) + '/'
PROGRAM = 'gPapers'
VERSION = 'v0.0.0'
GPL = open( RUN_FROM_DIR + 'GPL.txt', 'r' ).read()

ACM_BASE_URL = 'http://portal.acm.org'
IEEE_BASE_URL = 'http://ieeexplore.ieee.org'

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
    print 'trying to fetch:', url
    t = thread.start_new_thread( import_citation, (url,) )
    
def fetch_citations_via_urls(urls):
    for url in urls:
        fetch_citation_via_url(url)
    
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
    
def should_we_reimport_paper(paper):
    gtk.gdk.threads_enter()
    dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_OK_CANCEL, flags=gtk.DIALOG_MODAL )
    #dialog.connect('response', lambda x,y: dialog.destroy())
    dialog.set_markup('This paper already exists in your local library:\n\n<i>"%s"</i>\n(imported on %s)\n\nShould we continue the import, updating/overwriting the previous entry?' % ( paper.title, str(paper.imported.date()) ))
    dialog.set_default_response(gtk.RESPONSE_OK)
    dialog.show_all()
    response = dialog.run()
    dialog.destroy()
    gtk.gdk.threads_leave()
    return response == gtk.RESPONSE_OK

def import_acm_citation(params):
    print thread.get_ident(), 'downloading acm citation:', params['url']
    try:
        print thread.get_ident(), 'parsing...'
        soup = BeautifulSoup.BeautifulSoup( params['data'] )
        
        title = []
        for node in soup.find('a', attrs={'name':'FullText'}).parent.parent.parent.find('td').findAll('strong'):
            title.append(node.string)
        doi = ''
        try: doi = str(soup.find('form', attrs={'name':'popbinder'}).nextSibling.table.findAll('tr')[-1].findAll('td')[-1].a.string)
        except: pass
        paper, created = Paper.objects.get_or_create(
            title = html_strip(''.join(title)),
            doi = doi,
        )
        if created: paper.save()
        else: 
            print thread.get_ident(), 'paper already imported'
            if not should_we_reimport_paper(paper):
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
            source.acm_toc_url = ACM_BASE_URL +'/'+ node.contents[8]['href']
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
                file_url = ACM_BASE_URL +'/'+ node['href']
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
        main_gui.refresh_middle_top_pane_if_viewing_library()
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
            if not should_we_reimport_paper(paper):
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
    
    current_middle_top_pane_refresh_thread_ident = None
    
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
        self.init_paper_information_pane()
        self.refresh_left_pane()        
        main_window.show()

    def init_menu(self):
        self.ui.get_widget('menuitem_quit').connect('activate', gtk.main_quit)
        self.ui.get_widget('menuitem_import_url').connect('activate', self.import_url)
        self.ui.get_widget('menuitem_import_doi').connect('activate', self.import_doi)
        
    def init_search_box(self):
        thread.start_new_thread( self.watch_middle_pane_search, () )
        self.ui.get_widget('refresh_middle_pane_search').connect( 'clicked', lambda x: self.refresh_middle_pane_search() )

    def refresh_middle_pane_search(self):
        self.last_middle_pane_search_string = None
        print 'woot'

    def watch_middle_pane_search(self):
        self.last_middle_pane_search_string = ''
        while True:
            if self.ui.get_widget('middle_pane_search').get_text()!=self.last_middle_pane_search_string:
                self.last_middle_pane_search_string = self.ui.get_widget('middle_pane_search').get_text()
                print 'new search string =', self.last_middle_pane_search_string
                self.select_left_pane_item( self.ui.get_widget('left_pane') )
            time.sleep(1)
        
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
        
    def init_paper_information_pane(self):
        pane = self.ui.get_widget('paper_information_pane')
        # text
        self.paper_information_pane_model = gtk.ListStore( str, str )
        pane.set_model( self.paper_information_pane_model )
        
        pane.connect('size-allocate', self.resize_paper_information_pane )
        
        column = gtk.TreeViewColumn("", gtk.CellRendererText(), markup=0)
        column.set_min_width(64)
        pane.append_column( column )

        column = gtk.TreeViewColumn()
        renderer = gtk.CellRendererText()
        renderer.set_property('editable', True)
        renderer.set_property('wrap-mode', pango.WRAP_WORD)
        renderer.set_property('wrap-width', 500)
        column.pack_start(renderer, expand=True)
        column.add_attribute(renderer, 'markup', 1)
        pane.append_column( column )
        
    def resize_paper_information_pane(self, treeview, o2, width=None):
        if width==None:
            width = treeview.get_column(1).get_width()-16
        treeview.get_column(1).get_cell_renderers()[0].set_property('wrap-width', width)

    def refresh_left_pane(self):
        left_pane = self.ui.get_widget('left_pane')
        self.left_pane_model.clear()
        self.left_pane_model.append( None, ( '<b>My Library</b>', left_pane.render_icon(gtk.STOCK_HOME, gtk.ICON_SIZE_MENU) ) )
#        self.left_pane_model.append( self.left_pane_model.get_iter((0,)), ( 'My Library', ) )
        self.left_pane_model.append( None, ( 'ACM', gtk.gdk.pixbuf_new_from_file( os.path.join( RUN_FROM_DIR, 'icons', 'favicon_acm.ico' ) ) ) )
        self.left_pane_model.append( None, ( 'IEEE', gtk.gdk.pixbuf_new_from_file( os.path.join( RUN_FROM_DIR, 'icons', 'favicon_ieee.ico' ) )  ) )
        self.left_pane_model.append( None, ( 'PubMed', gtk.gdk.pixbuf_new_from_file( os.path.join( RUN_FROM_DIR, 'icons', 'favicon_pubmed.ico' ) )  ) )

    def select_left_pane_item(self, treeview):
        liststore, rows = treeview.get_selection().get_selected_rows()
        self.ui.get_widget('middle_pane_label').set_markup( liststore[rows[0]][0] )
        self.middle_top_pane_model.clear()
        print 'rows[0][0]', rows[0][0]
        if rows[0][0]==0:
            self.current_middle_top_pane_refresh_thread_ident = thread.start_new_thread( self.refresh_middle_pane_from_my_library, () )
        if rows[0][0]==1:
            self.current_middle_top_pane_refresh_thread_ident = thread.start_new_thread( self.refresh_middle_pane_from_acm, () )
        if rows[0][0]==2:
            self.current_middle_top_pane_refresh_thread_ident = thread.start_new_thread( self.refresh_middle_pane_from_ieee, () )
        if rows[0][0]==3:
            self.current_middle_top_pane_refresh_thread_ident = thread.start_new_thread( self.refresh_middle_pane_from_pubmed, () )
        self.select_middle_top_pane_item( self.ui.get_widget('middle_top_pane') )

    def init_middle_top_pane(self):
        middle_top_pane = self.ui.get_widget('middle_top_pane')
        # id, authors, title, journal, year, rating, abstract, icon, import_url
        self.middle_top_pane_model = gtk.ListStore( int, str, str, str, str, int, str, gtk.gdk.Pixbuf, str )
        middle_top_pane.set_model( self.middle_top_pane_model )
        middle_top_pane.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        
        #middle_top_pane.append_column( gtk.TreeViewColumn("", gtk.CellRendererToggle(), active=7) )
        #column = gtk.TreeViewColumn("Title", gtk.CellRendererText(), markup=2)
        #column.set_min_width(256)
        #column.set_expand(True)
        #middle_top_pane.append_column( column )

        column = gtk.TreeViewColumn()
        column.set_title('Title')
        column.set_min_width(256)
        renderer = gtk.CellRendererPixbuf()
        column.pack_start(renderer, expand=False)
        column.add_attribute(renderer, 'pixbuf', 7)
        renderer = gtk.CellRendererText()
        column.pack_start(renderer, expand=True)
        column.add_attribute(renderer, 'markup', 2)        
        middle_top_pane.append_column(column)
        
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
                if renderer.__class__.__name__=='CellRendererText':
                    renderer.set_property( 'ellipsize', pango.ELLIPSIZE_END )
        
        middle_top_pane.connect('cursor-changed', self.select_middle_top_pane_item)
        
    def select_middle_top_pane_item(self, treeview):
        selection = treeview.get_selection()
        liststore, rows = selection.get_selected_rows()
        self.paper_information_pane_model.clear()
        self.ui.get_widget('paper_information_pane').columns_autosize()
        paper_information_toolbar = self.ui.get_widget('paper_information_toolbar')
        paper_information_toolbar.foreach( paper_information_toolbar.remove )
        print 'rows =', rows
        if len(rows)==0:
            pass
        elif len(rows)==1:
            try: paper = Paper.objects.get(id=liststore[rows[0]][0])
            except: paper = None
            if liststore[rows[0]][2]:
                self.paper_information_pane_model.append(( '<b>Title:</b>', liststore[rows[0]][2] ,))
            if liststore[rows[0]][1]:
                self.paper_information_pane_model.append(( '<b>Authors:</b>', liststore[rows[0]][1] ,))
            if liststore[rows[0]][3]:
                self.paper_information_pane_model.append(( '<b>Journal:</b>', liststore[rows[0]][3] ,))
            status = []
            if paper and os.path.isfile( paper.get_full_text_filename() ):
                status.append( 'Full text saved in local library.' )
                button = gtk.ToolButton(gtk.STOCK_OPEN)
                button.set_tooltip_markup('Open the full text of this paper in a new window...')
                button.connect( 'clicked', lambda x: desktop.open( paper.get_full_text_filename() ) )
                paper_information_toolbar.insert( button, -1 )
            if status:
                self.paper_information_pane_model.append(( '<b>Status:</b>', '\n'.join(status) ,))
#            if paper.source:
#                description.append( 'Source:  %s %s (pages: %s)' % ( str(paper.source), paper.source_session, paper.source_pages ) )
            if liststore[rows[0]][6]:
                self.paper_information_pane_model.append(( '<b>Abstract:</b>', liststore[rows[0]][6] ,))
#            description.append( '' )
#            description.append( 'References:' )
#            for ref in paper.reference_set.all():
#                description.append( ref.line )
            #self.ui.get_widget('paper_information_pane').get_buffer().set_text( '\n'.join(description) )
            
            if liststore[rows[0]][8]:
                if paper:
                    print 'url', liststore[rows[0]][8]
                    button = gtk.ToolButton(gtk.STOCK_REFRESH)
                    button.set_tooltip_markup('Re-add this paper to your library...')
                    button.connect( 'clicked', lambda x: fetch_citation_via_url(liststore[rows[0]][8]) )
                    paper_information_toolbar.insert( button, -1 )
                else:
                    print 'url', liststore[rows[0]][8]
                    button = gtk.ToolButton(gtk.STOCK_ADD)
                    button.set_tooltip_markup('Add this paper to your library...')
                    button.connect( 'clicked', lambda x: fetch_citation_via_url(liststore[rows[0]][8]) )
                    paper_information_toolbar.insert( button, -1 )
        else:
            self.paper_information_pane_model.append(( '<b>Number of papers:</b>', len(rows) ,))
            downloadable_paper_urls = set()
            for row in rows:
                if liststore[row][8] and liststore[row][0]==-1:
                    downloadable_paper_urls.add( liststore[row][8] )
            if len(downloadable_paper_urls):
                self.paper_information_pane_model.append(( '<b>Number of new papers:</b>', len(downloadable_paper_urls) ,))
                button = gtk.ToolButton(gtk.STOCK_ADD)
                button.set_tooltip_markup( 'Add new papers (%i) to your library...' % len(downloadable_paper_urls) )
                button.connect( 'clicked', lambda x: fetch_citations_via_urls(downloadable_paper_urls) )
                paper_information_toolbar.insert( button, -1 )
        paper_information_toolbar.show_all()
        
    def echo_objects(self, a=None, b=None, c=None):
        print a,b,c
    
    def update_middle_top_pane_from_row_list_if_we_are_still_the_preffered_thread(self, rows):
        middle_top_pane = self.ui.get_widget('middle_top_pane')
        if self.current_middle_top_pane_refresh_thread_ident==thread.get_ident():
            gtk.gdk.threads_enter()
            self.middle_top_pane_model.clear()
            for row in rows:
                self.middle_top_pane_model.append(row)
            middle_top_pane.columns_autosize()
            gtk.gdk.threads_leave()

    def refresh_middle_pane_from_my_library(self):
        try:
            rows = []
            search_text = self.ui.get_widget('middle_pane_search').get_text()
            if search_text:
                paper_ids = set()
                for s in search_text.split():
                    for paper in Paper.objects.filter( title__icontains=s ):
                        paper_ids.add( paper.id )
                    for paper in Paper.objects.filter( doi__icontains=s ):
                        paper_ids.add( paper.id )
                    for paper in Paper.objects.filter( source_session__icontains=s ):
                        paper_ids.add( paper.id )
                    for paper in Paper.objects.filter( abstract__icontains=s ):
                        paper_ids.add( paper.id )
                    for sponsor in Sponsor.objects.filter( name__icontains=s ):
                        for paper in sponsor.paper_set.all(): paper_ids.add( paper.id )
                    for author in Author.objects.filter( name__icontains=s ):
                        for paper in author.paper_set.all(): paper_ids.add( paper.id )
                    for author in Author.objects.filter( location__icontains=s ):
                        for paper in author.paper_set.all(): paper_ids.add( paper.id )
                    for author in Author.objects.filter( organization__icontains=s ):
                        for paper in author.paper_set.all(): paper_ids.add( paper.id )
                    for author in Author.objects.filter( department__icontains=s ):
                        for paper in author.paper_set.all(): paper_ids.add( paper.id )
                    for source in Source.objects.filter( name__icontains=s ):
                        for paper in source.paper_set.all(): paper_ids.add( paper.id )
                    for source in Source.objects.filter( issue__icontains=s ):
                        for paper in source.paper_set.all(): paper_ids.add( paper.id )
                    for source in Source.objects.filter( location__icontains=s ):
                        for paper in source.paper_set.all(): paper_ids.add( paper.id )
                    for publisher in Publisher.objects.filter( name__icontains=s ):
                        for source in publisher.source_set.all():
                            for paper in source.paper_set.all(): paper_ids.add( paper.id )
                    for reference in Reference.objects.filter( line__icontains=s ):
                        paper_ids.add( reference.paper.id )
                    for reference in Reference.objects.filter( doi__icontains=s ):
                        paper_ids.add( reference.paper.id )
                papers = Paper.objects.in_bulk( list(paper_ids) ).values()
            else:
                papers = Paper.objects.all()
            for paper in papers:
                authors = []
                for author in paper.authors.order_by('id'):
                    authors.append( str(author.name) )
                if os.path.isfile( paper.get_full_text_filename() ):
                    icon = self.ui.get_widget('middle_top_pane').render_icon(gtk.STOCK_DND, gtk.ICON_SIZE_MENU)
                else:
                    icon = None
                if paper.source:
                    journal = paper.source.name
                    pub_year = paper.source.publication_date.year
                else: 
                    journal = ''
                    pub_year = ''
                rows.append( ( 
                    paper.id, ', '.join(authors), 
                    paper.title,
                    journal, 
                    pub_year, 
                    paper.rating, 
                    paper.abstract, 
                    icon, # icon
                    None, # import_url
                ) )
            self.update_middle_top_pane_from_row_list_if_we_are_still_the_preffered_thread(rows)
            self.refresh_my_library_count()
        except:
            traceback.print_exc()
    
    def refresh_middle_top_pane_if_viewing_library(self):
        selection = self.ui.get_widget('left_pane').get_selection()
        liststore, rows = selection.get_selected_rows()
        if rows[0]==(0,):
            self.current_middle_top_pane_refresh_thread_ident = thread.start_new_thread( self.refresh_middle_pane_from_my_library, () )
        else:
            self.refresh_my_library_count()
       
    def refresh_my_library_count(self):
        gtk.gdk.threads_enter()
        selection = self.ui.get_widget('left_pane').get_selection()
        liststore, rows = selection.get_selected_rows()
        liststore.set_value( self.left_pane_model.get_iter((0,)), 0, '<b>My Library</b>  <span foreground="#888888">(%i)</span>' % Paper.objects.count() )
        gtk.gdk.threads_leave()
    
    def refresh_middle_pane_from_acm(self):
        if not self.ui.get_widget('middle_pane_search').get_text(): return
        rows = []
        try:
            params = openanything.fetch( 'http://portal.acm.org/results.cfm?dl=ACM&query=%s' % defaultfilters.urlencode( self.ui.get_widget('middle_pane_search').get_text() ) )
            if params['status']==200 or params['status']==302:
                soup = BeautifulSoup.BeautifulSoup( params['data'] )
                parent_search_table_node = soup.find('div', attrs={'class':'authors'}).parent.parent.parent.parent.parent.parent
                for node in parent_search_table_node.contents[0].findNextSiblings('tr'):
                    node = node.find('table')
                    tds = node.findAll('td')
                    title = html_strip( tds[0].a.string )
                    authors = html_strip( tds[0].div.string )
                    if authors.find(','):
                        first_author = authors[0:authors.find(',')]
                    else:
                        first_author = authors
                    print 'first_author', first_author
                    try:
                        paper = Paper.objects.get( title=title, authors__name__exact=first_author )
                        paper_id = paper.id
                        if os.path.isfile( paper.get_full_text_filename() ):
                            icon = self.ui.get_widget('middle_top_pane').render_icon(gtk.STOCK_DND, gtk.ICON_SIZE_MENU)
                        else:
                            icon = None
                    except:
                        paper = None
                        paper_id = -1
                        icon = None
                    row = ( 
                        paper_id, # paper id 
                        authors, # authors 
                        title, # title 
                        ' '.join( [html_strip(x.string).replace('\n','').replace('\r','').replace('\t','') for x in tds[3].div.contents if x.string] ), # journal 
                        html_strip( tds[1].string )[-4:], # year 
                        0, # ranking
                        ' '.join( [html_strip(x.string).replace('\n','').replace('\r','').replace('\t','') for x in tds[-1].findAll() if x.string] ), # abstract
                        icon, # icon
                        ACM_BASE_URL +'/'+ node.find('a')['href'], # import_url
                    )
                    #print thread.get_ident(), 'row =', row
                    rows.append( row )
                self.update_middle_top_pane_from_row_list_if_we_are_still_the_preffered_thread(rows)
            else:
                gtk.gdk.threads_enter()
                error = gtk.MessageDialog( type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK, flags=gtk.DIALOG_MODAL )
                error.connect('response', lambda x,y: error.destroy())
                error.set_markup('<b>Unable to Search External Repository</b>\n\nHTTP Error code: %i' % params['status'])
                error.show()
                gtk.gdk.threads_leave()
        except:
            traceback.print_exc()
            
    def refresh_middle_pane_from_ieee(self):
        print 'woot'
        if not self.ui.get_widget('middle_pane_search').get_text(): return
        rows = []
        try:
            params = openanything.fetch( 'http://ieeexplore.ieee.org/search/freesearchresult.jsp?history=yes&queryText=%%28%s%%29&imageField.x=0&imageField.y=0' % defaultfilters.urlencode( self.ui.get_widget('middle_pane_search').get_text() ) )
            if params['status']==200 or params['status']==302:
                soup = BeautifulSoup.BeautifulSoup( params['data'].replace('<!-BMS End-->','') )
                for node in soup.findAll( 'td', attrs={'class':'bodyCopyBlackLarge'} ):
                    try:
                        tds = node.findAll( 'td', attrs={'class':'bodyCopyBlackLargeSpaced'} )
                        title = html_strip( tds[1].strong.string )
                        #print 'tds[1].contents', tds[1].contents
                        authors = html_strip( tds[1].contents[2].string )
                        if authors.find(';'):
                            first_author = authors[0:authors.find(';')]
                        else:
                            first_author = authors
                        print 'first_author', first_author
                        try:
                            paper = Paper.objects.get( title=title, authors__name__exact=first_author )
                            paper_id = paper.id
                            if os.path.isfile( paper.get_full_text_filename() ):
                                icon = self.ui.get_widget('middle_top_pane').render_icon(gtk.STOCK_DND, gtk.ICON_SIZE_MENU)
                            else:
                                icon = None
                        except:
                            paper = None
                            paper_id = -1
                            icon = None
                        row = ( 
                            paper_id, # paper id 
                            authors, # authors 
                            title, # title 
                            html_strip( tds[1].contents[5].string ), # journal 
                            '', # year 
                            0, # ranking
                            '', # abstract
                            icon, # icon
                            IEEE_BASE_URL + node.findAll('a', attrs={'class':'bodyCopySpaced'})[0]['href'], # import_url
                        )
                        print thread.get_ident(), 'row =', row
                        rows.append( row )
                    except:
                        traceback.print_exc()
                    
                self.update_middle_top_pane_from_row_list_if_we_are_still_the_preffered_thread(rows)
            else:
                gtk.gdk.threads_enter()
                error = gtk.MessageDialog( type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK, flags=gtk.DIALOG_MODAL )
                error.connect('response', lambda x,y: error.destroy())
                error.set_markup('<b>Unable to Search External Repository</b>\n\nHTTP Error code: %i' % params['status'])
                error.show()
                gtk.gdk.threads_leave()
        except:
            traceback.print_exc()
            
       

if __name__ == "__main__":
    if not os.path.isdir( settings.MEDIA_ROOT ):
        os.mkdir( settings.MEDIA_ROOT )
    if not os.path.isdir( os.path.join( settings.MEDIA_ROOT, 'papers' ) ):
        os.mkdir( os.path.join( settings.MEDIA_ROOT, 'papers' ) )
    global main_gui
    main_gui = MainGUI()
    gtk.main()
        
