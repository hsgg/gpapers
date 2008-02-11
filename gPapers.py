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

import commands, dircache, getopt, math, os, re, string, sys, thread, threading, time, traceback
from datetime import date, datetime, timedelta
from time import strptime
#from BeautifulSoup 
import BeautifulSoup
from htmlentitydefs import name2codepoint as n2cp


RUN_FROM_DIR = os.path.abspath(os.path.dirname(sys.argv[0])) + '/'
PROGRAM = 'gPapers'
VERSION = 'v0.0.0'
GPL = open( RUN_FROM_DIR + 'GPL.txt', 'r' ).read()

DATE_FORMAT = '%Y-%m-%d'
ACM_BASE_URL = 'http://portal.acm.org'
IEEE_BASE_URL = 'http://ieeexplore.ieee.org'
ACM_USERNAME = None
ACM_PASSWORD = None

# GUI imports
try:
    #import gconf
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
    print 'could not import required GTK libraries.  try running:'
    print '\tfor ubuntu: sudo apt-get install python python-glade2 python-gnome2 python-gconf'
    print '\tfor debian: sudo apt-get install python python-glade2 python-gnome2'
    print '\tfor redhat: yum install pygtk2 gnome-python2-gconf pygtk2-libglade'
    sys.exit()

LEFT_PANE_ADD_TO_PLAYLIST_DND_ACTION = ('add_to_playlist', gtk.TARGET_SAME_APP, 0)
MIDDLE_TOP_PANE_REORDER_PLAYLIST_DND_ACTION = ('reorder_playlist', gtk.TARGET_SAME_WIDGET, 1)

try:
    import sqlite3
except:
    try:
        from pysqlite2 import dbapi2 as sqlite3
    except:
        traceback.print_exc()
        print 'could not import required sqlite3 libraries.  try running:'
        print '\tfor ubuntu or debian: sudo apt-get install python-sqlite3'
        print '\tfor redhat: yum install python-sqlite3'
        print 'note that if your distro doesn\'t have python-sqlite3 yet, you can use pysqlite2'
        sys.exit()

try:
    from django.template import defaultfilters
    print 
    print 'note: django provides a web-based administrative tool for your database.  to use it, run the following...'
    print '         ./manage.py runserver'
    print '      and go to http://127.0.0.1:8000/admin/'
    print
except:
    traceback.print_exc()
    print 'could not import django [http://www.djangoproject.com/].  try running (from "%s"):' % RUN_FROM_DIR
    print '\tsvn co http://code.djangoproject.com/svn/django/trunk/django'
    sys.exit()

try:
    import deseb
except:
    traceback.print_exc()
    print 'could not import deseb [http://code.google.com/p/deseb/].  try running (from "%s"):' % RUN_FROM_DIR
    print '\tsvn checkout http://deseb.googlecode.com/svn/trunk/src/deseb'
    sys.exit()
    
try:
    import cairo
except:
    traceback.print_exc()
    print 'could not import pycairo [http://cairographics.org/pycairo/].  try running (from "%s"):' % RUN_FROM_DIR
    print '\tsudo apt-get install python-cairo'

try:
    import poppler
except:
    traceback.print_exc()
    print 'could not import python-poppler [https://code.launchpad.net/~poppler-python/poppler-python/].  try running (from "%s"):' % RUN_FROM_DIR
    print "(you'll need libpoppler2, libpoppler-dev, libpoppler-glib2, libpoppler-glib-dev)"
    print '\tbzr branch http://bazaar.launchpad.net/~poppler-python/poppler-python/poppler-0.6-experimental'
    print '\tcd poppler-0.6-experimental'
    print '\t./configure'
    print '\tmake'
    print '\tsudo make install'
    sys.exit()


import settings
import desktop, openanything
from django.template import defaultfilters
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
from django.db.models import Q
from gPapers.models import *
import importer



TEST_IMPORT_URLS = [
    'http://citeseer.ist.psu.edu/mihalcea01highly.html',
    'http://www.nature.com/nature/journal/v451/n7179/abs/nature06510.html;jsessionid=5AC0431F416BEBC6E380068E0F75B372',
    'http://portal.acm.org/citation.cfm?id=1073445.1073467&coll=GUIDE&dl=ACM&CFID=15957474&CFTOKEN=97039722#',
    'http://portal.acm.org/citation.cfm?id=1072064.1072107&coll=GUIDE&dl=ACM&CFID=15957143&CFTOKEN=75864759#',
    'http://portal.acm.org/citation.cfm?id=1072228.1072395&coll=GUIDE&dl=ACM&CFID=15944519&CFTOKEN=43144202#',
    'http://citeseer.ist.psu.edu/310506.html',
    'http://portal.acm.org/citation.cfm?id=1073012.1073049&coll=GUIDE&dl=ACM&CFID=54110344&CFTOKEN=66049449',
    'http://www.ncbi.nlm.nih.gov/pubmed/18260159?ordinalpos=1&itool=EntrezSystem2.PEntrez.Pubmed.Pubmed_ResultsPanel.Pubmed_RVDocSum',
    'http://ieeexplore.ieee.org/search/srchabstract.jsp?arnumber=4252372&isnumber=4252351&punumber=16&k2dockey=4252372@ieeejrns&query=%28moldovan%29%3Cin%3Emetadata&pos=4',
]





p_whitespace = re.compile( '[\s]+')
p_doi = re.compile( 'doi *: *(10.[a-z0-9]+/[a-z0-9.]+)', re.IGNORECASE )

def substitute_entity(match):
    ent = match.group(2)
    if match.group(1) == "#":
        return unichr(int(ent))
    else:
        cp = n2cp.get(ent)

        if cp:
            return unichr(cp)
        else:
            return match.group()

def decode_htmlentities(string):
    entity_re = re.compile("&(#?)(\d{1,5}|\w{1,8});")
    return entity_re.subn(substitute_entity, string)[0]

def html_strip(s):
    return decode_htmlentities( p_whitespace.sub( ' ', str(s).replace('&nbsp;', ' ').strip() ) )

def pango_excape(s):
    return s.replace('&','&amp;').replace('>','&gt;').replace('<','&lt;')

def humanize_count(x, s, p, places=1):
    output = []
    if places==-1:
        places = 0
        print_x = False
    else:
        print_x = True
    x = float(x)*math.pow(10, places)
    x = round(x)
    x = x/math.pow(10, places)
    if x-int(x)==0:
        x = int(x)
    if print_x: output.append( str(x) )
    if x==1:
        output.append(s)
    else:
        output.append(p)
    return ' '.join(output)

def truncate_long_str(s, max_length=96):
    s = str(s)
    if len(s)<max_length:
        return s
    else:
        return s[0:max_length] + '...'
    
def get_md5_hexdigest_from_data(data):
    m = md5.new()
    m.update(data)
    return m.hexdigest()

def set_model_from_list(cb, items):
    """Setup a ComboBox or ComboBoxEntry based on a list of (int,str)s."""           
    model = gtk.ListStore(int, str)
    for i in items:
        model.append(i)
    cb.set_model(model)
    cell = gtk.CellRendererText()
    cb.pack_start(cell, True)
    cb.add_attribute(cell, 'text', 1)

def index_of_in_list_of_lists(value, list, column, not_found=-1):
    for i in range(0,len(list)):
        if value==list[i][column]:
            return i
    return not_found
  
def make_all_columns_resizeable_clickable_ellipsize(columns):
    for column in columns:
        column.set_resizable(True)
        column.set_clickable(True)
        #column.connect('clicked', self.sortRows)
        for renderer in column.get_cell_renderers():
            if renderer.__class__.__name__=='CellRendererText':
                renderer.set_property( 'ellipsize', pango.ELLIPSIZE_END )
        
treeview_sort_states = {}
def sort_model_by_column(column, model, model_column_number):
    global treeview_sort_states
    sort_order = treeview_sort_states.get( str(model)+'-sort_order', gtk.SORT_ASCENDING )
    last_sort_column = treeview_sort_states.get( str(model)+'-last_sort_column', None )
    
    if last_sort_column is not None:
       last_sort_column.set_sort_indicator(False)

    # Ascending or descending?
    if last_sort_column == column:
        if sort_order == gtk.SORT_ASCENDING:
            sort_order = gtk.SORT_DESCENDING
        else:
            sort_order = gtk.SORT_ASCENDING
    else:
        sort_order = gtk.SORT_ASCENDING
        treeview_sort_states[str(model)+'-last_sort_column'] = column
    treeview_sort_states[str(model)+'-sort_order'] = sort_order

    rows = [tuple(r) + (i,) for i, r in enumerate(model)]
    rows.sort( key=lambda x:x[model_column_number], reverse=sort_order==gtk.SORT_DESCENDING )
    model.reorder([r[-1] for r in rows])
    
    column.set_sort_indicator(True)
    column.set_sort_order(sort_order)        
     
def fetch_citation_via_url(url):
    print 'trying to fetch:', url
    t = thread.start_new_thread( import_citation, (url,) )

def fetch_citation_via_middle_top_pane_row(row):
    t = thread.start_new_thread( import_citation_via_middle_top_pane_row, (row,) )
    
def fetch_citations_via_urls(urls):
    print 'trying to fetch:', urls
    t = thread.start_new_thread( import_citations, (urls,) )
    
def fetch_citations_via_references(references):
    print 'trying to fetch:', references
    t = thread.start_new_thread( import_citations_via_references, (references,) )

def fetch_citations_via_bibtexs(bibtexs):
    print 'trying to fetch bibtexs...'
    t = thread.start_new_thread( import_citations_via_bibtexs, (bibtexs,) )

def fetch_documents_via_filenames(filenames):
    print 'trying to fetch:', filenames
    t = thread.start_new_thread( import_documents_via_filenames, (bibtexs,) )
    
def import_citations(urls):
    for url in urls:
        import_citation(url, refresh_after=False)
    main_gui.refresh_middle_pane_search()
    
def import_citations_via_references(references):
    for reference in references:
        if not reference.referenced_paper:
            if reference.url_from_referencing_paper:
                reference.referenced_paper = import_citation( reference.url_from_referencing_paper, refresh_after=False )
                reference.save()
        if not reference.referencing_paper:
            if reference.url_from_referenced_paper:
                reference.referenced_paper = import_citation( reference.url_from_referenced_paper, refresh_after=False )
                reference.save()
    main_gui.refresh_middle_pane_search()
    
def import_documents_via_filenames(filenames):
    for filename in filenames:
        data = open(filename,'r').read()
        import_document( filename, data )
    main_gui.refresh_middle_pane_search()    

def import_citations_via_bibtexs(bibtexs):
    
    a_bibtex = []
    
    for line in bibtexs.split('\n'):
        if not line: continue
        if len(a_bibtex) and line.strip().startswith('@'):
            # found new bibtex start
            import_citation_via_bibtex( '\n'.join(a_bibtex) )
            a_bibtex = []
        a_bibtex.append(line)
    if len(a_bibtex):
        # import last found bibtex
        import_citation_via_bibtex( '\n'.join(a_bibtex) )
    
    main_gui.refresh_middle_pane_search()    

def import_citation_via_bibtex(bibtex):
    importer.import_bibtex_from_html(None, bibtex)
    
def import_citation_via_middle_top_pane_row(row):
    # id, authors, title, journal, year, rating, abstract, icon, import_url, doi, created, updated, empty_str, pubmed_id
    
    paper_id = row[0]
    authors = row[1]
    title = row[2]
    journal = row[3]
    year = row[4]
    abstract = row[6]
    import_url = row[8]
    doi = row[9]
    pubmed_id = row[13]
    
    paper, created = importer.get_or_create_paper_via( id=paper_id, doi=doi, pubmed_id=pubmed_id, import_url=import_url, title=title )
        
    if title: paper.title = title
    if abstract: paper.abstract = abstract
    if import_url: paper.import_url = import_url
    if doi: paper.doi = doi
    if pubmed_id: paper.pubmed_id = pubmed_id
    
    paper.save()
    
    import_citation( paper.import_url, paper=paper )
    
    
def import_citation(url, paper=None, refresh_after=True):
    main_gui.active_threads[ thread.get_ident() ] = 'importing: '+ url
    try:
        params = openanything.fetch(url)
        if params['status']!=200 and params['status']!=302 :
            print thread.get_ident(), 'unable to download: %s  (%i)' % ( url, params['status'] )
#            gtk.gdk.threads_enter()
#            error = gtk.MessageDialog( type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK, flags=gtk.DIALOG_MODAL )
#            error.set_markup('<b>Unable to Download Paper</b>\n\nThe following url:\n<i>%s</i>\n\nreturned the HTTP error code: %i' % ( url.replace('&', '&amp;'), params['status'] ))
#            error.run()
#            gtk.gdk.threads_leave()
            return
        if params['url'].startswith('http://portal.acm.org/citation'):
            paper = import_acm_citation(params, paper=paper)
            if paper and refresh_after: main_gui.refresh_middle_pane_search()
            return paper
#        if params['url'].startswith('http://dx.doi.org'):
#            paper = import_unknown_citation(params)
#            if paper and refresh_after: main_gui.refresh_middle_pane_search()
#            return paper
        if params['url'].startswith('http://ieeexplore.ieee.org'):
            if params['url'].find('search/wrapper.jsp')>-1:
                paper = import_ieee_citation( openanything.fetch( params['url'].replace('search/wrapper.jsp','xpls/abs_all.jsp') ), paper=paper )
                if paper and refresh_after: main_gui.refresh_middle_pane_search()
            else:
                paper = import_ieee_citation( params, paper=paper )
                if paper and refresh_after: main_gui.refresh_middle_pane_search()
            return paper
        
        # let's see if there's a pdf somewhere in here...
        paper = import_unknown_citation(params, params['url'], paper=paper)
        if paper and refresh_after: main_gui.refresh_middle_pane_search()
        if paper: return paper
        
    except:
        traceback.print_exc()
        gtk.gdk.threads_enter()
        error = gtk.MessageDialog( type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK, flags=gtk.DIALOG_MODAL )
        error.connect('response', lambda x,y: error.destroy())
        error.set_markup('<b>Unknown Error</b>\n\nUnable to download this resource.')
        error.run()
        gtk.gdk.threads_leave()

    gtk.gdk.threads_enter()
    error = gtk.MessageDialog( type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK, flags=gtk.DIALOG_MODAL )
    error.connect('response', lambda x,y: error.destroy())
    error.set_markup('<b>No Paper Found</b>\n\nThe given URL does not appear to contain or link to any PDF files. (perhaps you have it buy it?) Try downloading the file and adding it using "File &gt;&gt; Import..."\n\n%s' % pango_excape(url))
    error.run()
    gtk.gdk.threads_leave()
    if main_gui.active_threads.has_key( thread.get_ident() ):
        del main_gui.active_threads[ thread.get_ident() ]
    
def should_we_reimport_paper(paper):
    gtk.gdk.threads_enter()
    dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_OK_CANCEL, flags=gtk.DIALOG_MODAL )
    #dialog.connect('response', lambda x,y: dialog.destroy())
    dialog.set_markup('This paper already exists in your local library:\n\n<i>"%s"</i>\n(imported on %s)\n\nShould we continue the import, updating/overwriting the previous entry?' % ( paper.title, str(paper.created.date()) ))
    dialog.set_default_response(gtk.RESPONSE_OK)
    dialog.show_all()
    response = dialog.run()
    dialog.destroy()
    gtk.gdk.threads_leave()
    return response == gtk.RESPONSE_OK

def import_acm_citation(params, paper=None):
    print thread.get_ident(), 'downloading acm citation:', params['url']
    try:
        print thread.get_ident(), 'parsing...'
        
        soup = BeautifulSoup.BeautifulSoup( params['data'] )
        
        title = []
        for node in soup.findAll('td', attrs={'class':'medium-text'})[0].findAll('strong'):
            title.append(node.string)
        try: 
            doi = str(soup.find('form', attrs={'name':'popbinder'}).nextSibling.table.findAll('tr')[-1].findAll('td')[-1].a.string)
            if doi.startswith('http://doi.acm.org/'):
                doi = doi[len('http://doi.acm.org/'):]
        except: doi = ''

        full_text_data = None
        full_text_filename = None
        for node in soup.findAll('a', attrs={'name':'FullText'}):
            if node.contents[1]=='Pdf':
                file_url = ACM_BASE_URL +'/'+ node['href']
                print thread.get_ident(), 'downloading paper from', file_url
                params_file = openanything.fetch(file_url)
                if params_file['status']==200 or params_file['status']==302 :
                    try:
                        ext = params_file['url']
                        if ext.find('?')>-1:
                            ext = file_url[0:ext.find('?')]
                        ext = ext[ ext.rfind('.')+1: ]
                    except:
                        ext = 'unknown'
                    
                    if params_file['data'].startswith('%PDF'):
                        #paper.save_full_text_file( defaultfilters.slugify(paper.doi) +'_'+ defaultfilters.slugify(paper.title) +'.pdf', params_file['data'] )
                        full_text_filename = defaultfilters.slugify(doi) +'_'+ defaultfilters.slugify(title) +'.'+ defaultfilters.slugify(ext)
                        full_text_data = params_file['data']
                    elif params_file['data'].find('<!DOCTYPE')>-1 and params_file['data'].find('logfrm')>-1:
                        # it appears we have an ACM login page...

                        global ACM_USERNAME
                        global ACM_PASSWORD
                        if not ACM_USERNAME:
                            dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_OK_CANCEL, flags=gtk.DIALOG_MODAL )
                            #dialog.connect('response', lambda x,y: dialog.destroy())
                            dialog.set_markup('<b>ACM Login</b>\n\nEnter your ACM username and password:')
                            entry_username = gtk.Entry()
                            entry_password = gtk.Entry()
                            entry_password.set_activates_default(True)
                            dialog.vbox.pack_start(entry_username)
                            dialog.vbox.pack_start(entry_password)
                            dialog.set_default_response(gtk.RESPONSE_OK)
                            gtk.gdk.threads_enter()
                            dialog.show_all()
                            response = dialog.run()
                            if response == gtk.RESPONSE_OK:
                                ACM_USERNAME = entry_username.get_text()
                                ACM_PASSWORD = entry_password.get_text()
                            gtk.gdk.threads_leave()
                            dialog.destroy()
                            
                        post_data = {'username':ACM_USERNAME, 'password':ACM_PASSWORD, 'submit':'Login'}
                        params_login = openanything.fetch('https://portal.acm.org/poplogin.cfm?is=0&amp;dl=ACM&amp;coll=ACM&amp;comp_id=1220288&amp;want_href=delivery%2Ecfm%3Fid%3D1220288%26type%3Dpdf%26CFID%3D50512225%26CFTOKEN%3D24664038&amp;CFID=50512225&amp;CFTOKEN=24664038&amp;td=1200684914991', post_data=post_data, )
                        print "params_login['url']", params_login['url']
                        cfid = re.search( 'CFID=([0-9]*)', params_login['data'] ).group(1)
                        cftoken = re.search( 'CFTOKEN=([0-9]*)', params_login['data'] ).group(1)
                        new_file_url = file_url[0:file_url.find('&CFID=')] + '&CFID=%s&CFTOKEN=%s' % (cfid,cftoken)
                        print 'new_file_url', new_file_url
                        params_file = openanything.fetch(new_file_url)
                        if params_file['status']==200 or params_file['status']==302 :
                            if params_file['data'].startswith('%PDF'):
                                full_text_filename = defaultfilters.slugify(doi) +'_'+ defaultfilters.slugify(title) +'.'+ defaultfilters.slugify(ext)
                                full_text_data = params_file['data']
                            else:
                                print thread.get_ident(), 'error downloading paper - still not a pdf after login:', params_file
                        else:
                            print thread.get_ident(), 'error downloading paper - after login:', params_file
                    else:
                        print thread.get_ident(), 'this does not appear to be a pdf file...'
                        ext = params_file['url'][ params_file['url'].rfind('.')+1:]
                        if not ext or len(ext)>5:
                            ext = 'unknown'
                        #paper.save_full_text_file( defaultfilters.slugify(paper.doi) +'_'+ defaultfilters.slugify(paper.title) +'.'+ defaultfilters.slugify(ext), params_file['data'] )
                        full_text_filename = defaultfilters.slugify(doi) +'_'+ defaultfilters.slugify(title) +'.'+ defaultfilters.slugify(ext)
                        full_text_data = params_file['data']
                    #paper.save()
                    break
                else:
                    print thread.get_ident(), 'error downloading paper:', params_file
        
        if not paper:
            if full_text_data:
                md5_hexdigest = get_md5_hexdigest_from_data( full_text_data )
            else:
                md5_hexdigest = None
            paper, created = importer.get_or_create_paper_via(
                title = html_strip(''.join(title)),
                doi = doi,
                full_text_md5 = md5_hexdigest,
            )
            if created:
                if full_text_filename and full_text_data:
                    paper.save_full_text_file( full_text_filename, full_text_data )
                paper.save()
            else: 
                print thread.get_ident(), 'paper already imported'
                if not should_we_reimport_paper(paper):
                    return
        else:
            paper.title = html_strip(''.join(title))
            paper.doi = doi
            paper.save()
            if full_text_filename and full_text_data:
                paper.save_full_text_file( full_text_filename, full_text_data )
            

        paper.import_url = params['url']
        
        try: paper.source_session = html_strip( re.search( 'SESSION:(.*)', params['data'] ).group(1) )
        except: pass
        try: 
            abstract_node = soup.find('p', attrs={'class':'abstract'}).string
            if abstract_node:
                paper.abstract = html_strip( abstract_node )
            else:
                paper.abstract = ''
        except: pass
        paper.save()
        
        p_bibtex_link = re.compile( "popBibTex.cfm[^']+")
        bibtex_link = p_bibtex_link.search( params['data'] )
        if bibtex_link:
            params_bibtex = openanything.fetch('http://portal.acm.org/'+bibtex_link.group(0))
            if params_bibtex['status']==200 or params_bibtex['status']==302:
                importer.import_bibtex_from_html( paper, params_bibtex['data'] )

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
                    
        if soup.find('a', attrs={'name':'references'}):
            for node in soup.find('a', attrs={'name':'references'}).parent.findNextSibling('table').findAll('tr'):
                node = node.findAll('td')[2].div
                line = None
                doi = ''
                acm_referencing_url = ''
                for a in node.findAll('a'):
                    if a['href'].startswith('citation'):
                        line = html_strip(a.string)
                        acm_referencing_url = ACM_BASE_URL +'/'+ a['href']
                    if a['href'].startswith('http://dx.doi.org'):
                        doi = html_strip(a.string)
                if not line: line = html_strip(node.contents[0])
                reference, created = Reference.objects.get_or_create(
                    line_from_referencing_paper = line,
                    url_from_referencing_paper = acm_referencing_url,
                    doi_from_referencing_paper = doi,
                    referencing_paper = paper,
                )
                if created: reference.save()
        
        if soup.find('a', attrs={'name':'citings'}):
            for node in soup.find('a', attrs={'name':'citings'}).parent.findNextSibling('table').findAll('tr'):
                node = node.findAll('td')[1].div
                if node.string:
                    reference, created = Reference.objects.get_or_create(
                        line_from_referenced_paper = html_strip(node.string),
                        referenced_paper = paper,
                    )
                    if created: reference.save()
                else:
                    line = ''
                    doi = ''
                    for a in node.findAll('a'):
                        if a['href'].startswith('citation'):
                            line = html_strip(a.string)
                            url_from_referenced_paper = ACM_BASE_URL +'/'+ a['href']
                        if a['href'].startswith('http://dx.doi.org'):
                            doi = html_strip(a.string)
                    reference, created = Reference.objects.get_or_create(
                        line_from_referenced_paper = line,
                        url_from_referenced_paper = url_from_referenced_paper,
                        doi_from_referenced_paper = doi,
                        referenced_paper = paper,
                    )
                    if created: reference.save()
        
        
        paper.save()
        print thread.get_ident(), 'imported paper =', paper.doi, paper.title, paper.get_authors_in_order()
        return paper
    except:
        traceback.print_exc()
        if paper:
            paper.delete()


def import_ieee_citation(params, paper=None):
    print thread.get_ident(), 'downloading ieee citation:', params['url']
    try:
        print thread.get_ident(), 'parsing...'
        file = open('import.html','w')
        file.write( params['data'] )
        file.close()
        soup = BeautifulSoup.BeautifulSoup( params['data'].replace('<!-BMS End-->','').replace('<in>','') )
        
        print soup.find('span', attrs={'class':'headNavBlueXLarge2'})

        p_arnumber = re.compile( '<arnumber>[0-9]+</arnumber>', re.IGNORECASE )
        arnumber = p_arnumber.search( params['data'] ).group(0)
        if arnumber:
            print 'arnumber', arnumber
            params_bibtex = openanything.fetch('http://ieeexplore.ieee.org/xpls/citationAct', post_data={ 'dlSelect':'cite_abs', 'fileFormate':'BibTex', 'arnumber':arnumber, 'Submit':'Download'  } )
            print params_bibtex
            if params_bibtex['status']==200 or params_bibtex['status']==302:
                paper = importer.import_bibtex_from_html( paper, params_bibtex['data'] )
        
        if not paper:
            paper, created = importer.get_or_create_paper_via(
                title = html_strip( str(soup.find('title').string).replace('IEEEXplore#','') ),
                doi = re.search( 'Digital Object Identifier: ([a-zA-Z0-9./]*)', params['data'] ).group(1),
            )
            if created: paper.save()
            else: 
                print thread.get_ident(), 'paper already imported'
                if not should_we_reimport_paper(paper):
                    return

#        publisher, created = Publisher.objects.get_or_create(
#            name=html_strip( BeautifulSoup.BeautifulSoup( re.search( 'This paper appears in: (.*)', params['data'] ).group(1) ).a.strong.string ),
#        )
#        print 'publisher', publisher
#        if created: publisher.save()
        
        source_string = html_strip( BeautifulSoup.BeautifulSoup( re.search( 'This paper appears in: (.*)', params['data'] ).group(1) ).a.strong.string )
        try: location = html_strip( re.search( 'Location: (.*)', params['data'] ).group(1) )
        except: location = ''
        source, created = Source.objects.get_or_create(
            name = source_string,
            issue = html_strip(''),
            location = location,
            publication_date = None,
            publisher = None,
        )
        
        paper.import_url = params['url']
        paper.source = source
        paper.source_session = ''
        #paper.source_pages = html_strip( re.search( 'On page(s):(.*)<BR>', params['data'], re.DOTALL ).group(1) ),
        paper.abstract = html_strip( soup.findAll( 'td', attrs={'class':'bodyCopyBlackLargeSpaced'})[0].contents[-1] )
        paper.save()
        
        for node in soup.findAll('a', attrs={'class':'bodyCopy'}):
            if node.contents[0]=='PDF':
                file_url = IEEE_BASE_URL + node['href']
                print thread.get_ident(), 'downloading paper from', file_url
                params = openanything.fetch(file_url)
                if params['status']==200 or params['status']==302:
                    if params['data'].startswith('%PDF'):
                        ext = params['url'][ params['url'].rfind('.')+1:]
                        if not ext or len(ext)>5:
                            ext = 'pdf'
                        paper.save_full_text_file( defaultfilters.slugify(paper.doi) +'_'+ defaultfilters.slugify(paper.title) +'.'+ defaultfilters.slugify(ext), params['data'] )
                        paper.save()
                    else:
                        print thread.get_ident(), 'this isn\'t a pdf file:', params['url']
                    break
                else:
                    print thread.get_ident(), 'error downloading paper:', params
        
        print thread.get_ident(), 'imported paper =', paper.id, paper.doi, paper.title, paper.get_authors_in_order()
        return paper
    except:
        traceback.print_exc()
        if paper:
            paper.delete()

p_html_a = re.compile( "<a [^>]+>" , re.IGNORECASE)
p_html_a_href = re.compile( '''href *= *['"]([^'^"]+)['"]''' , re.IGNORECASE)

def import_unknown_citation(params, orig_url, paper=None):

    if params['data'].startswith('%PDF'):

        # we have a live one!
        try:
            filename = params['url'][ params['url'].rfind('/')+1 : ]
            data = params['data']
            print thread.get_ident(), 'importing paper =', filename
            
            if not paper:
                md5_hexdigest = get_md5_hexdigest_from_data( data )
                paper, created = importer.get_or_create_paper_via( full_text_md5=md5_hexdigest )
                if created:
                    #paper.title = filename
                    paper.save_full_text_file( defaultfilters.slugify(filename.replace('.pdf',''))+'.pdf', data )
                    paper.import_url = orig_url
                    paper.save()
                    print thread.get_ident(), 'imported paper =', filename
                else:
                    print thread.get_ident(), 'paper already exists: paper =', paper.id, paper.doi, paper.title, paper.get_authors_in_order()
            else:
                paper.save_full_text_file( defaultfilters.slugify(filename.replace('.pdf',''))+'.pdf', data )
                paper.import_url = orig_url
                paper.save()
        except:
            traceback.print_exc()
            if paper:
                paper.delete()
                paper = None
    
    else:
    
        # see 
        try:
            web_dir_root = params['url'][: params['url'].find('/',8) ]
            web_dir_current = params['url'][: params['url'].rfind('/') ]
            for a in p_html_a.findall( params['data'] ):
                try: href = p_html_a_href.search(a).group(1)
                except:
                    print thread.get_ident(), 'couldn\'t figure out href from link:', a
                    continue
                if href.find('?')>0:
                    href = href[ : href.find('?') ]
                if not href.lower().startswith('http'):
                    if href.startswith('/'):
                        href = web_dir_root + href
                    else:
                        href = web_dir_current +'/'+ href
                if href.lower().endswith('.pdf'):
                    print "href", href
                    paper = import_unknown_citation( openanything.fetch(href), orig_url, paper=paper )
                    if paper:
                        importer.import_bibtex_from_html( paper, params['data'] )
                        paper.save()
                        break
        except:
            traceback.print_exc()
            if paper:
                paper.delete()
                paper = None
    
    return paper
        

def import_document( filename, data=None ):
    paper = None
    if not data:
        params = openanything.fetch(filename)
        data = params['data']
        if not data:
            print thread.get_ident(), 'could not get', filename
    try:
        print thread.get_ident(), 'importing paper =', filename
        md5_hexdigest = get_md5_hexdigest_from_data( data )
        paper, created = importer.get_or_create_paper_via( full_text_md5=md5_hexdigest )
        if created:
            #paper.title = filename
            paper.save_full_text_file( defaultfilters.slugify(os.path.split(filename)[1].replace('.pdf',''))+'.pdf', data )
            if not data:
                paper.import_url = params['url']
            paper.save()
            print thread.get_ident(), 'imported paper =', filename
        else:
            print thread.get_ident(), 'paper already exists: paper =', paper.id, paper.doi, paper.title, paper.get_authors_in_order()
    except:
        traceback.print_exc()
        if paper:
            paper.delete()


class MainGUI:
    
    current_middle_top_pane_refresh_thread_ident = None
    active_threads = {}
    
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
    
    def import_file(self, o):
        dialog = gtk.FileChooserDialog(title='Select a PDF to import...', parent=None, action=gtk.FILE_CHOOSER_ACTION_OPEN, buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN,gtk.RESPONSE_OK), backend=None)
        #dialog.connect('response', lambda x,y: dialog.destroy())
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_select_multiple(True)
        dialog.show_all()
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            fetch_documents_via_filenames( dialog.get_filenames() )
        dialog.destroy()
    
    def import_bibtex(self, o):
        dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_OK_CANCEL, flags=gtk.DIALOG_MODAL )
        #dialog.connect('response', lambda x,y: dialog.destroy())
        dialog.set_markup('<b>Import BibTex...</b>\n\nEnter the BibTex entry (or entries) you would like to import:')
        entry = gtk.TextView()
        scrolledwindow = gtk.ScrolledWindow()
        scrolledwindow.add(entry)
        scrolledwindow.set_property( 'height-request', 300 )
        dialog.vbox.pack_start(scrolledwindow)
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.show_all()
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            text_buffer = entry.get_buffer()
            fetch_citations_via_bibtexs( text_buffer.get_text( text_buffer.get_start_iter(), text_buffer.get_end_iter() ) )
        dialog.destroy()
    
    def __init__(self):
        gnome.init(PROGRAM, VERSION)
        self.ui = gtk.glade.XML(RUN_FROM_DIR + 'ui.glade')
        main_window = self.ui.get_widget('main_window')
        main_window.connect("delete-event", lambda x,y: sys.exit(0) )
        self.init_menu()
        self.init_search_box()
        self.init_left_pane()
        self.init_my_library_filter_pane()
        self.init_middle_top_pane()
        self.init_paper_information_pane()
        self.init_busy_notifier()
        self.init_bookmark_pane()
        self.init_pdf_preview_pane()
        self.refresh_left_pane()  
        main_window.show()
        
    def init_busy_notifier(self):
        busy_notifier = self.ui.get_widget('busy_notifier')
        busy_notifier.set_from_file( os.path.join( RUN_FROM_DIR, 'icons', 'blank.gif' ) )
        self.busy_notifier_is_running = False
        
        treeview_running_tasks = self.ui.get_widget('treeview_running_tasks')
        # thread_id, text
        self.treeview_running_tasks_model = gtk.ListStore( int, str )
        treeview_running_tasks.set_model( self.treeview_running_tasks_model )
        
        renderer = gtk.CellRendererText()
        renderer.set_property("background", "#fff7e8") # gtk.gdk.color_parse("#fff7e8")
        column = gtk.TreeViewColumn("Running Tasks...", renderer, text=1)
        column.set_expand(True)
        treeview_running_tasks.append_column( column )
        make_all_columns_resizeable_clickable_ellipsize( treeview_running_tasks.get_columns() )
        
        thread.start_new_thread( self.watch_busy_notifier, () )

    def watch_busy_notifier(self):
        while True:
            try:
                if len(self.active_threads):
                    self.treeview_running_tasks_model.clear()
                    for x in self.active_threads.items():
                        self.treeview_running_tasks_model.append( x )
                    if not self.busy_notifier_is_running:
                        self.ui.get_widget('busy_notifier').set_from_file( os.path.join( RUN_FROM_DIR, 'icons', 'process-working.gif' ) )
                        self.busy_notifier_is_running = True
                        self.ui.get_widget('treeview_running_tasks').show()
                else:
                    if self.busy_notifier_is_running:
                        self.ui.get_widget('busy_notifier').set_from_file( os.path.join( RUN_FROM_DIR, 'icons', 'blank.gif' ) )
                        self.busy_notifier_is_running = False
                        self.ui.get_widget('treeview_running_tasks').hide()
            except:
                traceback.print_exc()
            time.sleep(1)
        

    def init_menu(self):
        self.ui.get_widget('menuitem_quit').connect('activate', lambda x: sys.exit(0))
        self.ui.get_widget('menuitem_import_url').connect('activate', self.import_url)
        self.ui.get_widget('menuitem_import_doi').connect('activate', self.import_doi)
        self.ui.get_widget('menuitem_import_file').connect('activate', self.import_file)
        self.ui.get_widget('menuitem_preferences').connect('activate', lambda x: PreferencesGUI())
        self.ui.get_widget('menuitem_import_test_urls').connect('activate', lambda x: fetch_citations_via_urls( TEST_IMPORT_URLS ) )
        self.ui.get_widget('menuitem_import_bibtex').connect('activate', self.import_bibtex)
        
    def init_search_box(self):
        thread.start_new_thread( self.watch_middle_pane_search, () )
        self.ui.get_widget('refresh_middle_pane_search').connect( 'clicked', lambda x: self.refresh_middle_pane_search() )
        self.ui.get_widget('clear_middle_pane_search').connect( 'clicked', lambda x: self.clear_all_search_and_filters() )
        self.ui.get_widget('save_smart_search').connect( 'clicked', lambda x: self.save_smart_search() )
        
    def clear_all_search_and_filters(self):
        self.ui.get_widget('middle_pane_search').set_text('')
        self.ui.get_widget('author_filter').get_selection().unselect_all()
        self.ui.get_widget('source_filter').get_selection().unselect_all()
        self.ui.get_widget('organization_filter').get_selection().unselect_all()
        
    def save_smart_search(self):
        liststore, rows = self.ui.get_widget('left_pane').get_selection().get_selected_rows()
        playlist, created = Playlist.objects.get_or_create(
            title = 'search: <i>%s</i>' % self.ui.get_widget('middle_pane_search').get_text(),
            search_text = self.ui.get_widget('middle_pane_search').get_text(),
            parent = str(rows[0][0])
        )
        if created: playlist.save()
        self.refresh_left_pane()

    def create_playlist(self, ids=None):
        playlist = Playlist.objects.create(
            title = '<i>(new collection)</i>',
            parent = '0'
        )
        if ids:
            for paper in Paper.objects.in_bulk(ids).values():
                playlist.papers.add(paper)
        playlist.save()
        self.refresh_left_pane()

    def refresh_middle_pane_search(self):
        self.last_middle_pane_search_string = None

    def watch_middle_pane_search(self):
        self.last_middle_pane_search_string = ''
        while True:
            if self.last_middle_pane_search_string==None or self.ui.get_widget('middle_pane_search').get_text()!=self.last_middle_pane_search_string:
                self.last_middle_pane_search_string = self.ui.get_widget('middle_pane_search').get_text()
                selection = self.ui.get_widget('left_pane').get_selection()
                liststore, rows = selection.get_selected_rows()
                selection.unselect_all()
                if rows:
                    gtk.gdk.threads_enter()
                    selection.select_path( (rows[0][0],) )
                    gtk.gdk.threads_leave()
            time.sleep(1)
        
    def init_left_pane(self):
        left_pane = self.ui.get_widget('left_pane')
        # name, icon, playlist_id, editable
        self.left_pane_model = gtk.TreeStore( str, gtk.gdk.Pixbuf, int, bool )
        left_pane.set_model( self.left_pane_model )
        
        column = gtk.TreeViewColumn()
        left_pane.append_column(column)
        renderer = gtk.CellRendererPixbuf()
        column.pack_start(renderer, expand=False)
        column.add_attribute(renderer, 'pixbuf', 1)
        renderer = gtk.CellRendererText()
        renderer.connect('edited', self.handle_playlist_edited)
        column.pack_start(renderer, expand=True)
        column.add_attribute(renderer, 'markup', 0)
        column.add_attribute(renderer, 'editable', 3)
        
        left_pane.get_selection().connect('changed', self.select_left_pane_item)
        left_pane.connect('button-press-event', self.handle_left_pane_button_press_event)
        
        left_pane.enable_model_drag_dest( [LEFT_PANE_ADD_TO_PLAYLIST_DND_ACTION], gtk.gdk.ACTION_COPY )
        left_pane.connect('drag-data-received', self.handle_left_pane_drag_data_received_event)
        left_pane.connect("drag-motion", self.handle_left_pane_drag_motion_event)
        
    def init_pdf_preview_pane(self):
        pdf_preview = self.ui.get_widget('pdf_preview')
        self.pdf_preview = {}
        self.pdf_preview['scale'] = None
        pdf_preview.connect("expose-event", self.on_expose_pdf_preview)
        self.ui.get_widget('button_move_previous_page').connect('clicked', lambda x: self.goto_pdf_page( self.pdf_preview['current_page_number']-1 ) )
        self.ui.get_widget('button_move_next_page').connect('clicked', lambda x: self.goto_pdf_page( self.pdf_preview['current_page_number']+1 ) )
        self.ui.get_widget('button_zoom_in').connect('clicked', lambda x: self.zoom_pdf_page( -1.2 ) )
        self.ui.get_widget('button_zoom_out').connect('clicked', lambda x: self.zoom_pdf_page( -.8 ) )
        self.ui.get_widget('button_zoom_normal').connect('clicked', lambda x: self.zoom_pdf_page( 1 ) )
        self.ui.get_widget('button_zoom_best_fit').connect('clicked', lambda x: self.zoom_pdf_page( None ) )

    def refresh_pdf_preview_pane(self):
        pdf_preview = self.ui.get_widget('pdf_preview')
        if self.displayed_paper and os.path.isfile( self.displayed_paper.get_full_text_filename() ):
            self.pdf_preview['document'] = poppler.document_new_from_file ('file://'+ self.displayed_paper.get_full_text_filename(), None)
            self.pdf_preview['n_pages'] = self.pdf_preview['document'].get_n_pages()
            self.pdf_preview['scale'] = None
            self.goto_pdf_page( self.pdf_preview['current_page_number'], new_doc=True )
        else:
            pdf_preview.set_size_request(0,0)
            self.pdf_preview['current_page'] = None
            self.ui.get_widget('button_move_previous_page').set_sensitive( False )
            self.ui.get_widget('button_move_next_page').set_sensitive( False )
            self.ui.get_widget('button_zoom_out').set_sensitive( False )
            self.ui.get_widget('button_zoom_in').set_sensitive( False )
            self.ui.get_widget('button_zoom_normal').set_sensitive( False )
            self.ui.get_widget('button_zoom_best_fit').set_sensitive( False )
        pdf_preview.queue_draw()
        
    def goto_pdf_page(self, page_number, new_doc=False):
        if self.displayed_paper:
            if not new_doc and self.pdf_preview.get('current_page') and self.pdf_preview['current_page_number']==page_number:
                return
            if page_number<0: page_number = 0
            pdf_preview = self.ui.get_widget('pdf_preview')
            self.pdf_preview['current_page_number'] = page_number
            self.pdf_preview['current_page'] = self.pdf_preview['document'].get_page( self.pdf_preview['current_page_number'] )
            if self.pdf_preview['current_page']:
                self.pdf_preview['width'], self.pdf_preview['height'] = self.pdf_preview['current_page'].get_size()
                self.ui.get_widget('button_move_previous_page').set_sensitive( page_number>0 )
                self.ui.get_widget('button_move_next_page').set_sensitive( page_number<self.pdf_preview['n_pages']-1 )
                self.zoom_pdf_page( self.pdf_preview['scale'], redraw=False )
            else:
                self.ui.get_widget('button_move_previous_page').set_sensitive( False )
                self.ui.get_widget('button_move_next_page').set_sensitive( False )
            pdf_preview.queue_draw()
        else:
            self.ui.get_widget('button_move_previous_page').set_sensitive( False )
            self.ui.get_widget('button_move_next_page').set_sensitive( False )

    def zoom_pdf_page(self, scale, redraw=True):
        """None==auto-size, negative means relative, positive means fixed"""
        if self.displayed_paper:
            if redraw and self.pdf_preview.get('current_page') and self.pdf_preview['scale']==scale:
                return
            pdf_preview = self.ui.get_widget('pdf_preview')
            auto_scale = (pdf_preview.get_parent().get_allocation().width-2.0) / self.pdf_preview['width']
            if scale==None:
                scale = auto_scale
            else:
                if scale<0:
                    if self.pdf_preview['scale']==None: self.pdf_preview['scale'] = auto_scale
                    scale = self.pdf_preview['scale'] = self.pdf_preview['scale'] * -scale
                else:
                    self.pdf_preview['scale'] = scale
            pdf_preview.set_size_request(int(self.pdf_preview['width']*scale), int(self.pdf_preview['height']*scale))
            self.ui.get_widget('button_zoom_out').set_sensitive( scale>0.3 )
            self.ui.get_widget('button_zoom_in').set_sensitive( True )
            self.ui.get_widget('button_zoom_normal').set_sensitive( True )
            self.ui.get_widget('button_zoom_best_fit').set_sensitive( True )
            if redraw: pdf_preview.queue_draw()
            return scale
        else:
            pass
        
    def on_expose_pdf_preview(self, widget, event):
        if not self.displayed_paper or not self.pdf_preview.get('current_page'): return
        cr = widget.window.cairo_create()
        cr.set_source_rgb(1, 1, 1)
        scale = self.pdf_preview['scale']
        if scale==None:
            scale = (self.ui.get_widget('pdf_preview').get_parent().get_allocation().width-2.0) / self.pdf_preview['width']
        if scale != 1:
            cr.scale(scale, scale)
        cr.rectangle(0, 0, self.pdf_preview['width'], self.pdf_preview['height'])
        cr.fill()
        self.pdf_preview['current_page'].render(cr)
        
    def init_my_library_filter_pane(self):
        
        author_filter = self.ui.get_widget('author_filter')
        # id, author, paper_count
        self.author_filter_model = gtk.ListStore( int, str, int )
        author_filter.set_model( self.author_filter_model )
        author_filter.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        column = gtk.TreeViewColumn("Author", gtk.CellRendererText(), text=1)
        column.set_min_width(128)
        column.set_expand(True)
        column.connect('clicked', sort_model_by_column, self.author_filter_model, 1)
        author_filter.append_column( column )
        column = gtk.TreeViewColumn("Papers", gtk.CellRendererText(), text=2)
        column.connect('clicked', sort_model_by_column, self.author_filter_model, 2)
        author_filter.append_column( column )
        make_all_columns_resizeable_clickable_ellipsize( author_filter.get_columns() )
        author_filter.get_selection().connect( 'changed', lambda x: thread.start_new_thread( self.refresh_middle_pane_from_my_library, (False,) ) )
        author_filter.connect('row-activated', self.handle_author_filter_row_activated )
        author_filter.connect('button-press-event', self.handle_author_filter_button_press_event)

        organization_filter = self.ui.get_widget('organization_filter')
        # id, org, author_count, paper_count
        self.organization_filter_model = gtk.ListStore( int, str, int, int )
        organization_filter.set_model( self.organization_filter_model )
        organization_filter.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        column = gtk.TreeViewColumn("Organization", gtk.CellRendererText(), text=1)
        column.set_min_width(128)
        column.set_expand(True)
        column.connect('clicked', sort_model_by_column, self.organization_filter_model, 1)
        organization_filter.append_column( column )
        column = gtk.TreeViewColumn("Authors", gtk.CellRendererText(), text=2)
        column.connect('clicked', sort_model_by_column, self.organization_filter_model, 2)
        organization_filter.append_column( column )
        column = gtk.TreeViewColumn("Papers", gtk.CellRendererText(), text=3)
        column.connect('clicked', sort_model_by_column, self.organization_filter_model, 3)
        organization_filter.append_column( column )
        make_all_columns_resizeable_clickable_ellipsize( organization_filter.get_columns() )
        organization_filter.get_selection().connect( 'changed', lambda x: thread.start_new_thread( self.refresh_middle_pane_from_my_library, (False,) ) )
        organization_filter.connect('row-activated', self.handle_organization_filter_row_activated )
        organization_filter.connect('button-press-event', self.handle_organization_filter_button_press_event)

        source_filter = self.ui.get_widget('source_filter')
        # id, name, issue, location, publisher, date
        self.source_filter_model = gtk.ListStore( int, str, str, str, str, str )
        source_filter.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        source_filter.set_model( self.source_filter_model )
        column = gtk.TreeViewColumn("Source", gtk.CellRendererText(), text=1)
        column.set_min_width(128)
        column.set_expand(True)
        column.connect('clicked', sort_model_by_column, self.source_filter_model, 1)
        source_filter.append_column( column )
        column = gtk.TreeViewColumn("Issue", gtk.CellRendererText(), text=2)
        column.connect('clicked', sort_model_by_column, self.source_filter_model, 2)
        source_filter.append_column( column )
        column = gtk.TreeViewColumn("Location", gtk.CellRendererText(), text=3)
        column.connect('clicked', sort_model_by_column, self.source_filter_model, 3)
        source_filter.append_column( column )
        column = gtk.TreeViewColumn("Publisher", gtk.CellRendererText(), text=4)
        column.connect('clicked', sort_model_by_column, self.source_filter_model, 4)
        source_filter.append_column( column )
        make_all_columns_resizeable_clickable_ellipsize( source_filter.get_columns() )
        source_filter.get_selection().connect( 'changed', lambda x: thread.start_new_thread( self.refresh_middle_pane_from_my_library, (False,) ) )
        source_filter.connect('row-activated', self.handle_source_filter_row_activated )
        source_filter.connect('button-press-event', self.handle_source_filter_button_press_event)

    def refresh_my_library_filter_pane(self):

        self.author_filter_model.clear()
        for author in Author.objects.order_by('name'):
            self.author_filter_model.append( ( author.id, author.name, author.paper_set.count() ) )

        self.organization_filter_model.clear()
        for organization in Organization.objects.order_by('name'):
            self.organization_filter_model.append( ( organization.id, organization.name, organization.author_set.count(), organization.paper_set.count() ) )

        self.source_filter_model.clear()
        for source in Source.objects.order_by('name'):
            self.source_filter_model.append( ( source.id, source.name, source.issue, source.location, source.publisher, source.publication_date ) )


    def init_bookmark_pane(self):
        treeview_bookmarks = self.ui.get_widget('treeview_bookmarks')
        # id, page, title, updated, words
        self.treeview_bookmarks_model = gtk.ListStore( int, int, str, str, int )
        treeview_bookmarks.set_model( self.treeview_bookmarks_model )
        #treeview_bookmarks.connect('button-press-event', self.handle_middle_top_pane_button_press_event)
        renderer = gtk.CellRendererSpin()
        renderer.set_property( 'adjustment', gtk.Adjustment(value=0, lower=0, upper=1000, step_incr=1, page_incr=10, page_size=10) )
        renderer.set_property("editable", True)
#        renderer.connect( 'edited', lambda cellrenderertext, path, new_text: self.organizations_model.set_value( self.organizations_model.get_iter(path), 1, new_text ) or self.update_organization_name( self.organizations_model.get_value( self.organizations_model.get_iter(path), 0 ), new_text ) )
        renderer.connect( 'edited', lambda cellrenderertext, path, new_text: self.treeview_bookmarks_model.set_value( self.treeview_bookmarks_model.get_iter(path), 1, int(new_text) ) or self.save_bookmark_page( self.treeview_bookmarks_model.get_value( self.treeview_bookmarks_model.get_iter(path), 0), int(new_text) ) )
        column = gtk.TreeViewColumn("Page", renderer, markup=1)
#        column.set_cell_data_func(renderer, self.save_bookmark_page) 
        column.connect('clicked', sort_model_by_column, self.treeview_bookmarks_model, 1)
        treeview_bookmarks.append_column( column )
        column = gtk.TreeViewColumn("Title", gtk.CellRendererText(), markup=2)
        column.set_expand(True)
        column.connect('clicked', sort_model_by_column, self.treeview_bookmarks_model, 2)
        treeview_bookmarks.append_column( column )
        column = gtk.TreeViewColumn("Words", gtk.CellRendererText(), markup=4)
        column.connect('clicked', sort_model_by_column, self.treeview_bookmarks_model, 4)
        treeview_bookmarks.append_column( column )
        column = gtk.TreeViewColumn("Updated", gtk.CellRendererText(), markup=3)
        column.set_min_width(75)
        column.connect('clicked', sort_model_by_column, self.treeview_bookmarks_model, 3)
        treeview_bookmarks.append_column( column )
        make_all_columns_resizeable_clickable_ellipsize( treeview_bookmarks.get_columns() )
        treeview_bookmarks.connect('button-press-event', self.handle_treeview_bookmarks_button_press_event)
        
        treeview_bookmarks.get_selection().connect( 'changed', self.select_bookmark_pane_item )
        
    def save_bookmark_page(self, bookmark_id, page):
        bookmark = Bookmark.objects.get(id=bookmark_id)
        bookmark.page = page
        bookmark.save()
        
    def init_paper_information_pane(self):
        paper_notes = self.ui.get_widget('paper_notes')
        paper_notes.modify_base( gtk.STATE_NORMAL, gtk.gdk.color_parse("#fff7e8") )
        paper_notes.modify_base( gtk.STATE_INSENSITIVE, gtk.gdk.color_parse("#ffffff") )
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
        #renderer.set_property('editable', True)
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
        self.left_pane_model.append( None, ( '<b>My Library</b>', left_pane.render_icon(gtk.STOCK_HOME, gtk.ICON_SIZE_MENU), -1, False ) )
        for playlist in Playlist.objects.filter(parent='0'):
            if playlist.search_text:
                icon = left_pane.render_icon(gtk.STOCK_FIND, gtk.ICON_SIZE_MENU)
            else:
                icon = left_pane.render_icon(gtk.STOCK_DND_MULTIPLE, gtk.ICON_SIZE_MENU)
            self.left_pane_model.append( self.left_pane_model.get_iter((0),), ( playlist.title, icon, playlist.id, True ) )
        self.left_pane_model.append( self.left_pane_model.get_iter((0),), ( '<i>recently added</i>', left_pane.render_icon(gtk.STOCK_NEW, gtk.ICON_SIZE_MENU), -2, False ) )
        self.left_pane_model.append( self.left_pane_model.get_iter((0),), ( '<i>most often read</i>', left_pane.render_icon(gtk.STOCK_DIALOG_INFO, gtk.ICON_SIZE_MENU), -3, False ) )
        self.left_pane_model.append( self.left_pane_model.get_iter((0),), ( '<i>never read</i>', gtk.gdk.pixbuf_new_from_file( os.path.join( RUN_FROM_DIR, 'icons', 'applications-development.png' ) ), -5, False ) )
        self.left_pane_model.append( self.left_pane_model.get_iter((0),), ( '<i>highest rated</i>', gtk.gdk.pixbuf_new_from_file( os.path.join( RUN_FROM_DIR, 'icons', 'emblem-favorite.png' ) ), -4, False ) )
        self.left_pane_model.append( None, ( 'ACM', gtk.gdk.pixbuf_new_from_file( os.path.join( RUN_FROM_DIR, 'icons', 'favicon_acm.ico' ) ), -1, False ) )
        for playlist in Playlist.objects.filter(parent='1'):
            if playlist.search_text:
                icon = left_pane.render_icon(gtk.STOCK_FIND, gtk.ICON_SIZE_MENU)
            else:
                icon = left_pane.render_icon(gtk.STOCK_DND_MULTIPLE, gtk.ICON_SIZE_MENU)
            self.left_pane_model.append( self.left_pane_model.get_iter((1),), ( playlist.title, icon, playlist.id, True ) )
        self.left_pane_model.append( None, ( 'IEEE', gtk.gdk.pixbuf_new_from_file( os.path.join( RUN_FROM_DIR, 'icons', 'favicon_ieee.ico' ) ), -1, False  ) )
        for playlist in Playlist.objects.filter(parent='2'):
            if playlist.search_text:
                icon = left_pane.render_icon(gtk.STOCK_FIND, gtk.ICON_SIZE_MENU)
            else:
                icon = left_pane.render_icon(gtk.STOCK_DND_MULTIPLE, gtk.ICON_SIZE_MENU)
            self.left_pane_model.append( self.left_pane_model.get_iter((2),), ( playlist.title, icon, playlist.id, True ) )
        self.left_pane_model.append( None, ( 'PubMed', gtk.gdk.pixbuf_new_from_file( os.path.join( RUN_FROM_DIR, 'icons', 'favicon_pubmed.ico' ) ), -1, False ) )
        for playlist in Playlist.objects.filter(parent='3'):
            if playlist.search_text:
                icon = left_pane.render_icon(gtk.STOCK_FIND, gtk.ICON_SIZE_MENU)
            else:
                icon = left_pane.render_icon(gtk.STOCK_DND_MULTIPLE, gtk.ICON_SIZE_MENU)
            self.left_pane_model.append( self.left_pane_model.get_iter((3),), ( playlist.title, icon, playlist.id, True ) )
        self.left_pane_model.append( None, ( 'CiteSeer', gtk.gdk.pixbuf_new_from_file( os.path.join( RUN_FROM_DIR, 'icons', 'favicon_citeseer.ico' ) ), -1, False ) )
        for playlist in Playlist.objects.filter(parent='4'):
            if playlist.search_text:
                icon = left_pane.render_icon(gtk.STOCK_FIND, gtk.ICON_SIZE_MENU)
            else:
                icon = left_pane.render_icon(gtk.STOCK_DND_MULTIPLE, gtk.ICON_SIZE_MENU)
            self.left_pane_model.append( self.left_pane_model.get_iter((4),), ( playlist.title, icon, playlist.id, True ) )
        left_pane.expand_all()
        self.ui.get_widget('left_pane').get_selection().select_path((0,))

    def select_left_pane_item(self, selection):
        liststore, rows = selection.get_selected_rows()
        left_pane_toolbar = self.ui.get_widget('left_pane_toolbar')
        left_pane_toolbar.foreach( left_pane_toolbar.remove )
        if not rows:
            self.ui.get_widget('middle_pane_label').set_markup('<i>nothing selected</i>')
            return
        self.ui.get_widget('middle_pane_label').set_markup( liststore[rows[0]][0] )
        self.middle_top_pane_model.clear()

        button = gtk.ToolButton(gtk.STOCK_ADD)
        button.set_tooltip(gtk.Tooltips(), 'Create a new document collection...')
        button.connect( 'clicked', lambda x: self.create_playlist() )
        button.show()
        left_pane_toolbar.insert( button, -1 )

        try:
            self.current_playlist = Playlist.objects.get(id=liststore[rows[0]][2])
            button = gtk.ToolButton(gtk.STOCK_DELETE)
            button.set_tooltip(gtk.Tooltips(), 'Delete this collection...')
            button.connect( 'clicked', lambda x: self.delete_playlist(self.current_playlist.id) )
            button.show()
            left_pane_toolbar.insert( button, -1 )
        except: self.current_playlist = None
        
        if liststore[rows[0]][2]==-2:
            self.current_papers = Paper.objects.filter( created__gte= datetime.now()-timedelta(7) ).order_by('-created')[:20]
        elif liststore[rows[0]][2]==-3:
            self.current_papers = Paper.objects.filter( read_count__gte=1 ).order_by('-read_count')[:20]
        elif liststore[rows[0]][2]==-4:
            self.current_papers = Paper.objects.filter( rating__gte=1 ).order_by('-rating')[:20]
        elif liststore[rows[0]][2]==-5:
            self.current_papers = Paper.objects.filter( read_count=0 )
        else:
            self.current_papers = None
        
        if self.current_playlist:
            if self.current_playlist.search_text:
                self.last_middle_pane_search_string = self.current_playlist.search_text
                self.ui.get_widget('middle_pane_search').set_text( self.current_playlist.search_text )
            else:
                self.last_middle_pane_search_string = ''
                self.ui.get_widget('middle_pane_search').set_text('')
#            if len(self.current_playlist.papers.count()):
        
        if self.current_papers!=None:
            self.last_middle_pane_search_string = ''
            self.ui.get_widget('middle_pane_search').set_text('')
                
        if rows[0][0]==0:
            self.current_middle_top_pane_refresh_thread_ident = thread.start_new_thread( self.refresh_middle_pane_from_my_library, (True,) )
        else:
            self.ui.get_widget('my_library_filter_pane').hide()
        if rows[0][0]==1:
            self.current_middle_top_pane_refresh_thread_ident = thread.start_new_thread( self.refresh_middle_pane_from_acm, () )
        if rows[0][0]==2:
            self.current_middle_top_pane_refresh_thread_ident = thread.start_new_thread( self.refresh_middle_pane_from_ieee, () )
        if rows[0][0]==3:
            self.current_middle_top_pane_refresh_thread_ident = thread.start_new_thread( self.refresh_middle_pane_from_pubmed, () )
        if rows[0][0]==4:
            self.current_middle_top_pane_refresh_thread_ident = thread.start_new_thread( self.refresh_middle_pane_from_citeseer, () )
        self.select_middle_top_pane_item( self.ui.get_widget('middle_top_pane').get_selection() )

    def init_middle_top_pane(self):
        middle_top_pane = self.ui.get_widget('middle_top_pane')
        # id, authors, title, journal, year, rating, abstract, icon, import_url, doi, created, updated, empty_str, pubmed_id
        self.middle_top_pane_model = gtk.ListStore( int, str, str, str, str, int, str, gtk.gdk.Pixbuf, str, str, str, str, str, str )
        middle_top_pane.set_model( self.middle_top_pane_model )
        middle_top_pane.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        middle_top_pane.connect('button-press-event', self.handle_middle_top_pane_button_press_event)
        
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
        column.connect('clicked', sort_model_by_column, self.middle_top_pane_model, 2)
        middle_top_pane.append_column(column)
        
        column = gtk.TreeViewColumn("Authors", gtk.CellRendererText(), markup=1)
        column.set_min_width(128)
        column.set_expand(True)
        column.connect('clicked', sort_model_by_column, self.middle_top_pane_model, 1)
        middle_top_pane.append_column( column )
        column = gtk.TreeViewColumn("Journal", gtk.CellRendererText(), markup=3)
        column.set_min_width(128)
        column.set_expand(True)
        column.connect('clicked', sort_model_by_column, self.middle_top_pane_model, 3)
        middle_top_pane.append_column( column )
        column = gtk.TreeViewColumn("Year", gtk.CellRendererText(), markup=4)
        column.set_min_width(48)
        column.set_expand(False)
        column.connect('clicked', sort_model_by_column, self.middle_top_pane_model, 4)
        middle_top_pane.append_column( column )
        column = gtk.TreeViewColumn("Rating", gtk.CellRendererProgress(), value=5, text=12)
        column.set_min_width(64)
        column.set_expand(False)
        column.connect('clicked', sort_model_by_column, self.middle_top_pane_model, 5)
        middle_top_pane.append_column( column )
        column = gtk.TreeViewColumn("Imported", gtk.CellRendererText(), markup=10)
        column.set_min_width(80)
        column.set_expand(False)
        column.connect('clicked', sort_model_by_column, self.middle_top_pane_model, 10)
        middle_top_pane.append_column( column )
        
        make_all_columns_resizeable_clickable_ellipsize( middle_top_pane.get_columns() )
        
        middle_top_pane.connect('row-activated', self.handle_middle_top_pane_row_activated )
        middle_top_pane.get_selection().connect('changed', self.select_middle_top_pane_item)
        
        middle_top_pane.enable_model_drag_source( gtk.gdk.BUTTON1_MASK, [LEFT_PANE_ADD_TO_PLAYLIST_DND_ACTION, MIDDLE_TOP_PANE_REORDER_PLAYLIST_DND_ACTION], gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE )
        middle_top_pane.connect('drag-data-get', self.handle_middle_top_pane_drag_data_get)
        middle_top_pane.enable_model_drag_dest( [MIDDLE_TOP_PANE_REORDER_PLAYLIST_DND_ACTION], gtk.gdk.ACTION_MOVE )
        middle_top_pane.connect('drag-data-received', self.handle_middle_top_pane_drag_data_received_event)
    
    def handle_middle_top_pane_row_activated(self, treeview, path, view_column):
        liststore, rows = treeview.get_selection().get_selected_rows()
        paper_id = treeview.get_model().get_value( treeview.get_model().get_iter(path), 0 )
        try:
            paper = Paper.objects.get(id=paper_id)
            paper.open()
        except:
            traceback.print_exc()
    
    def handle_middle_top_pane_drag_data_get(self, treeview, context, selection, info, timestamp):
        liststore, rows = treeview.get_selection().get_selected_rows()
        id = liststore[rows[0]][0]
        selection.set('text/plain', len(str(id)), str(id))

    def handle_author_filter_row_activated(self, treeview, path, view_column):
        liststore, rows = treeview.get_selection().get_selected_rows()
        id = treeview.get_model().get_value( treeview.get_model().get_iter(path), 0 )
        AuthorEditGUI(id)

    def handle_organization_filter_row_activated(self, treeview, path, view_column):
        liststore, rows = treeview.get_selection().get_selected_rows()
        id = treeview.get_model().get_value( treeview.get_model().get_iter(path), 0 )
        OrganizationEditGUI(id)

    def handle_source_filter_row_activated(self, treeview, path, view_column):
        liststore, rows = treeview.get_selection().get_selected_rows()
        id = treeview.get_model().get_value( treeview.get_model().get_iter(path), 0 )
        SourceEditGUI(id)
        
    def handle_left_pane_button_press_event(self, treeview, event):
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            time = event.time
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                treeview.grab_focus()
                treeview.set_cursor( path, col, 0)
                playlist_id = self.left_pane_model.get_value( self.left_pane_model.get_iter(path), 2 )
                if playlist_id>=0: #len(path)==2:
                    menu = gtk.Menu()
                    delete = gtk.ImageMenuItem(stock_id=gtk.STOCK_DELETE)
                    delete.connect( 'activate', lambda x: self.delete_playlist(playlist_id) )
                    menu.append(delete)
                    menu.show_all()
                    menu.popup(None, None, None, event.button, event.get_time())
            return True
        
    def handle_middle_top_pane_button_press_event(self, treeview, event):
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            time = event.time
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                treeview.grab_focus()
                treeview.set_cursor( path, col, 0)
                paper_id = self.middle_top_pane_model.get_value( self.middle_top_pane_model.get_iter(path), 0 )
                if paper_id>=0: #len(path)==2:
                    menu = gtk.Menu()
                    paper = Paper.objects.get(id=paper_id)
                    if paper and os.path.isfile( paper.get_full_text_filename() ):
                        button = gtk.ImageMenuItem(gtk.STOCK_OPEN)
                        button.connect( 'activate', lambda x: paper.open() )
                        menu.append(button)
                    button = gtk.ImageMenuItem(gtk.STOCK_EDIT)
                    button.connect( 'activate', lambda x: PaperEditGUI(paper.id) )
                    menu.append(button)
                    button = gtk.ImageMenuItem(gtk.STOCK_DELETE)
                    button.connect( 'activate', lambda x: self.delete_papers( [paper.id] ) )
                    menu.append(button)
                    menu.show_all()
                    menu.popup(None, None, None, event.button, event.get_time())
            return True
        
    def handle_author_filter_button_press_event(self, treeview, event):
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            time = event.time
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                treeview.grab_focus()
                treeview.set_cursor( path, col, 0)
                id = self.author_filter_model.get_value( self.author_filter_model.get_iter(path), 0 )
                if id>=0: #len(path)==2:
                    menu = gtk.Menu()
                    edit = gtk.ImageMenuItem(stock_id=gtk.STOCK_EDIT)
                    edit.connect( 'activate', lambda x: AuthorEditGUI(id) )
                    menu.append(edit)
                    delete = gtk.ImageMenuItem(stock_id=gtk.STOCK_DELETE)
                    delete.connect( 'activate', lambda x: self.delete_author(id) )
                    menu.append(delete)
                    menu.show_all()
                    menu.popup(None, None, None, event.button, event.get_time())
            return True
        
    def handle_source_filter_button_press_event(self, treeview, event):
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            time = event.time
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                treeview.grab_focus()
                treeview.set_cursor( path, col, 0)
                id = self.source_filter_model.get_value( self.source_filter_model.get_iter(path), 0 )
                if id>=0: #len(path)==2:
                    menu = gtk.Menu()
                    edit = gtk.ImageMenuItem(stock_id=gtk.STOCK_EDIT)
                    edit.connect( 'activate', lambda x: SourceEditGUI(id) )
                    menu.append(edit)
                    delete = gtk.ImageMenuItem(stock_id=gtk.STOCK_DELETE)
                    delete.connect( 'activate', lambda x: self.delete_source(id) )
                    menu.append(delete)
                    menu.show_all()
                    menu.popup(None, None, None, event.button, event.get_time())
            return True
        
    def handle_treeview_bookmarks_button_press_event(self, treeview, event):
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            time = event.time
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                treeview.grab_focus()
                treeview.set_cursor( path, col, 0)
                id = self.treeview_bookmarks_model.get_value( self.treeview_bookmarks_model.get_iter(path), 0 )
                if id>=0: #len(path)==2:
                    menu = gtk.Menu()
                    delete = gtk.ImageMenuItem(stock_id=gtk.STOCK_DELETE)
                    delete.connect( 'activate', lambda x: self.delete_bookmark(id) )
                    menu.append(delete)
                    menu.show_all()
                    menu.popup(None, None, None, event.button, event.get_time())
            return True
    
    def handle_organization_filter_button_press_event(self, treeview, event):
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            time = event.time
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                treeview.grab_focus()
                treeview.set_cursor( path, col, 0)
                id = self.organization_filter_model.get_value( self.organization_filter_model.get_iter(path), 0 )
                if id>=0: #len(path)==2:
                    menu = gtk.Menu()
                    edit = gtk.ImageMenuItem(stock_id=gtk.STOCK_EDIT)
                    edit.connect( 'activate', lambda x: OrganizationEditGUI(id) )
                    menu.append(edit)
                    delete = gtk.ImageMenuItem(stock_id=gtk.STOCK_DELETE)
                    delete.connect( 'activate', lambda x: self.delete_organization(id) )
                    menu.append(delete)
                    menu.show_all()
                    menu.popup(None, None, None, event.button, event.get_time())
            return True
        
    def handle_left_pane_drag_data_received_event(self, treeview, context, x, y, selection, info, timestamp):
        try:
            drop_info = treeview.get_dest_row_at_pos(x, y)
            if drop_info:
                model = treeview.get_model()
                path, position = drop_info
                data = selection.data
                playlist = Playlist.objects.get(id=model.get_value( model.get_iter(path), 2 ))
                playlist.papers.add( Paper.objects.get(id=int(data)) )
                playlist.save()
            return
        except:
            traceback.print_exc()
            
    def handle_middle_top_pane_drag_data_received_event(self, treeview, context, x, y, selection, info, timestamp):
        try:
            drop_info = treeview.get_dest_row_at_pos(x, y)
            if drop_info and self.current_playlist:
                model = treeview.get_model()
                path, position = drop_info
                data = selection.data
                playlist = self.current_playlist
                paper_list = list(playlist.papers.all())
                l = []
                for i in range(0,len(paper_list)):
                    paper = paper_list[i]
                    if str(paper.id)==str(data):
                        break
                if path[0]==i:
                    return
                if path[0]==i+1 and (position==gtk.TREE_VIEW_DROP_AFTER or position==gtk.TREE_VIEW_DROP_INTO_OR_AFTER):
                    return
                if path[0]==i-1 and (position==gtk.TREE_VIEW_DROP_BEFORE or position==gtk.TREE_VIEW_DROP_INTO_OR_BEFORE):
                    return
                paper_list[i] = None
                if position==gtk.TREE_VIEW_DROP_BEFORE or position==gtk.TREE_VIEW_DROP_INTO_OR_BEFORE:
                    paper_list.insert( path[0], paper )
                if position==gtk.TREE_VIEW_DROP_AFTER or position==gtk.TREE_VIEW_DROP_INTO_OR_AFTER:
                    paper_list.insert( path[0]+1, paper )
                paper_list.remove(None)
                playlist.papers.clear()
                for paper in paper_list:
                    playlist.papers.add(paper)
                thread.start_new_thread( self.refresh_middle_pane_from_my_library, (False,) )
            if not self.current_playlist:
                print 'can only reorder playlists'
        except:
            traceback.print_exc()
        
    def handle_left_pane_drag_motion_event(self, treeview, drag_context, x, y, eventtime):
        try:
            target_path, drop_position = treeview.get_dest_row_at_pos(x, y)
            model, source = treeview.get_selection().get_selected()
            target = model.get_iter(target_path)
            if len(target_path)>1 and target_path[0]==0:
                treeview.enable_model_drag_dest([LEFT_PANE_ADD_TO_PLAYLIST_DND_ACTION], gtk.gdk.ACTION_MOVE)
            else:
                treeview.enable_model_drag_dest([], gtk.gdk.ACTION_MOVE)
        except:
            # this will occur when we're not over a target
            # traceback.print_exc()
            treeview.enable_model_drag_dest([], gtk.gdk.ACTION_MOVE)
        
    def handle_playlist_edited(self, renderer, path, new_text):
        playlist_id = self.left_pane_model.get_value( self.left_pane_model.get_iter_from_string(path), 2)
        playlist = Playlist.objects.get(id=playlist_id)
        playlist.title = new_text
        playlist.save()
        self.refresh_left_pane()

    def select_middle_top_pane_item(self, selection):
        liststore, rows = selection.get_selected_rows()
        self.paper_information_pane_model.clear()
        self.ui.get_widget('paper_information_pane').columns_autosize()
        paper_information_toolbar = self.ui.get_widget('paper_information_toolbar')
        paper_information_toolbar.foreach( paper_information_toolbar.remove )
        self.displayed_paper = None

        if len(rows)==0:
            self.update_bookmark_pane_from_paper(None)
        elif len(rows)==1:
            try: 
                self.displayed_paper = paper = Paper.objects.get(id=liststore[rows[0]][0])
            except:
                paper = None
            if liststore[rows[0]][2]:
                self.paper_information_pane_model.append(( '<b>Title:</b>', pango_excape( liststore[rows[0]][2] ) ,))
            if liststore[rows[0]][1]:
                self.paper_information_pane_model.append(( '<b>Authors:</b>', pango_excape( liststore[rows[0]][1] ) ,))
            if liststore[rows[0]][3]:
                self.paper_information_pane_model.append(( '<b>Journal:</b>', pango_excape( liststore[rows[0]][3] ) ,))
            if liststore[rows[0]][9]:
                self.paper_information_pane_model.append(( '<b>DOI:</b>', pango_excape( liststore[rows[0]][9] ) ,))
            if liststore[rows[0]][13]:
                self.paper_information_pane_model.append(( '<b>PubMed:</b>', pango_excape( liststore[rows[0]][13] ) ,)) 
            if liststore[rows[0]][8]:
                self.paper_information_pane_model.append(( '<b>Import URL:</b>', pango_excape( liststore[rows[0]][8]) ,)) 
            status = []
            if paper and os.path.isfile( paper.get_full_text_filename() ):
                status.append( 'Full text saved in local library.' )
                button = gtk.ToolButton(gtk.STOCK_OPEN)
                button.set_tooltip(gtk.Tooltips(), 'Open the full text of this paper in a new window...')
                button.connect( 'clicked', lambda x: paper.open() )
                paper_information_toolbar.insert( button, -1 )
            if status:
                self.paper_information_pane_model.append(( '<b>Status:</b>', pango_excape( '\n'.join(status) ) ,))
#            if paper.source:
#                description.append( 'Source:  %s %s (pages: %s)' % ( str(paper.source), paper.source_session, paper.source_pages ) )
            if liststore[rows[0]][6]:
                self.paper_information_pane_model.append(( '<b>Abstract:</b>', pango_excape( liststore[rows[0]][6] ) ,))
#            description.append( '' )
#            description.append( 'References:' )
#            for ref in paper.reference_set.all():
#                description.append( ref.line )
            #self.ui.get_widget('paper_information_pane').get_buffer().set_text( '\n'.join(description) )
            
            if liststore[rows[0]][8]:
                button = gtk.ToolButton(gtk.STOCK_HOME)
                button.set_tooltip(gtk.Tooltips(), 'Open this URL in your browser...')
                button.connect( 'clicked', lambda x: desktop.open(liststore[rows[0]][8]) )
                paper_information_toolbar.insert( button, -1 )
                if paper:
                    button = gtk.ToolButton(gtk.STOCK_REFRESH)
                    button.set_tooltip(gtk.Tooltips(), 'Re-add this paper to your library...')
                    button.connect( 'clicked', lambda x: fetch_citation_via_middle_top_pane_row(liststore[rows[0]]) )
                    paper_information_toolbar.insert( button, -1 )
                else:
                    button = gtk.ToolButton(gtk.STOCK_ADD)
                    button.set_tooltip(gtk.Tooltips(), 'Add this paper to your library...')
                    button.connect( 'clicked', lambda x: fetch_citation_via_middle_top_pane_row(liststore[rows[0]]) )
                    paper_information_toolbar.insert( button, -1 )
                    
            if paper:
                importable_references = set()
                references = paper.reference_set.order_by('id')
#                self.paper_information_pane_model.append(( '<b>References:</b>', '\n'.join( [ '<i>'+ str(i) +':</i> '+ references[i].line_from_referencing_paper for i in range(0,len(references)) ] ) ,))
                for i in range(0,len(references)):
                    if i==0: col1 = '<b>References:</b>'
                    else: col1 = ''
                    if references[i].url_from_referencing_paper and not references[i].referenced_paper:
                        importable_references.add( references[i] )
                    self.paper_information_pane_model.append(( col1, '<i>'+ str(i+1) +':</i> '+ pango_excape( references[i].line_from_referencing_paper ) ) )
                importable_citations = set()
                citations = paper.citation_set.order_by('id')
#                self.paper_information_pane_model.append(( '<b>Citations:</b>', '\n'.join( [ '<i>'+ str(i) +':</i> '+ citations[i].line_from_referenced_paper for i in range(0,len(citations)) ] ) ,))
                for i in range(0,len(citations)):
                    if i==0: col1 = '<b>Citations:</b>'
                    else: col1 = ''
                    if citations[i].url_from_referenced_paper and not citations[i].referencing_paper:
                        importable_citations.add( citations[i] )
                    self.paper_information_pane_model.append(( col1, '<i>'+ str(i+1) +':</i> '+ pango_excape( citations[i].line_from_referenced_paper ) ) )

                self.update_bookmark_pane_from_paper(self.displayed_paper)

                button = gtk.ToolButton(gtk.STOCK_EDIT)
                button.set_tooltip(gtk.Tooltips(), 'Edit this paper...')
                button.connect( 'clicked', lambda x: PaperEditGUI(paper.id) )
                paper_information_toolbar.insert( button, -1 )

                if self.current_playlist:
                    button = gtk.ToolButton(gtk.STOCK_REMOVE)
                    button.set_tooltip(gtk.Tooltips(), 'Remove this paper from this collection...')
                    button.connect( 'clicked', lambda x: self.remove_papers_from_current_playlist([paper.id]) )
                    paper_information_toolbar.insert( button, -1 )

                if importable_references or importable_citations:
                    import_button = gtk.MenuToolButton(gtk.STOCK_ADD)
                    import_button.set_tooltip(gtk.Tooltips(), 'Import all cited and referenced documents...(%i)' % len(importable_references.union(importable_citations)) )
                    import_button.connect( 'clicked', lambda x: fetch_citations_via_references( importable_references.union(importable_citations) ) )
                    paper_information_toolbar.insert( import_button, -1 )
                    import_button_menu = gtk.Menu()
                    if importable_citations:
                        menu_item = gtk.MenuItem('Import all cited documents (%i)' % len(importable_citations) )
                        menu_item.connect( 'activate', lambda x: fetch_citations_via_references( importable_citations ) )
                        import_button_menu.append( menu_item )
                        menu_item = gtk.MenuItem('Import specific cited document')
                        import_button_submenu = gtk.Menu()
                        for citation in importable_citations:
                            submenu_item = gtk.MenuItem( truncate_long_str(citation.line_from_referenced_paper) )
                            submenu_item.connect( 'activate', lambda x: fetch_citations_via_references( (citation,) ) )
                            import_button_submenu.append( submenu_item )
                        menu_item.set_submenu(import_button_submenu)
                        import_button_menu.append( menu_item )
                    if importable_references:
                        menu_item = gtk.MenuItem('Import all referenced documents (%i)' % len(importable_references) )
                        menu_item.connect( 'activate', lambda x: fetch_citations_via_references( importable_references ) )
                        import_button_menu.append( menu_item )
                        menu_item = gtk.MenuItem('Import specific referenced document')
                        import_button_submenu = gtk.Menu()
                        for reference in importable_references:
                            submenu_item = gtk.MenuItem( truncate_long_str(reference.line_from_referencing_paper) )
                            submenu_item.connect( 'activate', lambda x: fetch_citations_via_references( (reference,) ) )
                            import_button_submenu.append( submenu_item )
                        menu_item.set_submenu(import_button_submenu)
                        import_button_menu.append( menu_item )
                    import_button_menu.show_all()
                    import_button.set_menu( import_button_menu )
            
        else:
            self.update_bookmark_pane_from_paper(None)
            self.paper_information_pane_model.append(( '<b>Number of papers:</b>', len(rows) ,))
            
            downloadable_paper_urls = set()
            for row in rows:
                if liststore[row][8] and liststore[row][0]==-1:
                    downloadable_paper_urls.add( liststore[row][8] )
            if len(downloadable_paper_urls):
                self.paper_information_pane_model.append(( '<b>Number of new papers:</b>', len(downloadable_paper_urls) ,))
                button = gtk.ToolButton(gtk.STOCK_ADD)
                button.set_tooltip(gtk.Tooltips(),  'Add new papers (%i) to your library...' % len(downloadable_paper_urls) )
                button.connect( 'clicked', lambda x: fetch_citations_via_urls(downloadable_paper_urls) )
                paper_information_toolbar.insert( button, -1 )

            selected_valid_paper_ids = []
            for row in rows:
                if liststore[row][0]!=-1:
                    selected_valid_paper_ids.append( liststore[row][0] )
            print 'selected_valid_paper_ids', selected_valid_paper_ids
            if len(selected_valid_paper_ids):
                button = gtk.ToolButton(gtk.STOCK_REMOVE)
                button.set_tooltip(gtk.Tooltips(), 'Remove these papers from your library...')
                button.connect( 'clicked', lambda x: self.delete_papers( selected_valid_paper_ids ) )
                paper_information_toolbar.insert( button, -1 )
                button = gtk.ToolButton(gtk.STOCK_DND_MULTIPLE)
                button.set_tooltip(gtk.Tooltips(), 'Create a new collection from these documents...')
                button.connect( 'clicked', lambda x: self.create_playlist( selected_valid_paper_ids ) )
                paper_information_toolbar.insert( button, -1 )

        self.pdf_preview['current_page_number'] = 0
        self.refresh_pdf_preview_pane()

        paper_information_toolbar.show_all()
        
    def update_bookmark_pane_from_paper(self, paper):
        toolbar_bookmarks = self.ui.get_widget('toolbar_bookmarks')
        toolbar_bookmarks.foreach( toolbar_bookmarks.remove )
        self.treeview_bookmarks_model.clear()
        if paper:
            for bookmark in paper.bookmark_set.order_by('page'):
                try: title = str(bookmark.notes).split('\n')[0]
                except: title = str(bookmark.notes)
                self.treeview_bookmarks_model.append( (bookmark.id, bookmark.page, title, bookmark.updated.strftime(DATE_FORMAT), len(str(bookmark.notes).split())) )
        self.select_bookmark_pane_item()
        
    def select_bookmark_pane_item(self, selection=None):
        if selection==None:
            selection = self.ui.get_widget('treeview_bookmarks').get_selection()
        toolbar_bookmarks = self.ui.get_widget('toolbar_bookmarks')
        toolbar_bookmarks.foreach( toolbar_bookmarks.remove )
        
        try: selected_bookmark_id = self.treeview_bookmarks_model.get_value( self.ui.get_widget('treeview_bookmarks').get_selection().get_selected()[1], 0 )
        except: selected_bookmark_id = -1
        
        paper_notes = self.ui.get_widget('paper_notes')
        try: 
            if not self.update_paper_notes_handler_id==None:
                paper_notes.get_buffer().disconnect(self.update_paper_notes_handler_id)
            self.update_paper_notes_handler_id = None
        except:
            self.update_paper_notes_handler_id = None
        
        if selected_bookmark_id!=-1:
                bookmark = Bookmark.objects.get(id=selected_bookmark_id)
                paper_notes.get_buffer().set_text( bookmark.notes )
                paper_notes.set_property('sensitive', True)
                self.goto_pdf_page( bookmark.page )
                self.update_paper_notes_handler_id = paper_notes.get_buffer().connect('changed', self.update_bookmark_notes, selected_bookmark_id )
        elif self.displayed_paper:
                paper_notes.get_buffer().set_text( self.displayed_paper.notes )
                paper_notes.set_property('sensitive', True)
                self.update_paper_notes_handler_id = paper_notes.get_buffer().connect('changed', self.update_paper_notes, self.displayed_paper.id )
        else:
            paper_notes.get_buffer().set_text('')
            paper_notes.set_property('sensitive', False)

        
        if self.displayed_paper:
            button = gtk.ToolButton(gtk.STOCK_ADD)
            button.set_tooltip(gtk.Tooltips(), 'Add a new page note...')
            button.connect( 'clicked', lambda x, paper: Bookmark.objects.create(paper=paper, page=self.pdf_preview['current_page_number']).save() or self.update_bookmark_pane_from_paper( self.displayed_paper ), self.displayed_paper )
            button.show()
            toolbar_bookmarks.insert( button, -1 )

        if selected_bookmark_id!=-1:
            button = gtk.ToolButton(gtk.STOCK_DELETE)
            button.set_tooltip(gtk.Tooltips(), 'Delete this page note...')
            button.connect( 'clicked', lambda x: self.delete_bookmark( selected_bookmark_id )  )
            button.show()
            toolbar_bookmarks.insert( button, -1 )
        
        
    def echo_objects(self, a=None, b=None, c=None):
        print a,b,c
        
    def update_paper_notes(self, text_buffer, id):
        paper = Paper.objects.get(id=id)
        #print 'saving notes', text_buffer.get_text( text_buffer.get_start_iter(), text_buffer.get_end_iter() )
        paper.notes = text_buffer.get_text( text_buffer.get_start_iter(), text_buffer.get_end_iter() )
        paper.save()
        
    def update_bookmark_notes(self, text_buffer, id):
        bookmark = Bookmark.objects.get(id=id)
        #print 'saving notes', text_buffer.get_text( text_buffer.get_start_iter(), text_buffer.get_end_iter() )
        bookmark.notes = text_buffer.get_text( text_buffer.get_start_iter(), text_buffer.get_end_iter() )
        bookmark.save()
        
    def delete_papers(self, paper_ids):
        papers = Paper.objects.in_bulk(paper_ids).values()
        paper_list_text = '\n'.join([ ('<i>"%s"</i>' % str(paper.title)) for paper in papers ])
        dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, flags=gtk.DIALOG_MODAL )
        dialog.set_markup('Really delete the following %s?\n\n%s\n\n' % ( humanize_count( len(papers), 'paper', 'papers', places=-1 ), paper_list_text ))
        dialog.set_default_response(gtk.RESPONSE_NO)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        if response == gtk.RESPONSE_YES:
            for paper in papers:
                print 'deleting paper:', paper.doi, paper.title, paper.get_authors_in_order()
                paper.delete()
            self.refresh_middle_pane_search()
            
    def remove_papers_from_current_playlist(self, paper_ids):
        if not self.current_playlist: return
        try:
            for paper in Paper.objects.in_bulk(paper_ids).values():
                self.current_playlist.papers.remove(paper)
            self.current_playlist.save()
            thread.start_new_thread( self.refresh_middle_pane_from_my_library, (False,) )
        except:
            traceback.print_exc()
            
    def delete_playlist(self, id):
        dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, flags=gtk.DIALOG_MODAL )
        dialog.set_markup('Really delete this document collection?')
        dialog.set_default_response(gtk.RESPONSE_NO)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        if response == gtk.RESPONSE_YES:
            Playlist.objects.get(id=id).delete()
            self.refresh_left_pane()
    
    def delete_author(self, id):
        dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, flags=gtk.DIALOG_MODAL )
        dialog.set_markup('Really delete this author?')
        dialog.set_default_response(gtk.RESPONSE_NO)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        if response == gtk.RESPONSE_YES:
            Author.objects.get(id=id).delete()
            self.refresh_my_library_filter_pane()
    
    def delete_bookmark(self, id):
        dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, flags=gtk.DIALOG_MODAL )
        dialog.set_markup('Really delete this bookmark?')
        dialog.set_default_response(gtk.RESPONSE_NO)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        if response == gtk.RESPONSE_YES:
            Bookmark.objects.get(id=id).delete()
            self.update_bookmark_pane_from_paper( self.displayed_paper )
    
    def delete_source(self, id):
        dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, flags=gtk.DIALOG_MODAL )
        dialog.set_markup('Really delete this source?')
        dialog.set_default_response(gtk.RESPONSE_NO)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        if response == gtk.RESPONSE_YES:
            Source.objects.get(id=id).delete()
            self.refresh_my_library_filter_pane()
    
    def delete_organization(self, id):
        dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, flags=gtk.DIALOG_MODAL )
        dialog.set_markup('Really delete this organization?')
        dialog.set_default_response(gtk.RESPONSE_NO)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        if response == gtk.RESPONSE_YES:
            Organization.objects.get(id=id).delete()
            self.refresh_my_library_filter_pane()
    
    def update_middle_top_pane_from_row_list_if_we_are_still_the_preffered_thread(self, rows):
        middle_top_pane = self.ui.get_widget('middle_top_pane')
        for column in middle_top_pane.get_columns():
            column.set_sort_indicator(False)
        if self.current_middle_top_pane_refresh_thread_ident==thread.get_ident():
            gtk.gdk.threads_enter()
            self.middle_top_pane_model.clear()
            for row in rows:
                self.middle_top_pane_model.append(row)
            middle_top_pane.columns_autosize()
            gtk.gdk.threads_leave()

    def refresh_middle_pane_from_my_library(self, refresh_library_filter_pane=True):
        self.active_threads[ thread.get_ident() ] = 'searching local library...'
        try:
            rows = []
            my_library_filter_pane = self.ui.get_widget('my_library_filter_pane')
            
            if not self.current_playlist and self.current_papers==None:
                
                search_text = self.ui.get_widget('middle_pane_search').get_text().strip()
                if search_text:
                    my_library_filter_pane.hide()
                    paper_ids = set()
                    for s in search_text.split():
                        for paper in Paper.objects.filter( Q(title__icontains=s) | Q(doi__icontains=s) | Q(source_session__icontains=s) | Q(abstract__icontains=s) ):
                            paper_ids.add( paper.id )
                        for sponsor in Sponsor.objects.filter( name__icontains=s ):
                            for paper in sponsor.paper_set.all(): paper_ids.add( paper.id )
                        for author in Author.objects.filter( Q(name__icontains=s) | Q(location__icontains=s) ):
                            for paper in author.paper_set.all(): paper_ids.add( paper.id )
                        for source in Source.objects.filter( Q(name__icontains=s) | Q(issue__icontains=s) | Q(location__icontains=s) ):
                            for paper in source.paper_set.all(): paper_ids.add( paper.id )
                        for organization in Organization.objects.filter( Q(name__icontains=s) | Q(location__icontains=s) ):
                            for paper in organization.paper_set.all(): paper_ids.add( paper.id )
                        for publisher in Publisher.objects.filter( name__icontains=s ):
                            for source in publisher.source_set.all():
                                for paper in source.paper_set.all(): paper_ids.add( paper.id )
                        for reference in Reference.objects.filter( Q(line_from_referencing_paper__icontains=s) | Q(doi_from_referencing_paper__icontains=s) ):
                            paper_ids.add( reference.referencing_paper.id )
                        for reference in Reference.objects.filter( Q(line_from_referenced_paper__icontains=s) | Q(doi_from_referenced_paper__icontains=s) ):
                            paper_ids.add( reference.referenced_paper.id )
                    papers = Paper.objects.in_bulk( list(paper_ids) ).values()
                else:
                    if refresh_library_filter_pane:
                        self.refresh_my_library_filter_pane()
                        my_library_filter_pane.show()
                    paper_query = Paper.objects.order_by('title')
    
                    filter_liststore, filter_rows = self.ui.get_widget('author_filter').get_selection().get_selected_rows()
                    q = None
                    for filter_row in filter_rows:
                        if q==None: q = Q(authors__id=filter_liststore[filter_row][0])
                        else: q = q | Q(authors__id=filter_liststore[filter_row][0])
                    if q: paper_query = paper_query.filter(q)
                    
                    filter_liststore, filter_rows = self.ui.get_widget('source_filter').get_selection().get_selected_rows()
                    q = None
                    for filter_row in filter_rows:
                        if q==None: q = Q(source__id=filter_liststore[filter_row][0])
                        else: q = q | Q(source__id=filter_liststore[filter_row][0])
                    if q: paper_query = paper_query.filter(q)
                    
                    filter_liststore, filter_rows = self.ui.get_widget('organization_filter').get_selection().get_selected_rows()
                    q = None
                    for filter_row in filter_rows:
                        if q==None: q = Q(organizations__id=filter_liststore[filter_row][0])
                        else: q = q | Q(organizations__id=filter_liststore[filter_row][0])
                    if q: paper_query = paper_query.filter(q)
                    
                    papers = paper_query.distinct()
                    
            else:
                my_library_filter_pane.hide()
                if self.current_playlist:
                    papers = self.current_playlist.get_papers_in_order()
                elif self.current_papers!=None:
                    papers = self.current_papers
                else:
                    papers = []
                    
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
                    if paper.source.publication_date:
                        pub_year = paper.source.publication_date.year
                    else:
                        pub_year = ''
                else: 
                    journal = ''
                    pub_year = ''
                rows.append( ( 
                    paper.id, ', '.join(authors), 
                    paper.title,
                    journal, 
                    pub_year, 
                    (paper.rating+10)*5, 
                    paper.abstract, 
                    icon, # icon
                    paper.import_url, # import_url
                    paper.doi, # doi
                    paper.created.strftime(DATE_FORMAT), # created
                    paper.updated.strftime(DATE_FORMAT), # updated
                    '', # empty_str
                    paper.pubmed_id, # pubmed_id
                ) )
            self.update_middle_top_pane_from_row_list_if_we_are_still_the_preffered_thread(rows)
            self.refresh_my_library_count()
        except:
            traceback.print_exc()
        if self.active_threads.has_key( thread.get_ident() ):
            del self.active_threads[ thread.get_ident() ]
        
    
    def refresh_my_library_count(self):
        gtk.gdk.threads_enter()
        selection = self.ui.get_widget('left_pane').get_selection()
        liststore, rows = selection.get_selected_rows()
        liststore.set_value( self.left_pane_model.get_iter((0,)), 0, '<b>My Library</b>  <span foreground="#888888">(%i)</span>' % Paper.objects.count() )
        gtk.gdk.threads_leave()
    
    def refresh_middle_pane_from_acm(self):
        search_text = self.ui.get_widget('middle_pane_search').get_text().strip()
        if not search_text: return
        self.active_threads[ thread.get_ident() ] = 'searching acm... (%s)' % search_text
        rows = []
        try:
            params = openanything.fetch( 'http://portal.acm.org/results.cfm?dl=ACM&query=%s' % defaultfilters.urlencode( search_text ) )
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
                    #print 'first_author', first_author
                    import_url = ACM_BASE_URL +'/'+ node.find('a')['href']
                    import_url_short = import_url[ 0: import_url.find('&') ]
                    try:
                        papers = list( Paper.objects.filter( title=title, authors__name__exact=first_author) )
                        papers.extend( Paper.objects.filter(import_url__startswith=import_url_short) )
                        paper = papers[0]
                        paper_id = paper.id
                        if os.path.isfile( paper.get_full_text_filename() ):
                            icon = self.ui.get_widget('middle_top_pane').render_icon(gtk.STOCK_DND, gtk.ICON_SIZE_MENU)
                        else:
                            icon = None
                    except:
                        #traceback.print_exc()
                        paper = None
                        paper_id = -1
                        icon = None
                    row = ( 
                        paper_id, # paper id 
                        authors, # authors 
                        title, # title 
                        ' '.join( [html_strip(x.string).replace('\n','').replace('\r','').replace('\t','') for x in tds[3].div.contents if len(html_strip(x.string).replace('\n','').replace('\r','').replace('\t',''))] ), # journal 
                        html_strip( tds[1].string )[-4:], # year 
                        0, # ranking
                        ' '.join( [html_strip(x.string).replace('\n','').replace('\r','').replace('\t','') for x in tds[-1].findAll() if x.string] ), # abstract
                        icon, # icon
                        import_url, # import_url
                        '', # doi
                        '', # created
                        '', # updated
                        '', # empty_str
                        '', # pubmed_id
                    )
                    #print thread.get_ident(), 'row =', row
                    rows.append( row )
                self.update_middle_top_pane_from_row_list_if_we_are_still_the_preffered_thread(rows)
            else:
                gtk.gdk.threads_enter()
                error = gtk.MessageDialog( type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK, flags=gtk.DIALOG_MODAL )
                #error.connect('response', lambda x,y: error.destroy())
                error.set_markup('<b>Unable to Search External Repository</b>\n\nHTTP Error code: %i' % params['status'])
                error.run()
                gtk.gdk.threads_leave()
        except:
            traceback.print_exc()
        if self.active_threads.has_key( thread.get_ident() ):
            del self.active_threads[ thread.get_ident() ]
            
    def refresh_middle_pane_from_ieee(self):
        search_text = self.ui.get_widget('middle_pane_search').get_text().strip()
        if not search_text: return
        self.active_threads[ thread.get_ident() ] = 'searching ieee... (%s)' % search_text
        rows = []
        try:
            params = openanything.fetch( 'http://ieeexplore.ieee.org/search/freesearchresult.jsp?history=yes&queryText=%%28%s%%29&imageField.x=0&imageField.y=0' % defaultfilters.urlencode( search_text ) )
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
                        #print 'first_author', first_author
                        try:
                            paper = Paper.objects.get( title=title )
                            paper_id = paper.id
                            if os.path.isfile( paper.get_full_text_filename() ):
                                icon = self.ui.get_widget('middle_top_pane').render_icon(gtk.STOCK_DND, gtk.ICON_SIZE_MENU)
                            else:
                                icon = None
                        except:
                            #traceback.print_exc()
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
                            '', # doi
                            '', # created
                            '', # updated
                            '', # empty_str
                            '', # pubmed_id
                        )
                        #print thread.get_ident(), 'row =', row
                        rows.append( row )
                    except: 
                        pass
                        #traceback.print_exc()
                    
                self.update_middle_top_pane_from_row_list_if_we_are_still_the_preffered_thread(rows)
            else:
                gtk.gdk.threads_enter()
                error = gtk.MessageDialog( type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK, flags=gtk.DIALOG_MODAL )
                error.connect('response', lambda x,y: error.destroy())
                error.set_markup('<b>Unable to Search External Repository</b>\n\nHTTP Error code: %i' % params['status'])
                error.run()
                gtk.gdk.threads_leave()
        except:
            traceback.print_exc()
        if self.active_threads.has_key( thread.get_ident() ):
            del self.active_threads[ thread.get_ident() ]

    def refresh_middle_pane_from_pubmed(self):
        search_text = self.ui.get_widget('middle_pane_search').get_text().strip()
        if not search_text: return
        self.active_threads[ thread.get_ident() ] = 'searching pubmed... (%s)' % search_text
        rows = []
        try:
            post_data = {
                'EntrezSystem2.PEntrez.DbConnector.Db': 'pubmed',
                'EntrezSystem2.PEntrez.DbConnector.TermToSearch': search_text,
                'EntrezSystem2.PEntrez.Pubmed.CommandTab.LimitsActive': 'false',
                'EntrezSystem2.PEntrez.Pubmed.Pubmed_ResultsPanel.Pager.InitialPageSize': '20',
                'EntrezSystem2.PEntrez.Pubmed.Pubmed_ResultsPanel.Pubmed_DisplayBar.PageSize': '20',
                'EntrezSystem2.PEntrez.Pubmed.Pubmed_ResultsPanel.Pubmed_DisplayBar.Presentation': 'XML',
            }
            params = openanything.fetch( 'http://www.ncbi.nlm.nih.gov/sites/entrez', post_data=post_data )
            post_data['EntrezSystem2.PEntrez.Pubmed.Pubmed_ResultsPanel.Pubmed_DisplayBar.Presentation'] = 'AbstractPlus'
            params2 = openanything.fetch( 'http://www.ncbi.nlm.nih.gov/sites/entrez', post_data=post_data )
            if (params['status']==200 or params['status']==302) and (params2['status']==200 or params2['status']==302):
                soup = BeautifulSoup.BeautifulStoneSoup( params['data'].replace('<i>','').replace('</i>','').replace('<s>','').replace('</s>','').replace('<b>','').replace('</b>','').replace('&gt;','>').replace('&lt;','<') )
                soup2 = BeautifulSoup.BeautifulSoup( params2['data'] )
                nodes = soup.findAll( 'tt', attrs={'class':'xmlrep'} )
                nodes2 = soup2.findAll( 'div', attrs={'class':'PubmedArticle'} )
                paired_nodes = []
                for i in range(0,len(nodes)):
                    paired_nodes.append( (nodes[i], nodes2[i]) )
                for node, node2 in paired_nodes:
                    #print 'found one ========================================================'
                    #print node.prettify()
                    #print node2.prettify()
                    try:
                        authors = []
                        for author_node in node.findAll('author'):
                            if author_node.has_key('validyn'):
                                authors.append( author_node.find('forename').string + ' '+ author_node.find('lastname').string )
                            else:
                                authors.append( author_node.find('firstname').string + ' '+ author_node.find('lastname').string )
                        try:
                            paper = Paper.objects.get( title=title, authors__name__exact=authors[0] )
                            paper_id = paper.id
                            if os.path.isfile( paper.get_full_text_filename() ):
                                icon = self.ui.get_widget('middle_top_pane').render_icon(gtk.STOCK_DND, gtk.ICON_SIZE_MENU)
                            else:
                                icon = None
                        except:
                            #traceback.print_exc()
                            paper = None
                            paper_id = -1
                            icon = None
                        try: journal = html_strip( node2.findAll('a')[0].string )
                        except: journal = ''
                        import_url = ''
                        try: 
                            doi = html_strip( node.find('articleid', idtype='doi').string )
                            import_url = 'http://dx.doi.org/'+doi
                        except: 
                            doi = ''
                        try:
                            pubmed_id = html_strip( node.find('articleid', idtype='pubmed').string )
                            import_url = 'http://www.ncbi.nlm.nih.gov/pubmed/'+pubmed_id
                        except: 
                            pubmed_id = ''
                        try: abstract = html_strip( node2.find('p', attrs={'class':'abstract'}).string )
                        except: abstract = ''
                        try: year = html_strip( node.find('journal').find('year').string )
                        except: year = ''
                        row = ( 
                            paper_id, # paper id 
                            ', '.join(authors), # authors 
                            html_strip( node.find('articletitle').string ), # title 
                            journal, # journal 
                            year, # year 
                            0, # ranking
                            abstract, # abstract
                            icon, # icon
                            import_url, # import_url
                            doi, # doi
                            '', # created
                            '', # updated
                            '', # empty_str
                            pubmed_id, # pubmed_id
                        )
                        #print thread.get_ident(), 'row =', row
                        rows.append( row )
                    except: 
                        #pass
                        traceback.print_exc()
                    
                self.update_middle_top_pane_from_row_list_if_we_are_still_the_preffered_thread(rows)
            else:
                gtk.gdk.threads_enter()
                error = gtk.MessageDialog( type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK, flags=gtk.DIALOG_MODAL )
                error.connect('response', lambda x,y: error.destroy())
                error.set_markup('<b>Unable to Search External Repository</b>\n\nHTTP Error code: %i' % params['status'])
                error.run()
                gtk.gdk.threads_leave()
        except:
            traceback.print_exc()
        if self.active_threads.has_key( thread.get_ident() ):
            del self.active_threads[ thread.get_ident() ]

    def refresh_middle_pane_from_citeseer(self):
        search_text = self.ui.get_widget('middle_pane_search').get_text().strip()
        if not search_text: return
        self.active_threads[ thread.get_ident() ] = 'searching citeseer... (%s)' % search_text
        rows = []
        try:
            params = openanything.fetch( 'http://citeseer.ist.psu.edu/cis?q=%s&cs=1&am=50' % defaultfilters.urlencode( search_text ) )
            if params['status']==200 or params['status']==302:
                for html in params['data'][ params['data'].find('<!--RLS-->')+20 : params['data'].find('<!--RLE-->') ].split('<!--RIS-->'):
                    node = BeautifulSoup.BeautifulStoneSoup( html.replace('<b>','').replace('</b>','') )
                    try:
                        title_authors_year = node.findAll('a')[0].string
                        o = re.search( '(.*) - (.*) [(](.*)[)]', title_authors_year )
                        title = html_strip( o.group(1) )
                        authors = html_strip( o.group(2) )
                        year = html_strip( o.group(3) )
                        import_url = node.findAll('a')[0]['href']
                        try:
                            papers = list( Paper.objects.filter( import_url=import_url ) )
                            papers.extend( Paper.objects.filter( title=title, authors__name__contains=authors.split(', ')[0] ) )
                            paper = papers[0]
                            paper_id = paper.id
                            if os.path.isfile( paper.get_full_text_filename() ):
                                icon = self.ui.get_widget('middle_top_pane').render_icon(gtk.STOCK_DND, gtk.ICON_SIZE_MENU)
                            else:
                                icon = None
                        except:
                            #traceback.print_exc()
                            paper = None
                            paper_id = -1
                            icon = None
                        try: journal = html_strip( node2.findAll('a')[0].string )
                        except: journal = ''
                        try: doi = html_strip( node.find('ArticleId', IdType='doi').string )
                        except: doi = ''
                        try: abstract = html_strip( node2.find('p', attrs={'class':'abstract'}).string )
                        except: abstract = ''
                        row = ( 
                            paper_id, # paper id 
                            authors, # authors 
                            title, # title 
                            journal, # journal 
                            year, # year 
                            0, # ranking
                            abstract, # abstract
                            icon, # icon
                            import_url, # import_url
                            doi, # doi
                            '', # created
                            '', # updated
                            '', # empty_str
                            '', # pubmed_id
                        )
                        rows.append( row )
                    except: 
                        #pass
                        traceback.print_exc()
                    
                self.update_middle_top_pane_from_row_list_if_we_are_still_the_preffered_thread(rows)
            else:
                gtk.gdk.threads_enter()
                error = gtk.MessageDialog( type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK, flags=gtk.DIALOG_MODAL )
                error.connect('response', lambda x,y: error.destroy())
                error.set_markup('<b>Unable to Search External Repository</b>\n\nHTTP Error code: %i' % params['status'])
                error.run()
                gtk.gdk.threads_leave()
        except:
            traceback.print_exc()
        if self.active_threads.has_key( thread.get_ident() ):
            del self.active_threads[ thread.get_ident() ]



class AuthorEditGUI:
    def __init__(self, author_id, callback_on_save=None):
        self.callback_on_save = callback_on_save
        if author_id==-1:
            self.author = Author.objects.create()
        else:
            self.author = Author.objects.get(id=author_id)
        self.ui = gtk.glade.XML(RUN_FROM_DIR + 'author_edit_gui.glade')
        self.author_edit_dialog = self.ui.get_widget('author_edit_dialog')
        self.author_edit_dialog.connect("delete-event", self.author_edit_dialog.destroy )
        self.ui.get_widget('button_connect').connect("clicked", lambda x: self.show_connect_menu() )
        self.ui.get_widget('button_cancel').connect("clicked", lambda x: self.author_edit_dialog.destroy() )
        self.ui.get_widget('button_delete').connect("clicked", lambda x: self.delete() )
        self.ui.get_widget('button_save').connect("clicked", lambda x: self.save() )
        self.ui.get_widget('entry_name').set_text( self.author.name )
        self.ui.get_widget('label_paper_count').set_text( str( self.author.paper_set.count() ) )
        self.ui.get_widget('notes').get_buffer().set_text( self.author.notes )
        self.ui.get_widget('notes').modify_base( gtk.STATE_NORMAL, gtk.gdk.color_parse("#fff7e8") )
        self.ui.get_widget('rating').set_value( self.author.rating )

        treeview_organizations = self.ui.get_widget('treeview_organizations')
        # id, org, location
        self.organizations_model = gtk.ListStore( int, str, str )
        treeview_organizations.set_model( self.organizations_model )
        treeview_organizations.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        renderer = gtk.CellRendererText()
        renderer.set_property('editable', True)
        renderer.connect( 'edited', lambda cellrenderertext, path, new_text: self.organizations_model.set_value( self.organizations_model.get_iter(path), 1, new_text ) or self.update_organization_name( self.organizations_model.get_value( self.organizations_model.get_iter(path), 0 ), new_text ) )
        column = gtk.TreeViewColumn("Organization", renderer, text=1)
        column.set_min_width(128)
        column.set_expand(True)
        column.connect('clicked', sort_model_by_column, self.organizations_model, 1)
        treeview_organizations.append_column( column )
        renderer = gtk.CellRendererText()
        renderer.set_property('editable', True)
        renderer.connect( 'edited', lambda cellrenderertext, path, new_text: self.organizations_model.set_value( self.organizations_model.get_iter(path), 2, new_text ) or self.update_organization_location( self.organizations_model.get_value( self.organizations_model.get_iter(path), 0 ), new_text ) )
        column = gtk.TreeViewColumn("Location", renderer, text=2)
        column.set_min_width(128)
        column.set_expand(True)
        column.connect('clicked', sort_model_by_column, self.organizations_model, 2)
        treeview_organizations.append_column( column )
        make_all_columns_resizeable_clickable_ellipsize( treeview_organizations.get_columns() )
        treeview_organizations.connect('button-press-event', self.handle_organizations_button_press_event)
        for organization in self.author.organizations.order_by('name'):
            self.organizations_model.append( ( organization.id, organization.name, organization.location ) )
        
        button = gtk.ToolButton(gtk.STOCK_ADD)
        button.set_tooltip(gtk.Tooltips(), 'Add an organization...')
        button.connect( 'clicked', lambda x: self.get_new_organizations_menu().popup(None, None, None, 0, 0) )
        button.show()
        self.ui.get_widget('toolbar_organizations').insert( button, -1 )
        
        self.author_edit_dialog.show()
        
    def delete(self):
        dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, flags=gtk.DIALOG_MODAL )
        dialog.set_markup('Really delete this author?')
        dialog.set_default_response(gtk.RESPONSE_NO)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        if response == gtk.RESPONSE_YES:
            self.author.delete()
            self.author_edit_dialog.destroy()
            main_gui.refresh_middle_pane_search()
        
    def update_organization_name( self, id, new_text ):
        organziation = Organization.objects.get(id=id)
        organziation.name = new_text.strip()
        organziation.save()
        
    def update_organization_location( self, id, new_text ):
        organziation = Organization.objects.get(id=id)
        organziation.location = new_text.strip()
        organziation.save()
        
    def handle_organizations_button_press_event(self, treeview, event):
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            time = event.time
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                treeview.grab_focus()
                treeview.set_cursor( path, col, 0)
                id = self.organizations_model.get_value( self.organizations_model.get_iter(path), 0 )
                if id>=0:
                    menu = gtk.Menu()
                    remove = gtk.ImageMenuItem(stock_id=gtk.STOCK_REMOVE)
                    remove.connect( 'activate', lambda x: self.organizations_model.remove( self.organizations_model.get_iter(path) ) )
                    menu.append(remove)
                    menu_item = gtk.ImageMenuItem(stock_id=gtk.STOCK_ADD)
                    menu_item.set_submenu( self.get_new_organizations_menu() )
                    menu.append(menu_item)
                    menu.show_all()
                    menu.popup(None, None, None, event.button, event.get_time())
            return True
        
    def get_new_organizations_menu(self):
        button_submenu = gtk.Menu()
        org_ids = set()
        self.organizations_model.foreach( lambda model, path, iter: org_ids.add( model.get_value( iter, 0 ) ) )
        for organization in Organization.objects.order_by('name'):
            if organization.id not in org_ids and len(organization.name):
                submenu_item = gtk.MenuItem( truncate_long_str(organization.name) )
                submenu_item.connect( 'activate', lambda x, r: self.organizations_model.append(r), ( organization.id, organization.name, organization.location ) )
                button_submenu.append( submenu_item )
        submenu_item = gtk.MenuItem( 'New...' )
        new_org = Organization.objects.create()
        submenu_item.connect( 'activate', lambda x, new_org: new_org.save() or self.organizations_model.append( ( new_org.id, new_org.name, new_org.location ) ), new_org )
        button_submenu.append( submenu_item )
        button_submenu.show_all()
        return button_submenu
        
        
    def save(self):
        self.author.name = self.ui.get_widget('entry_name').get_text()
        text_buffer = self.ui.get_widget('notes').get_buffer()
        self.author.notes = text_buffer.get_text( text_buffer.get_start_iter(), text_buffer.get_end_iter() )
        self.author.rating = round( self.ui.get_widget('rating').get_value() )
        self.author.save()
        org_ids = set()
        self.organizations_model.foreach( lambda model, path, iter: org_ids.add( model.get_value( iter, 0 ) ) )
        self.author.organizations = Organization.objects.in_bulk( list(org_ids) )
        self.author_edit_dialog.destroy()
        if self.callback_on_save:
            self.callback_on_save(self.author)
        main_gui.refresh_middle_pane_search()
    
    def connect(self, author, id):
        dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, flags=gtk.DIALOG_MODAL )
        dialog.set_markup('Really merge this author with "%s"?' % author.name)
        dialog.set_default_response(gtk.RESPONSE_NO)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        if response == gtk.RESPONSE_YES:
            author.merge(id)
            self.author_edit_dialog.destroy()
            main_gui.refresh_middle_pane_search()
    
    def show_connect_menu(self):
        menu = gtk.Menu()
        for author in Author.objects.order_by('name'):
            if author.id!=self.author.id:
                menu_item = gtk.MenuItem( truncate_long_str(author.name) )
                menu_item.connect( 'activate', lambda x, author, id: self.connect( author, id ), author, self.author.id )
                menu.append( menu_item )
        menu.popup(None, None, None, 0, 0)
        menu.show_all()
            

class OrganizationEditGUI:
    def __init__(self, id):
        self.organization = Organization.objects.get(id=id)
        self.ui = gtk.glade.XML(RUN_FROM_DIR + 'organization_edit_gui.glade')
        self.edit_dialog = self.ui.get_widget('organization_edit_dialog')
        self.edit_dialog.connect("delete-event", self.edit_dialog.destroy )
        self.ui.get_widget('button_connect').connect("clicked", lambda x: self.show_connect_menu() )
        self.ui.get_widget('button_cancel').connect("clicked", lambda x: self.edit_dialog.destroy() )
        self.ui.get_widget('button_delete').connect("clicked", lambda x: self.delete() )
        self.ui.get_widget('button_save').connect("clicked", lambda x: self.save() )
        self.ui.get_widget('entry_name').set_text( self.organization.name )
        self.ui.get_widget('entry_location').set_text( self.organization.location )
        self.edit_dialog.show()
        
    def delete(self):
        dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, flags=gtk.DIALOG_MODAL )
        dialog.set_markup('Really delete this organization?')
        dialog.set_default_response(gtk.RESPONSE_NO)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        if response == gtk.RESPONSE_YES:
            self.organization.delete()
            self.edit_dialog.destroy()
            main_gui.refresh_middle_pane_search()
        
    def save(self):
        self.organization.name = self.ui.get_widget('entry_name').get_text()
        self.organization.location = self.ui.get_widget('entry_location').get_text()
        self.organization.save()
        self.edit_dialog.destroy()
        main_gui.refresh_middle_pane_search()
        
    def connect(self, organization, id):
        dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, flags=gtk.DIALOG_MODAL )
        dialog.set_markup('Really merge this organization with "%s"?' % organization.name)
        dialog.set_default_response(gtk.RESPONSE_NO)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        if response == gtk.RESPONSE_YES:
            organization.merge(id)
            self.edit_dialog.destroy()
            main_gui.refresh_middle_pane_search()
    
    def show_connect_menu(self):
        menu = gtk.Menu()
        for organization in Organization.objects.order_by('name'):
            if organization.id!=self.organization.id:
                menu_item = gtk.MenuItem( truncate_long_str(organization.name) )
                menu_item.connect( 'activate', lambda x, organization, id: self.connect( organization, id ), organization, self.organization.id )
                menu.append( menu_item )
        menu.popup(None, None, None, 0, 0)
        menu.show_all()
            
            

class SourceEditGUI:
    def __init__(self, id):
        self.source = Source.objects.get(id=id)
        self.ui = gtk.glade.XML(RUN_FROM_DIR + 'source_edit_gui.glade')
        self.edit_dialog = self.ui.get_widget('source_edit_dialog')
        self.edit_dialog.connect("delete-event", self.edit_dialog.destroy )
        self.ui.get_widget('button_cancel').connect("clicked", lambda x: self.edit_dialog.destroy() )
        self.ui.get_widget('button_delete').connect("clicked", lambda x: self.delete() )
        self.ui.get_widget('button_save').connect("clicked", lambda x: self.save() )
        self.ui.get_widget('entry_name').set_text( self.source.name )
        self.ui.get_widget('entry_location').set_text( self.source.location )
        self.ui.get_widget('entry_issue').set_text( self.source.issue )
        self.edit_dialog.show()
        
    def delete(self):
        dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, flags=gtk.DIALOG_MODAL )
        dialog.set_markup('Really delete this source?')
        dialog.set_default_response(gtk.RESPONSE_NO)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        if response == gtk.RESPONSE_YES:
            self.source.delete()
            self.edit_dialog.destroy()
            main_gui.refresh_middle_pane_search()
        
    def save(self):
        self.source.name = self.ui.get_widget('entry_name').get_text()
        self.source.location = self.ui.get_widget('entry_location').get_text()
        self.source.issue = self.ui.get_widget('entry_issue').get_text()
        self.source.save()
        self.edit_dialog.destroy()
        main_gui.refresh_middle_pane_search()
        
            

class ReferenceEditGUI:
    def __init__(self, id):
        self.reference = Reference.objects.get(id=id)
        self.ui = gtk.glade.XML(RUN_FROM_DIR + 'reference_edit_gui.glade')
        self.edit_dialog = self.ui.get_widget('reference_edit_dialog')
        self.edit_dialog.connect("delete-event", self.edit_dialog.destroy )
        self.ui.get_widget('button_cancel').connect("clicked", lambda x: self.edit_dialog.destroy() )
        self.ui.get_widget('button_delete').connect("clicked", lambda x: self.delete() )
        self.ui.get_widget('button_save').connect("clicked", lambda x: self.save() )
        self.ui.get_widget('entry_line_from_referencing_paper').set_text( self.reference.line_from_referencing_paper )
        self.ui.get_widget('entry_doi_from_referencing_paper').set_text( self.reference.doi_from_referencing_paper )
        self.ui.get_widget('entry_url_from_referencing_paper').set_text( self.reference.url_from_referencing_paper )
        
        combobox_referencing_paper = self.ui.get_widget('combobox_referencing_paper')
        combobox_referenced_paper = self.ui.get_widget('combobox_referenced_paper')
        papers = [ ( paper.id, truncate_long_str(paper.pretty_string()) ) for paper in Paper.objects.order_by('title') ]
        papers.insert(0, ( -1, '(not in local library)' ))
        set_model_from_list( combobox_referencing_paper, papers )
        if self.reference.referencing_paper:
            combobox_referencing_paper.set_active( index_of_in_list_of_lists(value=self.reference.referencing_paper.id, list=papers, column=0, not_found=-1) )
        else:
            combobox_referencing_paper.set_active(0)
        set_model_from_list( combobox_referenced_paper, papers )
        if self.reference.referenced_paper:
            combobox_referenced_paper.set_active( index_of_in_list_of_lists(value=self.reference.referenced_paper.id, list=papers, column=0, not_found=-1) )
        else:
            combobox_referenced_paper.set_active(0)
        
        self.edit_dialog.show()
        
    def delete(self):
        dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, flags=gtk.DIALOG_MODAL )
        dialog.set_markup('Really delete this reference?')
        dialog.set_default_response(gtk.RESPONSE_NO)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        if response == gtk.RESPONSE_YES:
            self.reference.delete()
            self.edit_dialog.destroy()
        
    def save(self):
        self.reference.line_from_referencing_paper = self.ui.get_widget('entry_line_from_referencing_paper').get_text()
        self.reference.doi_from_referencing_paper = self.ui.get_widget('entry_doi_from_referencing_paper').get_text()
        self.reference.url_from_referencing_paper = self.ui.get_widget('entry_url_from_referencing_paper').get_text()
        print "self.ui.get_widget('combobox_referencing_paper').get_active()", self.ui.get_widget('combobox_referencing_paper').get_active()
        referencing_paper_id = self.ui.get_widget('combobox_referencing_paper').get_model()[ self.ui.get_widget('combobox_referencing_paper').get_active() ][0]
        try: self.reference.referencing_paper = Paper.objects.get(id=referencing_paper_id)
        except: self.reference.referencing_paper = None
        referenced_paper_id = self.ui.get_widget('combobox_referenced_paper').get_model()[ self.ui.get_widget('combobox_referenced_paper').get_active() ][0]
        try: self.reference.referenced_paper = Paper.objects.get(id=referenced_paper_id)
        except: self.reference.referenced_paper = None
        self.reference.save()
        self.edit_dialog.destroy()
        
            

class CitationEditGUI:
    def __init__(self, id):
        self.reference = Reference.objects.get(id=id)
        self.ui = gtk.glade.XML(RUN_FROM_DIR + 'citation_edit_gui.glade')
        self.edit_dialog = self.ui.get_widget('citation_edit_dialog')
        self.edit_dialog.connect("delete-event", self.edit_dialog.destroy )
        self.ui.get_widget('button_cancel').connect("clicked", lambda x: self.edit_dialog.destroy() )
        self.ui.get_widget('button_delete').connect("clicked", lambda x: self.delete() )
        self.ui.get_widget('button_save').connect("clicked", lambda x: self.save() )
        self.ui.get_widget('entry_line_from_referenced_paper').set_text( self.reference.line_from_referenced_paper )
        self.ui.get_widget('entry_doi_from_referenced_paper').set_text( self.reference.doi_from_referenced_paper )
        self.ui.get_widget('entry_url_from_referenced_paper').set_text( self.reference.url_from_referenced_paper )
        
        combobox_referencing_paper = self.ui.get_widget('combobox_referencing_paper')
        combobox_referenced_paper = self.ui.get_widget('combobox_referenced_paper')
        papers = [ ( paper.id, truncate_long_str(paper.pretty_string()) ) for paper in Paper.objects.order_by('title') ]
        papers.insert(0, ( -1, '(not in local library)' ))
        set_model_from_list( combobox_referencing_paper, papers )
        if self.reference.referencing_paper:
            combobox_referencing_paper.set_active( index_of_in_list_of_lists(value=self.reference.referencing_paper.id, list=papers, column=0, not_found=-1) )
        else:
            combobox_referencing_paper.set_active(0)
        set_model_from_list( combobox_referenced_paper, papers )
        if self.reference.referenced_paper:
            combobox_referenced_paper.set_active( index_of_in_list_of_lists(value=self.reference.referenced_paper.id, list=papers, column=0, not_found=-1) )
        else:
            combobox_referenced_paper.set_active(0)
        
        self.edit_dialog.show()
        
    def delete(self):
        dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, flags=gtk.DIALOG_MODAL )
        dialog.set_markup('Really delete this reference?')
        dialog.set_default_response(gtk.RESPONSE_NO)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        if response == gtk.RESPONSE_YES:
            self.reference.delete()
            self.edit_dialog.destroy()
        
    def save(self):
        self.reference.line_from_referenced_paper = self.ui.get_widget('entry_line_from_referenced_paper').get_text()
        self.reference.doi_from_referenced_paper = self.ui.get_widget('entry_doi_from_referenced_paper').get_text()
        self.reference.url_from_referenced_paper = self.ui.get_widget('entry_url_from_referenced_paper').get_text()
        referencing_paper_id = self.ui.get_widget('combobox_referencing_paper').get_model()[ self.ui.get_widget('combobox_referencing_paper').get_active() ][0]
        try: self.reference.referencing_paper = Paper.objects.get(id=referencing_paper_id)
        except: self.reference.referencing_paper = None
        referenced_paper_id = self.ui.get_widget('combobox_referenced_paper').get_model()[ self.ui.get_widget('combobox_referenced_paper').get_active() ][0]
        try: self.reference.referenced_paper = Paper.objects.get(id=referenced_paper_id)
        except: self.reference.referenced_paper = None
        self.reference.save()
        self.edit_dialog.destroy()
        
            

class PaperEditGUI:
    def __init__(self, id):
        self.paper = Paper.objects.get(id=id)
        self.ui = gtk.glade.XML(RUN_FROM_DIR + 'paper_edit_gui.glade')
        self.edit_dialog = self.ui.get_widget('paper_edit_dialog')
        self.edit_dialog.connect("delete-event", self.edit_dialog.destroy )
        self.ui.get_widget('button_cancel').connect("clicked", lambda x: self.edit_dialog.destroy() )
        self.ui.get_widget('button_delete').connect("clicked", lambda x: self.delete() )
        self.ui.get_widget('button_save').connect("clicked", lambda x: self.save() )
        self.ui.get_widget('toolbutton_refresh_from_pdf').connect("clicked", lambda x: self.toolbutton_refresh_extracted_text_from_pdf() )
        self.ui.get_widget('entry_title').set_text( self.paper.title )
        self.ui.get_widget('entry_doi').set_text( self.paper.doi )
        self.ui.get_widget('entry_import_url').set_text( self.paper.import_url )
        self.ui.get_widget('textview_abstract').get_buffer().set_text( self.paper.abstract )
        self.ui.get_widget('textview_bibtex').get_buffer().set_text( self.paper.bibtex )
        self.ui.get_widget('textview_extracted_text').get_buffer().set_text( self.paper.extracted_text )
        self.ui.get_widget('filechooserbutton').set_filename( self.paper.get_full_text_filename() )
        self.ui.get_widget('rating').set_value( self.paper.rating )
        self.ui.get_widget('spinbutton_read_count').set_value( self.paper.read_count )

        treeview_authors = self.ui.get_widget('treeview_authors')
        # id, name
        self.authors_model = gtk.ListStore( int, str )
        treeview_authors.set_model( self.authors_model )
        treeview_authors.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Author", renderer, text=1)
        column.set_expand(True)
        treeview_authors.append_column( column )
        make_all_columns_resizeable_clickable_ellipsize( treeview_authors.get_columns() )
        treeview_authors.connect('button-press-event', self.handle_authors_button_press_event)
        for author in self.paper.get_authors_in_order():
            self.authors_model.append( ( author.id, author.name ) )

        button = gtk.ToolButton(gtk.STOCK_ADD)
        button.set_tooltip(gtk.Tooltips(), 'Add an author...')
        button.connect( 'clicked', lambda x: self.get_new_authors_menu().popup(None, None, None, 0, 0) )
        button.show()
        self.ui.get_widget('toolbar_authors').insert( button, -1 )

        self.init_references_tab()
        self.init_citations_tab()

        self.edit_dialog.show()
        
    def toolbutton_refresh_extracted_text_from_pdf(self):
        self.paper.extract_document_information_from_pdf()
        self.authors_model.clear()
        for author in self.paper.get_authors_in_order():
            self.authors_model.append( ( author.id, author.name ) )
        self.ui.get_widget('textview_extracted_text').get_buffer().set_text( self.paper.extracted_text )
        self.ui.get_widget('entry_title').set_text( self.paper.title )
        
    def init_references_tab(self):
        treeview_references = self.ui.get_widget('treeview_references')
        # id, line, number, pix_buf
        self.references_model = gtk.ListStore( int, str, str, gtk.gdk.Pixbuf )
        treeview_references.set_model( self.references_model )
        treeview_references.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        treeview_references.append_column( gtk.TreeViewColumn("", gtk.CellRendererText(), markup=2) )
        column = gtk.TreeViewColumn()
        renderer = gtk.CellRendererPixbuf()
        column.pack_start(renderer, expand=False)
        column.add_attribute(renderer, 'pixbuf', 3)
        renderer = gtk.CellRendererText()
        column.pack_start(renderer, expand=True)
        column.add_attribute(renderer, 'markup', 1)        
        column.set_expand(True)
        treeview_references.append_column( column )
        #make_all_columns_resizeable_clickable_ellipsize( treeview_references.get_columns() )
        treeview_references.connect('button-press-event', self.handle_references_button_press_event)
        references = self.paper.reference_set.order_by('id')
        for i in range(0,len(references)):
            if references[i].referenced_paper and os.path.isfile( references[i].referenced_paper.get_full_text_filename() ):
                icon = treeview_references.render_icon(gtk.STOCK_DND, gtk.ICON_SIZE_MENU)
            else:
                icon = None
            self.references_model.append( ( references[i].id, references[i].line_from_referencing_paper , '<i>'+ str(i+1) +':</i>', icon ) )

        button = gtk.ToolButton(gtk.STOCK_ADD)
        button.set_tooltip(gtk.Tooltips(), 'Add a reference...')
        button.connect( 'clicked', lambda x: self.get_new_authors_menu().popup(None, None, None, 0, 0) )
        button.show()
        #self.ui.get_widget('toolbar_references').insert( button, -1 )
        
    def init_citations_tab(self):
        treeview_citations = self.ui.get_widget('treeview_citations')
        # id, line, number, pix_buf
        self.citations_model = gtk.ListStore( int, str, str, gtk.gdk.Pixbuf )
        treeview_citations.set_model( self.citations_model )
        treeview_citations.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        #treeview_citations.append_column( gtk.TreeViewColumn("", gtk.CellRendererText(), markup=2) )
        column = gtk.TreeViewColumn()
        renderer = gtk.CellRendererPixbuf()
        column.pack_start(renderer, expand=False)
        column.add_attribute(renderer, 'pixbuf', 3)
        renderer = gtk.CellRendererText()
        column.pack_start(renderer, expand=True)
        column.add_attribute(renderer, 'markup', 1)        
        column.set_expand(True)
        treeview_citations.append_column( column )
        #make_all_columns_resizeable_clickable_ellipsize( treeview_citations.get_columns() )
        treeview_citations.connect('button-press-event', self.handle_citations_button_press_event)
        references = self.paper.citation_set.order_by('id')
        for i in range(0,len(references)):
            if references[i].referencing_paper and os.path.isfile( references[i].referencing_paper.get_full_text_filename() ):
                icon = treeview_citations.render_icon(gtk.STOCK_DND, gtk.ICON_SIZE_MENU)
            else:
                icon = None
            self.citations_model.append( ( references[i].id, references[i].line_from_referenced_paper , '<i>'+ str(i+1) +':</i>', icon ) )

        button = gtk.ToolButton(gtk.STOCK_ADD)
        button.set_tooltip(gtk.Tooltips(), 'Add a reference...')
        button.connect( 'clicked', lambda x: self.get_new_authors_menu().popup(None, None, None, 0, 0) )
        button.show()
        #self.ui.get_widget('toolbar_references').insert( button, -1 )
    
    def delete(self):
        dialog = gtk.MessageDialog( type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, flags=gtk.DIALOG_MODAL )
        dialog.set_markup('Really delete this paper?')
        dialog.set_default_response(gtk.RESPONSE_NO)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        if response == gtk.RESPONSE_YES:
            self.paper.delete()
            self.edit_dialog.destroy()
            main_gui.refresh_middle_pane_search()
        
    def save(self):
        self.paper.title = self.ui.get_widget('entry_title').get_text()
        self.paper.doi = self.ui.get_widget('entry_doi').get_text()
        self.paper.import_url = self.ui.get_widget('entry_import_url').get_text()
        text_buffer = self.ui.get_widget('textview_abstract').get_buffer()
        self.paper.abstract = text_buffer.get_text( text_buffer.get_start_iter(), text_buffer.get_end_iter() )
        text_buffer = self.ui.get_widget('textview_bibtex').get_buffer()
        self.paper.bibtex = text_buffer.get_text( text_buffer.get_start_iter(), text_buffer.get_end_iter() )
        self.paper.rating = round( self.ui.get_widget('rating').get_value() )
        self.paper.read_count = self.ui.get_widget('spinbutton_read_count').get_value()
        new_file_name = self.ui.get_widget('filechooserbutton').get_filename()
        if new_file_name and new_file_name!=self.paper.get_full_text_filename():
            try:
                ext = new_file_name[ new_file_name.rfind('.')+1: ]
            except:
                ext = 'unknown'
            full_text_filename = defaultfilters.slugify(self.paper.doi) +'_'+ defaultfilters.slugify(self.paper.title) +'.'+ defaultfilters.slugify(ext)
            self.paper.save_full_text_file( full_text_filename, open(new_file_name,'r').read() )

        self.paper.authors.clear()
        self.authors_model.foreach( lambda model, path, iter: self.paper.authors.add( Author.objects.get(id=model.get_value( iter, 0 )) ) )
        
        self.paper.save()
        self.edit_dialog.destroy()
        main_gui.refresh_middle_pane_search()
        
    def handle_authors_button_press_event(self, treeview, event):
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            time = event.time
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                treeview.grab_focus()
                treeview.set_cursor( path, col, 0)
                id = self.authors_model.get_value( self.authors_model.get_iter(path), 0 )
                if id>=0:
                    menu = gtk.Menu()
                    remove = gtk.ImageMenuItem(stock_id=gtk.STOCK_REMOVE)
                    remove.connect( 'activate', lambda x: self.authors_model.remove( self.authors_model.get_iter(path) ) )
                    menu.append(remove)
                    menu_item = gtk.ImageMenuItem(stock_id=gtk.STOCK_ADD)
                    menu_item.set_submenu(self.get_new_authors_menu())
                    menu.append(menu_item)
                    menu.show_all()
                    menu.popup(None, None, None, event.button, event.get_time())
            return True

    def handle_references_button_press_event(self, treeview, event):
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            time = event.time
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                treeview.grab_focus()
                treeview.set_cursor( path, col, 0)
                id = self.references_model.get_value( self.references_model.get_iter(path), 0 )
                if id>=0:
                    reference = Reference.objects.get(id=id)
                    menu = gtk.Menu()
                    if reference.referenced_paper and os.path.isfile( reference.referenced_paper.get_full_text_filename() ):
                        menu_item = gtk.ImageMenuItem(stock_id=gtk.STOCK_OPEN)
                        menu_item.connect( 'activate', lambda x: reference.referenced_paper.open() )
                        menu.append(menu_item)
                    menu_item = gtk.ImageMenuItem(stock_id=gtk.STOCK_EDIT)
                    menu_item.connect( 'activate', lambda x: ReferenceEditGUI(reference.id) )
                    menu.append(menu_item)
                    menu.show_all()
                    menu.popup(None, None, None, event.button, event.get_time())
            return True

    def handle_citations_button_press_event(self, treeview, event):
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            time = event.time
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                treeview.grab_focus()
                treeview.set_cursor( path, col, 0)
                id = self.citations_model.get_value( self.citations_model.get_iter(path), 0 )
                if id>=0:
                    reference = Reference.objects.get(id=id)
                    menu = gtk.Menu()
                    if reference.referencing_paper and os.path.isfile( reference.referencing_paper.get_full_text_filename() ):
                        menu_item = gtk.ImageMenuItem(stock_id=gtk.STOCK_OPEN)
                        menu_item.connect( 'activate', lambda x: reference.referenced_paper.open() )
                        menu.append(menu_item)
                    menu_item = gtk.ImageMenuItem(stock_id=gtk.STOCK_EDIT)
                    menu_item.connect( 'activate', lambda x: CitationEditGUI(reference.id) )
                    menu.append(menu_item)
                    menu.show_all()
                    menu.popup(None, None, None, event.button, event.get_time())
            return True

    def get_new_authors_menu(self):
        button_submenu = gtk.Menu()
        author_ids = set()
        self.authors_model.foreach( lambda model, path, iter: author_ids.add( model.get_value( iter, 0 ) ) )
        for author in Author.objects.order_by('name'):
            if author.id not in author_ids and len(author.name):
                submenu_item = gtk.MenuItem( truncate_long_str(author.name) )
                submenu_item.connect( 'activate', lambda x, r: self.authors_model.append(r), ( author.id, author.name ) )
                button_submenu.append( submenu_item )
        submenu_item = gtk.MenuItem( 'New...' )
        submenu_item.connect( 'activate', lambda x: AuthorEditGUI(-1, callback_on_save=self.add_new_author) )
        button_submenu.append( submenu_item )
        button_submenu.show_all()
        return button_submenu
        
    def add_new_author(self, new_author):
        self.authors_model.append( ( new_author.id, new_author.name ) )
        
        
class PreferencesGUI:
    def __init__(self):
        self.ui = gtk.glade.XML(RUN_FROM_DIR + 'preferences_gui.glade')
        self.edit_dialog = self.ui.get_widget('preferences_dialog')
        self.edit_dialog.connect("delete-event", self.edit_dialog.destroy )
        self.ui.get_widget('button_cancel').connect("clicked", lambda x: self.edit_dialog.destroy() )
        self.ui.get_widget('button_save').connect("clicked", lambda x: self.save() )
        self.edit_dialog.show()
        
    def save(self):
        self.paper.title = self.ui.get_widget('entry_title').get_text()
        self.paper.doi = self.ui.get_widget('entry_doi').get_text()
        text_buffer = self.ui.get_widget('textview_abstract').get_buffer()
        self.paper.abstract = text_buffer.get_text( text_buffer.get_start_iter(), text_buffer.get_end_iter() )
        self.paper.save()
        self.edit_dialog.destroy()
        main_gui.refresh_middle_pane_search()
    

            

def init_db():
    import django.core.management.commands.syncdb
    django.core.management.commands.syncdb.Command().handle_noargs(interactive=True)
    for app in models.get_apps():
        app_name = app.__name__.split('.')[-2]
        if app_name=='gPapers':
            import deseb.schema_evolution
            deseb.schema_evolution.evolvedb(app, interactive=False, managed_upgrade_only=True)


if __name__ == "__main__":
    
    MEDIA_ROOT = settings.MEDIA_ROOT

    print 'gpapers: using database at', MEDIA_ROOT
    print
    
    if not os.path.isdir( MEDIA_ROOT ):
        os.mkdir( MEDIA_ROOT )
    if not os.path.isdir( os.path.join( MEDIA_ROOT, 'papers' ) ):
        os.mkdir( os.path.join( MEDIA_ROOT, 'papers' ) )
    global main_gui
    init_db()
    main_gui = MainGUI()
    gtk.main()
        
