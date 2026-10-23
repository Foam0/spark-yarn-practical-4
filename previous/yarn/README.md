# Домашнее задание №2: YARN и внешние интерфейсы Hadoop

Автоматическое развёртывание Apache Hadoop 3.4.1 YARN поверх существующего HDFS из [домашнего задания №1](https://github.com/Foam0/hdfs-cluster-practical-1). Проект запускает ResourceManager, два NodeManager и MapReduce JobHistoryServer, проверяет настоящее задание WordCount и публикует интерфейсы основных и вспомогательных демонов через edge-узел.

**Работающий стенд и результаты:** [LIVE.md](LIVE.md).

## Архитектура

```text
Внешний браузер → HTTPS-туннели → nginx на edge → сервер Docker
                                               ├─ HDFS: NameNode, SecondaryNameNode, 3 DataNode
                                               └─ YARN: ResourceManager, 2 NodeManager, JobHistoryServer
```

Все девять демонов находятся в отдельных контейнерах на одном сервере. Проект YARN подключается к существующей Docker-сети HDFS, использует её NameNode и три DataNode. Форматирование HDFS и удаление её томов не выполняются.

Проверенная среда: Ubuntu 24.04 x86_64, Docker Engine, Compose v2, около 4 GiB RAM на сервере Hadoop и доступ в Интернет. Для edge нужны nginx, Python 3 и cloudflared; скрипты устанавливают их автоматически. Интерфейсы опубликованы для просмотра: nginx допускает GET/HEAD и запрещает запросы на изменение данных. RPC Hadoop снаружи не публикуется.

## 1. Подготовить сервер Hadoop

Если Docker ещё не установлен:

```bash
git clone https://github.com/Foam0/yarn-cluster-practical-2.git ~/yarn-cluster-practical-2
cd ~/yarn-cluster-practical-2
sudo ./scripts/install-server.sh
```

Если кластер из ДЗ №1 ещё не запущен:

```bash
sudo git clone https://github.com/Foam0/hdfs-cluster-practical-1.git /opt/hdfs-cluster-practical-1
cd /opt/hdfs-cluster-practical-1
sudo ./scripts/deploy.sh
```

По умолчанию YARN читает HDFS-конфиги из `/opt/hdfs-cluster-practical-1/config` и подключается к Docker-сети `hdfs-lab_hdfs`. Для другого расположения скопируйте `.env.example` в `.env` и измените пути. Файлы конфигурации HDFS должны быть доступны на этом же сервере Docker.

## 2. Развернуть YARN и проверить вычисления

Вернуться в каталог этого репозитория (при клонировании по команде выше):

```bash
cd ~/yarn-cluster-practical-2
sudo ./scripts/deploy.sh
```

Скрипт создаёт в HDFS каталоги истории и агрегированных логов, запускает четыре демона, ожидает их готовности и выполняет `scripts/verify.sh`. Проверка включает:

1. Два зарегистрированных здоровых NodeManager в состоянии `RUNNING`.
2. Выполнение WordCount через YARN с отдельными ApplicationMaster, map и reduce контейнерами.
3. Чтение результата из HDFS и сравнение с ожидаемым: `hadoop=1`, `hdfs=1`, `yarn=2`.
4. Статусы `FINISHED / SUCCEEDED` в ResourceManager и `SUCCEEDED` в JobHistoryServer.
5. `hdfs fsck` входных и выходных файлов: `HEALTHY`.

Пример успешного вывода:

```text
NodeManager: 2 RUNNING, healthy
YARN: application_... FINISHED SUCCEEDED
JobHistory: job_... SUCCEEDED
HDFS: HEALTHY; WordCount: правильный результат; история задания сохранена.
```

Отчёты появляются в `results/`, вход и результат каждой проверки — в отдельном `/homework2/wordcount-*` в HDFS. Повторная проверка:

```bash
sudo ./scripts/verify.sh
sudo docker compose exec -T resourcemanager yarn node -list
sudo docker compose exec -T resourcemanager yarn application -list -appStates ALL
```

Для учебного стенда ограничены Java heapsize и размеры контейнеров: ResourceManager/JobHistoryServer — 256 MiB heap, NodeManager — 128 MiB; каждый NodeManager объявляет 768 MiB и 2 vcore. ApplicationMaster/map/reduce получают по 256 MiB с Java heap 160 MiB. Это настройки для небольших учебных заданий; для больших данных нужно увеличить RAM и лимиты.

## 3. Опубликовать веб-интерфейсы через edge

Сначала на сервере Hadoop экспортировать адреса контейнеров:

```bash
sudo python3 scripts/export-endpoints.py > endpoints.json
```

Скопировать `endpoints.json` и этот репозиторий на edge. Edge должен видеть внутренний IP сервера Hadoop и его HTTP-порты. На edge выполнить, подставив свои IP:

```bash
sudo ./scripts/publish-tunnels.sh INTERNAL_IP PUBLIC_IP endpoints.json
sudo journalctl -u hadoop-web-tunnels -f
```

После запуска получить все внешние HTTPS-адреса:

```bash
sudo cat /var/lib/hadoop-web/public-urls.json
```

Поле `portal` — общая страница со ссылками на девять интерфейсов. Ссылки и перенаправления между Hadoop-демонами переписываются на внешние адреса, включая REST-данные ResourceManager и переходы в историю задания. Соединения исходящие: входящие HTTP-порты у провайдера открывать не требуется.

Quick Tunnels предназначены для учебных и тестовых сред. Они работают, пока работает cloudflared, не имеют гарантии доступности и получают новые адреса при новом запуске. Systemd автоматически восстанавливает публикацию и обновляет страницу со ссылками; после перезапуска взять актуальный адрес `portal` из JSON. Если контейнеры пересозданы и их IP изменились, повторить экспорт `endpoints.json` и запуск публикации. Для постоянных адресов используйте именованный Cloudflare Tunnel с собственным доменом либо открытые HTTP-порты edge. [Документация Cloudflare](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

Если входящие HTTP-порты доступны, вместо туннелей можно выполнить:

```bash
sudo ./scripts/publish-web.sh INTERNAL_IP PUBLIC_IP endpoints.json
```

В этом режиме портал доступен на `http://PUBLIC_IP/`, интерфейсы — на портах из таблицы:

| Демон | Порт сервера Hadoop и nginx на edge |
| --- | --- |
| NameNode | 9870 |
| SecondaryNameNode | 9868 |
| DataNode 1 / 2 / 3 | 9864 / 9865 / 9866 |
| ResourceManager | 8088 |
| NodeManager 1 / 2 | 8042 / 8043 |
| JobHistoryServer | 19888 |

## 4. Проверить доступ с внешнего компьютера

Для HTTPS-туннелей сохранить публичный JSON с edge в файл `public-urls.json`, затем:

```bash
python3 scripts/verify-web.py PUBLIC_IP --public-urls public-urls.json
```

Для прямого HTTP:

```bash
python3 scripts/verify-web.py PUBLIC_IP
```

Проверяются десять страниц, REST-данные NodeManager и JobHistoryServer, три здоровых HDFS DataNode, переход по tracking URL успешного задания и запрет POST на основных интерфейсах. Сначала выполните `verify.sh`, чтобы в ResourceManager было успешное задание.

## Управление и диагностика

```bash
sudo docker compose ps
sudo docker compose logs --tail=200
sudo ./scripts/stop.sh                   # остановить только YARN
sudo ./scripts/deploy.sh                 # запустить и проверить снова
```

На edge:

```bash
sudo systemctl status nginx hadoop-web-tunnels
sudo journalctl -u hadoop-web-tunnels --since '10 minutes ago'
sudo cat /var/lib/hadoop-web/public-urls.json
```

Docker и публикация включены в автозагрузку. Контейнеры используют `restart: unless-stopped`. История заданий и агрегированные логи сохраняются в HDFS. Выполняемые задания и реестр ResourceManager не защищены HA; этот стенд предназначен для обучения.

## Файлы

| Файл | Назначение |
| --- | --- |
| `docker-compose.yml` | Четыре демона YARN/MapReduce и подключение к HDFS |
| `config/yarn-site.xml` | ResourceManager, NodeManager, shuffle, ресурсы и агрегация логов |
| `config/mapred-site.xml` | Выполнение MapReduce в YARN и история заданий |
| `scripts/deploy.sh`, `verify.sh`, `stop.sh` | Запуск, функциональная проверка, остановка |
| `scripts/install-server.sh` | Установка Docker на Ubuntu |
| `scripts/export-endpoints.py`, `render-nginx.py` | Адреса контейнеров, proxy и внешние ссылки |
| `scripts/publish-web.sh`, `publish-tunnels.sh`, `tunnel-supervisor.py` | Публикация HTTP/HTTPS и восстановление через systemd |
| `scripts/verify-web.py` | Проверка внешнего доступа |

Конфигурация основана на [Hadoop Cluster Setup 3.4.1](https://hadoop.apache.org/docs/r3.4.1/hadoop-project-dist/hadoop-common/ClusterSetup.html) и [REST API JobHistoryServer](https://hadoop.apache.org/docs/r3.4.1/hadoop-mapreduce-client/hadoop-mapreduce-client-hs/HistoryServerRest.html).
