Setup Instructions
------------------

 - Install the necessary deps:
	sudo apt-get install python python-glade2 python-gnome2 python-sqlite3 graphviz

 - Unpack Django:
	tar -zvxf ext/Django-1.0.2-final.tar.gz Django-1.0.2-final/django
	mv Django-1.0.2-final/django .
	rmdir Django-1.0.2-final

 - Install python-poppler:
	sudo apt-get install build-essential libpoppler-dev libpoppler-glib-dev python-cairo-dev bzr gnome-common python-dev python-gnome2-dev python-gtk2-dev python-gobject-dev python-pyorbit-dev
	tar -zxvf ext/pypoppler-0.8.1.tar.gz
	cd pypoppler-0.8.1
	./configure
	make
	sudo make install 

