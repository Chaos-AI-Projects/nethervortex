"""Tests for the nethervortex library components."""

import logging
import time

import pytest

from nethervortex import Node, Flow, ParallelStep, SharedData

# Configure logging to capture output for assertions
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ANode(Node):
    """A sample Node for testing purposes."""
    COMP = "D"

    # pylint: disable=W0613
    def prelude(self, shared, *, arg1, **_):
        """Executes before dispatch."""
        logger.info("ANode prelude: arg1=%s", arg1)
        return self.__class__.__name__

    # pylint: disable=W0613
    def dispatch(self, prelude_res, *, arg1, arg2, **_):
        """Contains the core logic for ANode."""
        logger.info("ANode dispatch: arg1=%s, arg2=%s", arg1, arg2)
        return "default"  # Ensure a default action for general flow

    # pylint: disable=W0613
    def postlude(self, shared, prep_res, exec_res, *, arg2, **_):
        """Executes after dispatch."""
        logger.info("ANode postlude: prep_res=%s, arg2=%s",
                    prep_res, arg2)
        # This method implicitly returns None, which is then returned by
        # Node.run


class BNode(Node):
    """A sample Node for testing purposes."""

    # pylint: disable=W0613
    def prelude(self, shared, **_):
        """Executes before dispatch."""
        logger.info("BNode prelude")
        return self.__class__.__name__

    # pylint: disable=W0613
    def postlude(self, shared, prep_res, exec_res, **_):
        """Executes after dispatch."""
        time.sleep(0.1)  # Shorter sleep for faster tests
        logger.info("BNode postlude: %s, sleep 0.1", prep_res)


class CNode(Node):
    """A sample Node for testing purposes."""

    # pylint: disable=W0613
    def prelude(self, shared, **_):
        """Executes before dispatch."""
        logger.info("CNode prelude")
        return self.__class__.__name__

    # pylint: disable=W0613
    def postlude(self, shared, prep_res, exec_res, **_):
        """Executes after dispatch."""
        time.sleep(0.05)  # Shorter sleep for faster tests
        logger.info("CNode postlude: %s, sleep 0.05", prep_res)


class DNode(Node):
    """A sample Node for testing purposes, includes looping logic."""
    COMP = "D"

    # pylint: disable=W0613
    def prelude(self, shared, **_):
        """Executes before dispatch."""
        logger.info("DNode prelude")
        return self.__class__.__name__

    # pylint: disable=W0613
    def postlude(self, shared, prep_res, exec_res, **_):
        """Executes after dispatch, contains looping logic."""
        d = shared["cmpnt"][self.COMP].get("data_d", 0)
        logger.info("DNode postlude: data_d=%s", d)
        if d > 1:
            logger.info("DNode postlude: finish")
            return "finish"
        logger.info("DNode postlude: data_d=%s", d)
        shared["cmpnt"][self.COMP]["data_d"] = d + 1
        return "again"


# --- Move FailingNode and AlwaysFailingNode to module level ---
class FailingNode(Node):
    """A node that fails a specified number of times."""
    call_count = 0
    _node_retry_waits = [0.05, 0.1]

    # pylint: disable=W0613
    def dispatch(self, prelude_res, **_):
        """Simulates failing and then succeeding."""
        FailingNode.call_count += 1
        logger.info("FailingNode dispatch call_count: %s",
                    FailingNode.call_count)
        if FailingNode.call_count <= 2:  # Fail twice, succeed on third
            raise ValueError("Simulated failure")
        return "success"

    # Add a postlude method to return the exec_res (dispatch result)
    # pylint: disable=W0613
    def postlude(self, shared, prep_res, exec_res, **_):
        """Returns the execution result to confirm dispatch success."""
        logger.info("FailingNode postlude: exec_res=%s", exec_res)
        return exec_res


class AlwaysFailingNode(Node):
    """A node that always fails."""
    call_count = 0
    _node_retry_waits = [0.05]

    # pylint: disable=W0613
    def dispatch(self, prelude_res, **_):
        """Always raises an error."""
        AlwaysFailingNode.call_count += 1
        logger.info("AlwaysFailingNode dispatch call_count: %s",
                    AlwaysFailingNode.call_count)
        raise ValueError("Always failing")

    # Add a postlude method, even though it will not be reached in this
    # specific test
    # pylint: disable=W0613
    def postlude(self, shared, prep_res, exec_res, **_):
        logger.info("AlwaysFailingNode postlude "
                    "(should not be reached in failure scenario).")
        return exec_res  # Or None, as it won't be called


# pylint: disable=W0621
@pytest.fixture
def capture_logs(caplog):
    """Fixture to capture log output."""
    caplog.set_level(logging.INFO)  # Capture INFO level messages and above
    return caplog

@pytest.fixture(autouse=True)
def reset_all_node_singletons():
    """Fixture to reset singleton instances and call_counts for all Node
    classes.
    """
    for node_class in [ANode, BNode, CNode, DNode,
                       FailingNode, AlwaysFailingNode]:
        # pylint: disable=W0212
        if hasattr(node_class, "_instance"):
            node_class._instance = None

        if hasattr(node_class, "call_count"):
            node_class.call_count = 0


# pylint: disable=W0621
def test_single_node_execution(capture_logs):
    """Test the execution of a single node."""
    node = ANode()
    initial_shared = SharedData(
        config={"arg1": "test_arg1"},
        cmpnt={"D": {"config": {"arg2": "test_arg2"}}},
        state=None
    )

    result = node.run(shared=initial_shared)

    assert "ANode prelude: arg1=test_arg1" in capture_logs.text
    assert ("ANode dispatch: arg1=test_arg1, arg2=test_arg2"
            in capture_logs.text)
    assert ("ANode postlude: prep_res=ANode, arg2=test_arg2"
            in capture_logs.text)
    assert result is None


# pylint: disable=W0621
def test_flow_execution_with_loop(capture_logs):
    """
    Tests the full flow including parallel steps, conditional branching,
    and shared data modification.
    """
    anode = ANode()
    bnode = BNode()
    cnode = CNode()
    dnode = DNode()

    # Define the flow
    # pylint: disable=W0104
    p = ParallelStep()[cnode, bnode]
    anode >> p
    p >> dnode
    dnode - "again" >> anode

    flow = Flow(start=anode)

    initial_shared_data = SharedData(
        config={"arg1": "arg1_v"},
        cmpnt={"D": {"config": {"arg2": "arg2_v", "data_d": 0}}},
        state=None
    )

    final_action = flow.run(shared=initial_shared_data)

    # Assertions for the flow's execution path and final state
    assert final_action == "finish"
    assert "ANode prelude: arg1=arg1_v" in capture_logs.text
    assert ("ANode dispatch: arg1=arg1_v, arg2=arg2_v"
            in capture_logs.text)
    assert "BNode prelude" in capture_logs.text
    assert "CNode prelude" in capture_logs.text
    assert "DNode prelude" in capture_logs.text

    # Verify the looping behavior of DNode
    # First pass: DNode returns "again"
    assert "DNode postlude: data_d=0" in capture_logs.text
    assert "DNode postlude: data_d=1" in capture_logs.text
    # Second pass: DNode returns "again"
    assert "DNode postlude: data_d=1" in capture_logs.text
    assert "DNode postlude: data_d=2" in capture_logs.text
    # Third pass: DNode returns "finish"
    assert "DNode postlude: finish" in capture_logs.text


# pylint: disable=W0621
def test_parallel_step_order_and_completion(capture_logs):
    """
    Tests that parallel steps complete and their results are handled.
    Note: The order of parallel execution output is not guaranteed by
    Python's threading, but both should execute.
    """
    anode = ANode()
    bnode = BNode()
    cnode = CNode()

    # Create a simple flow with a parallel step
    # pylint: disable=W0106
    anode >> ParallelStep()[cnode, bnode]

    flow = Flow(start=anode)
    initial_shared_data = SharedData(
        config={"arg1": "test_parallel_arg1"},
        cmpnt={"D": {"config": {"arg2": "parallel_arg2"}}},
        state=None
    )
    flow.run(shared=initial_shared_data)

    # Assert that both parallel nodes were processed
    assert "CNode prelude" in capture_logs.text
    assert "BNode prelude" in capture_logs.text
    assert "CNode postlude" in capture_logs.text
    assert "BNode postlude" in capture_logs.text


def test_node_retry_logic():
    """Tests the retry mechanism of a node."""
    FailingNode.call_count = 0

    # pylint: disable=W0212
    failing_node = FailingNode(retry_waits=FailingNode._node_retry_waits)
    initial_shared = SharedData(config={}, cmpnt={}, state=None)

    result = failing_node.run(shared=initial_shared)

    assert result == "success"
    assert FailingNode.call_count == 3


def test_node_retry_exhaustion():
    """Tests that an exception is re-raised when retries are exhausted."""
    AlwaysFailingNode.call_count = 0

    # pylint: disable=W0212
    always_failing_node = AlwaysFailingNode(
        retry_waits=AlwaysFailingNode._node_retry_waits)
    initial_shared = SharedData(config={}, cmpnt={}, state=None)

    with pytest.raises(ValueError, match="Always failing"):
        always_failing_node.run(shared=initial_shared)

    assert AlwaysFailingNode.call_count == 2
