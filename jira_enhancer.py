#!/usr/bin/env python3
"""
Jira Ticket Enhancer using Llama 3 8B
Stateless approach: sends policy + ticket data in each request
"""

import requests
import json
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class TicketData:
    """Structure for Jira ticket data"""
    title: str
    description: str
    priority: Optional[str] = None
    issue_type: Optional[str] = None
    assignee: Optional[str] = None
    labels: Optional[list] = None
    components: Optional[list] = None


class JiraTicketEnhancer:
    def __init__(self, ollama_host: str = "localhost", ollama_port: int = 11434, model_name: str = "llama3:8b"):
        """
        Initialize the Jira Ticket Enhancer

        Args:
            ollama_host: Ollama server host
            ollama_port: Ollama server port
            model_name: Name of the model to use
        """
        self.base_url = f"http://{ollama_host}:{ollama_port}"
        self.model_name = model_name
        self.policy_rules = self._load_default_policy()

    def _load_default_policy(self) -> str:
        """Load default policy rules"""
        return """
JIRA TICKET ENHANCEMENT POLICY:

1. MANDATORY FIELDS:
   - All tickets must have clear, descriptive titles
   - Descriptions must include specific details, not vague statements
   - Priority must be set (Critical, High, Medium, Low)
   - Issue type must be specified (Bug, Story, Task, Epic)

2. BUG TICKETS:
   - Must include reproduction steps
   - Must specify expected vs actual behavior
   - Should include environment details (browser, OS, version)
   - Must have severity assessment

3. STORY/FEATURE TICKETS:
   - Must include acceptance criteria
   - Should have user story format: "As a [user], I want [goal] so that [benefit]"
   - Must include definition of done

4. TASK TICKETS:
   - Must have clear action items
   - Should include estimated effort
   - Must specify deliverables

5. GENERAL RULES:
   - Use professional, clear language
   - Remove duplicate information
   - Add relevant labels and components
   - Suggest appropriate assignee if obvious
   - Flag missing critical information
   """

    def load_custom_policy(self, policy_file: str = None, policy_text: str = None):
        """
        Load custom policy rules from file or text

        Args:
            policy_file: Path to policy file
            policy_text: Policy text directly
        """
        if policy_file:
            try:
                with open(policy_file, 'r') as f:
                    self.policy_rules = f.read()
            except FileNotFoundError:
                print(f"Policy file {policy_file} not found. Using default policy.")
        elif policy_text:
            self.policy_rules = policy_text

    def test_connection(self) -> bool:
        """Test connection to Ollama server"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def enhance_ticket(self, ticket: TicketData, custom_instructions: str = "") -> Dict[str, Any]:
        """
        Enhance a Jira ticket using the model

        Args:
            ticket: TicketData object with ticket information
            custom_instructions: Additional specific instructions for this ticket

        Returns:
            Dict with enhanced ticket data and metadata
        """
        # Build the prompt
        prompt = self._build_prompt(ticket, custom_instructions)

        # Call the model
        try:
            response = self._call_model(prompt)
            return {
                "success": True,
                "enhanced_content": response,
                "original_ticket": ticket,
                "timestamp": time.time()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "original_ticket": ticket,
                "timestamp": time.time()
            }

    def _build_prompt(self, ticket: TicketData, custom_instructions: str = "") -> str:
        """Build the complete prompt with policy + ticket data"""

        # Format ticket information
        ticket_info = f"""
CURRENT TICKET:
Title: {ticket.title}
Description: {ticket.description}
Priority: {ticket.priority or 'Not set'}
Issue Type: {ticket.issue_type or 'Not set'}
Assignee: {ticket.assignee or 'Unassigned'}
Labels: {', '.join(ticket.labels) if ticket.labels else 'None'}
Components: {', '.join(ticket.components) if ticket.components else 'None'}
"""

        # Build complete prompt
        prompt = f"""{self.policy_rules}

{ticket_info}

{custom_instructions}

TASK: Analyze the current ticket and provide an enhanced version that follows the policy rules above. 
Provide your response in the following format:

ENHANCED TICKET:
Title: [Enhanced title]
Description: [Enhanced description with all necessary details]
Priority: [Appropriate priority level]
Issue Type: [Correct issue type]
Suggested Labels: [Relevant labels]
Suggested Components: [Relevant components]
Missing Information: [List any critical information that's still missing]
Recommendations: [Any additional recommendations for improving this ticket]

Please enhance this ticket now:"""

        return prompt

    def _call_model(self, prompt: str) -> str:
        """Make API call to Ollama"""
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for consistent results
                "top_p": 0.9,
                "num_ctx": 4096  # Context window
            }
        }

        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()

        result = response.json()
        return result.get("response", "")

    def batch_enhance(self, tickets: list[TicketData]) -> list[Dict[str, Any]]:
        """Enhance multiple tickets"""
        results = []
        for i, ticket in enumerate(tickets):
            print(f"Processing ticket {i + 1}/{len(tickets)}: {ticket.title}")
            result = self.enhance_ticket(ticket)
            results.append(result)

            # Add small delay to avoid overwhelming the server
            time.sleep(0.5)

        return results


def main():
    """Example usage"""
    # Initialize enhancer
    enhancer = JiraTicketEnhancer()

    # Test connection
    if not enhancer.test_connection():
        print("ERROR: Cannot connect to Ollama server. Make sure 'ollama serve' is running.")
        return

    print("✅ Connected to Ollama server")

    # Example ticket
    sample_ticket = TicketData(
        title="Login broken",
        description="Can't login",
        priority="High",
        issue_type="Bug"
    )

    print(f"\n🎫 Processing ticket: {sample_ticket.title}")

    # Enhance the ticket
    result = enhancer.enhance_ticket(sample_ticket)

    if result["success"]:
        print("\n✅ Enhancement completed:")
        print("=" * 50)
        print(result["enhanced_content"])
    else:
        print(f"\n❌ Error: {result['error']}")


if __name__ == "__main__":
    main()
