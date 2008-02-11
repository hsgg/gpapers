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

from gPapers.models import *

p_bibtex = re.compile( '[@][a-z]+[\s]*{([^<]*)}', re.IGNORECASE | re.DOTALL )


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



def get_or_create_paper_via( id=None, doi=None, pubmed_id=None, import_url=None, title=None, full_text_md5=None ):
    """tries to look up a paper by various forms of id, from most specific to least"""
    print id, doi, pubmed_id, import_url, title, full_text_md5
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


def import_bibtex_from_html( paper, html ):
    
    # ieee puts <br>s in their bibtex
    html = html.replace('<br>','')
    
    match = p_bibtex.search( html )
    if match:
        
        print 'bibtex', match.group(1)
        bibtex_lines = [ x.strip() for x in match.group(1).split('\n') ]
        bibtex = {}
        print 'bibtex_lines', bibtex_lines
        
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
            
        paper.doi = bibtex.get('doi','')
        paper.title = bibtex.get('title','')
        paper.source_pages = bibtex.get('pages','')
    
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
            