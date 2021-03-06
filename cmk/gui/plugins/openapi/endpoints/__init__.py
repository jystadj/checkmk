#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from cmk.gui.plugins.openapi.endpoints import (
    folder,
    host,
    host_group,
    version,
    contact_group,
    service_group,
)

__all__ = ['folder', 'host', 'host_group', 'version', 'contact_group', 'service_group']
