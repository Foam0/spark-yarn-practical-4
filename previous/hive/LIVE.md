# Работающий стенд — ДЗ №3

Проверки выполнялись **2026-10-09** на стенде team-27.

## Развёртывание

- `/opt/hive-cluster-practical-3` на `team-27-00`.
- Три отдельных контейнера: `apache/hive:4.0.0` (HiveServer2), `apache/hive:4.0.0` (Metastore), `postgres:16-bookworm` (PostgreSQL).
- `deploy-remote.py` завершился с кодом 0 и сообщением `Deployment and data load completed`.
- Метаданные в именованном volume PostgreSQL; строки таблицы в существующем HDFS на `team-27-nn`.
- Удалённый JDBC: `jdbc:hive2://10.27.0.12:10000/default`; удалённый Metastore: `thrift://127.0.0.1:9083` (другой контейнер в host network).

## Данные

Таблица `practical3.orders`, партиции:

```text
dt=2026-10-01/country=KZ
dt=2026-10-01/country=RU
dt=2026-10-02/country=KZ
dt=2026-10-02/country=RU
```

Проверено точное содержимое 8 строк. Данные загружались повторно через `LOAD DATA LOCAL ... OVERWRITE`; после повторного запуска загрузчика дубликатов нет.

```text
country  count  sum
KZ       4      220.00
RU       4      140.00
```

Фильтр `dt='2026-10-01' AND country='RU'` возвращает заказы 1 и 2. `EXPLAIN EXTENDED` показывает путь выбранной партиции. Агрегация проверена через MapReduce в YARN: `application_1790870690688_0004` — `FINISHED / SUCCEEDED`, progress 100%, diagnostics пустые.

## Одновременные клиенты

Проверка `verify-concurrent.py` открыла два самостоятельных клиента Beeline и получила результаты обоих до закрытия любой сессии. Одновременно существовали два установленных серверных TCP-соединения на порту 10000.

```text
client_a_ready  client_a  hive  1  10.00
client_a_ready  client_a  hive  2  20.00
client_b_ready  client_b  hive  3  30.00
client_b_ready  client_b  hive  4  40.00
```

Поля: маркер, `logged_in_user()`, `current_user()`, order_id, amount. `logged_in_user()` различается; `current_user()` — общий сервисный пользователь hive, потому что `doAs=false`. Имена клиентов не являются аутентификацией: стенд использует NONE в закрытой сети.

## Сохранность после пересоздания контейнеров

После успешного повторного `deploy-remote.py` выполнены `docker compose down`, затем `docker compose up -d --wait`. **До новой загрузки** повторно выполнен полный `verify.py`:

- 8 точных строк и 4 партиции сохранились.
- `application_1790870690688_0005` — `FINISHED / SUCCEEDED`, progress 100%, diagnostics пустые.
- Два одновременных клиента повторно получили результаты.
- PostgreSQL `VERSION.SCHEMA_VERSION` = **4.0.0**.
- `hdfs fsck /user/hive/practical3/orders` — **HEALTHY**.
- Итог скрипта: **PASS**, код завершения 0.

Полный вывод проверки: [verification-20261009.txt](docs/verification-20261009.txt).

Существующий кластер после проверки: 3 Live DataNode, 0 потерянных/повреждённых/недореплицированных блоков. У всех девяти контейнеров HDFS/YARN `OOMKilled=false`, `RestartCount=0`.

В официальном образе Hive при запуске выводится предупреждение о нескольких SLF4J bindings; это не помешало выполнению запросов. Для запуска `fsck` через Hive-узел разрешён внутренний HTTP-порт NameNode 9870 только через закрытый туннель.
