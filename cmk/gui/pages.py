#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import abc
import json
import inspect
from typing import Any, Callable, Dict, Mapping, Optional, Text, Type  # pylint: disable=unused-import
import six

import cmk.utils.plugin_registry
from cmk.gui.globals import html
import cmk.gui.config as config
from cmk.utils.exceptions import MKException
from cmk.gui.log import logger

PageHandlerFunc = Callable[[], None]
PageResult = Any
AjaxPageResult = Dict[str, Any]


class Page(six.with_metaclass(abc.ABCMeta, object)):
    #TODO: Use when we are using python3 abc.abstractmethod
    @classmethod
    def ident(cls):
        # type: () -> str
        raise NotImplementedError()

    def handle_page(self):
        # type: () -> None
        self.page()

    @abc.abstractmethod
    def page(self):
        # type: () -> PageResult
        """Override this to implement the page functionality"""
        raise NotImplementedError()


# TODO: Clean up implicit _from_vars() procotocol
class AjaxPage(six.with_metaclass(abc.ABCMeta, Page)):
    """Generic page handler that wraps page() calls into AJAX respones"""
    def __init__(self):
        super(AjaxPage, self).__init__()
        self._from_vars()

    def _from_vars(self):
        # type: () -> None
        """Override this method to set mode specific attributes based on the
        given HTTP variables."""
        pass

    def webapi_request(self):
        # type: () -> Dict[Text, Text]
        return html.get_request()

    @abc.abstractmethod
    def page(self):
        # type: () -> AjaxPageResult
        """Override this to implement the page functionality"""
        raise NotImplementedError()

    def handle_page(self):
        # type: () -> None
        """The page handler, called by the page registry"""
        html.set_output_format("json")
        try:
            action_response = self.page()
            response = {"result_code": 0, "result": action_response}
        except MKException as e:
            response = {"result_code": 1, "result": "%s" % e}

        except Exception as e:
            if config.debug:
                raise
            logger.exception("error calling AJAX page handler")
            response = {"result_code": 1, "result": "%s" % e}

        html.write(json.dumps(response))


class PageRegistry(cmk.utils.plugin_registry.ClassRegistry):
    def plugin_base_class(self):
        # type: () -> Type[Page]
        return Page

    def plugin_name(self, plugin_class):
        # type: (Type[Page]) -> str
        return plugin_class.ident()

    def register_page(self, path):
        # type: (str) -> Callable[[Type[Page]], Type[Page]]
        def wrap(plugin_class):
            # type: (Type[Page]) -> Type[Page]
            if not inspect.isclass(plugin_class):
                raise NotImplementedError()

            # mypy is not happy with this. Find a cleaner way
            plugin_class._ident = path  # type: ignore[attr-defined]
            plugin_class.ident = classmethod(lambda cls: cls._ident)  # type: ignore[assignment]

            self.register(plugin_class)
            return plugin_class

        return wrap


page_registry = PageRegistry()


# TODO: Refactor all call sites to sub classes of Page() and change the
# registration to page_registry.register("path")
def register(path):
    # type: (str) -> Callable[[PageHandlerFunc], PageHandlerFunc]
    """Register a function to be called when the given URL is called.

    In case you need to register some callable like staticmethods or
    classmethods, you will have to use register_page_handler() directly
    because this decorator can not deal with them.

    It is essentially a decorator that calls register_page_handler().
    """
    def wrap(wrapped_callable):
        # type: (PageHandlerFunc) -> PageHandlerFunc
        cls_name = "PageClass%s" % path.title().replace(":", "")
        LegacyPageClass = type(cls_name, (Page,), {
            "_wrapped_callable": (wrapped_callable,),
            "page": lambda self: self._wrapped_callable[0]()
        })

        page_registry.register_page(path)(LegacyPageClass)
        return lambda: LegacyPageClass().handle_page()

    return wrap


# TODO: replace all call sites by directly calling page_registry.register_page("path")
def register_page_handler(path, page_func):
    # type: (str, PageHandlerFunc) -> PageHandlerFunc
    """Register a function to be called when the given URL is called."""
    wrap = register(path)
    return wrap(page_func)


def get_page_handler(name, dflt=None):
    # type: (str, Optional[PageHandlerFunc]) -> Optional[PageHandlerFunc]
    """Returns either the page handler registered for the given name or None

    In case dflt is given it returns dflt instead of None when there is no
    page handler for the requested name."""
    # NOTE: Workaround for our non-generic registries... :-/
    pr = page_registry  # type: Mapping[str, Type[Page]]
    handle_class = pr.get(name)
    if handle_class is None:
        return dflt
    # NOTE: We can'use functools.partial because of https://bugs.python.org/issue3445
    return (lambda hc: lambda: hc().handle_page())(handle_class)
