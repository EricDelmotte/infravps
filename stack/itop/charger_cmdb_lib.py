"""Fonctions communes de chargement de la CMDB iTop."""
from itop_api import call

COMMENT = "Chargement CMDB par Claude"
log = []


def q(s):
    return s.replace("\\", "\\\\").replace("'", "\\'")


def get_id(cls, name, extra=None, missing_ok=False):
    oql = f"SELECT {cls} WHERE name = '{q(name)}'" + (f" AND {extra}" if extra else "")
    r = call({"operation": "core/get", "class": cls, "key": oql, "output_fields": "id"})
    objs = r.get("objects") or {}
    if not objs:
        if missing_ok:
            return None
        raise SystemExit(f"introuvable : {cls} {name}")
    return int(next(iter(objs.values()))["key"])


def upsert(cls, fields, key_field="name"):
    if cls in ("WebServer", "WebApplication", "ApplicationSolution", "DBServer", "DatabaseSchema"):
        fields = {k: v for k, v in fields.items() if k != "status"}
    extra = f"first_name = '{q(fields['first_name'])}'" if cls == "Person" else None
    oid = get_id(cls, fields[key_field], extra=extra, missing_ok=True)
    if oid:
        u = call({"operation": "core/update", "comment": COMMENT, "class": cls, "key": oid,
                  "output_fields": "id", "fields": fields})
        if u["code"] != 0:
            raise SystemExit(f"maj {cls} {fields[key_field]} : {u['message']}")
        log.append(f"= {cls} {fields[key_field]}")
        return oid
    c = call({"operation": "core/create", "comment": COMMENT, "class": cls, "output_fields": "id", "fields": fields})
    if c["code"] != 0:
        raise SystemExit(f"creation {cls} {fields[key_field]} : {c['message']}")
    log.append(f"+ {cls} {fields[key_field]}")
    return int(next(iter(c["objects"].values()))["key"])
