# Revue expérience utilisateur (comptable)

## 1. Parcours première utilisation (revue code UI)

| Étape | UI | API | Friction |
|---|---|---|---|
| Connexion | `/login` | identity | OK local ; pas de MFA |
| Choix organisation / société | tenant context | headers | Clair pour multi-sociétés |
| Création entreprise | organisation | tenancy | Présent |
| Configuration comptable initiale | dépend `ledger/status` | `ensure`/setup | Peu guidé |
| Import plan | plan-comptable | import CSV | Template CSV OK |
| Journaux | auto via setup | | Invisible pour l’utilisateur |
| Saisie écritures | journal/nouveau | draft/post | Cœur produit |
| Grand-livre / balance | pages dédiées | | OK |
| États financiers | `/etats` | statements + PDF | OK si ledger ready |
| Recherche / filtres | variable | | À enrichir |
| Mobile | Tailwind | | Non validé visuellement |

## 2. Améliorations priorisées

### P0 UX (avant bêta pilotes)

1. **Assistant de démarrage** : pays OHADA → devise → exercice → copie PCGO → première OD tutorielle.
2. **États vides explicites** : messages « initialisez le ledger » avec CTA.
3. **Glossaire / aide contextuelle** FR (partie double, contrepassation, clôture IT).

### P1

4. Messages d’erreur API reformulés (codes + actions).
5. Confirmation avant validation / contrepassation / clôture.
6. Indicateur période ouverte / validée / clôturée IT toujours visible.
7. Guide PDF « démarrage en 30 minutes ».

### P2

8. Raccourcis clavier saisie journal.
9. Mode « cabinet » : bascule sociétés plus ergonomique.
10. Accessibilité (focus, contrastes) audit dédié.

## 3. Terminologie

Globalement alignée SYSCOHADA (exercice, période, balance, grand-livre, contrepassation, liasse). Éviter le jargon IFRS dans l’UI.

## 4. Non couvert

- Tests utilisateurs avec vrais comptables (à planifier en bêta).
- Capture d’écran / parcours vidéo.
- Audit mobile navigateur (non réalisé dans cet audit).
