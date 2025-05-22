# Nethervortex

Nethervortex is a Python library designed for building and managing
sequential and parallel execution flows, particularly useful for
orchestrating tasks and processes. It provides a structured way to
define a series of operations (Nodes) and control their execution
order, including retries and conditional transitions.

Nethervortex is highly inspired by the [PocketFlow](https://github.com/The-Pocket/PocketFlow)
project. The essential
differences are:

1. The Node in NetherVortex is a singleton, allowing node
   connections to be defined directly in module files.
2. Nethervortex replaces `asyncio` with actors for concurrency.
3. The node methods: `prelude`, `dispatch`, and `postlude` now take
   preprocessed arguments from the `shared` data, aiming for a
   clearer interface.

## Installation

Nethervortex can be installed by either directly including the file
in your project or by installing it via pip from the Git repository.

1. **Directly include the file**: Copy `nethervortex.py` into your
    project directory.

2. **Install from GitHub (recommended for packaging)**: You can
    install Nethervortex directly from its GitHub repository using
    pip. This method is recommended if you plan to use it as a
    proper dependency in your project.

    ```bash
    pip install git+https://github.com/Chaos-AI-Projects/nethervortex.git
    ```

3. **Optional: Install for parallel execution**: If you need the
    `ParallelStep` functionality for concurrent task execution,
    you will need to install the `pykka` library. Since `pykka` is an
    optional dependency, you can install Nethervortex with it using
    the `parallel` extra.

    If installing from GitHub, you can specify the extra directly:

    ```bash
    pip install git+https://github.com/Chaos-AI-Projects/nethervortex.git[parallel]
    ```

    If `pykka` is not installed, the `ParallelStep` functionality will
    be disabled, and a warning will be logged.

## Core Concepts

### Node

The `Node` is the fundamental building block in Nethervortex. Each
`Node` represents a distinct step or operation within your flow.

* **`prelude(self, shared, **config)`**: (User-defined) Executed
    before the main `dispatch` logic. It receives the `shared` data.
    The keyword arguments (`**config`) passed to `prelude` are
    automatically populated from the `shared["config"]` section and,
    if `COMP` is defined for the node, from
    `shared["cmpnt"][self.COMP].get("config", {})`. This makes it
    convenient to directly access configuration parameters. For
    example:

    ```python
    def prelude(self, shared, *, some_config_param, another_param, **_):
        # 'some_config_param' and 'another_param' are taken directly
        # from shared["config"] or shared["cmpnt"][self.COMP]["config"]
        # if they exist there.
        print(f"In prelude: {some_config_param}, {another_param}")
        return self.__class__.__name__
    ```

* **`dispatch(self, prelude_res, **config)`**: (User-defined)
    Contains the core logic of the node. It receives the result of
    `prelude` (`prelude_res`). Similar to `prelude`, the `**config`
    keyword arguments are populated from `shared["config"]` and
    `shared["cmpnt"][self.COMP].get("config", {})`. The return value
    of `dispatch` can be used as an action for transitions in a
    `Flow`. For example:

    ```python
    def dispatch(self, prelude_res, *, dispatch_setting, **_):
        # 'dispatch_setting' is taken from shared["config"] or
        # component config.
        print(f"In dispatch, prelude result: {prelude_res}, "
              f"setting: {dispatch_setting}")
        return "next_action" # This can be used for conditional branching
    ```

* **`postlude(self, shared, prelude_res, exec_res, **config)`**:
    (User-defined) Executed after `dispatch`. It receives the `shared`
    data, results from `prelude` (`prelude_res`), and the result from
    `dispatch` (`exec_res`). The `**config` keyword arguments are
    populated in the same way as `prelude` and `dispatch`. For
    example:

    ```python
    def postlude(self, shared, prelude_res, exec_res, *, post_process_flag, **_):
        # 'post_process_flag' is taken from shared["config"] or
        # component config.
        print(f"In postlude: {prelude_res}, {exec_res}, "
              f"flag: {post_process_flag}")
        # Perform any final operations or cleanup
    ```

* **`retry_waits`**: This is a list of integers representing the
    wait times in seconds between retries if an exception occurs
    during the node's execution. You can customize the retry wait time
    for each failure attempt. For instance, `retry_waits=[0, 5, 10]`
    would mean:
  * The first retry happens immediately after the first failure
        (`0` seconds wait).
  * If that retry also fails, the next retry will occur after a
        5-second wait.
  * If it fails again, the final retry will happen after a
        10-second wait.
  * If all retries specified in `retry_waits` are exhausted and
        the operation still fails, the exception will be re-raised.
* **`COMP`**: An optional class attribute (string) that, if
    defined, allows the node to merge its configuration with a
    component-specific configuration found in `shared["cmpnt"]`.
* **Singleton Behavior**: Nodes are singletons, meaning only one
    instance of a given `Node` subclass will be created.

### Flow

The `Flow` class orchestrates the execution of `Node` objects. It
defines the sequence of operations.

* **`start(self, start)`**: Sets the initial `Node` for the flow.
* **`get_next_node(self, curr, action)`**: Determines the next node
    in the flow based on the current node and an `action`. The
    `action` is typically the return value of the `dispatch` method of
    the preceding node.
* **Chaining Nodes**: Nodes can be chained using the `>>` operator
    for default transitions.
* **Conditional Transitions**: Nodes can define conditional
    transitions using the `- "action" >>` syntax, where "action" is a
    string that matches the return value of a preceding node's
    `dispatch` method.

### ParallelStep

The `ParallelStep` class allows for the parallel execution of multiple
`Node` or `Flow` instances. It leverages `pykka` for actor-based
concurrency.

* **`__getitem__(self, tasks)`**: Defines the tasks (Nodes or
    Flows) to be executed in parallel.
* **Execution**: Each task is run in a separate `PSlot` (a Pykka
    actor). The tasks are executed concurrently, and the result of the
    first task is returned.

### SharedData

A `TypedDict` used to pass data throughout the flow. It has the
following keys:

* **`config`**: A dictionary for general configuration.
* **`cmpnt`**: A dictionary to hold component-specific data and
    configurations.
* **`state`**: A field to store the current state or the name of
    the currently executing node.

## Usage Examples

Let's illustrate the concepts with examples from `test_nethervortex.py`.

### Defining Nodes

```python
import time
from nethervortex import Node, Flow, ParallelStep, SharedData

class ANode(Node):
    COMP="D" # This node is associated with component "D"
    def prelude(self, shared, *, arg1, **_):
        print(self.__class__.__name__, arg1)
        return self.__class__.__name__

    def dispatch(self, prelude_res, *, arg1, arg2, **_):
        print(f"in dispatch, {arg1}, {arg2}")

    def postlude(self, shared, prep_res, exec_res,*, arg2, **_):
        print(prep_res, arg2)

class BNode(Node):
    def prelude(self, shared, **_):
        print(self.__class__.__name__)
        return self.__class__.__name__

    def postlude(self, shared, prep_res, exec_res, **_):
        time.sleep(3) # Simulates a long-running task
        print(prep_res, "sleep 3")


class CNode(Node):
    def prelude(self, shared, **_):
        print(self.__class__.__name__)
        return self.__class__.__name__

    def postlude(self, shared, prep_res, exec_res, **_):
        time.sleep(1) # Simulates a shorter task
        print(prep_res, "sleep 1")

class DNode(Node):
    COMP="D"
    def prelude(self, shared, **_):
        print(self.__class__.__name__)
        return self.__class__.__name__

    def postlude(self, shared, prep_res, exec_res, **_):

        d = shared["cmpnt"][self.COMP].get("data_d", 0)
        if d > 1:
            print(prep_res, "finish")
            return "finish" # Returns "finish" to trigger a specific transition
        print(prep_res, "data_d", d)
        shared["cmpnt"][self.COMP]["data_d"] = d+1 # Modifies shared data
        return "again" # Returns "again" to trigger a loop
```

### Building a Flow with Parallel Execution and Conditional Transitions

```python
# Instantiate nodes
anode=ANode()
bnode=BNode()
cnode=CNode()
dnode=DNode()


# Define a parallel step with CNode and BNode
p = ParallelStep()[cnode, bnode]

# Define the flow sequence: ANode -> ParallelStep -> DNode
anode >> p >> dnode

# Define a conditional transition: if DNode returns "again", go back to ANode
dnode - "again" >> anode

# Initialize the Flow with the starting node
f = Flow(start=anode)

# Prepare shared data, including initial configuration and
# component-specific data
res = f.run(shared=SharedData(config={"arg1": "arg1_v"},
                               cmpnt={"D":{"config": {"arg2":"arg2_v"}}},
                               state=None))

# Print the final result of the flow
print(res)
```

---
*This README and the accompanying documentation were generated by
Gemini, with human guidance.*
