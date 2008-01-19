import md5, os
from django.db import models


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

    class Admin:
        list_display = ( 'id', 'name', 'issue', 'location', 'publisher', 'publication_date', )

    def __unicode__(self):
        return self.name


class Organization(models.Model):

    name = models.CharField(max_length='1024')
    location = models.CharField(max_length='1024', blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Admin:
        list_display = ( 'id', 'name', 'location' )

    def __unicode__(self):
        return self.name
    
    
class Author(models.Model):

    name = models.CharField(max_length='1024')
    location = models.CharField(max_length='1024', blank=True)
    organizations = models.ManyToManyField(Organization)
    department = models.CharField(max_length='1024', blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

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
    rating = models.IntegerField(default=0)
    read_count = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    def _save_FIELD_file(self, field, filename, raw_contents, save=True):
        m = md5.new()
        m.update(raw_contents)
        self.full_text_md5 = m.hexdigest()
        super(Paper, self)._save_FIELD_file(field, filename, raw_contents, save)

    class Admin:
        list_display = ( 'id', 'doi', 'title' )

    def __unicode__(self):
        return 'Paper<%i: %s>' % ( self.id, ' '.join( [str(self.doi), str(self.title), str(self.authors.all())] ) )


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
    )
    title = models.CharField(max_length='1024', blank=True)
    search_text = models.CharField(max_length='1024', blank=True)
    parent = models.CharField(max_length=1, choices=SOURCES)
    papers = models.ManyToManyField(Paper)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Admin:
        list_display = ( 'id', 'title', 'parent', 'search_text' )

    def __unicode__(self):
        return self.title


