# Bruno collection

Requests for the Data Reaper API, for [Bruno](https://www.usebruno.com/).

## Setup

1. Open this `bruno/` folder as a collection in Bruno.
2. Select the `local` environment. `adminEmail` and `adminPassword` come
   from the seeded admin in the repo's `.env` (`ADMIN_SEED_EMAIL` /
   `ADMIN_SEED_PASSWORD`): `bruno/.env` is a symlink to it, and Bruno
   reads it through `{{process.env.…}}`.
3. Start the stack (`make up`).

Run each folder with the Collection Runner, in order. Requests pass ids
and tokens to each other through environment variables
(`bru.setEnvVar`).

## Auth

The bearer auth lives once, in `collection.bru`: `Bearer {{token}}`.
Every request inherits it (`auth: inherit`, through its folder), except
login and register, which send none. Each folder starts by logging in as
the admin, which stores the session token in `token`. To send a single
request by hand, run a login request first. `token` is a secret
environment variable, so Bruno keeps it locally and it never lands in
`environments/local.bru`.

From the command line:

```bash
cd bruno
npx @usebruno/cli run users --env local
npx @usebruno/cli run imports --env local
```

## `users/`

Logs in as the admin, registers Ana (public), creates Bernat, Carla and
David (admin only), makes Carla an admin and David a viewer, lists the
users, and finishes by logging in as Ana. Emails get a per-run suffix,
so the folder can run again.

## `imports/`

Logs in as the admin, scans the CSV folder (new files are queued; a
second run finds none), lists the imports and keeps the newest one's id,
gets that import, lists the failed ones, then reads the data: both
Datasets with their record counts, TheFork places matching "grill", and
the first page of events.
