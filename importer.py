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
from htmlentitydefs import name2codepoint as n2cp

import pygtk
pygtk.require("2.0")
import gobject
import gtk
import gtk.glade
import gnome
import gnome.ui
import pango

from gPapers.models import *
from django.template import defaultfilters
import BeautifulSoup, openanything
active_threads = None


ACM_BASE_URL = 'http://portal.acm.org'
IEEE_BASE_URL = 'http://ieeexplore.ieee.org'
ACM_USERNAME = None
ACM_PASSWORD = None

p_bibtex = re.compile( '[@][a-z]+[\s]*{([^<]*)}', re.IGNORECASE | re.DOTALL )
p_whitespace = re.compile( '[\s]+')
p_doi = re.compile( 'doi *: *(10.[a-z0-9]+/[a-z0-9.]+)', re.IGNORECASE )


def latex2unicode(s):
    """    
    *  \`{o} produces a grave accent
    * \'{o} produces an acute accent
    * \^{o} produces a circumflex
    * \"{o} produces an umlaut or dieresis
    * \H{o} produces a long Hungarian umlaut
    * \~{o} produces a tilde
    * \c{c} produces a cedilla
    * \={o} produces a macron accent (a bar over the letter)
    * \b{o} produces a bar under the letter
    * \.{o} produces a dot over the letter
    * \d{o} produces a dot under the letter
    * \u{o} produces a breve over the letter
    * \v{o} produces a "v" over the letter
    * \t{oo} produces a "tie" (inverted u) over the two letters
    """
    # TODO: expand this to really work
    return s.replace('\c{s}',u's')



def _decode_htmlentities(string):
    entity_re = re.compile("&(#?)(\d{1,5}|\w{1,8});")
    return entity_re.subn(_substitute_entity, string)[0]

def html_strip(s):
    return _decode_htmlentities( p_whitespace.sub( ' ', str(s).replace('&nbsp;', ' ').strip() ) )

def pango_excape(s):
    return s.replace('&','&amp;').replace('>','&gt;').replace('<','&lt;')

def get_md5_hexdigest_from_data(data):
    m = md5.new()
    m.update(data)
    return m.hexdigest()

def _substitute_entity(match):
    ent = match.group(2)
    if match.group(1) == "#":
        return unichr(int(ent))
    else:
        cp = n2cp.get(ent)

        if cp:
            return unichr(cp)
        else:
            return match.group()

def _should_we_reimport_paper(paper):
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

def get_or_create_paper_via( id=None, doi=None, pubmed_id=None, import_url=None, title=None, full_text_md5=None ):
    """tries to look up a paper by various forms of id, from most specific to least"""
    #print id, doi, pubmed_id, import_url, title, full_text_md5
    paper = None
    created = False
    if id>=0:
        try: paper = Paper.objects.get(id=id)
        except: pass
        
    if doi:
        if paper:
            if not paper.doi:
                paper.doi = doi
        else:
            try: paper = Paper.objects.get(doi=doi)
            except: pass
    
    if pubmed_id:
        if paper:
            if not paper.pubmed_id:
                paper.pubmed_id = pubmed_id
        else:
            try: paper = Paper.objects.get(pubmed_id=pubmed_id)
            except: pass
    
    if import_url:
        if paper:
            if not paper.import_url:
                paper.import_url = import_url
        else:
            try: paper = Paper.objects.get(import_url=import_url)
            except: pass
    
    if full_text_md5:
        if not paper:
            try: paper = Paper.objects.get(full_text_md5=full_text_md5)
            except: pass
    
    if title:
        if paper:
            if not paper.title:
                paper.title = title
        else:
            try: paper = Paper.objects.get(title=title)
            except: pass
    
    if not paper:
        # it looks like we haven't seen this paper before...
        if title==None: title = ''
        if doi==None: doi = ''
        if pubmed_id==None: pubmed_id = ''
        if import_url==None: import_url = ''
        paper = Paper.objects.create( doi=doi, pubmed_id=pubmed_id, import_url=import_url, title=title )
        created = True
        
    return paper, created


def update_paper_from_bibtex_html( paper, html ):
    
    # ieee puts <br>s in their bibtex
    html = html.replace('<br>','')
    
    match = p_bibtex.search( html )
    if match:
        
        bibtex_lines = [ x.strip() for x in match.group(1).split('\n') ]
        bibtex = {}
        
        for x in bibtex_lines:
            i = x.find('=')
            if i>0:
                k, v = x[:i].strip(), x[i+1:].strip()
                bibtex[k.lower()] = latex2unicode( v.strip('"\'{},') )
                
        # fix for ACM's doi retardedness
        if bibtex.get('doi','').startswith('http://dx.doi.org/'):
            bibtex['doi'] = bibtex['doi'][ len('http://dx.doi.org/'): ]
        if bibtex.get('doi','').startswith('http://doi.acm.org/'):
            bibtex['doi'] = bibtex['doi'][ len('http://doi.acm.org/'): ]
                
        # create our paper if not provided for us
        if not paper:
            paper, created = get_or_create_paper_via( doi=bibtex.get('doi'), title=bibtex.get('title') )
            if created:
                print thread.get_ident(), 'creating paper:', paper
            else:
                print thread.get_ident(), 'updating paper:', paper
            
        if bibtex.get('doi'): paper.doi = bibtex.get('doi','')
        if bibtex.get('title'): paper.title = bibtex.get('title','')
        if bibtex.get('source_pages'): paper.source_pages = bibtex.get('pages','')
        if bibtex.get('abstract'): paper.abstract = bibtex.get('abstract','')
    
        # search for author information
        if bibtex.get('author') and paper.authors.count()==0:
            for author_name in bibtex['author'].split(' and '):
                author_name = author_name.strip()
                author, created = Author.objects.get_or_create( name=author_name )
                if created: author.save()
                paper.authors.add( author )

        # set publisher and source
        publisher_name = bibtex.get('publisher')
        if publisher_name:
            publisher, created = Publisher.objects.get_or_create( name=publisher_name )
            if created: publisher.save()
        else:
            publisher = None
        publication_date = None
        try: publication_date = date( int( bibtex.get('year') ), 1, 1 )
        except: pass
        source_name = None
        if not source_name and bibtex.get('booktitle'): source_name = bibtex['booktitle']
        if not source_name and bibtex.get('journal'): source_name = bibtex['journal']
        if source_name:
            source, created = Source.objects.get_or_create(
                name = source_name,
                issue = bibtex.get('booktitle',''),
                location = bibtex.get('location',''),
                publication_date = publication_date,
                publisher = publisher,
            )
            if created:
                source.save()
            paper.source = source
        

        paper.bibtex = match.group(0)
        paper.save()
        print thread.get_ident(), 'imported bibtex =', bibtex

    return paper
            
            
def import_citation(url, paper=None, callback=None):
    active_threads[ thread.get_ident() ] = 'importing: '+ url
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
            paper = _import_acm_citation(params, paper=paper)
            if paper and callback: callback()
            return paper
#        if params['url'].startswith('http://dx.doi.org'):
#            paper = import_unknown_citation(params)
#            if paper and refresh_after: main_gui.refresh_middle_pane_search()
#            return paper
        if params['url'].startswith('http://ieeexplore.ieee.org'):
            if params['url'].find('search/wrapper.jsp')>-1:
                paper = _import_ieee_citation( openanything.fetch( params['url'].replace('search/wrapper.jsp','xpls/abs_all.jsp') ), paper=paper )
                if paper and callback: callback()
            else:
                paper = _import_ieee_citation( params, paper=paper )
                if paper and callback: callback()
            return paper
        
        # let's see if there's a pdf somewhere in here...
        paper = _import_unknown_citation(params, params['url'], paper=paper)
        if paper and callback:callback()
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
    if active_threads.has_key( thread.get_ident() ):
        del active_threads[ thread.get_ident() ]
    



def _import_acm_citation(params, paper=None):
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
            paper, created = get_or_create_paper_via(
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
                if not _should_we_reimport_paper(paper):
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
                update_paper_from_bibtex_html( paper, params_bibtex['data'] )

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


def _import_ieee_citation(params, paper=None):
    print thread.get_ident(), 'downloading ieee citation:', params['url']
    try:
        print thread.get_ident(), 'parsing...'
        file = open('import.html','w')
        file.write( params['data'] )
        file.close()
        soup = BeautifulSoup.BeautifulSoup( params['data'].replace('<!-BMS End-->','').replace('<in>','') )
        
        print soup.find('span', attrs={'class':'headNavBlueXLarge2'})

        p_arnumber = re.compile( '<arnumber>[0-9]+</arnumber>', re.IGNORECASE )
        match = p_arnumber.search( params['data'] )
        if match:
            arnumber = match.group(0)
            print 'arnumber', arnumber
            params_bibtex = openanything.fetch('http://ieeexplore.ieee.org/xpls/citationAct', post_data={ 'dlSelect':'cite_abs', 'fileFormate':'BibTex', 'arnumber':arnumber, 'Submit':'Download'  } )
            print params_bibtex
            if params_bibtex['status']==200 or params_bibtex['status']==302:
                paper = update_paper_from_bibtex_html( paper, params_bibtex['data'] )
        
        if not paper:
            paper, created = get_or_create_paper_via(
                title = html_strip( str(soup.find('title').string).replace('IEEEXplore#','') ),
                doi = re.search( 'Digital Object Identifier: ([a-zA-Z0-9./]*)', params['data'] ).group(1),
            )
            if created: paper.save()
            else: 
                print thread.get_ident(), 'paper already imported'
                if not _should_we_reimport_paper(paper):
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

def _import_unknown_citation(params, orig_url, paper=None):

    if params['data'].startswith('%PDF'):

        # we have a live one!
        try:
            filename = params['url'][ params['url'].rfind('/')+1 : ]
            data = params['data']
            print thread.get_ident(), 'importing paper =', filename
            
            if not paper:
                md5_hexdigest = get_md5_hexdigest_from_data( data )
                paper, created = get_or_create_paper_via( full_text_md5=md5_hexdigest )
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
                    paper = _import_unknown_citation( openanything.fetch(href), orig_url, paper=paper )
                    if paper:
                        update_paper_from_bibtex_html( paper, params['data'] )
                        paper.save()
                        break
        except:
            traceback.print_exc()
            if paper:
                paper.delete()
                paper = None
    
    return paper
