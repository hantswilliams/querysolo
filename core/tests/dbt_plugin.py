# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""The step 2 spike's plugin lives in the package since the real-data round (R5):
``querysolo.dbt.plugin``. This module stays so the spike's and step 6's profiles resolve."""

from querysolo.dbt.plugin import Plugin

__all__ = ["Plugin"]
