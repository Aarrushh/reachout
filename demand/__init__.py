"""The demand workspace.

This file exists for import hygiene, not for code. demand/tests, demand/ingest,
demand/scripts and demand/api all carry an __init__.py; without one here,
pytest's default "prepend" import mode walks up from a test file to the first
parent WITHOUT an __init__.py -- demand/ -- and puts that on sys.path. Every
module underneath then has two importable names (`ingest.trends_client` and
`demand.ingest.trends_client`), which load as two distinct module objects.
Monkeypatching one copy leaves the other holding the real, billed `fetch`.
With this file present pytest inserts the repo root instead, and the
`demand.` path is the only way in.
"""
