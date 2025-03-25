#!/bin/bash
# Fixes missing archives in filesystem that are in SQL

result=$(sqlite3 /mconfig/manga.db -separator "§" "select archive from manga;")
while IFS=§ read -r archiveCol; do
        filename=$(basename "$archiveCol")
        absoluteParent=$(dirname "$archiveCol")
        anilistId="$(basename "$absoluteParent")"
        quarantine="/mdata/quarantine/$anilistId/$filename"
        origin="/mdata/archivec/$anilistId/$filename"
        dest="/mdata/archive/$anilistId/$filename"
        destFolder="/mdata/archive/$anilistId"
        if [ -f "$archiveCol" ] || [ -f "$quarantine" ]; then
            #echo "$archiveCol"
            continue
        else 
            #echo "$archiveCol"
            echo "delete from manga where series = '$archiveCol'"
            sqlite3 /mconfig/manga.db "delete from manga where archive = '$archiveCol'"
            #if [ -f "$origin" ]; then
            #    echo "But file exists in backup"
            #    mkdir -p "$destFolder"
            #    mv "$origin" "$dest"
            #fi
        fi
done <<< $result
