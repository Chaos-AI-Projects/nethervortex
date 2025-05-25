# Nethervortex

**Note: Nethervortex requires Python 3.11+ due to its use of features
like `typing.Required`.**

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
    pip install git+https://github.com/Chaos-AI-Projects/nethervortex.git#egg=nethervortex[parallel]
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

A `TypedDict` used to pass data throughout the flow. As of the latest
version of `nethervortex.py`:

* **`config: Required[dict]`**: A dictionary for general configuration. This
  field is mandatory.
* **`cmpnt: dict`**: A dictionary to hold component-specific data and
  configurations. This field is optional.
* **`state: Any`**: A field to store the current state or the name of
  the currently executing node. This field is optional.

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

### Showcase: Iterative LLM Flow (`llm_flow_showcase.py`)

The `llm_flow_showcase.py` script, located in the root of the repository,
demonstrates a more advanced, iterative flow where simulated Language Models
(LLMs) interact in a loop to achieve a goal. This showcase highlights
several key features and idiomatic uses of the Nethervortex library.

#### Purpose

The primary purpose of this showcase is to illustrate:
- An iterative multi-step process involving LLM interactions.
- Component-based data management within `SharedData`.
- Configuration injection for clients and templates.
- Conditional looping and termination based on node outcomes.
- Error handling within nodes (e.g., missing data via `ValueError`).

#### Flow Overview

The flow simulates an iterative process of generating and assessing text:

1.  **`PromptGenerationNode`**:
    *   Retrieves a `problem_definition` (e.g., "Write a poem about a cat")
        from `shared_data["cmpnt"]["LLM_ITERATOR"]`.
    *   Increments a `round_count` within the same component data.
    *   Uses a `gemma_prompt_generation_template` (passed as config) and the
        `problem_definition` to construct a prompt for a Gemini model.
    *   In its `dispatch` method, calls a (placeholder) `GeminiClient`
        (passed as config) to generate a prompt suitable for a Gemma model.
    *   Saves the generated Gemma prompt to
        `shared_data["cmpnt"]["LLM_ITERATOR"]["current_gemma_prompt"]`.

2.  **`GemmaEvaluationNode`**:
    *   Retrieves the `current_gemma_prompt`.
    *   In its `dispatch` method, calls a (placeholder) `OllamaClient`
        (passed as config) to simulate Gemma processing the prompt and
        producing a response.
    *   Saves Gemma's response to
        `shared_data["cmpnt"]["LLM_ITERATOR"]["current_gemma_response"]`.

3.  **`AssessmentNode`**:
    *   Retrieves `current_gemma_response` and the original
        `problem_definition`.
    *   Constructs a prompt for Gemini using an `assessment_prompt_template`
        (passed as config) to ask if Gemma's response satisfies the
        problem definition.
    *   In its `dispatch` method, calls the `GeminiClient` (passed as config)
        to get an assessment (e.g., "YES" or "NO").
    *   Its `postlude` method checks this assessment and the `round_count`:
        - If "YES": transitions to `satisfied_end_flow`.
        - If "NO" and `round_count` < 5: transitions to `unsatisfied_loop_back`
          (back to `PromptGenerationNode`).
        - If "NO" and `round_count` >= 5: transitions to `max_rounds_end_flow`.
        - Handles errors (e.g., missing API key for Gemini) by transitioning
          to `assessment_failed_end_flow`.

4.  **`FlowEndNode`**:
    *   A terminal node that logs the final state, such as the total rounds
        attempted and the last Gemma response.

#### Nethervortex Concepts Demonstrated

This showcase illustrates several important Nethervortex concepts:

-   **Node Definition**: Clear separation of concerns into `prelude`,
    `dispatch`, and `postlude` methods for each logical step.
-   **Component-Based Data Management**: Nodes use `COMP = "LLM_ITERATOR"`
    to store and retrieve data within a dedicated namespace
    (`shared_data["cmpnt"]["LLM_ITERATOR"]`), keeping shared data organized.
-   **Configuration Injection**:
    -   Client instances (`GeminiClient`, `OllamaClient`) are instantiated
        once and passed globally via `shared_data["config"]`. Nodes receive
        these clients as named keyword arguments in their `dispatch` (or
        `prelude`) methods where needed.
    -   Prompt templates (`gemma_prompt_generation_template`,
        `assessment_prompt_template`) are stored in
        `shared_data["cmpnt"]["LLM_ITERATOR"]["config"]` and are also passed
        as named keyword arguments to the relevant node methods.
-   **Conditional Transitions & Looping**: The `AssessmentNode` demonstrates
    conditional branching based on its `dispatch` result, creating a loop
    back to `PromptGenerationNode` or proceeding to `FlowEndNode`.
-   **Error Handling**: `prelude` methods in nodes like `PromptGenerationNode`
    and `GemmaEvaluationNode` raise `ValueError` for critical missing data,
    which would typically halt the flow unless caught by a higher-level
    error handling mechanism in the `Flow` (not explicitly shown in this
    showcase's `Flow` runner, but a capability of robust Nethervortex usage).
    `AssessmentNode` also demonstrates returning specific error actions.
-   **Idiomatic Data Flow**: Nodes primarily return `(action_string, payload)`
    from `dispatch`, and `postlude` is responsible for persisting the
    `payload` to `shared_data` and returning the `action_string` for flow
    control. `prelude` returns only the data `dispatch` needs.

#### How to Run

1.  **Environment Setup**:
    *   **Nethervortex requires Python 3.11+**. Ensure your environment
        meets this requirement.
    *   The `llm_flow_showcase.py` script itself does not add further
        dependencies beyond standard Python libraries and what Nethervortex
        might require (e.g., `pykka` if `ParallelStep` were used, though it's
        not in this specific showcase).

2.  **Set Environment Variable (Important for AssessmentNode)**:
    The `AssessmentNode` requires a `GEMINI_API_KEY` to simulate making an
    assessment call. While the `GeminiClient` is a placeholder, the node's
    logic checks for the presence of this key in the client instance.
    To run the showcase through all potential paths, including successful
    assessment (simulated), set the environment variable:
    ```bash
    export GEMINI_API_KEY="your_dummy_or_actual_api_key"
    ```
    If this key is not set, the `GeminiClient` instance will have `api_key=None`.
    `PromptGenerationNode`'s `dispatch` will use the placeholder's no-key
    fallback. `AssessmentNode`'s `dispatch` will detect the missing key on its
    `gemini_client` argument and return an `"assessment_error_missing_key"`
    action, leading to the `assessment_failed_end_flow` path.

3.  **Execute the Script**:
    Navigate to the root directory of the repository and run:
    ```bash
    python llm_flow_showcase.py
    ```

#### Placeholder Clients

It's crucial to understand that `OllamaClient` and `GeminiClient` in this
script are **placeholders**. They simulate responses and do not make actual
API calls. For real-world use, these would need to be replaced with
implementations that interact with the actual Ollama and Gemini services.

#### Expected Output

The script produces console logs detailing the flow's execution. While
highly verbose entry/exit logs for every single `prelude`, `dispatch`, and
`postlude` method have been reduced for clarity, you will still see key
operational logs, including:
- Initialization messages and client readiness (e.g., Gemini client warnings
  if an API key is not provided).
- `PromptGenerationNode`: Round progression (e.g., "Round: 1/5"),
  constructed prompts for Gemini, and the resulting Gemma prompt from Gemini.
- `GemmaEvaluationNode`: The Gemma prompt being sent to Ollama, and the
  simulated response from Ollama.
- `AssessmentNode`: The constructed assessment prompt for Gemini, the
  assessment result ("YES"/"NO") from Gemini, and the decision logic based
  on the assessment and round count (e.g., "Assessment is NO. Problem not
  satisfied...", "Max rounds not reached... Looping back.", or "Problem
  satisfied...").
- `FlowEndNode`: A summary message including total rounds attempted and the
  final Gemma response for the problem.
- Overall flow start and end messages, including the final action that
  terminated the flow and the final state of the `LLM_ITERATOR` component
  in `shared_data`.

The logs provide a clear trace of the iterative process, key data being
generated and passed, and how conditional logic directs the flow.
For example, if `GEMINI_API_KEY` is not set, you should expect the
`AssessmentNode` to log an error about the missing key and the flow to
terminate via the `assessment_failed_end_flow` path. If the key is set,
the flow will loop 5 times (as the placeholders currently always result in a "NO"
assessment) and then terminate via `max_rounds_end_flow`.

---
*This README and the accompanying documentation were generated by
Gemini, with human guidance.*
