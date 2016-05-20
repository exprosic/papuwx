#!/bin/bash

sudo pkill uwsgi
sudo cp music.db *.py *.ini *.sh *.txt /var/www/papuwx
cd /var/www/papuwx
sudo chown nginx:nginx -R .
sudo uwsgi default.ini
