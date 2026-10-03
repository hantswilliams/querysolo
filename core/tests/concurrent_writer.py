# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""One writer process for the concurrency test: its own embedded catalog on the shared
SQLite file (brief D3), N appends through pyiceberg, retry on a 409 by reloading."""

import sys

import pyarrow as pa
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.exceptions import CommitFailedException

from querysolo.catalog import EmbeddedCatalog, Store, create_app


def main(store_url: str, warehouse: str, writer: int, commits: int) -> None:
    server = EmbeddedCatalog(create_app(Store(store_url), warehouse=warehouse))
    url = server.start()
    cat = RestCatalog("querysolo", uri=url)
    retries = 0
    for i in range(commits):
        while True:
            try:
                cat.load_table("main.t").append(pa.table({"writer": [writer], "i": [i]}))
                break
            except CommitFailedException:
                retries += 1
    server.stop()
    print(retries)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
