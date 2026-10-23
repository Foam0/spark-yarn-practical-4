# Фактическая проверка — 23 октября 2026

Учебный стенд **team-27**, проект `/opt/spark-yarn-practical-4` на `team-27-01`.

## Первый полный запуск

- Установка нативного Spark и подготовка HDFS: `DEPLOY PASS`.
- Spark **3.5.7**, `master=yarn`, `deploy_mode=client`.
- YARN application: **application_1790870690688_0007**, тип **SPARK**, состояние **FINISHED**, итог **SUCCEEDED**.
- Driver: `10.255.28.2:39002`; удалённый executor: **nodemanager2:36735**.
- Источник: `hdfs://namenode:8020/user/hive/practical3/orders`, 8 строк из ДЗ №3, сумма 360.00.
- Результат: `/user/spark/practical4/daily_sales`, 4 строки, 4 партиции, формат Parquet.
- Beeline через существующий HiveServer2 прочитал все строки **после завершения драйвера Spark**. Каждая строка и все агрегаты сравнивались с ожидаемыми значениями.
- Фильтр `dt='2026-10-02' AND country='RU'` вернул `2` и `110.00`.
- HDFS fsck — **HEALTHY**.
- Полная проверка завершилась **PASS**, код возврата 0.

| dt | country | order_count | gross_amount | avg_amount | product_count | vat_amount |
|---|---|---:|---:|---:|---:|---:|
| 2026-10-01 | KZ | 2 | 70.00 | 35.00 | 2 | 14.00 |
| 2026-10-01 | RU | 2 | 30.00 | 15.00 | 2 | 6.00 |
| 2026-10-02 | KZ | 2 | 150.00 | 75.00 | 2 | 30.00 |
| 2026-10-02 | RU | 2 | 110.00 | 55.00 | 2 | 22.00 |

Первичные отчёты: [проверка](docs/verification-first.json), [Spark](docs/spark-first.json), [YARN REST](docs/yarn-first.json).

Начальное ожидание ресурсов YARN может давать предупреждение `Initial job has not accepted any resources`: запуск ожидает выделения executor на небольшом учебном кластере. Финальное состояние и результат задания проверяются отдельно, предупреждение не считается подтверждением завершения.

## Повторное развёртывание и запуск

Повторный `scripts/deploy.py` завершился `DEPLOY PASS`. После него повторён полный `scripts/run.py`: **PASS**, код возврата 0.

- Application: **application_1790870690688_0008**, **FINISHED / SUCCEEDED**.
- Удалённый executor: `Map(10.255.28.2:39002 -> (294440140,294253248), nodemanager2:46275 -> (97832140,97645248))`.
- Снова прочитаны 8 входных строк, результат содержит ровно 4 строки и 4 партиции; дубликатов после overwrite нет.
- Чтение через Hive выполнено после завершения Spark, все значения совпали, HDFS fsck — HEALTHY.
- Исходный кластер: 3 Live DataNode, 0 missing/corrupt/under-replicated blocks; 2 Active NodeManager, 0 Lost/Unhealthy; приложений FAILED = 0.

Финальные артефакты: [сводка](docs/verification.json), [Spark](docs/spark-result.json), [YARN](docs/yarn-application.json), [строки Hive](docs/hive-rows.tsv), [партиции](docs/hive-partitions.tsv), [схема и LOCATION Hive](docs/hive-describe.tsv), [файлы HDFS](docs/hdfs-files.log), [fsck](docs/hdfs-fsck.log), [spark-submit](docs/spark-submit.log).
