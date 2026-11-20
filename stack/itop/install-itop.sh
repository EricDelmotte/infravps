#!/bin/sh
# Installation non interactive d iTop : lit les mots de passe dans secrets/, ne les affiche jamais.
set -e
cd /opt/stack/itop
[ -s secrets/admin_password ] || { echo "secrets/admin_password manquant"; exit 1; }
X=$(mktemp); chmod 600 "$X"
cp /var/www-itop-template.xml "$X" 2>/dev/null || cp web/setup/unattended-install/xml_setup/itil-fresh-install.xml "$X"
python3 - "$X" <<PY
import sys,xml.etree.ElementTree as ET
p=sys.argv[1]; t=ET.parse(p); r=t.getroot()
dbp=open("secrets/db_password").read().strip(); adp=open("secrets/admin_password").read().strip()
def s(path,val): r.find(path).text=val
s("database/server","itop-db"); s("database/user","itop"); s("database/pwd",dbp); s("database/name","itop"); s("database/prefix","")
s("database/db_tls_enabled","0")
s("url","https://itsm.e-delmotte.fr/")
s("admin_account/user","eric"); s("admin_account/pwd",adp); s("admin_account/language","FR FR"); s("language","FR FR")
s("sample_data","0")
t.write(p,encoding="UTF-8",xml_declaration=True)
PY
docker cp "$X" itop:/tmp/params.xml; rm -f "$X"
docker exec itop chown www-data /tmp/params.xml
docker exec -u www-data itop php /var/www/html/setup/unattended-install/unattended-install.php --param-file=/tmp/params.xml --installation_xml=/var/www/html/datamodels/2.x/installation.xml 2>&1 | grep -viE "pwd|password" | tail -25
docker exec itop rm -f /tmp/params.xml
