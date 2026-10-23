# HDFS-кластер: NameNode, SecondaryNameNode и 3 DataNode

Автоматизированное развёртывание учебного HDFS-кластера на Apache Hadoop 3.4.1. Проект поднимает пять изолированных сервисов через Docker Compose, сохраняет данные в именованных томах и сам проверяет работоспособность кластера.

## Архитектура

```text
                       Web UI :9870
                             │
                    ┌────────▼────────┐
                    │    NameNode     │
                    │ RPC :8020       │
                    └───┬────┬────┬───┘
                        │    │    │
              ┌─────────┘    │    └─────────┐
              ▼              ▼              ▼
        ┌───────────┐  ┌───────────┐  ┌───────────┐
        │ DataNode1 │  │ DataNode2 │  │ DataNode3 │
        └───────────┘  └───────────┘  └───────────┘
                        Репликация = 3

              ┌───────────────────────┐
              │   SecondaryNameNode   │
              │ checkpoints / :9868  │
              └───────────────────────┘
```

SecondaryNameNode не является резервным NameNode: он периодически объединяет `fsimage` и журнал правок, создавая checkpoint метаданных.

## Требования

- Docker Engine 24+ или Docker Desktop;
- Docker Compose v2;
- свободные порты `9870`, `9868`, `9864`, `9865`, `9866`;
- ориентировочно 4 ГБ свободной оперативной памяти.

Поддерживаются Linux, macOS и Windows с WSL2. Образ `apache/hadoop:3.4.1` может запускаться через эмуляцию на ARM-машинах, поэтому первый старт там дольше.

## Быстрый запуск

```bash
git clone <URL_ЭТОГО_РЕПОЗИТОРИЯ>
cd hdfs-cluster
./scripts/deploy.sh
```

Скрипт:

1. создаёт сеть и постоянные тома;
2. при первом старте форматирует NameNode;
3. запускает NameNode, SecondaryNameNode и три DataNode;
4. ждёт регистрации всех DataNode;
5. записывает в HDFS тестовый файл, читает его обратно, устанавливает репликацию `3` и запускает `fsck`.

Успешный результат выглядит так:

```text
Проверка пройдена:
Live datanodes (3):
Dead datanodes (0):
Status: HEALTHY
Number of data-nodes: 3
SecondaryNameNode: RUNNING
```

## Ручная проверка

Открыть интерфейс NameNode: [http://localhost:9870](http://localhost:9870). В разделе **Datanodes** должны отображаться три живых узла и ни одного мёртвого.

Проверка из терминала:

```bash
docker compose exec namenode hdfs dfsadmin -report
docker compose exec namenode hdfs fsck / -files -blocks -locations
docker compose exec secondarynamenode ps -eo pid,args
```

Повторный полный автоматический тест:

```bash
./scripts/verify.sh
```

Интерфейсы сервисов:

| Сервис | Адрес |
|---|---|
| NameNode | http://localhost:9870 |
| SecondaryNameNode | http://localhost:9868 |
| DataNode 1 | http://localhost:9864 |
| DataNode 2 | http://localhost:9865 |
| DataNode 3 | http://localhost:9866 |

## Остановка и очистка

Остановить контейнеры, сохранив данные:

```bash
./scripts/stop.sh
```

Повторный `./scripts/deploy.sh` продолжит работу с существующими томами. Чтобы полностью удалить кластер вместе со всеми данными HDFS:

```bash
docker compose down -v
```

Команда с `-v` необратимо удаляет учебные данные из именованных томов проекта.

## Что находится в репозитории

```text
.
├── .github/workflows/verify.yml  # проверка кластера в GitHub Actions
├── config/
│   ├── core-site.xml             # адрес NameNode
│   └── hdfs-site.xml             # каталоги, репликация, checkpoint
├── scripts/
│   ├── deploy.sh                 # развёртывание + проверка
│   ├── verify.sh                 # проверка целостности
│   └── stop.sh                   # безопасная остановка
└── docker-compose.yml            # описание пяти сервисов и томов
```

## Диагностика

Статус контейнеров и последние логи:

```bash
docker compose ps
docker compose logs --tail=200 namenode
docker compose logs --tail=200 secondarynamenode
docker compose logs --tail=200 datanode1 datanode2 datanode3
```

Если после изменения конфигурации требуется чистый кластер, выполните `docker compose down -v`, затем снова `./scripts/deploy.sh`.
