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


import settings
import desktop, openanything
from django.template import defaultfilters
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
from django.db.models import Q
from gPapers.models import *


p_whitespace = re.compile( '[\s]+')

def html_strip(s):
    return p_whitespace.sub( ' ', str(s).replace('&nbsp;', ' ').strip() )

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
    print 'trying to fetch:', urls
    t = thread.start_new_thread( import_citations, (urls,) )
    
def fetch_citations_via_references(references):
    print 'trying to fetch:', references
    t = thread.start_new_thread( import_citations_via_references, (references,) )

def fetch_documents_via_filenames(filenames):
    print 'trying to fetch:', filenames
    t = thread.start_new_thread( import_documents_via_filenames, (filenames,) )
    
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
    
def import_citation(url, refresh_after=True):
    main_gui.active_thread_ids.add( thread.get_ident() )
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
            paper = import_acm_citation(params)
            if refresh_after: main_gui.refresh_middle_pane_search()
            return paper
        if params['url'].startswith('http://ieeexplore.ieee.org'):
            if params['url'].find('search/wrapper.jsp')>-1:
                paper = import_ieee_citation( openanything.fetch( params['url'].replace('search/wrapper.jsp','xpls/abs_all.jsp') ) )
                if refresh_after: main_gui.refresh_middle_pane_search()
            else:
                paper = import_ieee_citation( params )
                if refresh_after: main_gui.refresh_middle_pane_search()
            return paper
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
    error.set_markup('<b>Unknown Source</b>\n\nThis URL is from an unknown citation source.')
    error.run()
    gtk.gdk.threads_leave()
    main_gui.active_thread_ids.remove( thread.get_ident() )
    
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

def import_acm_citation(params):
    print thread.get_ident(), 'downloading acm citation:', params['url']
    paper = None
    try:
        print thread.get_ident(), 'parsing...'
        soup = BeautifulSoup.BeautifulSoup( params['data'] )
        
        title = []
        for node in soup.findAll('td', attrs={'class':'medium-text'})[0].findAll('strong'):
            title.append(node.string)
        try: doi = str(soup.find('form', attrs={'name':'popbinder'}).nextSibling.table.findAll('tr')[-1].findAll('td')[-1].a.string)
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
        
        if full_text_data:
            md5_hexdigest = get_md5_hexdigest_from_data( full_text_data )
            papers = Paper.objects.filter( full_text_md5=md5_hexdigest )
        else:
            papers = []

        if len(papers):
            print thread.get_ident(), 'paper already imported'
            if not should_we_reimport_paper(papers[0]):
                return
            created = False
            paper = papers[0]
            paper.title = title
            paper.doi = doi
            paper.save()
        else:
            paper, created = Paper.objects.get_or_create(
                title = html_strip(''.join(title)),
                doi = doi,
            )
            if created:
                if full_text_filename and full_text_data:
                    paper.save_full_text_file( full_text_filename, full_text_data )
                paper.save()
            else: 
                print thread.get_ident(), 'paper already imported'
                if not should_we_reimport_paper(paper):
                    return

        try: publisher_name = html_strip( soup.find('div', attrs={'class':'publishers'}).contents[0] )
        except: publisher_name = None
        if publisher_name:
            publisher, created = Publisher.objects.get_or_create( name=publisher_name )
            if created: publisher.save()
        else:
            publisher = None
            
        node = soup.find('strong', text='Source').parent.parent.nextSibling.nextSibling
        source, created = Source.objects.get_or_create(
            name = html_strip(node.contents[1].string),
            issue = html_strip(node.contents[6].string),
            location = html_strip(node.contents[11].string),
            publication_date = date( int( html_strip( re.search( 'Year of Publication:(.*)', params['data'] ).group(1) ) ), 1, 1 ),
#            publication_date = date( int( html_strip(node.contents[17].string).replace('Year of Publication: ','') ), 1, 1 ),
            publisher = publisher,
        )
        if created:
            for n in node.contents:
                try:
                    if n.name=='a' and n['href'].startswith('toc.cfm'):
                        source.acm_toc_url = ACM_BASE_URL +'/'+ n['href']
                except:
                    pass
            source.save()
        
        paper.source = source
        try: paper.source_session = html_strip( re.search( 'SESSION:(.*)', params['data'] ).group(1) )
        except: pass
        try: paper.source_pages = html_strip( re.search( 'Pages:(.*)', params['data'] ).group(1) )
        except: pass
        try: paper.abstract = html_strip( soup.find('p', attrs={'class':'abstract'}).string )
        except: pass
        paper.save()
        
        for node in soup.find('div', attrs={'class':'authors'}).findAll('tr'):
            td1, td2 = node.findAll('td')
            org_and_location = td2.find('small')
            if org_and_location:
                if org_and_location.string.find(',')>-1:
                    organization_name = html_strip( org_and_location.string[0:org_and_location.string.index(',')] )
                    location = html_strip( org_and_location.string[org_and_location.string.index(',')+1:] )
                else:
                    organization_name = html_strip(org_and_location)
                    location = ''
                organization, created = Organization.objects.get_or_create( name=organization_name )
                if created: organization.save()
                author, created = Author.objects.get_or_create(
                    name = html_strip( td1.find('a').string ),
                )
                author.organizations.add(organization)
                author.save()
                paper.organizations.add(organization)
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
        print thread.get_ident(), 'imported paper =', paper.doi, paper.title, paper.authors.all()
        return paper
    except:
        traceback.print_exc()
        if paper:
            paper.delete()


def import_ieee_citation(params):
    print thread.get_ident(), 'downloading ieee citation:', params['url']
    paper = None
    try:
        print thread.get_ident(), 'parsing...'
        file = open('import.html','w')
        file.write( params['data'] )
        file.close()
        soup = BeautifulSoup.BeautifulSoup( params['data'].replace('<!-BMS End-->','').replace('<in>','') )
        
        print soup.find('span', attrs={'class':'headNavBlueXLarge2'})
        
        paper, created = Paper.objects.get_or_create(
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
        
        paper.source = source
        paper.source_session = ''
        #paper.source_pages = html_strip( re.search( 'On page(s):(.*)<BR>', params['data'], re.DOTALL ).group(1) ),
        paper.abstract = html_strip( soup.findAll( 'td', attrs={'class':'bodyCopyBlackLargeSpaced'})[0].contents[-1] )
        paper.save()
        
        for node in soup.findAll('p', attrs={'class':'bodyCopyBlackLargeSpaced'})[0].findAll('a', attrs={'class':'bodyCopy'}):
            print 'author node:', node
            if node.string:
                name = html_strip( node.string )
            else:
                name = html_strip( node.b.font.string ) + html_strip( node.contents[-1] )
            print 'author', name
            author, created = Author.objects.get_or_create(
                name = name,
            )
            if created: author.save()
            paper.authors.add( author )
            
        for node in soup.findAll('a', attrs={'class':'bodyCopy'}):
            if node.contents[0]=='PDF':
                file_url = IEEE_BASE_URL + node['href']
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
        
        print thread.get_ident(), 'imported paper =', paper.id, paper.doi, paper.title, paper.authors.all()
        return paper
    except:
        traceback.print_exc()
        if paper:
            paper.delete()

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
        paper, created = Paper.objects.get_or_create( full_text_md5=md5_hexdigest )
        if created:
            paper.title = filename
            paper.save_full_text_file( defaultfilters.slugify(filename.replace('.pdf',''))+'.pdf', data )
            paper.save()
            print thread.get_ident(), 'imported paper =', filename
        else:
            print thread.get_ident(), 'paper already exists: paper =', paper.id, paper.doi, paper.title, paper.authors.all()
    except:
        traceback.print_exc()
        if paper:
            paper.delete()


class MainGUI:
    
    current_middle_top_pane_refresh_thread_ident = None
    active_thread_ids = set()
    
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
        self.refresh_left_pane()  
        self.init_busy_notifier()      
        main_window.show()
        
    def init_busy_notifier(self):
        busy_notifier = self.ui.get_widget('busy_notifier')
        busy_notifier.set_from_file( os.path.join( RUN_FROM_DIR, 'icons', 'blank.gif' ) )
        self.busy_notifier_is_running = False
        thread.start_new_thread( self.watch_busy_notifier, () )

    def watch_busy_notifier(self):
        while True:
            try:
                if len(self.active_thread_ids):
                    if not self.busy_notifier_is_running:
                        self.ui.get_widget('busy_notifier').set_from_file( os.path.join( RUN_FROM_DIR, 'icons', 'process-working.gif' ) )
                        self.busy_notifier_is_running = True
                else:
                    if self.busy_notifier_is_running:
                        self.ui.get_widget('busy_notifier').set_from_file( os.path.join( RUN_FROM_DIR, 'icons', 'blank.gif' ) )
                        self.busy_notifier_is_running = False
            except:
                traceback.print_exc()
            time.sleep(1)
        

    def init_menu(self):
        self.ui.get_widget('menuitem_quit').connect('activate', lambda x: sys.exit(0))
        self.ui.get_widget('menuitem_import_url').connect('activate', self.import_url)
        self.ui.get_widget('menuitem_import_doi').connect('activate', self.import_doi)
        self.ui.get_widget('menuitem_import_file').connect('activate', self.import_file)
        self.ui.get_widget('menuitem_preferences').connect('activate', lambda x: PreferencesGUI())
        
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
        
    def init_my_library_filter_pane(self):
        
        author_filter = self.ui.get_widget('author_filter')
        # id, author
        self.author_filter_model = gtk.ListStore( int, str )
        author_filter.set_model( self.author_filter_model )
        author_filter.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        column = gtk.TreeViewColumn("Author", gtk.CellRendererText(), text=1)
        column.set_min_width(128)
        column.set_expand(True)
        author_filter.append_column( column )
        self.make_all_columns_resizeable_clickable_ellipsize( author_filter.get_columns() )
        author_filter.get_selection().connect( 'changed', lambda x: thread.start_new_thread( self.refresh_middle_pane_from_my_library, (False,) ) )
        author_filter.connect('row-activated', self.handle_author_filter_row_activated )

        organization_filter = self.ui.get_widget('organization_filter')
        # id, org
        self.organization_filter_model = gtk.ListStore( int, str )
        organization_filter.set_model( self.organization_filter_model )
        organization_filter.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        column = gtk.TreeViewColumn("Organization", gtk.CellRendererText(), text=1)
        column.set_min_width(128)
        column.set_expand(True)
        organization_filter.append_column( column )
        self.make_all_columns_resizeable_clickable_ellipsize( organization_filter.get_columns() )
        organization_filter.get_selection().connect( 'changed', lambda x: thread.start_new_thread( self.refresh_middle_pane_from_my_library, (False,) ) )
        organization_filter.connect('row-activated', self.handle_organization_filter_row_activated )

        source_filter = self.ui.get_widget('source_filter')
        # id, name, issue, location, publisher, date
        self.source_filter_model = gtk.ListStore( int, str, str, str, str, str )
        source_filter.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        source_filter.set_model( self.source_filter_model )
        column = gtk.TreeViewColumn("Source", gtk.CellRendererText(), text=1)
        column.set_min_width(128)
        column.set_expand(True)
        source_filter.append_column( column )
        source_filter.append_column( gtk.TreeViewColumn("Issue", gtk.CellRendererText(), text=2) )
        source_filter.append_column( gtk.TreeViewColumn("Location", gtk.CellRendererText(), text=3) )
        source_filter.append_column( gtk.TreeViewColumn("Publisher", gtk.CellRendererText(), text=4) )
        self.make_all_columns_resizeable_clickable_ellipsize( source_filter.get_columns() )
        source_filter.get_selection().connect( 'changed', lambda x: thread.start_new_thread( self.refresh_middle_pane_from_my_library, (False,) ) )
        source_filter.connect('row-activated', self.handle_source_filter_row_activated )

    def refresh_my_library_filter_pane(self):

        self.author_filter_model.clear()
        for author in Author.objects.all():
            self.author_filter_model.append( ( author.id, author.name ) )

        self.organization_filter_model.clear()
        for organization in Organization.objects.all():
            self.organization_filter_model.append( ( organization.id, organization.name ) )

        self.source_filter_model.clear()
        for source in Source.objects.all():
            self.source_filter_model.append( ( source.id, source.name, source.issue, source.location, source.publisher, source.publication_date ) )

        
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
        button.set_tooltip_markup('Create a new document collection...')
        button.connect( 'clicked', lambda x: self.create_playlist() )
        button.show()
        left_pane_toolbar.insert( button, -1 )

        try:
            self.current_playlist = Playlist.objects.get(id=liststore[rows[0]][2])
            button = gtk.ToolButton(gtk.STOCK_REMOVE)
            button.set_tooltip_markup('Delete this collection...')
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
        self.select_middle_top_pane_item( self.ui.get_widget('middle_top_pane').get_selection() )

    def init_middle_top_pane(self):
        middle_top_pane = self.ui.get_widget('middle_top_pane')
        # id, authors, title, journal, year, rating, abstract, icon, import_url, doi, created, updated
        self.middle_top_pane_model = gtk.ListStore( int, str, str, str, str, int, str, gtk.gdk.Pixbuf, str, str, str, str )
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
        column = gtk.TreeViewColumn("Imported", gtk.CellRendererText(), markup=10)
        column.set_min_width(80)
        column.set_expand(False)
        middle_top_pane.append_column( column )
        
        self.make_all_columns_resizeable_clickable_ellipsize( middle_top_pane.get_columns() )
        
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
            if paper.full_text:
                desktop.open( paper.get_full_text_filename() )
                paper.read_count = paper.read_count + 1
                paper.save()
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
                print 'path, col, cellx, celly', path, col, cellx, celly
                treeview.grab_focus()
                treeview.set_cursor( path, col, 0)
                if len(path)==2 and False:
                    menu = gtk.Menu()
                    delete = gtk.ImageMenuItem(stock_id=gtk.STOCK_DELETE)
                    #delete.connect( 'activate', self.delete_element, pthinfo[0][0], self.included_dirs, self.refresh_included_dirs_list )
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

    def make_all_columns_resizeable_clickable_ellipsize(self, columns):
        for column in columns:
            column.set_resizable(True)
            column.set_clickable(True)
            #column.connect('clicked', self.sortRows)
            for renderer in column.get_cell_renderers():
                if renderer.__class__.__name__=='CellRendererText':
                    renderer.set_property( 'ellipsize', pango.ELLIPSIZE_END )
        
        
    def select_middle_top_pane_item(self, selection):
        liststore, rows = selection.get_selected_rows()
        self.paper_information_pane_model.clear()
        self.ui.get_widget('paper_information_pane').columns_autosize()
        paper_notes = self.ui.get_widget('paper_notes')
        try: 
            if not self.update_paper_notes_handler_id==None:
                paper_notes.get_buffer().disconnect(self.update_paper_notes_handler_id)
            self.update_paper_notes_handler_id = None
        except:
            self.update_paper_notes_handler_id = None
        paper_notes.get_buffer().set_text('')
        paper_notes.set_property('sensitive', False)
        paper_information_toolbar = self.ui.get_widget('paper_information_toolbar')
        paper_information_toolbar.foreach( paper_information_toolbar.remove )
        if len(rows)==0:
            pass
        elif len(rows)==1:
            try: 
                paper = Paper.objects.get(id=liststore[rows[0]][0])
            except:
                paper = None
            if liststore[rows[0]][2]:
                self.paper_information_pane_model.append(( '<b>Title:</b>', liststore[rows[0]][2] ,))
            if liststore[rows[0]][1]:
                self.paper_information_pane_model.append(( '<b>Authors:</b>', liststore[rows[0]][1] ,))
            if liststore[rows[0]][3]:
                self.paper_information_pane_model.append(( '<b>Journal:</b>', liststore[rows[0]][3] ,))
            if liststore[rows[0]][9]:
                self.paper_information_pane_model.append(( '<b>DOI:</b>', liststore[rows[0]][9] ,))
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
                    button = gtk.ToolButton(gtk.STOCK_REFRESH)
                    button.set_tooltip_markup('Re-add this paper to your library...')
                    button.connect( 'clicked', lambda x: fetch_citation_via_url(liststore[rows[0]][8]) )
                    paper_information_toolbar.insert( button, -1 )
                else:
                    button = gtk.ToolButton(gtk.STOCK_ADD)
                    button.set_tooltip_markup('Add this paper to your library...')
                    button.connect( 'clicked', lambda x: fetch_citation_via_url(liststore[rows[0]][8]) )
                    paper_information_toolbar.insert( button, -1 )
                    
            if paper:
                importable_references = set()
                references = paper.reference_set.all()
#                self.paper_information_pane_model.append(( '<b>References:</b>', '\n'.join( [ '<i>'+ str(i) +':</i> '+ references[i].line_from_referencing_paper for i in range(0,len(references)) ] ) ,))
                for i in range(0,len(references)):
                    if i==0: col1 = '<b>References:</b>'
                    else: col1 = ''
                    if references[i].url_from_referencing_paper and not references[i].referenced_paper:
                        importable_references.add( references[i] )
                    self.paper_information_pane_model.append(( col1, '<i>'+ str(i+1) +':</i> '+ references[i].line_from_referencing_paper ) )
                importable_citations = set()
                citations = paper.citation_set.all()
#                self.paper_information_pane_model.append(( '<b>Citations:</b>', '\n'.join( [ '<i>'+ str(i) +':</i> '+ citations[i].line_from_referenced_paper for i in range(0,len(citations)) ] ) ,))
                for i in range(0,len(citations)):
                    if i==0: col1 = '<b>Citations:</b>'
                    else: col1 = ''
                    if citations[i].url_from_referenced_paper and not citations[i].referencing_paper:
                        importable_citations.add( citations[i] )
                    self.paper_information_pane_model.append(( col1, '<i>'+ str(i+1) +':</i> '+ citations[i].line_from_referenced_paper ) )

                paper_notes.get_buffer().set_text( paper.notes )
                paper_notes.set_property('sensitive', True)
                self.update_paper_notes_handler_id = paper_notes.get_buffer().connect('changed', self.update_paper_notes, paper.id )

                button = gtk.ToolButton(gtk.STOCK_EDIT)
                button.set_tooltip_markup('Edit this paper...')
                button.connect( 'clicked', lambda x: PaperEditGUI(paper.id) )
                paper_information_toolbar.insert( button, -1 )

                if self.current_playlist:
                    button = gtk.ToolButton(gtk.STOCK_REMOVE)
                    button.set_tooltip_markup('Remove this paper from this collection...')
                    button.connect( 'clicked', lambda x: self.remove_papers_from_current_playlist([paper.id]) )
                    paper_information_toolbar.insert( button, -1 )

                if importable_references or importable_citations:
                    import_button = gtk.MenuToolButton(gtk.STOCK_ADD)
                    import_button.set_tooltip_markup('Import all cited and referenced documents...(%i)' % len(importable_references.union(importable_citations)) )
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

            selected_valid_paper_ids = []
            for row in rows:
                if liststore[row][0]!=-1:
                    selected_valid_paper_ids.append( liststore[row][0] )
            print 'selected_valid_paper_ids', selected_valid_paper_ids
            if len(selected_valid_paper_ids):
                button = gtk.ToolButton(gtk.STOCK_REMOVE)
                button.set_tooltip_markup('Remove these papers from your library...')
                button.connect( 'clicked', lambda x: self.delete_papers( selected_valid_paper_ids ) )
                paper_information_toolbar.insert( button, -1 )

        paper_information_toolbar.show_all()
        
    def echo_objects(self, a=None, b=None, c=None):
        print a,b,c
        
    def update_paper_notes(self, text_buffer, paper_id):
        paper = Paper.objects.get(id=paper_id)
        #print 'saving notes', text_buffer.get_text( text_buffer.get_start_iter(), text_buffer.get_end_iter() )
        paper.notes = text_buffer.get_text( text_buffer.get_start_iter(), text_buffer.get_end_iter() )
        paper.save()
        
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
                print 'deleting paper:', paper.doi, paper.title, paper.authors.all()
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
    
    def update_middle_top_pane_from_row_list_if_we_are_still_the_preffered_thread(self, rows):
        middle_top_pane = self.ui.get_widget('middle_top_pane')
        if self.current_middle_top_pane_refresh_thread_ident==thread.get_ident():
            gtk.gdk.threads_enter()
            self.middle_top_pane_model.clear()
            for row in rows:
                self.middle_top_pane_model.append(row)
            middle_top_pane.columns_autosize()
            gtk.gdk.threads_leave()

    def refresh_middle_pane_from_my_library(self, refresh_library_filter_pane=True):
        self.active_thread_ids.add( thread.get_ident() )
        try:
            rows = []
            my_library_filter_pane = self.ui.get_widget('my_library_filter_pane')
            
            if not self.current_playlist and self.current_papers==None:
                
                search_text = self.ui.get_widget('middle_pane_search').get_text()
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
                    paper_query = Paper.objects.all()
    
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
                    paper.rating, 
                    paper.abstract, 
                    icon, # icon
                    None, # import_url
                    paper.doi, # doi
                    paper.created.strftime(DATE_FORMAT), # created
                    paper.updated.strftime(DATE_FORMAT), # updated
                ) )
            self.update_middle_top_pane_from_row_list_if_we_are_still_the_preffered_thread(rows)
            self.refresh_my_library_count()
        except:
            traceback.print_exc()
        self.active_thread_ids.remove( thread.get_ident() )
    
    def refresh_my_library_count(self):
        gtk.gdk.threads_enter()
        selection = self.ui.get_widget('left_pane').get_selection()
        liststore, rows = selection.get_selected_rows()
        liststore.set_value( self.left_pane_model.get_iter((0,)), 0, '<b>My Library</b>  <span foreground="#888888">(%i)</span>' % Paper.objects.count() )
        gtk.gdk.threads_leave()
    
    def refresh_middle_pane_from_acm(self):
        if not self.ui.get_widget('middle_pane_search').get_text(): return
        self.active_thread_ids.add( thread.get_ident() )
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
                    #print 'first_author', first_author
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
                        '', # doi
                        '', # created
                        '', # updated
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
        self.active_thread_ids.remove( thread.get_ident() )
            
    def refresh_middle_pane_from_ieee(self):
        if not self.ui.get_widget('middle_pane_search').get_text(): return
        self.active_thread_ids.add( thread.get_ident() )
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
                        #print 'first_author', first_author
                        try:
                            paper = Paper.objects.get( title=title, authors__name__exact=first_author )
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
        self.active_thread_ids.remove( thread.get_ident() )

    def refresh_middle_pane_from_pubmed(self):
        if not self.ui.get_widget('middle_pane_search').get_text(): return
        self.active_thread_ids.add( thread.get_ident() )
        rows = []
        try:
            post_data = {
                'EntrezSystem2.PEntrez.DbConnector.Db': 'pubmed',
                'EntrezSystem2.PEntrez.DbConnector.TermToSearch': self.ui.get_widget('middle_pane_search').get_text(),
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
                print len(nodes), len(nodes2)
                for i in range(0,len(nodes)):
                    paired_nodes.append( (nodes[i], nodes2[i]) )
                for node, node2 in paired_nodes:
                    #print 'found one ========================================================'
                    #print node.prettify()
                    #print node2.prettify()
                    try:
                        authors = []
                        for author_node in node.findAll('author'):
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
                        try: doi = html_strip( node.find('ArticleId', IdType='doi').string )
                        except: doi = ''
                        try: abstract = html_strip( node2.find('p', attrs={'class':'abstract'}).string )
                        except: abstract = ''
                        row = ( 
                            paper_id, # paper id 
                            ', '.join(authors), # authors 
                            html_strip( node.find('articletitle').string ), # title 
                            journal, # journal 
                            html_strip( node.find('journal').find('year').string ), # year 
                            0, # ranking
                            abstract, # abstract
                            icon, # icon
                            '', # import_url
                            doi, # doi
                            '', # created
                            '', # updated
                        )
                        print thread.get_ident(), 'row =', row
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
        self.active_thread_ids.remove( thread.get_ident() )



class AuthorEditGUI:
    def __init__(self, author_id):
        self.author = Author.objects.get(id=author_id)
        self.ui = gtk.glade.XML(RUN_FROM_DIR + 'author_edit_gui.glade')
        self.author_edit_dialog = self.ui.get_widget('author_edit_dialog')
        self.author_edit_dialog.connect("delete-event", self.author_edit_dialog.destroy )
        self.ui.get_widget('button_cancel').connect("clicked", lambda x: self.author_edit_dialog.destroy() )
        self.ui.get_widget('button_delete').connect("clicked", lambda x: self.delete() )
        self.ui.get_widget('button_save').connect("clicked", lambda x: self.save() )
        self.ui.get_widget('entry_name').set_text( self.author.name )
        self.author_edit_dialog.show()
        
    def delete(self):
        self.author.delete()
        self.author_edit_dialog.destroy()
        main_gui.refresh_middle_pane_search()
        
    def save(self):
        self.author.name = self.ui.get_widget('entry_name').get_text()
        self.author.save()
        self.author_edit_dialog.destroy()
        main_gui.refresh_middle_pane_search()
        
            

class OrganizationEditGUI:
    def __init__(self, id):
        self.organization = Organization.objects.get(id=id)
        self.ui = gtk.glade.XML(RUN_FROM_DIR + 'organization_edit_gui.glade')
        self.edit_dialog = self.ui.get_widget('organization_edit_dialog')
        self.edit_dialog.connect("delete-event", self.edit_dialog.destroy )
        self.ui.get_widget('button_cancel').connect("clicked", lambda x: self.edit_dialog.destroy() )
        self.ui.get_widget('button_delete').connect("clicked", lambda x: self.delete() )
        self.ui.get_widget('button_save').connect("clicked", lambda x: self.save() )
        self.ui.get_widget('entry_name').set_text( self.organization.name )
        self.ui.get_widget('entry_location').set_text( self.organization.location )
        self.edit_dialog.show()
        
    def delete(self):
        self.organization.delete()
        self.edit_dialog.destroy()
        main_gui.refresh_middle_pane_search()
        
    def save(self):
        self.organization.name = self.ui.get_widget('entry_name').get_text()
        self.organization.location = self.ui.get_widget('entry_location').get_text()
        self.organization.save()
        self.edit_dialog.destroy()
        main_gui.refresh_middle_pane_search()
        
            

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
        
            

class PaperEditGUI:
    def __init__(self, id):
        self.paper = Paper.objects.get(id=id)
        self.ui = gtk.glade.XML(RUN_FROM_DIR + 'paper_edit_gui.glade')
        self.edit_dialog = self.ui.get_widget('paper_edit_dialog')
        self.edit_dialog.connect("delete-event", self.edit_dialog.destroy )
        self.ui.get_widget('button_cancel').connect("clicked", lambda x: self.edit_dialog.destroy() )
        self.ui.get_widget('button_delete').connect("clicked", lambda x: self.delete() )
        self.ui.get_widget('button_save').connect("clicked", lambda x: self.save() )
        self.ui.get_widget('entry_title').set_text( self.paper.title )
        self.ui.get_widget('entry_doi').set_text( self.paper.doi )
        self.ui.get_widget('textview_abstract').get_buffer().set_text( self.paper.abstract )
        self.ui.get_widget('filechooserbutton').set_filename( self.paper.get_full_text_filename() )
        self.edit_dialog.show()
        
    def delete(self):
        self.paper.delete()
        self.edit_dialog.destroy()
        main_gui.refresh_middle_pane_search()
        
    def save(self):
        self.paper.title = self.ui.get_widget('entry_title').get_text()
        self.paper.doi = self.ui.get_widget('entry_doi').get_text()
        text_buffer = self.ui.get_widget('textview_abstract').get_buffer()
        self.paper.abstract = text_buffer.get_text( text_buffer.get_start_iter(), text_buffer.get_end_iter() )
        new_file_name = self.ui.get_widget('filechooserbutton').get_filename()
        if new_file_name and new_file_name!=self.paper.get_full_text_filename():
            try:
                ext = new_file_name[ new_file_name.rfind('.')+1: ]
            except:
                ext = 'unknown'
            full_text_filename = defaultfilters.slugify(self.paper.doi) +'_'+ defaultfilters.slugify(self.paper.title) +'.'+ defaultfilters.slugify(ext)
            self.paper.save_full_text_file( full_text_filename, open(new_file_name,'r').read() )
        self.paper.save()
        self.edit_dialog.destroy()
        main_gui.refresh_middle_pane_search()
        
        
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
    if not os.path.isdir( settings.MEDIA_ROOT ):
        os.mkdir( settings.MEDIA_ROOT )
    if not os.path.isdir( os.path.join( settings.MEDIA_ROOT, 'papers' ) ):
        os.mkdir( os.path.join( settings.MEDIA_ROOT, 'papers' ) )
    global main_gui
    init_db()
    main_gui = MainGUI()
    gtk.main()
        
