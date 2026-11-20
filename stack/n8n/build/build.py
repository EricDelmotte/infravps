"""Génère les workflows n8n (JSON importable par `n8n import:workflow`)."""
import json, uuid

COMMON = r"""
const ITOP = 'http://itop/webservices/rest.php?version=1.3';
const h = this.helpers;
async function itop(op) {
  const body = 'json_data=' + encodeURIComponent(JSON.stringify(op));
  const r = await h.httpRequest({ method: 'POST', url: ITOP, body, json: true,
    headers: { 'Auth-Token': $env.ITOP_TOKEN, 'Content-Type': 'application/x-www-form-urlencoded' } });
  if (r.code !== 0) throw new Error('iTop : ' + r.message);
  return Object.values(r.objects || {}).map(o => ({ key: o.key, ...o.fields }));
}
const q = s => String(s ?? '').replace(/\\/g, '\\\\').replace(/"/g, '\\"');
const esc = s => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const frDate = d => new Date(d).toLocaleDateString('fr-FR', { timeZone: 'Europe/Paris' });
async function orgEdelmotte() {
  return (await itop({ operation: 'core/get', class: 'Organization', key: 'SELECT Organization WHERE name LIKE "e-delmotte%"', output_fields: 'name' }))[0].key;
}
// demandeur d'un ticket : doit appartenir à l'organisation du ticket (premier contact de l'organisation)
async function demandeur(orgId) {
  const p = await itop({ operation: 'core/get', class: 'Person', key: `SELECT Person WHERE org_id = ${Number(orgId)}`, output_fields: 'name' });
  p.sort((a, b) => Number(a.key) - Number(b.key));
  return p[0] ? p[0].key : null;
}
async function personne(nom, prenom, orgId, email) {
  const f = await itop({ operation: 'core/get', class: 'Person', key: `SELECT Person WHERE name = "${q(nom)}" AND first_name = "${q(prenom)}"`, output_fields: 'name' });
  if (f[0]) return f[0].key;
  const c = await itop({ operation: 'core/create', class: 'Person', comment: 'n8n', output_fields: 'name',
    fields: { name: nom, first_name: prenom, org_id: orgId, email } });
  return c[0].key;
}
async function assigner(cls, id) {
  const team = (await itop({ operation: 'core/get', class: 'Team', key: 'SELECT Team WHERE name = "Support e-delmotte"', output_fields: 'name' }))[0];
  const agent = (await itop({ operation: 'core/get', class: 'Person', key: 'SELECT Person WHERE email = "eric@e-delmotte.com"', output_fields: 'name' }))[0];
  if (!team || !agent) return;
  await itop({ operation: 'core/apply_stimulus', class: cls, key: id, stimulus: 'ev_assign', comment: 'n8n',
    fields: { team_id: team.key, agent_id: agent.key }, output_fields: 'status' });
}
"""

FORM = COMMON + r"""
const req = $input.first().json;
const hdr = req.headers || {};
if (!$env.FORM_SECRET || hdr['x-formulaire-secret'] !== $env.FORM_SECRET) return [{ json: { ok: false, error: 'secret invalide' } }];
const b = req.body || {};
const type = b.type === 'incident' ? 'incident' : 'demande';
const cut = (v, n) => String(v ?? '').trim().slice(0, n);
const nom = cut(b.nom, 100), email = cut(b.email, 150), msg = cut(b.message, 5000), site = cut(b.site, 200);
const source = cut(b.source || 'formulaire', 60), ip = cut(b.ip, 60), tel = cut(b.telephone, 40);
if (!nom || !email || !msg) return [{ json: { ok: false, error: 'champs manquants' } }];

// Sites sans ticket iTop : le message devient une tâche du tableau de bord Pilotage
const SANS_TICKET = /arbitre-echecs/i;
if (SANS_TICKET.test(source)) {
  const premiere0 = (msg.split('\n').find(l => l.trim()) || msg).trim();
  await h.httpRequest({ method: 'POST', url: 'http://pilotage:8000/api/tasks', json: true, body: {
    title: `Contact ${source} : ${nom} — ${premiere0.slice(0, 60)}${premiere0.length > 60 ? '…' : ''}`,
    client: '', platform: 'Arbitrage', priority: 'Normale', status: 'À faire', due: '',
    detail: `De : ${nom} <${email}>${tel ? ' — ' + tel : ''}\n\n${msg}` } });
  return [{ json: { ok: true, ref: 'tâche Pilotage', type: 'tache' } }];
}

const edm = await orgEdelmotte();
let org = edm, caller = null, connu = false;
const p = (await itop({ operation: 'core/get', class: 'Person', key: `SELECT Person WHERE email = "${q(email)}"`, output_fields: 'org_id' }))[0];
if (p) { org = p.org_id; caller = p.key; connu = true; }
else caller = await personne('Formulaire web', 'Contact', edm, 'no-reply@e-delmotte.com');

let cis = [], siteNom = '';
if (site) {
  let host = '';
  try { host = new URL(/^https?:\/\//i.test(site) ? site : 'https://' + site).hostname.replace(/^www\./, ''); } catch (e) {}
  if (host) {
    const w = (await itop({ operation: 'core/get', class: 'WebApplication', key: `SELECT WebApplication WHERE url LIKE "%${q(host)}%"`, output_fields: 'name,org_id' }))[0];
    if (w && (!connu || w.org_id === org)) { if (w.org_id === org) cis = [{ functionalci_id: w.key }]; siteNom = w.name; }
  }
}
const premiere = msg.split('\n').find(l => l.trim()) || msg;
const titre = `[${source}] ${premiere.trim().slice(0, 70)}${premiere.trim().length > 70 ? '…' : ''}`;
const desc = `<p><b>De :</b> ${esc(nom)} &lt;${esc(email)}&gt;${tel ? ' — ' + esc(tel) : ''}${connu ? '' : ' <i>(contact inconnu de la CMDB)</i>'}</p>`
  + (site ? `<p><b>Site concerné :</b> ${esc(site)}${siteNom ? ' (' + esc(siteNom) + ')' : ''}</p>` : '')
  + `<p>${esc(msg).replace(/\n/g, '<br>')}</p><p><small>Reçu via ${esc(source)}${ip ? ', IP ' + esc(ip) : ''}</small></p>`;
const cls = type === 'incident' ? 'Incident' : 'UserRequest';
const fields = { org_id: org, caller_id: caller, title: titre, description: desc, origin: 'portal', functionalcis_list: cis };
if (type === 'incident') { fields.urgency = '2'; fields.impact = '3'; }
const t = (await itop({ operation: 'core/create', class: cls, comment: 'formulaire ' + source, output_fields: 'ref', fields }))[0];
return [{ json: { ok: true, ref: t.ref, type } }];
"""

KUMA = COMMON + r"""
const req = $input.first().json;
const hdr = req.headers || {};
// Appel réservé au réseau interne (Caddy bloque /webhook/kuma depuis Internet) ; secret facultatif en plus
if ($env.KUMA_SECRET && hdr['x-kuma-secret'] && hdr['x-kuma-secret'] !== $env.KUMA_SECRET) return [{ json: { ok: false, error: 'secret invalide' } }];
const b = req.body || {};
const hb = b.heartbeat, mon = b.monitor || {};
if (!hb || !mon.name) return [{ json: { ok: true, note: 'notification de test reçue' } }];
const nom = mon.name;
const titre = `[Kuma] ${nom} injoignable`;
const ouverts = await itop({ operation: 'core/get', class: 'Incident',
  key: `SELECT Incident WHERE title = "${q(titre)}" AND operational_status NOT IN ("resolved","closed")`, output_fields: 'ref,status' });

if (hb.status === 0) {
  if (ouverts.length) return [{ json: { ok: true, ref: ouverts[0].ref, note: 'incident déjà ouvert' } }];
  let ci = (await itop({ operation: 'core/get', class: 'WebApplication', key: `SELECT WebApplication WHERE name = "${q(nom)}"`, output_fields: 'name,org_id' }))[0];
  if (!ci && mon.url) {
    let host = ''; try { host = new URL(mon.url).hostname.replace(/^www\./, ''); } catch (e) {}
    if (host) ci = (await itop({ operation: 'core/get', class: 'WebApplication', key: `SELECT WebApplication WHERE url LIKE "%${q(host)}%"`, output_fields: 'name,org_id' }))[0];
  }
  let org = ci ? ci.org_id : await orgEdelmotte();
  let caller = await demandeur(org);
  if (!caller) { org = await orgEdelmotte(); caller = await demandeur(org); }
  const desc = `<p>Uptime Kuma signale <b>${esc(nom)}</b> injoignable.</p><ul><li>Adresse : ${esc(mon.url || '?')}</li>`
    + `<li>Message : ${esc(hb.msg || b.msg || '')}</li><li>Détecté le : ${esc(hb.localDateTime || hb.time || '')}</li></ul>`
    + `<p>Incident créé automatiquement par n8n ; il sera résolu automatiquement au retour du site.</p>`;
  const t = (await itop({ operation: 'core/create', class: 'Incident', comment: 'n8n Kuma', output_fields: 'ref',
    fields: { org_id: org, caller_id: caller, title: titre, description: desc, origin: 'monitoring', impact: '3', urgency: '2',
              service_id: 2, functionalcis_list: ci ? [{ functionalci_id: ci.key }] : [] } }))[0];
  await assigner('Incident', t.key);
  return [{ json: { ok: true, ref: t.ref, note: 'incident créé' } }];
}
if (hb.status === 1 && ouverts.length) {
  const refs = [];
  for (const i of ouverts) {
    if (i.status === 'new') await assigner('Incident', i.key);
    await itop({ operation: 'core/apply_stimulus', class: 'Incident', key: i.key, stimulus: 'ev_resolve', comment: 'n8n Kuma', output_fields: 'ref',
      fields: { resolution_code: 'other', solution: `Rétabli : Uptime Kuma signale ${nom} de nouveau en ligne (${hb.localDateTime || hb.time || ''}). Résolution automatique.` } });
    refs.push(i.ref);
  }
  return [{ json: { ok: true, resolus: refs } }];
}
return [{ json: { ok: true, note: 'rien à faire' } }];
"""

DOMAINES = COMMON + r"""
const jour = 86400000, fmt = d => d.toISOString().slice(0, 10);
const debut = new Date(), fin = new Date(Date.now() + 15 * jour);
const contrats = await itop({ operation: 'core/get', class: 'ProviderContract',
  key: `SELECT ProviderContract WHERE name LIKE "OVH – Domaine%" AND end_date >= "${fmt(debut)}" AND end_date <= "${fmt(fin)}"`,
  output_fields: 'name,org_id,organization_name,end_date,description' });
const service = (await itop({ operation: 'core/get', class: 'Service', key: 'SELECT Service WHERE name = "Noms de domaine et DNS"', output_fields: 'name' }))[0];
const faits = [];
for (const c of contrats) {
  const domaine = c.name.replace(/^OVH\s*[–-]\s*Domaine\s*/i, '').trim();
  const titre = `Échéance du domaine ${domaine}`;
  const deja = await itop({ operation: 'core/get', class: 'UserRequest',
    key: `SELECT UserRequest WHERE title LIKE "${q(titre)}%" AND start_date > DATE_SUB(NOW(), INTERVAL 40 DAY)`, output_fields: 'ref' });
  if (deja.length) continue;
  const manuel = /manuel/i.test(c.description || '');
  let orgT = c.org_id, caller = await demandeur(orgT);
  if (!caller) { orgT = await orgEdelmotte(); caller = await demandeur(orgT); }
  const action = manuel
    ? `<p><b>Renouvellement manuel.</b> Demander au client (${esc(c.organization_name)}) s'il souhaite continuer. S'il confirme : renouveler dans l'espace client OVH (Facturation &gt; Mes services), puis mettre à jour la date de fin du contrat dans iTop. Sinon : le prévenir par écrit de l'arrêt du site et des e-mails à l'échéance.</p>`
    : `<p><b>Renouvellement automatique prévu.</b> Vérifier dans l'espace client OVH (Facturation &gt; Mes services) que le renouvellement est bien en automatique et que le moyen de paiement est valide. Aucune action client.</p>`;
  const desc = `<p>Le domaine <b>${esc(domaine)}</b> arrive à échéance le <b>${frDate(c.end_date)}</b>.</p>${action}<p><small>Rappel automatique n8n (J-15).</small></p>`;
  const fields = { org_id: orgT, caller_id: caller, title: `${titre} le ${frDate(c.end_date)}`, description: desc, origin: 'mail' };
  if (service) fields.service_id = service.key;
  const t = (await itop({ operation: 'core/create', class: 'UserRequest', comment: 'n8n domaines', output_fields: 'ref', fields }))[0];
  await assigner('UserRequest', t.key);
  try {
    await h.httpRequest({ method: 'POST', url: 'http://pilotage:8000/api/tasks', json: true, body: {
      title: `Domaine ${domaine} : ${manuel ? 'confirmer le renouvellement avec le client' : 'vérifier le renouvellement automatique'}`,
      client: c.organization_name, platform: 'Nom de domaine', priority: manuel ? 'Haute' : 'Normale', status: 'À faire',
      due: c.end_date, detail: `Ticket iTop ${t.ref} — échéance le ${frDate(c.end_date)}.` } });
  } catch (e) { /* le tableau de bord est facultatif */ }
  faits.push({ domaine, ref: t.ref, manuel });
}
return [{ json: { ok: true, contrats: contrats.length, tickets: faits } }];
"""

def code_node(name, js, pos):
    return {"parameters": {"jsCode": js.strip()}, "id": str(uuid.uuid4()), "name": name,
            "type": "n8n-nodes-base.code", "typeVersion": 2, "position": pos}

def webhook_wf(wid, name, path, js):
    hook = {"parameters": {"httpMethod": "POST", "path": path, "responseMode": "responseNode", "options": {}},
            "id": str(uuid.uuid4()), "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2,
            "position": [0, 0], "webhookId": str(uuid.uuid5(uuid.NAMESPACE_URL, path))}
    code = code_node("Traitement", js, [240, 0])
    resp = {"parameters": {"respondWith": "json", "responseBody": "={{ JSON.stringify($json) }}", "options": {}},
            "id": str(uuid.uuid4()), "name": "Réponse", "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": [480, 0]}
    return {"id": wid, "name": name, "active": False, "nodes": [hook, code, resp],
            "connections": {"Webhook": {"main": [[{"node": "Traitement", "type": "main", "index": 0}]]},
                            "Traitement": {"main": [[{"node": "Réponse", "type": "main", "index": 0}]]}},
            "settings": {"executionOrder": "v1", "timezone": "Europe/Paris"}}

def schedule_wf(wid, name, cron, js):
    sch = {"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": cron}]}},
           "id": str(uuid.uuid4()), "name": "Chaque jour 8 h 05", "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [0, 0]}
    man = {"parameters": {}, "id": str(uuid.uuid4()), "name": "Lancement manuel", "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [0, 200]}
    code = code_node("Traitement", js, [260, 100])
    return {"id": wid, "name": name, "active": False, "nodes": [sch, man, code],
            "connections": {"Chaque jour 8 h 05": {"main": [[{"node": "Traitement", "type": "main", "index": 0}]]},
                            "Lancement manuel": {"main": [[{"node": "Traitement", "type": "main", "index": 0}]]}},
            "settings": {"executionOrder": "v1", "timezone": "Europe/Paris"}}

wfs = [
    webhook_wf("FormulaireTicket01", "Formulaire de contact → ticket iTop", "formulaire", FORM),
    webhook_wf("KumaIncident000001", "Alerte Uptime Kuma → incident iTop", "kuma", KUMA),
    schedule_wf("DomainesJ15000001", "Échéances des domaines à J-15 → ticket iTop + tâche", "5 8 * * *", DOMAINES),
]
for w in wfs:
    json.dump([w], open(f"/mnt/user-data/outputs/n8n-{w['id']}.json", "w"), ensure_ascii=False, indent=1)
print("ok", [w["name"] for w in wfs])
