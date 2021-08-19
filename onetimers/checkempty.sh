#!/bin/bash
database="/mconfig/manga.db"
findResult="/mconfig/result"
archiveRoot="/mdata/sources/../archive/"

#find "$archiveRoot" -type f > $findResult
#
#while read nextVal; do
#    #echo "$nextVal"
#    escapedVal=$(echo $nextVal | sed "s/'/''/g")
#    sqlite3 manga.db "select '$escapedVal' where NOT(EXISTS(SELECT * FROM manga WHERE archive='$escapedVal'));"
#done < "$findResult"
find "$archiveRoot" -type f -print0 | while read -d $'\0' nextVal
do
    escapedVal=$(echo $nextVal | sed "s/'/''/g")
    res=$(sqlite3 manga.db "select '$escapedVal' where NOT(EXISTS(SELECT * FROM manga WHERE archive='$escapedVal'));")
    [ -z "$res" ] || echo $escapedVal
done
