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
    The Gemini client call is moved to `dispatch`.
    Error handling for missing `problem_definition` is now by raising
    `ValueError` in `prelude`. Max rounds check is removed from `prelude`.
    """
    COMP = "LLM_ITERATOR"

    def prelude(self, shared_data: SharedData, *,
                gemma_prompt_generation_template: str, **_config_kwargs):
        """
        Prepares for Gemma prompt generation.

        Retrieves problem definition, increments round count, and constructs
        the prompt string for Gemini.

        Args:
            shared_data: The shared data object for the flow.
            gemma_prompt_generation_template: A template string for
                generating the prompt for Gemini.
            _config_kwargs: Catch-all for other config parameters from
                Nethervortex.

        Returns:
            The constructed prompt string for Gemini.

        Raises:
            ValueError: If `problem_definition` is not found in
                `shared_data["cmpnt"][self.COMP]`.
        """
        class_name = self.__class__.__name__
        # logging.info("%s (Component: %s): Starting prelude.",  # Removed
        #              class_name, self.COMP)

        comp_data = shared_data["cmpnt"].get(self.COMP, {})
        problem_definition = comp_data.get("problem_definition")
        if not problem_definition:
            error_msg = (
                f"{class_name}: Problem definition not found in "
                f"shared_data[\"cmpnt\"][\"{self.COMP}\"]."
            )
            logging.error(error_msg)
            raise ValueError(error_msg)

        # Initialize or increment round count
        round_count = comp_data.get("round_count", 0) + 1
        shared_data["cmpnt"][self.COMP]["round_count"] = round_count
        logging.info("Round: %s/5 for component %s", round_count, self.COMP)
        # Max rounds check is removed from here as per Phase 2 guidelines.
        # It will be handled by AssessmentNode or flow logic.

        prompt_for_gemini = gemma_prompt_generation_template.format(
            problem_definition=problem_definition
        )
        logging.info("%s: Constructed prompt for Gemini.", class_name)
        # Line wrapping for potentially long prompt:
        if len(prompt_for_gemini) > 60: # Arbitrary length for summary
            logging.debug("%s: Full prompt: %s", class_name, prompt_for_gemini)
        else:
            logging.info("%s: Prompt for Gemini: %s", class_name, prompt_for_gemini)


        return prompt_for_gemini

    def dispatch(self, prelude_res_prompt_for_gemini: str, *,
                 gemini_client: GeminiClient, **_config_kwargs):
        """
        Generates the Gemma prompt using Gemini.

        Receives the prompt string for Gemini from `prelude` (which is
        `prelude_res_prompt_for_gemini`) and calls the Gemini client.

        Args:
            prelude_res_prompt_for_gemini: The prompt string for Gemini,
                returned by `prelude`.
            gemini_client: An instance of GeminiClient, passed via config.
            _config_kwargs: Catch-all for other config parameters from
                Nethervortex.

        Returns:
            A tuple (action_string, payload).
            `action_string` is "prompt_generated".
            `payload` is the generated Gemma prompt.
        """
        class_name = self.__class__.__name__
        # prelude_res_prompt_for_gemini is now directly the prompt string.
        # No action_from_prelude or error checks here as prelude handles them
        # by raising ValueError or returning the prompt.
        
        logging.info("%s: Calling Gemini to generate Gemma prompt.", class_name)
        gemma_prompt = gemini_client.generate_content(
            prelude_res_prompt_for_gemini
        )
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
        # logging.info("%s (Component: %s): Postlude.", class_name, self.COMP) # Removed
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
    The Ollama client call is made in `dispatch`. Error handling for
    missing `current_gemma_prompt` is by raising `ValueError` in `prelude`.
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
            The Gemma prompt string if found.

        Raises:
            ValueError: If `current_gemma_prompt` is not found in
                `shared_data["cmpnt"][self.COMP]`.
        """
        class_name = self.__class__.__name__
        # logging.info("%s (Component: %s): Starting prelude.", # Removed
        #              class_name, self.COMP)

        comp_data = shared_data["cmpnt"].get(self.COMP, {})
        gemma_prompt = comp_data.get("current_gemma_prompt")
        if not gemma_prompt:
            error_msg = (
                f"{class_name}: Gemma prompt not found in "
                f"shared_data[\"cmpnt\"][\"{self.COMP}\"]"
                "[\"current_gemma_prompt\"]."
            )
            logging.error(error_msg)
            raise ValueError(error_msg)

        logging.info("%s: Retrieved Gemma prompt for dispatch.", class_name)
        return gemma_prompt

    def dispatch(self, prelude_res_gemma_prompt: str, *,
                 ollama_client: OllamaClient, **_config_kwargs):
        """
        Sends the prompt to Gemma (via Ollama client) and gets the response.

        Args:
            prelude_res_gemma_prompt: The Gemma prompt string from `prelude`.
            ollama_client: An instance of OllamaClient, passed via config.
            _config_kwargs: Catch-all for other config parameters from
                Nethervortex.

        Returns:
            A tuple (action_string, payload).
            `action_string` is "evaluation_complete".
            `payload` is the Gemma response string.
        """
        class_name = self.__class__.__name__
        # prelude_res_gemma_prompt is now directly the prompt string.
        # Error handling for missing prompt is done in prelude by raising ValueError.
        
        logging.info("%s: Sending prompt to Ollama (Gemma): '%s'",
                     class_name, prelude_res_gemma_prompt)
        gemma_response = ollama_client.run(prelude_res_gemma_prompt)
        logging.info("%s: Received response from Ollama (Gemma): '%s'",
                     class_name, gemma_response)

        return "evaluation_complete", gemma_response

    def postlude(self, shared_data: SharedData, _prelude_res, exec_res,
                 **_config_kwargs):
        """
        Saves the Gemma response to shared component data.

        Args:
            shared_data: The shared data object for the flow.
            _prelude_res: The result from `prelude` (Gemma prompt string,
                unused here as `exec_res` contains the response).
            exec_res: The tuple (action, gemma_response) from `dispatch`.
            _config_kwargs: Catch-all for other config parameters from
                Nethervortex.

        Returns:
            The action string from `exec_res` for flow control.
        """
        class_name = self.__class__.__name__
        # logging.info("%s (Component: %s): Postlude.", class_name, self.COMP) # Removed
        action, gemma_response = exec_res

        if action == "evaluation_complete" and gemma_response is not None:
            # It's good practice to ensure component data dict exists
            comp_data = shared_data["cmpnt"].setdefault(self.COMP, {})
            comp_data["current_gemma_response"] = gemma_response
            logging.info(
                "%s: Saved Gemma response to shared_data[\"cmpnt\"][\"%s\"]"
                "[\"current_gemma_response\"].", class_name, self.COMP
            )
        # No specific error action from dispatch to handle here, as errors
        # in prelude now raise exceptions. Dispatch errors would be exceptions too.
        
        return action

class AssessmentNode(Node):
    """
    Node 3: Assesses Gemma's response using a Gemini model.
    It determines if the response satisfies the problem definition.
    The Gemini client call is made in `dispatch`. Error handling for
    missing data is by raising `ValueError` in `prelude`. The max rounds
    check is now performed in `postlude`.
    """
    COMP = "LLM_ITERATOR"

    def prelude(self, shared_data: SharedData, *,
                assessment_prompt_template: str, **_config_kwargs):
        """Prepares for assessing Gemma's response.

        Retrieves Gemma's response and problem definition, then constructs
        the assessment prompt for Gemini.

        Args:
            shared_data: The shared data object.
            assessment_prompt_template: Template for the assessment prompt.
            _config_kwargs: Unused config parameters.

        Returns:
            The constructed prompt string for Gemini.

        Raises:
            ValueError: If essential data is missing from `shared_data`.
        """
        class_name = self.__class__.__name__
        # "Starting prelude" log removed.
        comp_data = shared_data["cmpnt"].get(self.COMP, {})
        gemma_response = comp_data.get("current_gemma_response")
        problem_definition = comp_data.get("problem_definition")

        if gemma_response is None:
            error_msg = (
                f"{class_name}: Gemma response not found in component "
                f"\"{self.COMP}\"."
            )
            logging.error(error_msg)
            raise ValueError(error_msg)
        if not problem_definition:
            error_msg = (
                f"{class_name}: Problem definition not found in component "
                f"\"{self.COMP}\" for assessment."
            )
            logging.error(error_msg)
            raise ValueError(error_msg)

        prompt_for_gemini_assessment = assessment_prompt_template.format(
            problem_definition=problem_definition,
            gemma_response=gemma_response
        )
        # Log kept, consider DEBUG if too verbose for INFO.
        logging.info("%s: Constructed assessment prompt for Gemini.", class_name)
        return prompt_for_gemini_assessment

    def dispatch(self, prelude_res_assessment_prompt: str, *,
                 gemini_client: GeminiClient, **_config_kwargs):
        """Sends the assessment prompt to Gemini and gets the result.

        Args:
            prelude_res_assessment_prompt: The prompt string from `prelude`.
            gemini_client: An instance of GeminiClient from config.
            _config_kwargs: Unused config parameters.

        Returns:
            A tuple (action_string, payload), where payload is the
            assessment result ("YES"/"NO") or None on error.
        """
        class_name = self.__class__.__name__
        if not gemini_client.api_key:
            logging.error(
                "%s: Gemini API key missing. Cannot perform assessment.",
                class_name
            )
            return "assessment_error_missing_key", None
        
        # Truncated log for potentially long prompts.
        logging.info(
            "%s: Sending assessment prompt to Gemini (first 50 chars): '%s...'",
            class_name, prelude_res_assessment_prompt[:50]
        )
        try:
            assessment_result = gemini_client.generate_content(
                prelude_res_assessment_prompt
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
        """Determines next flow step based on assessment and round count.

        Args:
            shared_data: The shared data object.
            _prelude_res: Result from `prelude` (unused).
            exec_res: Tuple (action, assessment_result) from `dispatch`.
            _config_kwargs: Unused config parameters.

        Returns:
            The action string for flow control.
        """
        class_name = self.__class__.__name__
        # "Postlude." log removed.
        action, assessment_result = exec_res

        if action in ["assessment_error_missing_key",
                      "assessment_error_api_call"]:
            logging.error( # Kept
                "%s: Assessment error occurred (action: %s). Ending flow path.",
                class_name, action
            )
            return "assessment_failed_end_flow"

        current_round = shared_data["cmpnt"][self.COMP].get("round_count", 0)

        if assessment_result == "YES":
            logging.info( # Kept
                "%s: Assessment is YES. Problem satisfied in round %s.",
                class_name, current_round
            )
            return "satisfied_end_flow"
        
        if assessment_result != "NO": 
            logging.warning( # Kept
                "%s: Assessment result was '%s', not 'NO'. Treating as NO.",
                class_name, assessment_result
            )
        
        logging.info( # Kept
            "%s: Assessment is NO. Problem not satisfied in round %s.",
            class_name, current_round
        )
        if current_round >= 5:
            logging.info( # Kept
                "%s: Max rounds (%s/5) reached for component %s. Ending flow.",
                class_name, current_round, self.COMP
            )
            return "max_rounds_end_flow"
        
        logging.info( # Kept
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
        # "Flow has reached its end." log was already made more specific.
        comp_data = shared_data["cmpnt"].get(self.COMP, {})
        final_round_count = comp_data.get("round_count", "N/A")
        final_gemma_response = comp_data.get("current_gemma_response", "N/A")
        problem_def = comp_data.get("problem_definition", "N/A")
        
        logging.info( 
            "%s (Component: %s): Flow ended. Total rounds: %s. "
            "Final Gemma response for '%s': %s",
            class_name, self.COMP, final_round_count,
            problem_def, final_gemma_response
        ) # This log is kept as it's a summary.
        
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
        # "Dispatching final actions" log changed to debug.
        logging.debug("%s (Component: %s): Dispatch in FlowEndNode.",
                     class_name, self.COMP)
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
        # "Finalizing flow." log changed to debug.
        logging.debug("%s (Component: %s): Postlude in FlowEndNode.",
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
(prompt_gen_node - "prompt_generated") >> gemma_eval_node
(gemma_eval_node - "evaluation_complete") >> assessment_node # Explicit action

# Define conditional transitions from AssessmentNode
assessment_node - "satisfied_end_flow" >> flow_end_node
assessment_node - "max_rounds_end_flow" >> flow_end_node
assessment_node - "assessment_failed_end_flow" >> flow_end_node
assessment_node - "unsatisfied_loop_back" >> prompt_gen_node

# Error/exception handling in prelude of PromptGenerationNode and GemmaEvaluationNode
# now raises ValueError, which would halt the flow if not caught by a custom
# Flow error handling mechanism (not implemented in this showcase).
# The specific error transitions for these nodes are removed.
# AssessmentNode's internal errors are handled by its postlude returning
# "assessment_failed_end_flow".

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
