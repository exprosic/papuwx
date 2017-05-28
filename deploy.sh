#!/bin/bash

sudo pkill uwsgi
#cp ~/music.db .
#sudo cp music.db db *.py *.ini *.sh *.txt /var/www/papuwx
sudo cp db *.py *.ini *.sh *.txt /var/www/papuwx
cd /var/www/papuwx
sudo chown nginx:nginx -R .
sudo uwsgi default.ini
