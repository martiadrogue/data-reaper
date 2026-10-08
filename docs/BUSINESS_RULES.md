# Business Requirements Document (BRD)

**Project Name:** Data Reaper
**Companion of:** [Night Crawler](https://github.com/martiadrogue/night-crawler), the crawling platform that writes the files this project imports

---

## 1. Project Overview & Vision

Night Crawler writes one CSV per Crawler Execution and moves it to `var/csv/validated/` once its rows pass validation. Those files are the crawl's only output: Night Crawler never writes them into a database. The importer loads every validated CSV into MongoDB collections whose fields match the CSV columns. The result is one deduplicated, queryable record per item, kept fresh as new runs land.

---

## 2. Core Business Objectives

* **One record per item:** the same restaurant or show crawled by many runs, or by several Crawlers of one website, is stored once.
* **Freshness without churn:** a newer run updates a record only when its content changed; an unchanged one only gets a new "last seen" time.
* **Hands-off:** new files are picked up automatically; nothing has to be triggered by hand.
* **Resilience:** one bad row never loses a file; one bad file never stops the others; any failed import can be retried safely.
* **Traceability:** every record says which Crawler, run, and file last saw it, and every import says what it did, row by row.

---

## 3. Scope

### 3.1 Inputs

* Every `.csv` directly inside the configured folder (`CSV_SOURCE_DIR`, by default `./var/csv/validated`), named `<crawler_id>_<execution_id>_<started>.csv`.
* The files are read, never changed, moved, or deleted: they are the crawler's only copy.

### 3.2 Datasets and their columns

The importer recognises two Datasets from the CSV header ([DOMAIN_MODEL §5.3](DOMAIN_MODEL.md#53-csv-format-and-dataset-detection)):

| Dataset | Collection | What | Sources seen so far |
|---|---|---|---|
| `places` | `dataset_places` | Restaurants, bars, venues | TheFork (`thefork.es`), Google Maps (`maps.google.com`) |
| `events` | `dataset_events` | Shows and sessions | `atrapalo.com`, `thecomedyclubhouse.es`, `barcelonacomedyclub.com`, `tinta-roja.cat`, `englishstandupbarcelona.com` |

Each collection has one typed field per CSV column (numbers as numbers, dates as dates, JSON lists as arrays, `location` as an embedded point), plus the tracking fields. A file may hold any subset of its Dataset's columns; `item_id`, `name`, and `source_url` are required.

### 3.3 Out of scope

* Raw (not yet validated) CSVs in `var/csv/raw/`.
* Editing or deleting records through the API: the data is read-only to users.
* Any dataset beyond places and events. A file whose header fits neither fails with the reason.

---

## 4. Functional Requirements

1. **Discovery:** every minute, list the folder and queue an import for each file name never seen before, oldest run first. Admins can also scan at once from the UI or API.
2. **Detection:** decide the Dataset from the header alone; refuse a header that fits none, or both, with a message saying why.
3. **Normalization:** unescape HTML entities, trim text, type every value, and store an empty cell as `null` (or `[]`). A missing optional value is never an error.
4. **Deduplication:** key every record on its natural key, Source + `item_id`. The Source is the website, the host of `source_url` without `www.`, so three TheFork Crawlers feed one set of TheFork records.
5. **Change detection:** hash each record's content. Same hash: only `last_seen_at` moves. Different hash: the content and `updated_at` change too.
6. **Ordering:** a file never overwrites data a newer file already wrote. Rows from an older run than a record's `last_seen_at` are rejected with the reason.
7. **Error isolation:** a row that can't be imported is rejected, counted, and its reason kept (the first 20 per file); the file goes on. A file that can't be read, or fits no Dataset, fails on its own; the others go on.
8. **Idempotency and retries:** importing a file twice changes nothing. Any import that isn't `imported` can be retried.
9. **Monitoring:** each import records its counters (inserted, updated, unchanged, rejected), duration, and status, as metrics and on the Imports page. It also counts, per field, how many updated rows changed it. The Imports page shows the three most changed fields, and the import's detail lists them all.

---

## 5. Data & Persistence Requirements

* **Database:** MongoDB, like Night Crawler, in a database of its own (`data_reaper`).
* **Collections:** `dataset_imports`, `dataset_places`, `dataset_events`. Each validates its documents' field types and ranges ([DOMAIN_MODEL §6](DOMAIN_MODEL.md#6-structural-invariants)).
* **Transactions:** each batch of rows (500 by default) is written in one transaction, so a crash loses at most one batch. A retry finds the earlier batches `unchanged`.

---

## 6. Strategies, Limitations & Trade-offs

**Strategies**

* **Discovery** is a folder scan diffed against the stored file names, not a filesystem watch. It works on any mount (including Docker on macOS) and survives restarts; the cost is up to a minute of delay.
* **Deduplication** uses the website plus the website's own id, never a hash of the content, so a record keeps its identity when its rating or name changes.
* **Order safety** compares run start times, read from the file name, not import times. Files can be imported in any order, and imported again, with the same result.
* **Merging, not replacing:** a column a file lacks keeps its stored value. A cheaper listing crawl never erases what a detail crawl found; an empty cell still clears it.
* **One worker, one import at a time** (`--concurrency 1`): imports run in queue order (oldest run first), and two files never race to insert the same new record. Each of the 76 sample files (up to about 1,300 rows) imported in under 0.5 s.

**Known limitations**

* **Ratings are kept on the source's scale:** TheFork rates out of 10, Google out of 5. Compare ratings within one Source only.
* **Event times are wall-clock times** in each event's `timezone`, not UTC. Every event seen so far is in `Europe/Madrid`; sorting across time zones would need a UTC copy.
* **Repeated ids within one file merge:** Google Maps' grid search lists overlapping places, so a file of 578 rows yields 320 places. This is intended, but the row counts and record counts differ.
* **Listing filters are capped:** like Night Crawler, a filtered listing returns one page of 50, and an unfiltered one pages up to 300 deep. Search narrows a large Dataset instead of paging through it.
* **Local folder only:** workers on several machines would need the CSVs on shared or object storage, behind the same `AbstractDatasetFileStorage` port.
* **A file renamed after import is a new file.** Its rows come back `unchanged`, so no data changes, but it gets an import of its own.

---

## 7. Deliverables

1. **Source code:** the same layered architecture, tooling, and code of conduct as Night Crawler ([CONTRIBUTING.md](CONTRIBUTING.md)).
2. **Documentation:** this file, [ARCHITECTURE.md](ARCHITECTURE.md), [DOMAIN_MODEL.md](DOMAIN_MODEL.md), and the [README](../README.md).
3. **Web UI:** a Reflex app with Imports, Places, and Events pages.

## 8. Authentication and Abuse Protection

* Logging in, signing up, and passwords are Keycloak's (Night Crawler's
  `night-crawler` realm); the importer keeps no password and issues no
  token. Every API request carries a Keycloak access token.
* Brute-force protection is Keycloak's too: the realm's settings decide
  how failed logins lock an account, and for how long.
* Admins scan the folder and retry imports; every logged-in user browses imports, places, and events.

## 9. User Accounts

* Accounts live in Night Crawler's Keycloak realm, shared with Night
  Crawler; the importer keeps none of its own. Admins manage them
  through `/api/users` (list, view, create, change, disable); nobody
  else can.
* **Disable, never delete:** removing an account disables it. Keycloak
  keeps it and its id, so it can't log in but nothing that names it
  breaks; a disabled account still shows in the list.
* **New accounts are `user`s with a temporary password:** an admin
  sets it, and the user must replace it at their first login. A
  password an admin sets later is temporary too. Only an admin's
  update changes a role.
* **Emails are unique:** creating or changing an account to an email
  already in use is refused (400).
* **There is always an enabled admin:** demoting or disabling the last
  enabled account that holds `admin` is refused (400). A disabled
  admin doesn't count.
* The first admin comes from the realm import, not from the importer.
