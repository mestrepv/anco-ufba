# Restore — recuperação de backup do banco

Procedimento documentado para restaurar a plataforma AnCo a partir de
um dump do PostgreSQL gerado por `manage.py backup_db` (Fase 7).

> **Política**: o restore deve ser exercitado em **staging trimestralmente**.
> Sem teste real, o backup é wishful thinking. Veja a checklist de
> verificação pós-restore ao final.

---

## 1. Pré-requisitos

- Acesso ao bucket S3 (ou diretório local) onde estão os dumps.
- Containers Docker do projeto rodando (web + db). Em modo "fresh", basta
  `docker compose up -d db` antes do restore.
- Permissão de superusuário no Postgres (o `POSTGRES_USER` do `.env` é
  superuser por padrão da imagem oficial).
- O dump deve ser do mesmo **schema major** que o app espera. Restores
  cruzados entre versões do schema são frágeis; rodar `migrate` depois.

## 2. Localizar o dump desejado

### 2.1. Local (retenção de 7 dias)

```bash
ls -lh /var/backups/anco/anco-*.dump | sort -r | head
```

### 2.2. Remoto (S3/MinIO/Wasabi)

```bash
aws s3 ls "s3://$BACKUP_S3_BUCKET/backups/" \
    --endpoint-url "$BACKUP_S3_ENDPOINT" | sort -r | head

aws s3 cp "s3://$BACKUP_S3_BUCKET/backups/anco-20260429T030000Z.dump" /tmp/restore.dump \
    --endpoint-url "$BACKUP_S3_ENDPOINT"
```

## 3. Procedimento de restore

### 3.1. Em staging (recomendado)

```bash
# 1. Sobe banco vazio
docker compose -f infra/docker-compose.yml down -v db
docker compose -f infra/docker-compose.yml up -d db

# 2. Aguarda saúde
until docker compose -f infra/docker-compose.yml exec -T db pg_isready -U "$POSTGRES_USER"; do
    sleep 2
done

# 3. Restaura
docker compose -f infra/docker-compose.yml exec -T db pg_restore \
    --no-owner --no-privileges \
    --dbname "$POSTGRES_DB" \
    --username "$POSTGRES_USER" \
    < /tmp/restore.dump

# 4. Aplica migrations (caso o dump seja de uma versão anterior do schema)
docker compose -f infra/docker-compose.yml exec -T web python manage.py migrate
```

### 3.2. Em produção (situação de incidente)

> ⚠️ **Coloque a plataforma em modo manutenção antes**: pare o serviço
> `web` para evitar escritas inconsistentes durante o restore.

```bash
# 1. Snapshot do estado atual antes de sobrescrever (defensivo)
docker compose -f infra/docker-compose.yml exec -T db pg_dump \
    --format=custom --compress=9 -U "$POSTGRES_USER" "$POSTGRES_DB" \
    > /tmp/pre-restore-snapshot.dump

# 2. Para o web (mantém db rodando)
docker compose -f infra/docker-compose.yml stop web worker

# 3. Drop + recreate da database (como superuser)
docker compose -f infra/docker-compose.yml exec -T db psql -U "$POSTGRES_USER" -d postgres -c "
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE datname = '$POSTGRES_DB' AND pid <> pg_backend_pid();
"
docker compose -f infra/docker-compose.yml exec -T db psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS $POSTGRES_DB;"
docker compose -f infra/docker-compose.yml exec -T db psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;"

# 4. Restaura do dump
docker compose -f infra/docker-compose.yml exec -T db pg_restore \
    --no-owner --no-privileges \
    --dbname "$POSTGRES_DB" \
    --username "$POSTGRES_USER" \
    < /tmp/restore.dump

# 5. Migrations (idempotente; pega delta de schema se houver)
docker compose -f infra/docker-compose.yml run --rm web python manage.py migrate

# 6. Sobe web e worker
docker compose -f infra/docker-compose.yml up -d web worker
```

## 4. Checklist de verificação pós-restore

Após qualquer restore (staging ou prod), confirme:

- [ ] `manage.py check` retorna sem issues.
- [ ] Tela `/admin/` carrega e mostra os modelos esperados.
- [ ] Total de análises confere com o esperado:
      `Analise.objects.count()` ~= valor pré-incidente.
- [ ] Acervo público lista pelo menos 1 análise pública.
- [ ] Login OAuth funciona (em staging, simular com superuser local).
- [ ] Histórico de versões (`simple_history`) aparece em pelo menos 1
      análise (confirma que tabelas de histórico vieram).
- [ ] Schedules do django-q2 estão presentes (aparecem em
      `/admin/django_q/schedule/`).
- [ ] E-mails de notificação saem normalmente (testar no console em
      staging).

## 5. Roteiro de teste trimestral em staging

Roteiro recomendado, executado a cada três meses:

1. Baixar o dump mais recente do S3.
2. Provisionar uma instância staging vazia (compose em servidor isolado).
3. Restaurar conforme §3.1.
4. Rodar a checklist §4.
5. Documentar o resultado em `docs/restores/YYYYMMDD-staging.md` (se
   houver problema, registrar a causa raiz e abrir issue).
6. Derrubar a staging.

Sem este teste, a primeira vez que o backup é exercitado de verdade é
durante um incidente real — e aí mora o desastre.

## 6. Troubleshooting

### "permission denied for schema public"

O dump traz comandos `OWNER` que exigem usuário super. Garanta que
está restaurando como o usuário do `.env` (`POSTGRES_USER`), que é
superuser na imagem oficial. As flags `--no-owner --no-privileges`
evitam que pg_restore tente reaplicar grants do dump.

### "extension unaccent does not exist"

A migration `apps/publico/0001_initial.py` cria a extensão. Rodar
`manage.py migrate publico` antes (ou após, dependendo do estado do
dump). Em prod, a extensão já existe no volume `pgdata`.

### Dump corrompido / parcial

Se `pg_restore` reclamar de fim de arquivo prematuro, o dump foi
truncado. Use o anterior. Por isso a retenção de 7 dias locais + 90
remotos: redundância intencional.

### Schemas dessincronizados

Se o dump é de uma versão antiga do schema, `pg_restore` aplica o
schema do dump; depois `manage.py migrate` aplica os deltas até a
versão atual. Nunca pular o `migrate` pós-restore.

---

**Última revisão**: 2026-04-29.
**Próxima revisão programada**: 2026-07-29 (trimestral).
