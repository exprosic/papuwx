#!/bin/bash

sudo cp *.py *.ini *.sh *.txt /var/www/papuwx
cd /var/www/papuwx
sudo chown nginx:nginx -R .
