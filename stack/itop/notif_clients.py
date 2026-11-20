#!/usr/bin/env python3
"""Notifications e-mail aux clients (demandeurs) des tickets iTop - 20/11/2026.

- Accuse de reception a la creation du ticket
- E-mail quand Eric ajoute un commentaire public
- E-mail a la resolution (avec invitation a cloturer ou reouvrir depuis le portail)
- E-mail a Eric quand le client agit depuis le portail (commentaire, cloture, reouverture)
Les incidents crees automatiquement par la supervision (titre "[Kuma] ...") ne declenchent
aucun e-mail au client.
"""
import sys
sys.path.insert(0, "/opt/stack/itop")
from itop_api import call

COMMENT = "Notifications clients (Claude)"
log = []
SIGN = ("<p>Cordialement,<br/><b>Eric Delmotte</b><br/>06 83 56 36 52 · "
        "<a href=\"https://www.e-delmotte.fr\">www.e-delmotte.fr</a></p>"
        "<p style=\"color:#777;font-size:12px\">Message automatique : pour répondre, "
        "ajoutez un commentaire au ticket depuis le portail d'assistance "
        "(https://itsm.e-delmotte.fr).</p>")
DEST_CLIENT = "SELECT Person WHERE id = :this->caller_id AND id != :current_contact_id"
DEST_ERIC = "SELECT Person WHERE email = 'eric@e-delmotte.com'"
SANS_KUMA = "title NOT LIKE '[Kuma]%'"


def q(s):
    return s.replace("\\", "\\\\").replace("'", "\\'")


def find(cls, oql_where):
    r = call({"operation": "core/get", "class": cls, "key": f"SELECT {cls} WHERE {oql_where}",
              "output_fields": "id"})
    if r["code"] != 0:
        raise SystemExit(f"get {cls} : {r['message']}")
    objs = r.get("objects") or {}
    return int(next(iter(objs.values()))["key"]) if objs else None


def save(cls, where, fields, label):
    oid = find(cls, where)
    if oid:
        r = call({"operation": "core/update", "comment": COMMENT, "class": cls, "key": oid,
                  "output_fields": "id", "fields": fields})
        op = "="
    else:
        r = call({"operation": "core/create", "comment": COMMENT, "class": cls,
                  "output_fields": "id", "fields": fields})
        op = "+"
    if r["code"] != 0:
        raise SystemExit(f"{cls} {label} : {r['message']}")
    oid = oid or int(next(iter(r["objects"].values()))["key"])
    log.append(f"{op} {cls} {label} ({oid})")
    return oid


def action(name, to, subject, body, description):
    return save("ActionEmail", f"name = '{q(name)}'", {
        "name": name, "status": "enabled", "description": description,
        "from": "no-reply@e-delmotte.com", "from_label": "Assistance e-delmotte",
        "reply_to": "eric@e-delmotte.com", "reply_to_label": "Eric Delmotte",
        "to": to, "subject": subject, "body": body, "language": "FR FR"}, name)


def trigger(cls, desc, fields, act):
    fields = dict(fields, description=desc, action_list=[{"action_id": act, "order": 1}])
    return save(cls, f"description = '{q(desc)}'", fields, desc)


# ---------- Actions ----------
a_ar = action(
    "Client – accusé de réception du ticket", DEST_CLIENT,
    "[$this->ref$] Votre demande a bien été enregistrée : $this->title$",
    "<p>Bonjour $this->caller_id->first_name$,</p>"
    "<p>Votre ticket <b>$this->ref$</b> a bien été enregistré. Je le prends en charge "
    "et je reviens vers vous rapidement.</p>"
    "<p><b>Objet :</b> $this->title$</p>"
    "<p>Vous pouvez suivre son avancement et ajouter des informations à tout moment : "
    "$this->hyperlink(portal)$</p>" + SIGN,
    "Accusé de réception envoyé au demandeur à la création d'un ticket (hors incidents Kuma).")

a_com = action(
    "Client – nouveau commentaire", DEST_CLIENT,
    "[$this->ref$] Nouveau message sur votre ticket : $this->title$",
    "<p>Bonjour $this->caller_id->first_name$,</p>"
    "<p>Un nouveau message a été ajouté à votre ticket <b>$this->ref$</b> :</p>"
    "<blockquote>$this->head_html(public_log)$</blockquote>"
    "<p>Pour répondre ou consulter l'historique : $this->hyperlink(portal)$</p>" + SIGN,
    "Prévient le demandeur quand un commentaire public est ajouté par quelqu'un d'autre que lui.")

a_res = action(
    "Client – ticket résolu", DEST_CLIENT,
    "[$this->ref$] Votre ticket est résolu : $this->title$",
    "<p>Bonjour $this->caller_id->first_name$,</p>"
    "<p>Votre ticket <b>$this->ref$</b> est résolu.</p>"
    "<p><b>Solution :</b></p><blockquote>$this->html(solution)$</blockquote>"
    "<p>Si tout est en ordre, vous pouvez le clore depuis le portail (bouton <b>Clore</b>). "
    "Si le problème persiste, cliquez sur <b>Ré-ouvrir</b> en expliquant ce qui ne va pas : "
    "$this->hyperlink(portal)$</p>"
    "<p>Sans réponse de votre part, le ticket sera clôturé automatiquement dans 7 jours.</p>" + SIGN,
    "Prévient le demandeur de la résolution et l'invite à clôturer ou réouvrir.")

a_eric = action(
    "Eric – action du client sur le portail", DEST_ERIC,
    "[iTop] $this->ref$ mis à jour par le client ($this->status$) : $this->title$",
    "<p>Le client a mis à jour le ticket <b>$this->ref$</b> depuis le portail.</p>"
    "<p>Organisation : $this->org_id_friendlyname$<br/>Demandeur : $this->caller_id_friendlyname$<br/>"
    "Statut : $this->status$</p>"
    "<blockquote>$this->head_html(public_log)$</blockquote>"
    "<p>Ouvrir le ticket : $this->hyperlink()$</p>",
    "Prévient Eric quand un client commente, clôture ou réouvre un ticket depuis le portail.")

# ---------- Declencheurs ----------
for cls in ("UserRequest", "Incident"):
    flt = f"SELECT {cls} WHERE {SANS_KUMA}"
    trigger("TriggerOnObjectCreate", f"Client – création {cls}",
            {"target_class": cls, "filter": flt}, a_ar)
    trigger("TriggerOnObjectUpdate", f"Client – commentaire public {cls}",
            {"target_class": cls, "filter": flt, "target_attcodes": "public_log"}, a_com)
    trigger("TriggerOnStateEnter", f"Client – résolution {cls}",
            {"target_class": cls, "filter": flt, "state": "resolved"}, a_res)
    trigger("TriggerOnPortalUpdate", f"Eric – mise à jour portail {cls}",
            {"target_class": cls}, a_eric)

print("\n".join(log))
