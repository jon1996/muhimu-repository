# Checklist lancement bêta contrôlée

**Cible :** comptables, experts-comptables, auditeurs — données fictives uniquement.  
**Décision actuelle :** CONDITIONAL GO (voir `RELEASE_READINESS.md`).

Légende : `[ ]` à faire · `[x]` fait · `[~]` partiel

---

## A. Technique (P0 obligatoires)

- [ ] ACC-01 — snapshots concurrents corrigés + tests
- [ ] SAAS-03 — tests isolation RLS inter-organisations verts
- [ ] OPS-01 — backup + restore testés et documentés
- [ ] ARCH-01 — runtime pilote sans `runserver`/bootstrap auto
- [ ] SEC-P0-01 — rate-limit authentification
- [ ] SYSCO-01 — validation écrite mapping liasse par EC (jeux fictifs)
- [x] Suite tests existante verte (195/195 — 2026-10-10 Docker)

## B. Environnement

- [ ] Instance dédiée bêta ≠ prod future
- [ ] `DJANGO_DEBUG=0`, secrets rotatés
- [ ] `BOOTSTRAP_LOCAL_ACCOUNTS=0`
- [ ] HTTPS + cookies Secure
- [ ] SMTP opérationnel (invitations)
- [ ] Monitoring basique (uptime API + disque + Postgres)

## C. Données & isolation

- [ ] Jeux de données fictifs réalistes (PME + cabinet)
- [ ] Aucune donnée financière réelle
- [ ] Procédure purge / fin de grant
- [ ] Export minimal pour restitution (au moins PDF + CSV soldes)

## D. Accès utilisateurs

- [ ] Invitations via DemoGrant / console
- [ ] Liste nominative des testeurs
- [ ] Rôles limités (accountant / auditor / viewer)
- [ ] Procédure de désactivation < 1 h
- [ ] MFA optionnel ou fort pour comptes staff

## E. Produit & support

- [ ] Guide démarrage FR (PDF ou Notion)
- [ ] Canal bugs (email / Linear / GitHub Issues privé)
- [ ] Template retour d’expérience
- [ ] Horaires support pendant pilote
- [ ] CGU + confidentialité acceptées à la 1ʳᵉ connexion

## F. Critères de sortie de bêta

- [ ] 0 incident P0 ouvert > 48 h
- [ ] Au moins 2 EC ont validé une liasse fictive
- [ ] Drill restore réussi dans le mois
- [ ] Aucune fuite inter-tenant détectée
- [ ] Décision GO commercialisation ou itération

## G. Interdits pendant la bêta

- Livres clients réels
- Affirmation marketing « certifié / conforme SYSCOHADA »
- Partage de credentials démo publics
- Modifications schema en prod sans rollback plan
