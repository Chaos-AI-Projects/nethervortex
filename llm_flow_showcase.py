"""Showcase for a multi-step LLM interaction flow using Nethervortex.

This script demonstrates a pipeline involving:
1.  Generating a prompt for a Gemma model using a Gemini model (PromptGenerationNode).
2.  Evaluating the Gemma model's output using a placeholder Ollama client (GemmaEvaluationNode).
3.  Assessing Gemma's response against the original problem using Gemini (AssessmentNode).
The flow includes logic for iteration and round counting.
"""

import os
import logging
from nethervortex import Node, Flow, SharedData # ParallelStep not used in this version

# Basic logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)

# --- Placeholder for external services ---
class OllamaClient:
    """A placeholder for the Ollama client to simulate Gemma responses."""
    def run(self, prompt: str) -> str:
        """Simulates running a prompt through Gemma via Ollama.
        
        Args:
            prompt: The prompt to send to Gemma.

        Returns:
            A simulated response string from Gemma.
        """
        logging.info("OLLAMA_CLIENT: Received prompt: %s", prompt)
        if "poem about a cat" in prompt.lower():
            return "Upon a mat, a cat once sat, purring soft, a furry plat."
        if "code for factorial" in prompt.lower():
            return "def factorial(n): return 1 if n == 0 else n * factorial(n-1)"
        return "Gemma's default placeholder response."

class GeminiClient:
    """A placeholder for the Gemini client."""
    def __init__(self, api_key: str | None):
        """Initializes the GeminiClient.

        Args:
            api_key: The API key for the Gemini service.

        Raises:
            ValueError: If the API key is not provided (and a real client
                        would require it). Placeholder allows None for some cases.
        """
        # The subtask requires raising ValueError if api_key is None for AssessmentNode.
        # For PromptGenerationNode, the template allows proceeding without a key
        # to let the placeholder return a generic Gemma prompt.
        # This dual behavior is tricky. For now, the node using the client
        # will be responsible for ensuring the key is present if strictly needed by that node.
        if api_key is None:
            logging.warning(
                "GeminiClient initialized without API key. "
                "Functionality will be limited to placeholder responses."
            )
        self.api_key = api_key
        logging.info("GeminiClient initialized.")

    def generate_content(self, prompt_for_gemini: str) -> str:
        """Simulates content generation by Gemini.
        
        Args:
            prompt_for_gemini: The prompt to send to Gemini.

        Returns:
            A simulated response string from Gemini.
        """
        logging.info("GEMINI_CLIENT: Received prompt: %s", prompt_for_gemini)
        if "generate a gemma prompt" in prompt_for_gemini.lower():
            if "poem about a cat" in prompt_for_gemini.lower():
                return "Generate a short poem about a happy cat."
            if "factorial function" in prompt_for_gemini.lower():
                return "Write a Python function to calculate factorial."
            # Fallback for generic gemma prompt generation if API key might be missing
            if not self.api_key:
                return "Generic prompt for Gemma (API key not found for specific generation)."
        elif "does the following text" in prompt_for_gemini.lower(): # For Node 3
            if "purring soft" in prompt_for_gemini:
                return "YES"
            if "factorial(n-1)" in prompt_for_gemini:
                return "YES"
            return "NO"
        return "Gemini's default content generation response."

# --- End Placeholder ---

class PromptGenerationNode(Node):
    """
    Node 1: Generates a prompt for a target LLM (Gemma) using an LLM
    (Gemini).
    It manages iteration rounds and constructs prompts based on templates.
    The Gemini call is made in `dispatch`.
    """
    COMP = "LLM_ITERATOR"

    def prelude(self, shared_data: SharedData, *,
                gemma_prompt_generation_template: str, **_config_kwargs):
        """
        Prepares for Gemma prompt generation.

        Retrieves problem definition, manages round count, and constructs
        the prompt string for Gemini (which will generate the Gemma prompt).

        Args:
            shared_data: The shared data object for the flow.
            gemma_prompt_generation_template: A template string for
                generating the prompt for Gemini.
            _config_kwargs: Catch-all for other config parameters from
                Nethervortex.

        Returns:
            A tuple (action_string, payload).
            `action_string` indicates status ("proceed_to_dispatch",
            "MAX_ROUNDS_REACHED", or "error_missing_problem_def").
            `payload` is the constructed prompt string for Gemini or None.
        """
        class_name = self.__class__.__name__
        logging.info("%s (Component: %s): Starting prelude.",
                     class_name, self.COMP)

        problem_definition = shared_data["cmpnt"][self.COMP].get(
            "problem_definition"
        )
        if not problem_definition:
            logging.error(
                "%s: Problem definition not found in "
                "shared_data[\"cmpnt\"][\"%s\"].",
                class_name, self.COMP
            )
            return "error_missing_problem_def", None

        round_count = shared_data["cmpnt"][self.COMP].get("round_count", 0) + 1
        shared_data["cmpnt"][self.COMP]["round_count"] = round_count
        logging.info("Round: %s/5 for component %s", round_count, self.COMP)

        if round_count > 5:
            logging.warning("%s: Max rounds reached for component %s.",
                            class_name, self.COMP)
            return "MAX_ROUNDS_REACHED", None

        prompt_for_gemini = gemma_prompt_generation_template.format(
            problem_definition=problem_definition
        )
        logging.info("%s: Constructed prompt for Gemini: %s",
                     class_name, prompt_for_gemini)

        return "proceed_to_dispatch", prompt_for_gemini

    def dispatch(self, prelude_res, *, gemini_client: GeminiClient,
                 **_config_kwargs):
        """
        Generates the Gemma prompt using Gemini.

        Receives the prompt string for Gemini from `prelude_res` and
        calls the Gemini client.

        Args:
            prelude_res: The tuple (action, prompt_for_gemini) from
                `prelude`.
            gemini_client: An instance of GeminiClient, passed via config.
            _config_kwargs: Catch-all for other config parameters from
                Nethervortex.

        Returns:
            A tuple (action_string, payload).
            `action_string` indicates status ("prompt_generated",
            "max_rounds_exceeded", or "error_problem_def_missing").
            `payload` is the generated Gemma prompt or None.
        """
        class_name = self.__class__.__name__
        action_from_prelude, prompt_for_gemini = prelude_res

        if action_from_prelude == "MAX_ROUNDS_REACHED":
            return "max_rounds_exceeded", None
        if action_from_prelude == "error_missing_problem_def":
            # This error implies problem_definition was missing in prelude
            return "error_problem_def_missing", None
        
        # action_from_prelude is "proceed_to_dispatch"
        logging.info("%s: Calling Gemini to generate Gemma prompt.", class_name)
        gemma_prompt = gemini_client.generate_content(prompt_for_gemini)
        logging.info("%s: Generated Gemma prompt by Gemini: %s",
                     class_name, gemma_prompt)
        
        return "prompt_generated", gemma_prompt

    def postlude(self, shared_data: SharedData, _prelude_res, exec_res,
                 **_config_kwargs):
        """
        Saves the generated Gemma prompt to shared component data.

        Args:
            shared_data: The shared data object for the flow.
            _prelude_res: The result from `prelude` (unused here).
            exec_res: The tuple (action, gemma_prompt) from `dispatch`.
            _config_kwargs: Catch-all for other config parameters from
                Nethervortex.

        Returns:
            The action string from `exec_res` for flow control.
        """
        class_name = self.__class__.__name__
        logging.info("%s (Component: %s): Postlude.", class_name, self.COMP)
        action, gemma_prompt = exec_res

        if action == "prompt_generated" and gemma_prompt:
            shared_data["cmpnt"][self.COMP]["current_gemma_prompt"] = gemma_prompt
            logging.info(
                "%s: Saved Gemma prompt to shared_data[\"cmpnt\"][\"%s\"]"
                "[\"current_gemma_prompt\"].", class_name, self.COMP
            )
        elif action in ("max_rounds_exceeded", "error_problem_def_missing"):
            logging.warning(
                "%s: Prompt generation skipped or failed (action: %s). "
                "No Gemma prompt saved.", class_name, action
            )
        
        return action

class GemmaEvaluationNode(Node):
    """
    Node 2: Evaluates a Gemma prompt using an Ollama client.
    The Ollama client call is made in `dispatch`.
    """
    COMP = "LLM_ITERATOR"

    def prelude(self, shared_data: SharedData, **_config_kwargs):
        """
        Prepares for Gemma prompt evaluation.

        Retrieves the current Gemma prompt from shared component data.

        Args:
            shared_data: The shared data object for the flow.
            _config_kwargs: Catch-all for other config parameters from
                Nethervortex.

        Returns:
            A tuple (action_string, payload).
            `action_string` indicates status ("proceed_to_dispatch" or
            "error_missing_gemma_prompt").
            `payload` is the Gemma prompt string or None.
        """
        class_name = self.__class__.__name__
        logging.info("%s (Component: %s): Starting prelude.",
                     class_name, self.COMP)

        gemma_prompt = shared_data["cmpnt"][self.COMP].get("current_gemma_prompt")
        if not gemma_prompt:
            logging.error(
                "%s: Gemma prompt not found in shared_data[\"cmpnt\"][\"%s\"].",
                class_name, self.COMP
            )
            return "error_missing_gemma_prompt", None

        logging.info("%s: Retrieved Gemma prompt for dispatch.", class_name)
        return "proceed_to_dispatch", gemma_prompt

    def dispatch(self, prelude_res, *, ollama_client: OllamaClient,
                 **_config_kwargs):
        """
        Sends the prompt to Gemma (via Ollama client) and gets the response.

        Args:
            prelude_res: The tuple (action, gemma_prompt_str) from `prelude`.
            ollama_client: An instance of OllamaClient, passed via config.
            _config_kwargs: Catch-all for other config parameters from
                Nethervortex.

        Returns:
            A tuple (action_string, payload).
            `action_string` indicates status ("evaluation_complete" or
            "evaluation_error_no_prompt").
            `payload` is the Gemma response string or None.
        """
        class_name = self.__class__.__name__
        action_from_prelude, gemma_prompt_str = prelude_res

        if action_from_prelude == "error_missing_gemma_prompt":
            logging.error(
                "%s: Cannot proceed to dispatch, Gemma prompt was missing.",
                class_name
            )
            return "evaluation_error_no_prompt", None

        # action_from_prelude is "proceed_to_dispatch"
        logging.info("%s: Sending prompt to Ollama (Gemma): '%s'",
                     class_name, gemma_prompt_str)
        gemma_response = ollama_client.run(gemma_prompt_str)
        logging.info("%s: Received response from Ollama (Gemma): '%s'",
                     class_name, gemma_response)

        return "evaluation_complete", gemma_response

    def postlude(self, shared_data: SharedData, _prelude_res, exec_res,
                 **_config_kwargs):
        """
        Saves the Gemma response to shared component data.

        Args:
            shared_data: The shared data object for the flow.
            _prelude_res: The result from `prelude` (unused here).
            exec_res: The tuple (action, gemma_response) from `dispatch`.
            _config_kwargs: Catch-all for other config parameters from
                Nethervortex.

        Returns:
            The action string from `exec_res` for flow control.
        """
        class_name = self.__class__.__name__
        logging.info("%s (Component: %s): Postlude.", class_name, self.COMP)
        action, gemma_response = exec_res

        if action == "evaluation_complete" and gemma_response is not None:
            shared_data["cmpnt"][self.COMP]["current_gemma_response"] = gemma_response
            logging.info(
                "%s: Saved Gemma response to shared_data[\"cmpnt\"][\"%s\"]"
                "[\"current_gemma_response\"].", class_name, self.COMP
            )
        elif action == "evaluation_error_no_prompt":
            logging.error(
                "%s: Evaluation error due to missing prompt in prelude. "
                "No Gemma response saved.", class_name
            )

        return action

class AssessmentNode(Node):
    """
    Node 3: Assesses Gemma's response using a Gemini model.
    It determines if the response satisfies the problem definition and
    manages loop-back or flow termination based on the assessment and
    current round count. The Gemini client call is made in `dispatch`.
    """
    COMP = "LLM_ITERATOR"

    def prelude(self, shared_data: SharedData, *,
                assessment_prompt_template: str, **_config_kwargs):
        """
        Prepares for assessing Gemma's response.

        Retrieves Gemma's response and the problem definition from shared
        component data. Constructs the full assessment prompt string for Gemini.

        Args:
            shared_data: The shared data object for the flow.
            assessment_prompt_template: A template string for the assessment
                prompt.
            _config_kwargs: Catch-all for other config parameters from
                Nethervortex.

        Returns:
            A tuple (action_string, payload).
            `action_string` indicates status ("proceed_to_dispatch" or
            an error string like "error_missing_gemma_response").
            `payload` is the constructed prompt string for Gemini or None.
        """
        class_name = self.__class__.__name__
        logging.info("%s (Component: %s): Starting prelude.",
                     class_name, self.COMP)

        comp_data = shared_data["cmpnt"][self.COMP]
        gemma_response = comp_data.get("current_gemma_response")
        problem_definition = comp_data.get("problem_definition")

        if gemma_response is None:
            logging.error(
                "%s: Gemma response not found in shared_data[\"cmpnt\"][\"%s\"].",
                class_name, self.COMP
            )
            return "error_missing_gemma_response", None
        if not problem_definition:
            logging.error(
                "%s: Problem definition not found in shared_data[\"cmpnt\"]"
                "[\"%s\"] for assessment.", class_name, self.COMP
            )
            return "error_missing_problem_def_for_assessment", None

        prompt_for_gemini_assessment = assessment_prompt_template.format(
            problem_definition=problem_definition,
            gemma_response=gemma_response
        )
        logging.info("%s: Constructed assessment prompt for Gemini.", class_name)
        return "proceed_to_dispatch", prompt_for_gemini_assessment

    def dispatch(self, prelude_res, *, gemini_client: GeminiClient,
                 **_config_kwargs):
        """
        Sends the assessment prompt to Gemini and gets the YES/NO result.

        Args:
            prelude_res: The tuple (action, prompt_str) from `prelude`.
            gemini_client: An instance of GeminiClient, passed via config.
            _config_kwargs: Catch-all for other config parameters from
                Nethervortex.

        Returns:
            A tuple (action_string, payload).
            `action_string` indicates status ("assessment_done" or an
            error string).
            `payload` is the assessment result string ("YES"/"NO") or None.
        """
        class_name = self.__class__.__name__
        action_from_prelude, prompt_for_assessment = prelude_res

        if action_from_prelude in [
            "error_missing_gemma_response",
            "error_missing_problem_def_for_assessment"
        ]:
            logging.error(
                "%s: Cannot proceed to dispatch due to error from prelude: %s.",
                class_name, action_from_prelude
            )
            # Consolidate error action for postlude to handle
            return "assessment_error_missing_data", None

        if not gemini_client.api_key:
            logging.error(
                "%s: Gemini API key missing in provided client. "
                "Cannot perform assessment.", class_name
            )
            return "assessment_error_missing_key", None
        
        logging.info(
            "%s: Sending assessment prompt to Gemini.", class_name
        )
        try:
            assessment_result = gemini_client.generate_content(
                prompt_for_assessment
            ).strip().upper()
            logging.info("%s: Received assessment from Gemini: '%s'",
                         class_name, assessment_result)
        except Exception as e:  # pylint: disable=broad-except
            logging.error("%s: Error during Gemini client call: %s",
                          class_name, e)
            return "assessment_error_api_call", None
            
        return "assessment_done", assessment_result

    def postlude(self, shared_data: SharedData, _prelude_res, exec_res,
                 **_config_kwargs):
        """
        Determines the next flow step based on assessment and round count.

        Args:
            shared_data: The shared data object for the flow.
            _prelude_res: The result from `prelude` (unused here).
            exec_res: The tuple (action, assessment_result) from `dispatch`.
            _config_kwargs: Catch-all for other config parameters from
                Nethervortex.

        Returns:
            The action string for flow control (e.g., "satisfied_end_flow",
            "max_rounds_end_flow", "unsatisfied_loop_back", or
            "assessment_failed_end_flow").
        """
        class_name = self.__class__.__name__
        logging.info("%s (Component: %s): Postlude.", class_name, self.COMP)
        action, assessment_result = exec_res

        if action in ["assessment_error_missing_data",
                      "assessment_error_api_call",
                      "assessment_error_missing_key"]:
            logging.error(
                "%s: Assessment error occurred (action: %s). Ending flow path.",
                class_name, action
            )
            return "assessment_failed_end_flow"

        # No shared data modifications are made in this postlude,
        # only decision logic for the next step.
        current_round = shared_data["cmpnt"][self.COMP].get("round_count", 0)

        if assessment_result == "YES":
            logging.info(
                "%s: Assessment is YES. Problem satisfied in round %s.",
                class_name, current_round
            )
            return "satisfied_end_flow"
        
        if assessment_result != "NO": 
            logging.warning(
                "%s: Assessment result was '%s', not 'NO'. Treating as NO.",
                class_name, assessment_result
            )
        
        logging.info(
            "%s: Assessment is NO. Problem not satisfied in round %s.",
            class_name, current_round
        )
        if current_round >= 5:
            logging.info(
                "%s: Max rounds (%s/5) reached for component %s. Ending flow.",
                class_name, current_round, self.COMP
            )
            return "max_rounds_end_flow"
        
        logging.info(
            "%s: Max rounds not reached (%s/5) for component %s. Looping back.",
            class_name, current_round, self.COMP
        )
        return "unsatisfied_loop_back"

class FlowEndNode(Node):
    """
    Node 4: Marks the end of the LLM interaction flow.
    Logs final information from the shared component data.
    """
    COMP = "LLM_ITERATOR"  # Ensures consistency in accessing component data

    def prelude(self, shared_data: SharedData, **_config_kwargs):
        """
        Prepares for flow termination by logging final state information.

        Args:
            shared_data: The shared data object for the flow, used to
                access component-specific data.
            _config_kwargs: Catch-all for other config parameters passed by
                Nethervortex (unused in this node).

        Returns:
            A tuple containing an action string ("flow_ended_data_collected")
            and a None payload, as no specific data needs to be passed to
            this node's dispatch method.
        """
        class_name = self.__class__.__name__
        logging.info("%s (Component: %s): Flow has reached its end.",
                     class_name, self.COMP)

        comp_data = shared_data["cmpnt"].get(self.COMP, {})
        final_round_count = comp_data.get("round_count", "N/A")
        logging.info(
            "%s: Total rounds attempted in component %s: %s",
            class_name, self.COMP, final_round_count
        )

        final_gemma_response = comp_data.get("current_gemma_response", "N/A")
        problem_def = comp_data.get("problem_definition", "N/A")
        logging.info(
            "%s: Final Gemma response for problem '%s': %s",
            class_name, problem_def, final_gemma_response
        )
        
        return "flow_ended_data_collected", None

    def dispatch(self, _prelude_res, **_config_kwargs):
        """
        Performs final dispatch actions, which are typically none for an end
        node.

        Args:
            _prelude_res: The result from `prelude` (unused in this node).
            _config_kwargs: Catch-all for other config parameters passed by
                Nethervortex (unused in this node).

        Returns:
            A tuple containing a final action string ("flow_complete") and a
            None payload.
        """
        class_name = self.__class__.__name__
        logging.info(
            "%s (Component: %s): Dispatching final actions (if any).",
            class_name, self.COMP
        )
        return "flow_complete", None

    def postlude(self, _shared_data: SharedData, _prelude_res, exec_res,
                 **_config_kwargs):
        """
        Finalizes the flow after all operations.

        Args:
            _shared_data: The shared data object (unused in this method).
            _prelude_res: The result from `prelude` (unused in this method).
            exec_res: The tuple (action, payload) from `dispatch`.
            _config_kwargs: Catch-all for other config parameters passed by
                Nethervortex (unused in this node).

        Returns:
            The action string from `dispatch`'s result, signaling the end
            of this node's execution.
        """
        class_name = self.__class__.__name__
        logging.info("%s (Component: %s): Finalizing flow.",
                     class_name, self.COMP)
        action, _unused_payload = exec_res
        return action

# --- Client Instantiations ---
# In a real application, GEMINI_API_KEY would be crucial here.
# The placeholder client has some tolerance for a missing key.
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if not gemini_api_key:
    logging.warning(
        "GEMINI_API_KEY environment variable not set. "
        "Using placeholder GeminiClient with limited functionality for "
        "prompt generation. AssessmentNode might fail if key is strictly "
        "required by its internal logic."
    )
gemini_client_instance = GeminiClient(api_key=gemini_api_key)
ollama_client_instance = OllamaClient()

# --- Node Instantiations ---
prompt_gen_node = PromptGenerationNode()
gemma_eval_node = GemmaEvaluationNode()
assessment_node = AssessmentNode()
flow_end_node = FlowEndNode()

# --- Flow Logic Definition ---
# Define the main flow path
(prompt_gen_node - "prompt_generated") >> gemma_eval_node # Corrected transition
gemma_eval_node >> assessment_node

# Define conditional transitions from AssessmentNode
assessment_node - "satisfied_end_flow" >> flow_end_node
assessment_node - "max_rounds_end_flow" >> flow_end_node
assessment_node - "assessment_failed_end_flow" >> flow_end_node
assessment_node - "unsatisfied_loop_back" >> prompt_gen_node

# Define transitions for errors/max_rounds from earlier nodes
prompt_gen_node - "max_rounds_exceeded" >> flow_end_node
prompt_gen_node - "error_problem_def_missing" >> flow_end_node 
gemma_eval_node - "evaluation_error_no_prompt" >> flow_end_node
# AssessmentNode's internal errors like missing data, key, or API call failure
# are routed to "assessment_failed_end_flow" by its postlude.

# --- Main Execution Block ---
if __name__ == "__main__":
    logging.info("Starting LLM Flow Showcase...")

    # Initial problem definition and prompt templates
    problem_def = "Write a short and sweet poem about a happy cat."
    gemma_prompt_gen_template = (
        "You are an assistant that generates concise prompts for another "
        "AI (Gemma). Based on the problem definition: "
        "'{problem_definition}', generate a short, clear prompt for "
        "Gemma to fulfill this definition."
    )
    assessment_template = (
        "Problem definition: '{problem_definition}'. Does the following "
        "text generated by another AI satisfy this problem definition? "
        "TEXT: '{gemma_response}'. Respond with only YES or NO."
    )

    # Prepare initial SharedData
    # Nethervortex requires 'config', 'cmpnt', and 'state' to be present.
    initial_shared_data = SharedData(
        config={
            "gemini_client": gemini_client_instance,
            "ollama_client": ollama_client_instance,
            # Templates are now passed via component config for better modularity
        },
        cmpnt={
            "LLM_ITERATOR": {
                "problem_definition": problem_def,
                "round_count": 0, # Initialized, Node 1 increments before use
                "config": { 
                    "gemma_prompt_generation_template": gemma_prompt_gen_template,
                    "assessment_prompt_template": assessment_template,
                }
                # current_gemma_prompt and current_gemma_response
                # will be populated by the nodes during the flow.
            }
        },
        state=None # Nethervortex manages this, set to None initially
    )

    # Initialize the Flow
    flow = Flow(start=prompt_gen_node)

    # Run the flow
    logging.info("Running the Nethervortex flow...")
    final_result_action = flow.run(initial_shared_data) # Changed to positional argument
    logging.info(
        "Nethervortex flow finished with final action: %s",
        final_result_action
    )
    logging.info(
        "Final shared data state for component %s: %s",
        PromptGenerationNode.COMP, 
        initial_shared_data["cmpnt"].get(PromptGenerationNode.COMP, {})
    )
