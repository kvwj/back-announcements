#!bin/bash
# Song announcements startup script
mkdir /mnt/zara
mount -t cifs //${SERVER}/${FOLDER} -o user=${USER},pass=${PASS},reparse=wsl /mnt/zara
cd /opt/app
python3 set_announcement_file.py
