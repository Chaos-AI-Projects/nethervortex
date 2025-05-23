# MIT License
#
# Copyright (c) 2025 Jun Sheng (Aka Chaos Eternal)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""NetherVortex ultra-light pipeline for building Agents.
"""
import logging
import time
from typing import Any, TypedDict
from typing_extensions import Required

logger = logging.getLogger(__name__)

class SharedData(TypedDict):
    config: Required[dict]
    # Reverting cmpnt and state to be not strictly Required for broader compatibility
    # as the showcase SharedData initialization does not include them as Required.
    # The strictness was added for a 3.11+ target, but compatibility is key now.
    cmpnt: dict 
    state: Any

class _Singleton(object):
    _instance = None

    # pylint: disable=W0613
    def __new__(class_, *args, **kwargs):
        if not isinstance(class_._instance, class_):
            class_._instance = object.__new__(class_)
        return class_._instance

class BaseNode():
    """The base class for Node and Flow.
    """

    def __init__(self):
        self.successors = {}

    def next(self, target, action="default"):
        if action in self.successors:
            logger.warning(
                "Overloading existing successor for action '%s'",
                action
            )
        self.successors[action] = target
        return target

    # pylint: disable=W0613
    def _prep(self, shared):
        return None

    # pylint: disable=W0613
    def _exec1(self, prep_res):
        return None

    # pylint: disable=W0613
    def _post(self, shared, prep_res, exec_res):
        return None

    def _run(self, shared):
    # pylint: disable=E1128
        t0 = self._prep(shared)
        t1 = self._exec1(t0)
        t2 = self._post(shared, t0, t1)
        return t2

    def run(self, shared: SharedData):
        if self.successors:
            logger.warning("Successors are ignored in Node.run. Use Flow.")
        return self._run(shared)

    def __rshift__(self, other):
        return self.next(other)

    def __sub__(self, action):
        if isinstance(action,str):
            return _TransHelper(self, action)
        raise TypeError("Action must be a string")

class _TransHelper:
    def __init__(self, src, action):
        self.src, self.action = src, action

    def __rshift__(self, target):
        return self.src.next(target, self.action)

class Node(_Singleton, BaseNode):
    """The Node class is the main place to put the logic."""

    _initialized: bool = False

    def __init__(self, retry_waits=None):
        if not self._initialized:
            super().__init__()
            if retry_waits:
                self.retry_waits = retry_waits
            else:
                self.retry_waits = [0]
            self._initialized = True

    def _prep(self, shared):
        cfg = dict(**shared["config"])
        if (hasattr(self, "COMP") and
            self.COMP in shared["cmpnt"]):
            cfg |= shared["cmpnt"][self.COMP].get("config", {})
        if hasattr(self, "prelude"):
            return self.prelude(shared, **cfg), cfg
        return None, cfg

    def _exec(self, prep_res):
        prelude_res, cfg = prep_res
        if hasattr(self, "dispatch"):
            return self.dispatch(prelude_res, **cfg)
        else:
            return None

    def _post(self, shared, prep_res, exec_res):
        prelude_res, cfg = prep_res

        if hasattr(self, "postlude"):
            return self.postlude(shared, prelude_res, exec_res, **cfg)
        else:
            return None

    def _exec_fallback(self,
                      prep_res,
                      exc):
        raise exc

    def _exec1(self, prep_res):
        waits = [i for i in self.retry_waits]
        while True:
            try:
                return self._exec(prep_res)

            # pylint: disable=W0718
            except Exception as exp:
                if waits:
                    w = waits.pop(0)
                    time.sleep(w)
                else:
                    return self._exec_fallback(prep_res, exp)

    def _run(self, shared):
        shared["state"] = self.__class__.__name__
        return super()._run(shared)

class Flow(BaseNode):
    """Flow class is the engine to run the pipeline."""

    def __init__(self, start=None):
        super().__init__()
        self.start_node = start

    def start(self, start):
        self.start_node = start
        return start

    def get_next_node(self, curr, action):
        cadr = curr.successors.get(action if action else "default")
        if not cadr and curr.successors:
            logger.debug(
                "Flow ends: '%s' not found in %s"
                ,action
                ,list(curr.successors)
            )
        return cadr

    def _loop(self, shared):
        curr, last_action =self.start_node, None
        while curr:
            logger.debug("run node %s", curr.__class__.__name__)

            # pylint: disable=W0212
            last_action = curr._run(shared)
            logger.debug(
                "node %s result: %s",
                curr.__class__.__name__,
                last_action
            )
            curr = self.get_next_node(curr, last_action)

        return last_action

    def _run(self, shared):
        # pylint: disable=E1128
        t0 = self._prep(shared)
        t1 = self._loop(shared)
        return self._post(shared, t0, t1)

    def _post(self, shared, prep_res, exec_res):
        return exec_res


try:
    import pykka

    class PSlot(pykka.ThreadingActor):
        def __init__(self, shared):
            super().__init__()
            self._shared = shared

        def on_receive(self, flow):
            return flow.run(shared=self._shared)

    class ParallelStep(BaseNode):
        """The ParallelStep run the nodes in threads via actors.
        """

        def __init__(self):
            super().__init__()
            self._tasks = ()

        def __getitem__(self, tasks):
            if (isinstance(tasks, Node) or
                isinstance(tasks, Flow)):
                self._tasks = (tasks,)
            else:
                self._tasks = tuple(x for x in tasks)
            return self

        def _prep(self, shared):
            return [PSlot.start(shared) for _ in self._tasks]

        def _post(self, shared, prep_res, exec_res):
            futures = [p.ask(f, block=False)
                       for (p, f) in zip(prep_res, self._tasks)]
            results = [f.get() for f in futures]

            for s in prep_res:
                s.stop()
            return results[0]

except ImportError:
    logger.warning("Install Pykka to enable ParallelStep.")
