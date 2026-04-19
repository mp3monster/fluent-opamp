# Copyright 2026 mp3monster.org
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unified consumer entrypoint that routes to the correct runtime implementation.

This module exists so operators can launch one stable command
(`python -m opamp_consumer.client`) without needing to know which concrete
client module to invoke. It parses shared CLI/config options once, resolves
`consumer.service_type`, then dispatches to one of:

- `opamp_consumer.fluentbit_client`
- `opamp_consumer.fluentd_client`
- `opamp_consumer.simulator_client`

In short: this file is a lightweight router, not a full client implementation.
"""

from __future__ import annotations

import argparse

from opamp_consumer import config as consumer_config
from opamp_consumer.client_bootstrap import (
    build_common_cli_parser,
    load_config_from_cli_args,
)
from opamp_consumer.config import (
    SERVICE_TYPE_FLUENTBIT,
    SERVICE_TYPE_FLUENTD,
    SERVICE_TYPE_SIMULATOR,
)


def _parse_args_for_routing() -> argparse.Namespace:
    """Parse shared CLI args once to determine target service implementation."""
    parser = build_common_cli_parser()
    args, _unknown = parser.parse_known_args()
    return args


def main() -> None:
    """Route to the concrete consumer entrypoint selected by `consumer.service_type`."""
    args = _parse_args_for_routing()
    config = load_config_from_cli_args(args)
    consumer_config.set_config(config)
    service_type = str(config.service_type or SERVICE_TYPE_FLUENTBIT).strip().lower()

    if service_type == SERVICE_TYPE_FLUENTBIT:
        from opamp_consumer import fluentbit_client as target_module
    elif service_type == SERVICE_TYPE_FLUENTD:
        from opamp_consumer import fluentd_client as target_module
    elif service_type == SERVICE_TYPE_SIMULATOR:
        from opamp_consumer import simulator_client as target_module
    else:
        raise ValueError(
            "unsupported consumer.service_type "
            f"{service_type!r}; expected one of "
            f"{SERVICE_TYPE_FLUENTBIT}, {SERVICE_TYPE_FLUENTD}, {SERVICE_TYPE_SIMULATOR}"
        )

    if hasattr(target_module, "CONFIG"):
        setattr(target_module, "CONFIG", config)
    target_module.main()
