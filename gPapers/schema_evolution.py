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

# all of your evolution scripts, mapping the from_version and to_version to a list if sql commands
sqlite3_evolutions = [
    [('fv1:350446761','fv1:710386236'), # generated 2008-01-14 13:20:20.870928
        "CREATE TABLE \"gPapers_publisher\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"name\" varchar(1024) NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "CREATE TABLE \"gPapers_playlist\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"title\" varchar(1024) NOT NULL,\n    \"search_text\" varchar(1024) NOT NULL,\n    \"parent\" varchar(1) NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "CREATE TABLE \"gPapers_reference\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"referencing_paper_id\" integer NULL,\n    \"referenced_paper_id\" integer NULL,\n    \"line_from_referencing_paper\" varchar(1024) NOT NULL,\n    \"line_from_referenced_paper\" varchar(1024) NOT NULL,\n    \"doi_from_referencing_paper\" varchar(1024) NOT NULL,\n    \"doi_from_referenced_paper\" varchar(1024) NOT NULL,\n    \"url_from_referencing_paper\" varchar(200) NOT NULL,\n    \"url_from_referenced_paper\" varchar(200) NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "CREATE TABLE \"gPapers_author\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"name\" varchar(1024) NOT NULL,\n    \"location\" varchar(1024) NOT NULL,\n    \"department\" varchar(1024) NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "CREATE TABLE \"gPapers_bookmark\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"paper_id\" integer NOT NULL,\n    \"page\" integer NOT NULL,\n    \"notes\" text NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "CREATE TABLE \"gPapers_source\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"name\" varchar(1024) NOT NULL,\n    \"issue\" varchar(1024) NOT NULL,\n    \"acm_toc_url\" varchar(200) NOT NULL,\n    \"location\" varchar(1024) NOT NULL,\n    \"publication_date\" date NULL,\n    \"publisher_id\" integer NULL REFERENCES \"gPapers_publisher\" (\"id\"),\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "CREATE TABLE \"gPapers_paper\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"title\" varchar(1024) NOT NULL,\n    \"doi\" varchar(1024) NOT NULL,\n    \"source_id\" integer NULL REFERENCES \"gPapers_source\" (\"id\"),\n    \"source_session\" varchar(1024) NOT NULL,\n    \"source_pages\" varchar(1024) NOT NULL,\n    \"abstract\" text NOT NULL,\n    \"notes\" text NOT NULL,\n    \"full_text\" varchar(100) NOT NULL,\n    \"rating\" integer NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "CREATE TABLE \"gPapers_sponsor\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"name\" varchar(1024) NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "CREATE TABLE \"gPapers_organization\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"name\" varchar(1024) NOT NULL,\n    \"location\" varchar(1024) NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "CREATE TABLE \"gPapers_playlist_papers\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"playlist_id\" integer NOT NULL REFERENCES \"gPapers_playlist\" (\"id\"),\n    \"paper_id\" integer NOT NULL REFERENCES \"gPapers_paper\" (\"id\"),\n    UNIQUE (\"playlist_id\", \"paper_id\")\n)\n;",
        "CREATE TABLE \"gPapers_author_organizations\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"author_id\" integer NOT NULL REFERENCES \"gPapers_author\" (\"id\"),\n    \"organization_id\" integer NOT NULL REFERENCES \"gPapers_organization\" (\"id\"),\n    UNIQUE (\"author_id\", \"organization_id\")\n)\n;",
        "CREATE TABLE \"gPapers_paper_authors\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"paper_id\" integer NOT NULL REFERENCES \"gPapers_paper\" (\"id\"),\n    \"author_id\" integer NOT NULL REFERENCES \"gPapers_author\" (\"id\"),\n    UNIQUE (\"paper_id\", \"author_id\")\n)\n;",
        "CREATE TABLE \"gPapers_paper_sponsors\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"paper_id\" integer NOT NULL REFERENCES \"gPapers_paper\" (\"id\"),\n    \"sponsor_id\" integer NOT NULL REFERENCES \"gPapers_sponsor\" (\"id\"),\n    UNIQUE (\"paper_id\", \"sponsor_id\")\n)\n;",
        "CREATE TABLE \"gPapers_paper_organizations\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"paper_id\" integer NOT NULL REFERENCES \"gPapers_paper\" (\"id\"),\n    \"organization_id\" integer NOT NULL REFERENCES \"gPapers_organization\" (\"id\"),\n    UNIQUE (\"paper_id\", \"organization_id\")\n)\n;",
    ],
    [('fv1:710386236','fv1:-601791475'), # generated 2008-01-15 19:03:43.467515
        "ALTER TABLE \"gPapers_paper\" ADD COLUMN \"full_text_md5\" varchar(32) NULL;",
        "UPDATE \"gPapers_paper\" SET \"full_text_md5\" = '' WHERE \"full_text_md5\" IS NULL ;",
        "-- FYI: sqlite does not support changing columns, so we create a new \"gPapers_paper\" and delete the old (ie, this could take a while if you have a lot of data)",
        "ALTER TABLE \"gPapers_paper\" RENAME TO \"gPapers_paper_1337_TMP\";",
        "CREATE TABLE \"gPapers_paper\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"title\" varchar(1024) NOT NULL,\n    \"doi\" varchar(1024) NOT NULL,\n    \"source_id\" integer NULL REFERENCES \"gPapers_source\" (\"id\"),\n    \"source_session\" varchar(1024) NOT NULL,\n    \"source_pages\" varchar(1024) NOT NULL,\n    \"abstract\" text NOT NULL,\n    \"notes\" text NOT NULL,\n    \"full_text\" varchar(100) NOT NULL,\n    \"full_text_md5\" varchar(32) NOT NULL,\n    \"rating\" integer NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "INSERT INTO \"gPapers_paper\" SELECT \"id\",\"title\",\"doi\",\"source_id\",\"source_session\",\"source_pages\",\"abstract\",\"notes\",\"full_text\",\"full_text_md5\",\"rating\",\"created\",\"updated\" FROM \"gPapers_paper_1337_TMP\";",
        "DROP TABLE \"gPapers_paper_1337_TMP\";",
    ],
    [('fv1:-601791475','fv1:973383202'), # generated 2008-01-18 17:07:22.335450
        "ALTER TABLE \"gPapers_paper\" ADD COLUMN \"read_count\" integer NULL;",
        "UPDATE \"gPapers_paper\" SET \"read_count\" = 0 WHERE \"read_count\" IS NULL ;",
        "-- FYI: sqlite does not support changing columns, so we create a new \"gPapers_paper\" and delete the old (ie, this could take a while if you have a lot of data)",
        "ALTER TABLE \"gPapers_paper\" RENAME TO \"gPapers_paper_1337_TMP\";",
        "CREATE TABLE \"gPapers_paper\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"title\" varchar(1024) NOT NULL,\n    \"doi\" varchar(1024) NOT NULL,\n    \"source_id\" integer NULL REFERENCES \"gPapers_source\" (\"id\"),\n    \"source_session\" varchar(1024) NOT NULL,\n    \"source_pages\" varchar(1024) NOT NULL,\n    \"abstract\" text NOT NULL,\n    \"notes\" text NOT NULL,\n    \"full_text\" varchar(100) NOT NULL,\n    \"full_text_md5\" varchar(32) NOT NULL,\n    \"rating\" integer NOT NULL,\n    \"read_count\" integer NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "INSERT INTO \"gPapers_paper\" SELECT \"id\",\"title\",\"doi\",\"source_id\",\"source_session\",\"source_pages\",\"abstract\",\"notes\",\"full_text\",\"full_text_md5\",\"rating\",\"read_count\",\"created\",\"updated\" FROM \"gPapers_paper_1337_TMP\";",
        "DROP TABLE \"gPapers_paper_1337_TMP\";",
    ],
    [('fv1:973383202','fv1:1245036263'), # generated 2008-01-22 18:17:43.604272
        "ALTER TABLE \"gPapers_paper\" ADD COLUMN \"bibtex\" text NULL;",
        "UPDATE \"gPapers_paper\" SET \"bibtex\" = '' WHERE \"bibtex\" IS NULL ;",
        "-- FYI: sqlite does not support changing columns, so we create a new \"gPapers_paper\" and delete the old (ie, this could take a while if you have a lot of data)",
        "ALTER TABLE \"gPapers_paper\" RENAME TO \"gPapers_paper_1337_TMP\";",
        "CREATE TABLE \"gPapers_paper\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"title\" varchar(1024) NOT NULL,\n    \"doi\" varchar(1024) NOT NULL,\n    \"source_id\" integer NULL REFERENCES \"gPapers_source\" (\"id\"),\n    \"source_session\" varchar(1024) NOT NULL,\n    \"source_pages\" varchar(1024) NOT NULL,\n    \"abstract\" text NOT NULL,\n    \"notes\" text NOT NULL,\n    \"full_text\" varchar(100) NOT NULL,\n    \"full_text_md5\" varchar(32) NOT NULL,\n    \"rating\" integer NOT NULL,\n    \"read_count\" integer NOT NULL,\n    \"bibtex\" text NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "INSERT INTO \"gPapers_paper\" SELECT \"id\",\"title\",\"doi\",\"source_id\",\"source_session\",\"source_pages\",\"abstract\",\"notes\",\"full_text\",\"full_text_md5\",\"rating\",\"read_count\",\"bibtex\",\"created\",\"updated\" FROM \"gPapers_paper_1337_TMP\";",
        "DROP TABLE \"gPapers_paper_1337_TMP\";",
    ],
    [('fv1:1245036263','fv1:-1992981100'), # generated 2008-01-30 12:19:58.507907
        "ALTER TABLE \"gPapers_paper\" ADD COLUMN \"extracted_text\" text NULL;",
        "UPDATE \"gPapers_paper\" SET \"extracted_text\" = '' WHERE \"extracted_text\" IS NULL ;",
        "-- FYI: sqlite does not support changing columns, so we create a new \"gPapers_paper\" and delete the old (ie, this could take a while if you have a lot of data)",
        "ALTER TABLE \"gPapers_paper\" RENAME TO \"gPapers_paper_1337_TMP\";",
        "CREATE TABLE \"gPapers_paper\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"title\" varchar(1024) NOT NULL,\n    \"doi\" varchar(1024) NOT NULL,\n    \"source_id\" integer NULL REFERENCES \"gPapers_source\" (\"id\"),\n    \"source_session\" varchar(1024) NOT NULL,\n    \"source_pages\" varchar(1024) NOT NULL,\n    \"abstract\" text NOT NULL,\n    \"notes\" text NOT NULL,\n    \"full_text\" varchar(100) NOT NULL,\n    \"full_text_md5\" varchar(32) NOT NULL,\n    \"extracted_text\" text NOT NULL,\n    \"rating\" integer NOT NULL,\n    \"read_count\" integer NOT NULL,\n    \"bibtex\" text NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "INSERT INTO \"gPapers_paper\" SELECT \"id\",\"title\",\"doi\",\"source_id\",\"source_session\",\"source_pages\",\"abstract\",\"notes\",\"full_text\",\"full_text_md5\",\"extracted_text\",\"rating\",\"read_count\",\"bibtex\",\"created\",\"updated\" FROM \"gPapers_paper_1337_TMP\";",
        "DROP TABLE \"gPapers_paper_1337_TMP\";",
    ],
    [('fv1:-1992981100','fv1:-2070349988'), # generated 2008-01-30 12:32:02.047776
        "ALTER TABLE \"gPapers_paper\" ADD COLUMN \"page_count\" integer NULL;",
        "UPDATE \"gPapers_paper\" SET \"page_count\" = 0 WHERE \"page_count\" IS NULL ;",
        "-- FYI: sqlite does not support changing columns, so we create a new \"gPapers_paper\" and delete the old (ie, this could take a while if you have a lot of data)",
        "ALTER TABLE \"gPapers_paper\" RENAME TO \"gPapers_paper_1337_TMP\";",
        "CREATE TABLE \"gPapers_paper\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"title\" varchar(1024) NOT NULL,\n    \"doi\" varchar(1024) NOT NULL,\n    \"source_id\" integer NULL REFERENCES \"gPapers_source\" (\"id\"),\n    \"source_session\" varchar(1024) NOT NULL,\n    \"source_pages\" varchar(1024) NOT NULL,\n    \"abstract\" text NOT NULL,\n    \"notes\" text NOT NULL,\n    \"full_text\" varchar(100) NOT NULL,\n    \"full_text_md5\" varchar(32) NOT NULL,\n    \"extracted_text\" text NOT NULL,\n    \"page_count\" integer NOT NULL,\n    \"rating\" integer NOT NULL,\n    \"read_count\" integer NOT NULL,\n    \"bibtex\" text NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "INSERT INTO \"gPapers_paper\" SELECT \"id\",\"title\",\"doi\",\"source_id\",\"source_session\",\"source_pages\",\"abstract\",\"notes\",\"full_text\",\"full_text_md5\",\"extracted_text\",\"page_count\",\"rating\",\"read_count\",\"bibtex\",\"created\",\"updated\" FROM \"gPapers_paper_1337_TMP\";",
        "DROP TABLE \"gPapers_paper_1337_TMP\";",
    ],
    [('fv1:-2070349988','fv1:2049392851'), # generated 2008-02-04 19:44:31.772013
        "ALTER TABLE \"gPapers_author\" ADD COLUMN \"notes\" text NULL;",
        "UPDATE \"gPapers_author\" SET \"notes\" = '' WHERE \"notes\" IS NULL ;",
        "-- FYI: sqlite does not support changing columns, so we create a new \"gPapers_author\" and delete the old (ie, this could take a while if you have a lot of data)",
        "ALTER TABLE \"gPapers_author\" RENAME TO \"gPapers_author_1337_TMP\";",
        "CREATE TABLE \"gPapers_author\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"name\" varchar(1024) NOT NULL,\n    \"location\" varchar(1024) NOT NULL,\n    \"department\" varchar(1024) NOT NULL,\n    \"notes\" text NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "INSERT INTO \"gPapers_author\" SELECT \"id\",\"name\",\"location\",\"department\",\"notes\",\"created\",\"updated\" FROM \"gPapers_author_1337_TMP\";",
        "DROP TABLE \"gPapers_author_1337_TMP\";",
    ],
    [('fv1:2049392851','fv1:-394475879'), # generated 2008-02-04 19:44:40.243905
        "ALTER TABLE \"gPapers_author\" ADD COLUMN \"rating\" integer NULL;",
        "UPDATE \"gPapers_author\" SET \"rating\" = 0 WHERE \"rating\" IS NULL ;",
        "-- FYI: sqlite does not support changing columns, so we create a new \"gPapers_author\" and delete the old (ie, this could take a while if you have a lot of data)",
        "ALTER TABLE \"gPapers_author\" RENAME TO \"gPapers_author_1337_TMP\";",
        "CREATE TABLE \"gPapers_author\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"name\" varchar(1024) NOT NULL,\n    \"location\" varchar(1024) NOT NULL,\n    \"department\" varchar(1024) NOT NULL,\n    \"notes\" text NOT NULL,\n    \"rating\" integer NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "INSERT INTO \"gPapers_author\" SELECT \"id\",\"name\",\"location\",\"department\",\"notes\",\"rating\",\"created\",\"updated\" FROM \"gPapers_author_1337_TMP\";",
        "DROP TABLE \"gPapers_author_1337_TMP\";",
    ],
    [('fv1:-394475879','fv1:-91336673'), # generated 2008-02-05 01:15:38.477186
        "ALTER TABLE \"gPapers_paper\" ADD COLUMN \"pubmed_id\" varchar(1024) NULL;",
        "UPDATE \"gPapers_paper\" SET \"pubmed_id\" = '' WHERE \"pubmed_id\" IS NULL ;",
        "-- FYI: sqlite does not support changing columns, so we create a new \"gPapers_paper\" and delete the old (ie, this could take a while if you have a lot of data)",
        "ALTER TABLE \"gPapers_paper\" RENAME TO \"gPapers_paper_1337_TMP\";",
        "CREATE TABLE \"gPapers_paper\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"title\" varchar(1024) NOT NULL,\n    \"doi\" varchar(1024) NOT NULL,\n    \"pubmed_id\" varchar(1024) NOT NULL,\n    \"source_id\" integer NULL REFERENCES \"gPapers_source\" (\"id\"),\n    \"source_session\" varchar(1024) NOT NULL,\n    \"source_pages\" varchar(1024) NOT NULL,\n    \"abstract\" text NOT NULL,\n    \"notes\" text NOT NULL,\n    \"full_text\" varchar(100) NOT NULL,\n    \"full_text_md5\" varchar(32) NOT NULL,\n    \"extracted_text\" text NOT NULL,\n    \"page_count\" integer NOT NULL,\n    \"rating\" integer NOT NULL,\n    \"read_count\" integer NOT NULL,\n    \"bibtex\" text NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "INSERT INTO \"gPapers_paper\" SELECT \"id\",\"title\",\"doi\",\"pubmed_id\",\"source_id\",\"source_session\",\"source_pages\",\"abstract\",\"notes\",\"full_text\",\"full_text_md5\",\"extracted_text\",\"page_count\",\"rating\",\"read_count\",\"bibtex\",\"created\",\"updated\" FROM \"gPapers_paper_1337_TMP\";",
        "DROP TABLE \"gPapers_paper_1337_TMP\";",
    ],
    [('fv1:-91336673','fv1:752600870'), # generated 2008-02-05 01:31:17.132883
        "ALTER TABLE \"gPapers_paper\" ADD COLUMN \"import_url\" varchar(200) NULL;",
        "UPDATE \"gPapers_paper\" SET \"import_url\" = '' WHERE \"import_url\" IS NULL ;",
        "-- FYI: sqlite does not support changing columns, so we create a new \"gPapers_paper\" and delete the old (ie, this could take a while if you have a lot of data)",
        "ALTER TABLE \"gPapers_paper\" RENAME TO \"gPapers_paper_1337_TMP\";",
        "CREATE TABLE \"gPapers_paper\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"title\" varchar(1024) NOT NULL,\n    \"doi\" varchar(1024) NOT NULL,\n    \"pubmed_id\" varchar(1024) NOT NULL,\n    \"import_url\" varchar(200) NOT NULL,\n    \"source_id\" integer NULL REFERENCES \"gPapers_source\" (\"id\"),\n    \"source_session\" varchar(1024) NOT NULL,\n    \"source_pages\" varchar(1024) NOT NULL,\n    \"abstract\" text NOT NULL,\n    \"notes\" text NOT NULL,\n    \"full_text\" varchar(100) NOT NULL,\n    \"full_text_md5\" varchar(32) NOT NULL,\n    \"extracted_text\" text NOT NULL,\n    \"page_count\" integer NOT NULL,\n    \"rating\" integer NOT NULL,\n    \"read_count\" integer NOT NULL,\n    \"bibtex\" text NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "INSERT INTO \"gPapers_paper\" SELECT \"id\",\"title\",\"doi\",\"pubmed_id\",\"import_url\",\"source_id\",\"source_session\",\"source_pages\",\"abstract\",\"notes\",\"full_text\",\"full_text_md5\",\"extracted_text\",\"page_count\",\"rating\",\"read_count\",\"bibtex\",\"created\",\"updated\" FROM \"gPapers_paper_1337_TMP\";",
        "DROP TABLE \"gPapers_paper_1337_TMP\";",
    ],
    [('fv1:752600870','fv1:-138692700'), # generated 2008-02-12 13:29:28.474059
        "ALTER TABLE \"gPapers_bookmark\" ADD COLUMN \"x\" real NULL;",
        "UPDATE \"gPapers_bookmark\" SET \"x\" = '0.01' WHERE \"x\" IS NULL ;",
        "-- FYI: sqlite does not support changing columns, so we create a new \"gPapers_bookmark\" and delete the old (ie, this could take a while if you have a lot of data)",
        "ALTER TABLE \"gPapers_bookmark\" RENAME TO \"gPapers_bookmark_1337_TMP\";",
        "CREATE TABLE \"gPapers_bookmark\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"paper_id\" integer NOT NULL REFERENCES \"gPapers_paper\" (\"id\"),\n    \"page\" integer NOT NULL,\n    \"x\" real NOT NULL,\n    \"notes\" text NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "INSERT INTO \"gPapers_bookmark\" SELECT \"id\",\"paper_id\",\"page\",\"x\",\"notes\",\"created\",\"updated\" FROM \"gPapers_bookmark_1337_TMP\";",
        "DROP TABLE \"gPapers_bookmark_1337_TMP\";",
    ],
    [('fv1:-138692700','fv1:556047524'), # generated 2008-02-12 13:29:36.906530
        "ALTER TABLE \"gPapers_bookmark\" ADD COLUMN \"y\" real NULL;",
        "UPDATE \"gPapers_bookmark\" SET \"y\" = '0.01' WHERE \"y\" IS NULL ;",
        "-- FYI: sqlite does not support changing columns, so we create a new \"gPapers_bookmark\" and delete the old (ie, this could take a while if you have a lot of data)",
        "ALTER TABLE \"gPapers_bookmark\" RENAME TO \"gPapers_bookmark_1337_TMP\";",
        "CREATE TABLE \"gPapers_bookmark\" (\n    \"id\" integer NOT NULL PRIMARY KEY,\n    \"paper_id\" integer NOT NULL REFERENCES \"gPapers_paper\" (\"id\"),\n    \"page\" integer NOT NULL,\n    \"x\" real NOT NULL,\n    \"y\" real NOT NULL,\n    \"notes\" text NOT NULL,\n    \"created\" datetime NOT NULL,\n    \"updated\" datetime NOT NULL\n)\n;",
        "INSERT INTO \"gPapers_bookmark\" SELECT \"id\",\"paper_id\",\"page\",\"x\",\"y\",\"notes\",\"created\",\"updated\" FROM \"gPapers_bookmark_1337_TMP\";",
        "DROP TABLE \"gPapers_bookmark_1337_TMP\";",
    ],
] # don't delete this comment! ## sqlite3_evolutions_end ##
