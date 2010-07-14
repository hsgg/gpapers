from django.conf.urls.defaults import *

urlpatterns = patterns('',
    # Example:
    # (r'^gPapers/', include('gPapers.foo.urls')),

    # Uncomment this for admin:
     (r'^admin/', include('django.contrib.admin.urls')),
)
