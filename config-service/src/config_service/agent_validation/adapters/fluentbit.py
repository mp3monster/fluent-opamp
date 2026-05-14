#!/usr/bin/env python3
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

from __future__ import annotations
import logging

from config_service.agent_validation.adapters.base import TemplateCommandAdapter

FLB_VER_LABEL = "Fluent Bit v"

FILTER_LINE_PREFIXES = ("*", "|", "___", "\\_", "Celebrating",
                        "* Copyright ", "* Fluent Bit is")

FILTER_LINE_CONTAINS = ("Direct Routes Ahead")

logger = logging.getLogger(__name__)


class FluentBitValidationAdapter(TemplateCommandAdapter):
    """Fluent Bit command and output behavior wrapper."""

    def interpret_result(self, result_text: str) -> dict[str, object]:
        parsed = super().interpret_result(result_text)
        messages = parsed.get("messages", [])
        filtered_messages = []
        try:
            for message in messages:
                text = str(message).lstrip()
                logger.debug ("Inspecting output Line>>%s", text)
                if any(text.startswith(prefix) for prefix in FILTER_LINE_PREFIXES):
                    continue
                if any(contained not in text for contained in FILTER_LINE_CONTAINS):
                    continue
                if text.startswith("Fluent Bit v") and ("used_version" not in parsed):
                    parsed["used_version"] = text[len(FLB_VER_LABEL): ] 
                    logger.debug("VERSION >%s< taken from >%s<", parsed["used_version"], text)
                    continue
                    
                filtered_messages.append(str(message))
        except Exception as err:
            logger.error("Caught while trying to process FluentBit output:\n%s", err)
            filtered_messages = messages

        parsed["messages"] = filtered_messages
        has_error = any("[error]" in str(message).lower() for message in filtered_messages)
        parsed["ok"] = not has_error
        
        logger.debug (parsed)
        return parsed
