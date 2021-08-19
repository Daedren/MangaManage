#!/bin/bash
newDatabase="/tmp/testn"
sqlite3 manga.db -separator "§" "select id, archive,source from manga;" > $newDatabase
while IFS=§ read -r rowId archiveCol sourceCol; do
        #echo "$archiveCol a $sourceCol"
        echo "$rowId"
done < "$newDatabase"
