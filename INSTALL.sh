#!/bin/bash

sudo mv /home/pi/FIAFormulaEDocs/FIAFormulaEDocs.service /etc/systemd/system/ && sudo systemctl daemon-reload
python3 -m pip install yagmail tweepy pdf2image psutil --no-cache-dir
sudo apt install poppler-utils -y
chmod +x -R /home/pi/FIAFormulaEDocs/*