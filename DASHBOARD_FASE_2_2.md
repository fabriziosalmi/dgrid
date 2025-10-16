# Fase 2.2: Dashboard Generator e Auto-Healing

## Panoramica

La **Fase 2.2** completa il sistema di gestione centralizzata di D-GRID introducendo:

1. **Torre di Controllo Visuale** - Dashboard in tempo reale che mostra lo stato di nodi e task
2. **Auto-Healing System** - Identificazione e recupero automatico di task bloccati (orfani)
3. **GitHub Pages Deployment** - Accesso pubblico al pannello di controllo
4. **Ciclo di Aggiornamento** - Refresh automatico ogni 5 minuti

---

## Architettura

### `.github/scripts/generate_dashboard.py`

**Responsabilità principale:**
- Scansionare la directory `nodes/` e determinare lo stato (attivo/inattivo)
- Contare i task per stato (queue, in_progress, completed, failed)
- Identificare e ripulire task orfani
- Generare HTML della dashboard

**Logica di Auto-Healing:**

```
Per ogni nodo:
  ↓
  timestamp_ultimo_heartbeat = leggi da nodes/{node_id}.json
  tempo_trascorso = now - timestamp
  
  SE tempo_trascorso > 5 minuti:
    nodo = INATTIVO 🔴
    
    Per ogni task in tasks/in_progress/:
      filename = {node_id_del_nodo}-{task_id}.json
      SE file in_progress corrisponde a questo nodo inattivo:
        → Sposta file da in_progress/ a queue/ usando `git mv`
        → Task rimesso in coda 🔄
```

**Logica di Determinazione Stato Nodo:**

```python
now = datetime.now(timezone.utc)
last_heartbeat = datetime.fromisoformat(node['last_heartbeat'])
uptime = now - last_heartbeat

SE uptime < 5 minuti:
  status = "🟢 ATTIVO"
ELSE:
  status = "🔴 INATTIVO"
```

---

### `.github/workflows/update-gh-pages.yml`

**Trigger:**
- `push` al branch `main` (quando ci sono cambiamenti in `nodes/`, `tasks/`, o nello script)
- `workflow_dispatch` (trigger manuale)
- `schedule` (ogni 5 minuti)

**Pipeline:**
1. **Checkout** - Scaricare il repository
2. **Python Setup** - Preparare l'ambiente Python 3.11
3. **Git Config** - Configurare il bot per i commit
4. **Generate Dashboard** - Eseguire `generate_dashboard.py`
5. **Commit Changes** - Se ci sono stati cambiamenti (pulizia task), committa e pusha su main
6. **Setup Pages** - Preparare la configurazione di GitHub Pages
7. **Upload Artifact** - Caricare `index.html` come artifact
8. **Deploy** - Pubblicare il sito su GitHub Pages
9. **Summary** - Mostrare il resoconto nel job summary

---

## Flusso Operativo Completo

### Scenario 1: Nodo si disconnette e ha un task bloccato

```
Timeline:
│
├─ T0: Worker-001 riceve task fibonacci-2025.json
│       File spostato: queue/ → in_progress/worker-001-fibonacci-2025.json
│       ✓ Heartbeat: worker-001 = T0
│
├─ T+3min: Network failure su Worker-001
│        ❌ Heartbeat timeout
│        worker-001 non può aggiornare il timestamp
│
├─ T+6min: Workflow update-gh-pages.yml si avvia (scheduled)
│        1. Scansiona nodes/ → trova worker-001 con ultimo heartbeat a T0
│        2. Calcola: uptime = 6 minuti > 5 minuti threshold
│        3. Determina: Worker-001 = INATTIVO 🔴
│        4. Scansiona in_progress/ → trova worker-001-fibonacci-2025.json
│        5. Usa `git mv` per spostare il file indietro a queue/
│        6. Committa e pusha il cambio su main
│        7. Genera dashboard mostrando worker-001 come inattivo
│
├─ T+7min: Prossimo worker disponibile
│        Esegue pull, vede fibonacci-2025.json in queue/
│        ✓ Lo prende con git mv atomico e lo esegue
│        ✓ Output completato e reportato
│
└─ [Fine] Task completato anche se il primo worker è scomparso
```

### Scenario 2: Task in esecuzione, nodo inattivo ma il task completa velocemente

```
├─ T0: Worker-002 riceve task fibonacci-25.json
│       File: in_progress/worker-002-fibonacci-25.json
│
├─ T+1sec: Task completa velocemente (fibonacci-25 è leggero)
│        Worker-002 sposta a completed/ e pusha
│        ✓ completed/fibonacci-25-result.json con output
│
├─ T+3min: Worker-002 network failure
│        ❌ Heartbeat timeout
│
├─ T+6min: Workflow update-gh-pages.yml si avvia
│        1. Scansiona in_progress/ → vuoto (non ha questo file)
│        2. Nessun cleanup necessario
│        3. Dashboard mostra: completed = 1 (successo)
│
└─ [Fine] Task già completato prima del timeout
```

### Scenario 3: Multiple workers, uno fallisce

```
├─ T0: Worker-001, Worker-002, Worker-003 = ATTIVI 🟢
│       Task in queue: 10
│       Task in progress: 3 (uno per worker)
│
├─ T+2min: Worker-002 crashes
│        ❌ Heartbeat non più aggiornato
│        Task in progress: 2 task attivi + 1 task orfano
│
├─ T+5min: Workflow update-gh-pages.yml si avvia
│        1. Identifica worker-002 come inattivo
│        2. Trova in_progress/worker-002-task-xyz.json
│        3. Sposta a queue/task-xyz.json
│        4. Dashboard now mostra:
│           - Nodi attivi: 2 (Worker-001, Worker-003) 🟢
│           - Nodo inattivo: 1 (Worker-002) 🔴
│           - Queue: 11 (10 originali + 1 recuperato)
│           - In progress: 2
│
├─ T+6min: Worker-001 o Worker-003 prende il task recuperato
│        ✓ Esecuzione riprende normalmente
│
└─ [Fine] Sistema auto-guarito, nessun intervento manuale
```

---

## Dashboard HTML

La dashboard visualizza:

### Sezione 1: Header
- Titolo: "🌐 D-GRID Mission Control"
- Subtitle: "Stato della rete decentralizzata"
- Timestamp dell'ultimo aggiornamento (UTC)
- Info: Auto-refresh ogni 60 secondi

### Sezione 2: Statistiche Principali
```
┌─────────────┐ ┌──────────┐ ┌─────────────┐ ┌────────────┐
│ 2 Nodi      │ │ 5 Task   │ │ 2 In Exec   │ │ 3 Completati
│ Attivi 🟢   │ │ in Coda  │ │ ⚙️          │ │ ✅         │
└─────────────┘ └──────────┘ └─────────────┘ └────────────┘
```

### Sezione 3: Tabella Nodi
```
┌────────┬──────────────┬─────────┬────────┬──────────────────┐
│ Stato  │ ID Nodo      │ CPU     │ RAM    │ Ultimo Heartbeat │
├────────┼──────────────┼─────────┼────────┼──────────────────┤
│ 🟢     │ worker-001   │ 4       │ 8.5 GB │ 2 secondi fa      │
│ 🟢     │ worker-003   │ 8       │ 16 GB  │ 15 secondi fa     │
│ 🔴     │ worker-002   │ 4       │ 8 GB   │ 6 minuti fa       │
└────────┴──────────────┴─────────┴────────┴──────────────────┘
```

### Sezione 4: Footer
- Versione: D-GRID v2.0
- Status: Operational
- Link al repository GitHub

---

## Integrazione con Worker Node

### Durante l'Esecuzione del Worker

```python
# main.py - Loop worker
while not shutdown_requested:
    try:
        git_handler.pull_rebase()
        task = task_runner.find_task_to_run()
        if task:
            result = task_runner.execute_task(task)
            task_runner.report_task_result(task, result)
        else:
            state_manager.send_heartbeat()  # ← AGGIORNA TIMESTAMP
        git_handler.commit_and_push(...)
    except Exception:
        git_handler.pull_rebase()  # Recovery
```

### Frequenza Heartbeat

- **Al termine di ogni task**: Automaticamente spostato a completed/failed
- **Se non ci sono task**: Heartbeat esplicito ogni `HEARTBEAT_INTERVAL` (default: 30 secondi)
- **Formato heartbeat**: Aggiorna semplicemente il timestamp `last_heartbeat` nel file `nodes/{node_id}.json`

---

## Come Viene Rilevato lo "Orfanità"

### Condizioni per Considerare un Task Orfano

```python
# File è orfano SE:
filename = "in_progress/{node_id}-{task_id}.json"
         ↓
node_id_dal_filename = estrarre da filename
         ↓
cercare in nodes/{node_id_dal_filename}.json
         ↓
SE nodo non esiste O nodo inattivo (uptime > 5 min):
  ALLORA file è ORFANO 🔴
         ↓
Azione: git mv da in_progress/ a queue/
```

### Soglia di Inattività

- **Default: 5 minuti** (configurabile in `generate_dashboard.py` come `ORPHAN_TIMEOUT_MINUTES`)
- **Razionale**: 
  - Abbastanza lungo da permettere al worker di ritornare da una disconnessione breve
  - Abbastanza corto da non far marcire i task per troppo tempo

---

## Recovery Senza Perdita di Dati

### Garantie

✅ **Atomicità**: `git mv` è atomico a livello di repository  
✅ **Durabilità**: Tutti i cambiamenti vengono pushati su GitHub  
✅ **Idempotenza**: Se lo script gira due volte, non duplica il lavoro  
✅ **Consistenza**: Git è la fonte di verità unica

### Caso di Errore

Se `git mv` fallisce durante cleanup:

```python
try:
    subprocess.run(["git", "mv", src, dst], check=True)
except subprocess.CalledProcessError:
    print(f"⚠️ git mv fallito, skip task {task_file}")
    continue  # Continua con il prossimo task, non interrompi tutto
```

Il task rimane in `in_progress/` e verrà ritentato al prossimo ciclo di dashboard.

---

## Monitoraggio

### Log di Dashboard

Lo script `generate_dashboard.py` produce un output dettagliato:

```
======================================================================
🚀 D-GRID Mission Control Dashboard Generator
======================================================================

📍 Percorsi:
  Repo root: /path/to/repo
  Nodes dir: /path/to/repo/nodes
  Tasks dir: /path/to/repo/tasks

1️⃣  Scansione dello stato dei nodi...
   ✓ Nodo 'worker-001': 🟢 ATTIVO (2 secondi fa)
   ✓ Nodo 'worker-003': 🟢 ATTIVO (15 secondi fa)
   ✓ Nodo 'worker-002': 🔴 INATTIVO (6 minuti fa)
   → 3 nodi totali

2️⃣  Pulizia task orfani...
   ❗️ Task orfano: worker-002-fibonacci-2025.json
     Nodo 'worker-002' inattivo. Rimetto in coda...
     ✓ Rimosso in fibonacci-2025.json

✅ Cleanup completato: 1 task rimessi in coda
✓ Commit e push completati

3️⃣  Conteggio task per stato...
  queue: 5 task
  in_progress: 2 task
  completed: 3 task
  failed: 0 task

4️⃣  Generazione HTML della dashboard...
5️⃣  Salvataggio dashboard...
   ✓ Dashboard salvata in /path/to/index.html

======================================================================
✅ Generazione dashboard completata con successo
======================================================================
```

### Job Summary nel Workflow

GitHub Actions genera un riepilogo automatico:

```
## 🌐 Dashboard Generation Complete

**Status:** ✅ Success

- Dashboard updated and pushed to main
- Deployed to GitHub Pages
```

---

## Troubleshooting

### "Dashboard non si aggiorna"

**Possibili cause:**
1. Workflow non triggered (controllare il branch)
2. `generate_dashboard.py` non trovato (controllare path)
3. Permissions insufficienti (controllare settings GitHub Pages)

**Soluzione:**
- Triggerare manualmente da Actions → "Generate and Deploy Dashboard" → "Run workflow"

### "Task rimane bloccato in in_progress anche dopo timeout"

**Possibili cause:**
1. Timeout impostato troppo lungo
2. Nodo disconnesso ma heartbeat non ancora scaduto
3. Workflow non si è avviato ancora

**Soluzione:**
- Diminuire `ORPHAN_TIMEOUT_MINUTES` in `generate_dashboard.py`
- Trigggerare manualmente il workflow
- Verificare che il nodo sia effettivamente inattivo

### "Errore: git mv fallito durante cleanup"

**Possibili cause:**
1. File già stato spostato da un altro processo
2. Conflitto git locale
3. Permessi insufficienti

**Soluzione:**
- Lo script gestisce gracefully (log warning e continua)
- Il task verrà ritentato al prossimo ciclo
- Se persiste, controllare il repository manualmente

---

## Prossimi Passi

La Fase 2.2 è **COMPLETA**. La torre di controllo è operativa.

**Ora siamo pronti per:**

1. **[Fase 5]** Test Locale del Worker Node (vedi NEXT STEPS)
2. Osservare la dashboard aggiornarsi in tempo reale
3. Verificare il cleanup automatico dei task orfani
4. Procedere con Docker build e lancio

---

## File di Riferimento

- `.github/scripts/generate_dashboard.py` - Script generatore (~330 linee)
- `.github/workflows/update-gh-pages.yml` - Workflow (75 linee)
- `index.html` - Output generato (auto)
- `progress.md` - Roadmap aggiornata

**Status Finale:** 🟢🟡🟡⚪⚪ **70% → 80% TARGET**
