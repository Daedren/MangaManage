#!/bin/bash
# Checks files that are archived, yet aren't in SQL
# Replaced by checkMissingSQL.py

database="/mconfig/manga.db"
findResult="/mconfig/result"
archiveRoot="/mdata/sources/../archive/"

find "$archiveRoot" -type f -print0 | while read -d $'\0' nextVal
do
    escapedVal=$(echo $nextVal | sed "s/'/''/g")
    res=$(sqlite3 manga.db "select '$escapedVal' where NOT(EXISTS(SELECT * FROM manga WHERE archive='$escapedVal'));")
    [ -z "$res" ] || echo $escapedVal
done
