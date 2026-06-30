# Dossier technique — Bot Conseiller PEA

**Projet :** Assistant personnel d'investissement PEA via Telegram
**Auteure :** Marine
**Statut :** Phase de conception
**Dernière mise à jour :** Juin 2026

---

## 1. Objectif du projet

Construire un bot conversationnel Telegram, codé en Python, qui agit comme un conseiller/accompagnateur personnel pour la gestion d'un PEA Boursorama. Le bot doit permettre :

- Une vraie conversation libre (pas un simple menu de commandes)
- Un suivi automatisé du portefeuille (valorisation, plus-value)
- Des alertes proactives (news importantes, opportunités)
- Un apprentissage personnel en développement (Python, API, déploiement, CI/CD)

**Double objectif assumé :** outil utile au quotidien + terrain d'apprentissage technique. Les choix d'architecture doivent équilibrer les deux (ex: privilégier la compréhension à la rapidité d'implémentation quand c'est pertinent).

---

## 2. Fonctionnalités (cahier des charges)

### 2.1 Conversationnel
- Discussion libre avec mémoire de contexte (le bot se souvient des échanges précédents)
- Ajout/suppression de tickers suivis directement par la conversation (« ajoute ASML à ma watchlist »)
- Modification des préférences sectorielles dans le temps (« je veux m'orienter vers le médical »)
- Questions libres sur un titre (risque, volatilité, stabilité)

### 2.2 Suivi de portefeuille
- Source de vérité : base Notion "Transactions PEA"
- Calcul automatique de la valorisation actuelle et de la plus-value (cours via EODHD)
- Mise à jour du portefeuille après confirmation d'un achat (saisie manuelle ou texte libre, parsing automatique)

### 2.3 Recommandations
- Sur demande (« je veux investir, j'ai 50€ ») : proposition de 2-3 répartitions selon le budget et les préférences sectorielles
- Évaluation du risque d'un titre (volatilité historique, stabilité) à la demande
- Conseils contextuels (ex: « pas assez pour cet ETF, attends le mois prochain »)

### 2.4 Automatisations passives
- Récap hebdomadaire programmé : valorisation, plus-value, actualité du secteur suivi
- Alerte exceptionnelle hors planning : si une actualité à fort impact est détectée sur un titre suivi

---

## 3. Architecture technique

### 3.1 Stack retenue

| Composant | Choix | Justification |
|---|---|---|
| Langage | Python 3.12+ | Niveau déjà solide, écosystème riche pour ce type de projet |
| IA conversationnelle | Groq API (Llama 3.3 70B) | Gratuit (rate-limited, pas de facturation), rapide, qualité largement suffisante. API compatible format OpenAI. |
| Réception messages | python-telegram-bot (polling en dev → webhook en prod) | Librairie mature, bien documentée |
| Base de données | SQLite (dev) → Postgres (prod, si besoin) | Légère, suffisante pour stocker l'historique de conversation et l'état utilisateur |
| Stockage métier | Notion (API officielle) | Déjà en place, source de vérité pour transactions/budget |
| Données de marché | EODHD (endpoint `/api/eod/`, plan gratuit) | Couverture confirmée Europe + US, 20 req/jour suffisant pour l'usage prévu |
| News | À déterminer (Finnhub envisagé) | À valider en phase 3 |
| Hébergement | Render (palier gratuit) | Seul hébergeur avec un vrai gratuit permanent en 2026, sans CB |
| Versioning / CI-CD | GitHub + GitHub Actions | Standard de l'industrie, gratuit pour repos publics/privés en usage perso |

### 3.2 Pourquoi pas Ollama (pour l'instant)

Décision actée : Ollama (LLM local) n'est pas utilisé dans ce projet.
- Nécessite une machine allumée en permanence avec assez de RAM (8 Go+ pour un modèle correct)
- Incompatible avec les hébergements gratuits standards (512 Mo - 1 Go de RAM)
- Apprentissage du ML local est un sujet à part entière, mieux traité dans un projet dédié plus tard

### 3.3 Pourquoi pas Make (pour la partie conversationnelle)

Make a été testé en amont pour la partie conversationnelle et s'est avéré inadapté :
- Pas de gestion native de mémoire/contexte de conversation
- Mécanique d'état bricolée via Data Store, fragile et peu lisible
- Outil pensé pour des workflows linéaires (trigger → actions), pas pour du dialogue

**Make reste pertinent et sera conservé séparément pour :**
- Le récapitulatif hebdomadaire programmé (tâche planifiée, linéaire)
- Les alertes basées sur des règles simples (variation de prix, etc.)

Ces deux usages (workflows programmés) correspondent à ce que Make fait bien nativement.

---

## 4. Architecture applicative (vue d'ensemble)

```
┌─────────────┐      ┌──────────────────┐      ┌─────────────┐
│   Telegram   │◄────►│   Bot Python      │◄────►│  Groq API    │
│  (utilisateur)│      │  (Render, free)   │      │ (Llama 3.3)  │
└─────────────┘      └────────┬──────────┘      └─────────────┘
                               │
                ┌──────────────┼───────────────┐
                ▼              ▼               ▼
        ┌──────────────┐ ┌──────────┐  ┌──────────────┐
        │ SQLite/Postgres│ │  Notion  │  │    EODHD     │
        │ (historique,  │ │   API    │  │  (cours)     │
        │  contexte)    │ │(transac- │  │              │
        └──────────────┘ │  tions)  │  └──────────────┘
                          └──────────┘

   (en parallèle, séparé) :
   ┌─────────┐   planifié   ┌──────────┐
   │  Make   │─────────────►│ Telegram │  (récap hebdo, alertes simples)
   └─────────┘              └──────────┘
```

---

## 5. Roadmap

### Phase 0 — Setup (en cours)
- [x] Compte Telegram bot créé (BotFather)
- [x] Base Notion Transactions PEA en place
- [x] Compte EODHD + ticker mapping validé (format `.XETRA`, `.PA`, `.US`)
- [ ] Compte Groq créé, clé API récupérée
- [ ] Repo GitHub créé
- [ ] Environnement Python local configuré (venv, dépendances de base)

### Phase 1 — Bot conversationnel minimal (MVP)
- [ ] Connexion Telegram en polling (réception/envoi de messages basique)
- [ ] Connexion Groq (réponse simple à un message)
- [ ] Stockage de l'historique de conversation en SQLite (mémoire contextuelle)
- [ ] Premier test bout en bout : échange libre avec mémoire de contexte

### Phase 2 — Intégration métier
- [ ] Connexion API Notion (lecture transactions, écriture nouvelle transaction)
- [ ] Connexion API EODHD (récupération de cours)
- [ ] Logique de calcul de valorisation / plus-value
- [ ] Commande/intention « je veux investir » → suggestions selon budget + préférences
- [ ] Parsing de message libre pour enregistrer un achat (« j'ai acheté 2 ASML à 650€ »)
- [ ] Gestion dynamique de la watchlist (ajout/suppression de tickers en conversation)
- [ ] Gestion des préférences sectorielles modifiables en conversation

### Phase 3 — Enrichissement
- [ ] Intégration d'une source de news (Finnhub ou équivalent)
- [ ] Évaluation de risque/volatilité d'un titre à la demande
- [ ] Conseils contextuels (budget insuffisant, etc.)

### Phase 4 — Déploiement
- [ ] Déploiement sur Render (palier gratuit)
- [ ] Bascule polling → webhook
- [ ] Variables d'environnement sécurisées (clés API)

### Phase 5 — Automatisations programmées (Make, en parallèle)
- [ ] Scénario Make : récap hebdomadaire (valorisation, plus-value, actualité)
- [ ] Scénario Make : alerte si variation de prix significative

### Phase 6 — CI/CD (montée en compétence)
- [ ] Tests unitaires de base (pytest)
- [ ] GitHub Actions : lancer les tests à chaque push
- [ ] GitHub Actions : déploiement automatique sur Render à chaque merge sur `main`
- [ ] (Optionnel) Linting automatique (ruff/black)

---

## 6. Documentation et liens utiles

### APIs et services
- Telegram Bot API : https://core.telegram.org/bots/api
- python-telegram-bot (librairie) : https://docs.python-telegram-bot.org/
- Groq API (docs) : https://console.groq.com/docs
- Groq — compatibilité OpenAI SDK : https://console.groq.com/docs/openai
- EODHD API docs : https://eodhd.com/financial-apis/
- Notion API : https://developers.notion.com/
- Notion API — Python SDK (notion-client) : https://github.com/ramnes/notion-sdk-py

### Hébergement et déploiement
- Render docs : https://render.com/docs
- Render — déploiement Python : https://render.com/docs/deploy-python

### CI/CD
- GitHub Actions docs : https://docs.github.com/actions
- GitHub Actions — Python : https://docs.github.com/actions/automating-builds-and-tests/building-and-testing-python

### Base de données
- SQLite (doc Python) : https://docs.python.org/3/library/sqlite3.html
- SQLAlchemy (ORM, si besoin de monter en complexité) : https://docs.sqlalchemy.org/

---

## 7. Décisions actées (journal)

| Date | Décision | Raison |
|---|---|---|
| Juin 2026 | Abandon de Make pour la partie conversationnelle | Mémoire/contexte non géré nativement, friction technique excessive |
| Juin 2026 | Groq plutôt qu'Ollama | Gratuit, pas de contrainte matérielle/hébergement, qualité suffisante |
| Juin 2026 | Render plutôt que Railway/Fly.io | Seul palier gratuit permanent sans CB en 2026 |
| Juin 2026 | SQLite/Postgres en plus de Notion | Notion pas adapté pour stocker un historique de conversation volumineux |
| Juin 2026 | Polling en dev, webhook en prod | Simplicité de développement local, performance en production |

---

## 8. Notes ouvertes / à trancher plus tard

- Choix définitif de la source de news (Finnhub vs alternative)
- Granularité exacte de l'analyse de risque (formule de volatilité à définir)
- Politique de sauvegarde de la base SQLite/Postgres
- Gestion des secrets en production (variables d'environnement Render vs autre solution)