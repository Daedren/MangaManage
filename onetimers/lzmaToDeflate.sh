#!/bin/bash

allBooks=(
)


mkdir /tmp/aaaa
for t in ${allBooks[@]}; do
    noExt="${t%.*}"
    7za x "$t" -o/tmp/aa
    mv $t /tmp/
    7za a -tzip "$noExt.cbz" /tmp/aa/*
    rm -r /tmp/aa
done
