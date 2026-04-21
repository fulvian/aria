# Disaster Recovery Runbook

**Documento**: ARIA Phase 1 DR Runbook  
**Version**: 1.0.0  
**Date**: 2026-04-21  
**Owner**: fulvio  
**Phase**: 1 (Sprint 1.4)

---

## 1. Panoramica

Questo documento definisce le procedure di Disaster Recovery per ARIA, per mitigating data loss e ensuring rapid recovery.

### 1.1 Obiettivi di Recovery

| Metrica | Target | Note |
|---------|--------|------|
| **RPO** (Recovery Point Objective) | 7 giorni | Backup weekly; daily raccomandato per utenti attivi |
| **RTO** (Recovery Time Objective) | < 30 minuti | Tempo per restore completo |

### 1.2 Componenti Critici

- **Memory DB**: `.aria/runtime/memory/episodic.db` (SQLite raw + FTS5)
- **Scheduler DB**: `.aria/runtime/scheduler/scheduler.db`
- **Gateway Sessions DB**: `.aria/runtime/gateway/sessions.db`
- **Credentials**: `.aria/credentials/` (SOPS cifrati)
- **Runtime State**: `.aria/runtime/` (logs, tmp)

---

## 2. Backup Strategy

### 2.1 Backup Script (`scripts/backup.sh`)

Il backup script esegue:
1. **WAL checkpoint** su tutti i DB SQLite prima del backup
2. **Crea tarball** di `.aria/runtime` e `.aria/credentials`
3. **Cifra con age** usando la chiave pubblica in `.age.pub`
4. **Deposita** in `$HOME/.aria-backups/aria-backup-<timestamp>.tar.age`
5. **Cleanup** automatico dei backup > 30 giorni

### 2.2 Schedule

| Task | Cron | Policy | Note |
|------|------|--------|------|
| weekly-backup | `0 3 * * 0` (domenica 03:00) | allow | Backup full system |

### 2.3 Chiavi di Cifratura

- **Chiave pubblica** (per cifrazione): `.age.pub` nel repo
- **Chiave privata** (per decifrazione): `$HOME/.config/sops/age/keys.txt` **FUORI dal repo**

⚠️ **CRITICO**: La chiave privata DEVE essere fuori dal repo per sicurezza.

---

## 3. Restore Procedure

### 3.1 Restore da Backup

```bash
# List available backups
aria backup list
# o
ls -la ~/.aria-backups/

# Restore from backup
aria backup restore ~/.aria-backups/aria-backup-20260421-030000.tar.age

# Restore most recent
aria backup restore last
```

### 3.2 Restore Manuale Step-by-Step

1. **Verificare la chiave privata esista**:
   ```bash
   ls -la ~/.config/sops/age/keys.txt
   ```

2. **Identificare il backup**:
   ```bash
   ls -lt ~/.aria-backups/aria-backup-*.tar.age | head -5
   ```

3. **Eseguire restore** (conferma richiesta):
   ```bash
   ./scripts/restore.sh ~/.aria-backups/aria-backup-YYYYMMDD-HHMMSS.tar.age
   ```

4. **Verificare**:
   ```bash
   sqlite3 ~/.aria/runtime/memory/episodic.db "SELECT COUNT(*) FROM episodes"
   aria schedule list
   ```

5. **Restart servizi**:
   ```bash
   systemctl --user restart aria-scheduler.service aria-gateway.service
   ```

### 3.3 Restore su Ambiente Pulito

1. Reinstall ARIA:
   ```bash
   cd /home/fulvio/coding/aria
   ./scripts/bootstrap.sh
   ```

2. Ripristinare il backup:
   ```bash
   ./scripts/restore.sh ~/.aria-backups/aria-backup-YYYYMMDD-HHMMSS.tar.age
   ```

3. Verificare i servizi:
   ```bash
   systemctl --user status aria-scheduler.service aria-gateway.service
   ```

---

## 4. Test Backup/Restore

Il test di backup/restore è **obbligatorio** prima del merge e in CI.

```bash
# Eseguire il test
./scripts/test_backup_restore.sh

# Expected: exit code 0, "All tests PASSED"
```

### 4.1 Cosa testa `test_backup_restore.sh`

1. Crea un DB SQLite sintetico con 2 record
2. Esegue backup.sh
3. Verifica il file di backup creato
4. Cancella il DB originale
5. Esegue restore.sh
6. Verifica che il DB sia stato ripristinato con i 2 record

---

## 5. Scenari di Recovery

### 5.1 Corruzione Database Memory

**Sintomi**: Errori SQLite, query che falliscono

**Recovery**:
```bash
# 1. Stop servizi
systemctl --user stop aria-scheduler.service aria-gateway.service

# 2. Restore da backup
./scripts/restore.sh last

# 3. Restart servizi
systemctl --user start aria-scheduler.service aria-gateway.service
```

### 5.2 Perdita Completa del Sistema

**Sintomi**: Sistema non avviabile, directory corrotta

**Recovery**:
1. Reinstall OS/configurazione base
2. Clone repo ARIA
3. Run bootstrap.sh
4. Restore backup
5. Verificare servizi

### 5.3 Credential Leak Sospetto

**Sintomi**: Accesso non autorizzato sospettato

**Recovery**:
1. **Revoke immediata** di tutte le credenziali:
   ```bash
   aria creds revoke-all
   ```
2. Rotate tutte le API keys tramite provider
3. Revoke OAuth tokens Google:
   ```bash
   python -c "from aria.agents.workspace import GoogleOAuthHelper; \
     GoogleOAuthHelper().revoke('primary')"
   ```
4. Re-run oauth_first_setup.py per Google Workspace
5. Cambiare tutte le password

---

## 6. Checklist DR Test (mensile)

- [ ] Backup eseguito con successo
- [ ] Restore testato su ambiente pulito
- [ ] Chiave privata ancora valida
- [ ] Servizi restartano correttamente post-restore
- [ ] No errori nei log

---

## 7. Contatti Emergenza

| Ruolo | Contatto |
|-------|----------|
| Owner | Fulvio |

---

## 8. Log

| Data | Azione | Esito |
|------|--------|-------|
| 2026-04-21 | Sprint 1.4 implementation | Creato |

---

**Fine DR Runbook**
