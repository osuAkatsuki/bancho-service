#!/bin/bash

peppy_dir="/home/akatsuki/pep.py"
lets_dir="/home/akatsuki/lets"
common_dir="/home/akatsuki/ripple-common"

while true
do
    python3.9 pep.py
    ec=$? # 137 sigkill; 130 ctrl+c
    if [[ $ec == 137 || $ec == 130 ]]; then # shutdown
        echo "Shutting down.."
        break
    elif [[ $ec == 0 ]]; then # update
        echo "Updating.."
        git pull # pep.py

        cd $lets_dir
        git pull # lets

        cd $common_dir
        git pull # ripple-common

        cd $peppy_dir # reset dir
    else
        echo "Unknown exit code recieved (" $ec ").."
    fi
done
