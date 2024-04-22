#!/usr/bin/env sh

cp nebo.service /usr/lib/systemd/system/nebo.service
cp vneshniy.service /usr/lib/systemd/system/vneshniy.service
cp napitok.service /usr/lib/systemd/system/napitok.service
systemctl daemon-reload
