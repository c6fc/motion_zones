#! /bin/bash

if [ "$#" -ne "2" ]; then
   echo "Syntax: $0 <source> <dest>"
   exit 1
fi

source /motiondata/credentials
aws s3 cp $1 $2
