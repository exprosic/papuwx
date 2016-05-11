#!/bin/bash

git push
cd /var/www/papuwx
sudo -u nginx git pull
sudo uwsgi default.ini
