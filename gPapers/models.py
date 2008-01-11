import os
from django.db import models


class Publisher(models.Model):

    name = models.CharField(max_length='1024')
    imported = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Admin:
        list_display = ( 'id', 'name', )

    def __unicode__(self):
        return self.name

    
class Source(models.Model):

    name = models.CharField(max_length='1024')
    issue = models.CharField(max_length='1024')
    acm_toc_url = models.URLField()
    location = models.CharField(max_length='1024')
    publication_date = models.DateField()
    publisher = models.ForeignKey(Publisher, null=True)
    imported = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Admin:
        list_display = ( 'id', 'name', 'issue', 'location', 'publisher', 'publication_date', )

    def __unicode__(self):
        return self.name


class Author(models.Model):

    name = models.CharField(max_length='1024')
    location = models.CharField(max_length='1024', blank=True)
    organization = models.CharField(max_length='1024', blank=True)
    department = models.CharField(max_length='1024', blank=True)
    imported = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Admin:
        list_display = ( 'id', 'name', 'location', 'organization', 'department' )

    def __unicode__(self):
        return self.name
    
    
class Sponsor(models.Model):

    name = models.CharField(max_length='1024')
    imported = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Admin:
        list_display = ( 'id', 'name', )

    def __unicode__(self):
        return self.name
    
    
class Paper(models.Model):
    
    title = models.CharField(max_length='1024')
    doi = models.CharField(max_length='1024', blank=True)
    source = models.ForeignKey(Source, null=True)
    source_session = models.CharField(max_length='1024')
    source_pages = models.CharField(max_length='1024')
    abstract = models.TextField()
    notes = models.TextField()
    authors = models.ManyToManyField(Author)
    sponsors = models.ManyToManyField(Sponsor)
    full_text = models.FileField(upload_to=os.path.join('papers','%Y','%m'))
    rating = models.IntegerField(default=0)
    imported = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    class Admin:
        list_display = ( 'id', 'doi', 'title' )


class Reference(models.Model):

    paper = models.ForeignKey(Paper)
    line = models.CharField(max_length='1024')
    doi = models.CharField(max_length='1024', blank=True)
    ieee_url = models.URLField()
    imported = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Admin:
        list_display = ( 'id', 'line', 'doi' )

    def __unicode__(self):
        return self.line


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


