#!/usr/bin/env sh

cp tanjiro.service /usr/lib/systemd/system/tanjiro.service
systemctl daemon-reload
systemctl restart tanjiro.service
