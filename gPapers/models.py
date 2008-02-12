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

import md5, os, re, traceback
from django.db import models
import desktop, pyPdf


p_doi = re.compile( 'doi *: *(10.[a-z0-9]+/[a-z0-9.]+)', re.IGNORECASE )


class Publisher(models.Model):

    name = models.CharField(max_length='1024')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Admin:
        list_display = ( 'id', 'name', )

    def __unicode__(self):
        return self.name

    
class Source(models.Model):

    name = models.CharField(max_length='1024')
    issue = models.CharField(max_length='1024')
    acm_toc_url = models.URLField()
    location = models.CharField(max_length='1024', blank=True)
    publication_date = models.DateField(null=True)
    publisher = models.ForeignKey(Publisher, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def merge(self, id):
        if id==self.id:
            return
        other_source = Source.objects.get(id=id)
        if not self.publisher: 
            self.publisher = other_source.publisher
        for paper in other_source.paper_set.all():
            self.paper_set.add( paper )
        other_source.delete()

    class Admin:
        list_display = ( 'id', 'name', 'issue', 'location', 'publisher', 'publication_date', )

    def __unicode__(self):
        return self.name


class Organization(models.Model):

    name = models.CharField(max_length='1024')
    location = models.CharField(max_length='1024', blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def merge(self, id):
        if id==self.id:
            return
        other_organization = Organization.objects.get(id=id)
        for author in other_organization.author_set.all():
            self.author_set.add( author )
        for paper in other_organization.paper_set.all():
            self.paper_set.add( paper )
        other_organization.delete()

    class Admin:
        list_display = ( 'id', 'name', 'location' )

    def __unicode__(self):
        return self.name
    
    
class Author(models.Model):

    name = models.CharField(max_length='1024')
    location = models.CharField(max_length='1024', blank=True)
    organizations = models.ManyToManyField(Organization)
    department = models.CharField(max_length='1024', blank=True)
    notes = models.TextField(blank=True)
    rating = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    def merge(self, id):
        if id==self.id:
            return
        other_author = Author.objects.get(id=id)
        for organization in other_author.organizations.all():
            self.organizations.add( organization )
        from django.db import connection
        cursor = connection.cursor()
        # we want to preserve the order of the authors, so do an update via SQL instead of using the built in set manipulators
        # FIXME: this will fail if you merge two authors of the same paper
        cursor.execute("update gPapers_paper_authors set author_id=%s where author_id=%s;", [self.id, id])
        other_author.delete()

    class Admin:
        list_display = ( 'id', 'name', 'location' )

    def __unicode__(self):
        return self.name
    
    
class Sponsor(models.Model):

    name = models.CharField(max_length='1024')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Admin:
        list_display = ( 'id', 'name', )

    def __unicode__(self):
        return self.name
    
    
class Paper(models.Model):
    
    title = models.CharField(max_length='1024')
    doi = models.CharField(max_length='1024', blank=True)
    pubmed_id = models.CharField(max_length='1024', blank=True)
    import_url = models.URLField(blank=True)
    source = models.ForeignKey(Source, null=True)
    source_session = models.CharField(max_length='1024', blank=True)
    source_pages = models.CharField(max_length='1024', blank=True)
    abstract = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    authors = models.ManyToManyField(Author)
    sponsors = models.ManyToManyField(Sponsor)
    organizations = models.ManyToManyField(Organization)
    full_text = models.FileField(upload_to=os.path.join('papers','%Y','%m'))
    full_text_md5 = models.CharField(max_length='32', blank=True)
    extracted_text = models.TextField(blank=True)
    page_count = models.IntegerField(default=0)
    rating = models.IntegerField(default=0)
    read_count = models.IntegerField(default=0)
    bibtex = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    def _save_FIELD_file(self, field, filename, raw_contents, save=True):
        m = md5.new()
        m.update(raw_contents)
        self.full_text_md5 = m.hexdigest()
        super(Paper, self)._save_FIELD_file(field, filename, raw_contents, save)
        try: self.extract_document_information_from_pdf()
        except: traceback.print_exc()

    def get_authors_in_order(self):
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute("select author_id from gPapers_paper_authors where paper_id=%s order by id;", [self.id])
        rows = cursor.fetchall()
        author_list = []
        for row in rows:
            author_list.append( Author.objects.get(id=row[0]) )
        return author_list
    
    def open(self):
        if os.path.isfile( self.get_full_text_filename() ):
            desktop.open( self.get_full_text_filename() )
            self.read_count = self.read_count + 1
            self.save()

    def extract_document_information_from_pdf(self, force_overwrite=False):
        """will overwrite the extracted_text and page_count fields, and the title if the title is empty"""
        if os.path.isfile( self.get_full_text_filename() ):
            content = []

            # Load PDF into pyPDF
            pdf = pyPdf.PdfFileReader(file(self.get_full_text_filename(), "rb"))
            doc_info = pdf.getDocumentInfo()
            content.append( str(doc_info) )
            content.append('\n\n')
            if force_overwrite or not self.title:
                try: self.title = doc_info['/Title']
                except: self.title = os.path.split(self.get_full_text_filename())[1]
            if force_overwrite or self.authors.count()==0:
                try:
                    author_text = doc_info['/Author']
                    print 'author_text', author_text
                    if author_text.find(';')>0:
                        author_list = author_text.split(';')
                    else:
                        author_list = author_text.split(',')
                    if author_list:
                        self.authors.clear()
                        for author_name in author_list:
                            author, created = Author.objects.get_or_create(name=author_name.strip())
                            if created:
                                author.save()
                            self.authors.add(author)
                except:
                    pass
            # also has: doc_info['/Author'], doc_info['/ModDate'], doc_info['/CreationDate']

            # extract the actual text
            stdin, stdout = os.popen4( 'ps2txt "%s"' % self.get_full_text_filename() )
            for line in stdout:
                content.append(line)
                try:
                    self.doi = p_doi.search(line).group(1)
                    print self.doi
                except: pass
            
            self.extracted_text = ''.join( content )
        else:
            self.page_count = 0
            self.extracted_text = ''
        return self.extracted_text

    class Admin:
        list_display = ( 'id', 'doi', 'title' )

    def __unicode__(self):
        return 'Paper<%i: %s>' % ( self.id, ' '.join( [str(self.doi), str(self.title), str(self.authors.all())] ) )
    
    def pretty_string(self):
        return '['+ ', '.join( [ author.name for author in self.get_authors_in_order() ] )  +'] '+ self.title


class Reference(models.Model):

    referencing_paper = models.ForeignKey(Paper, null=True, blank=True)
    referenced_paper = models.ForeignKey(Paper, null=True, blank=True, related_name='citation_set')
    line_from_referencing_paper = models.CharField(max_length='1024', blank=True)
    line_from_referenced_paper = models.CharField(max_length='1024', blank=True)
    doi_from_referencing_paper = models.CharField(max_length='1024', blank=True)
    doi_from_referenced_paper = models.CharField(max_length='1024', blank=True)
    url_from_referencing_paper = models.URLField(blank=True)
    url_from_referenced_paper = models.URLField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Admin:
        list_display = ( 'id', 'referencing_paper', 'line_from_referencing_paper', 'doi_from_referencing_paper', 'referenced_paper', 'line_from_referenced_paper', 'doi_from_referenced_paper' )

    def __unicode__(self):
        return 'Reference<%s,%s>' % (str(self.referencing_paper), str(self.referenced_paper))


class Bookmark(models.Model):

    paper = models.ForeignKey(Paper)
    page = models.IntegerField()
#    title = models.CharField(max_length='1024', blank=True)
    notes = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Admin:
        list_display = ( 'id', 'paper', 'page' )

    def __unicode__(self):
        return self.notes


class Playlist(models.Model):

    SOURCES = (
        ('0', 'My Library'),
        ('1', 'ACM'),
        ('2', 'IEEE'),
        ('3', 'PubMed'),
        ('4', 'CiteSeer'),
    )
    title = models.CharField(max_length='1024', blank=True)
    search_text = models.CharField(max_length='1024', blank=True)
    parent = models.CharField(max_length=1, choices=SOURCES)
    papers = models.ManyToManyField(Paper)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    def get_papers_in_order(self):
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute("select paper_id from gPapers_playlist_papers where playlist_id=%s order by id;", [self.id])
        rows = cursor.fetchall()
        paper_list = []
        for row in rows:
            paper_list.append( Paper.objects.get(id=row[0]) )
        return paper_list

    class Admin:
        list_display = ( 'id', 'title', 'parent', 'search_text' )

    def __unicode__(self):
        return self.title


