#!/bin/bash
# Fixes missing archives in filesystem that are in SQL

result=$(sqlite3 /mconfig/manga.db -separator "§" "select archive from manga;")
while IFS=§ read -r archiveCol; do
        if [ -f "$archiveCol" ]; then
            echo "$archiveCol"
        else 
            echo "$archiveCol"
            echo "does not exist."
            filename=$(basename "$archiveCol")
            absoluteParent=$(dirname "$archiveCol")
            anilistId="$(basename "$absoluteParent")"
            origin="/mdata/archivec/$anilistId/$filename"
            dest="/mdata/archive/$anilistId/$filename"
            destFolder="/mdata/archive/$anilistId"
            echo $origin
            echo $dest
            if [ -f "$origin" ]; then
                echo "But file exists in backup"
                mkdir -p "$destFolder"
                mv "$origin" "$dest"
            fi
        fi
done <<< $result
