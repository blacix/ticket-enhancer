#!/usr/bin/env python3
"""
Jira Ticket Enhancer using atlassian-python-api library
Clean implementation using jira.Issue objects throughout
"""

import os
from atlassian import Jira
from typing import Dict, Any, Optional, Tuple
import time


class LlamaJiraEnhancer:
    """Llama enhancer that works directly with jira.Issue objects"""

    def __init__(self, ollama_host: str = "localhost", ollama_port: int = 11434, model_name: str = "llama3:8b"):
        """
        Initialize the Llama Jira Enhancer

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

    def enhance_ticket(self, issue, custom_instructions: str = "") -> Dict[str, Any]:
        """
        Enhance a Jira issue using the model

        Args:
            issue: jira.Issue object
            custom_instructions: Additional specific instructions for this ticket

        Returns:
            Dict with enhanced ticket data and metadata
        """
        # Build the prompt
        prompt = self._build_prompt(issue, custom_instructions)

        # Call the model
        try:
            response = self._call_model(prompt)
            enhanced_description = self._extract_description_from_output(response)

            return {
                "success": True,
                "enhanced_description": enhanced_description,
                "full_response": response,
                "original_issue": issue,
                "timestamp": time.time()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "original_issue": issue,
                "timestamp": time.time()
            }

    def _build_prompt(self, issue, custom_instructions: str = "") -> str:
        """Build the complete prompt with policy + issue data"""

        fields = issue['fields']

        # Format issue information
        issue_info = f"""
CURRENT TICKET:
Key: {issue['key']}
Title: {fields.get('summary', 'No title')}
Description: {fields.get('description', 'No description')}
Priority: {fields.get('priority', {}).get('name', 'Not set') if fields.get('priority') else 'Not set'}
Issue Type: {fields.get('issuetype', {}).get('name', 'Not set') if fields.get('issuetype') else 'Not set'}
Assignee: {fields.get('assignee', {}).get('displayName', 'Unassigned') if fields.get('assignee') else 'Unassigned'}
Status: {fields.get('status', {}).get('name', 'Unknown') if fields.get('status') else 'Unknown'}
Labels: {', '.join(fields.get('labels', [])) if fields.get('labels') else 'None'}
Components: {', '.join([c['name'] for c in fields.get('components', [])]) if fields.get('components') else 'None'}
"""

        # Build complete prompt
        prompt = f"""{self.policy_rules}

{issue_info}

{custom_instructions}

TASK: Analyze the current ticket and provide an enhanced description that follows the policy rules above. 
Focus ONLY on improving the description field while maintaining all the important information.

Provide your response in the following format:

ENHANCED DESCRIPTION:
[Your enhanced description here - be detailed, structured, and professional]

Please enhance this ticket description now:"""

        return prompt

    def _call_model(self, prompt: str) -> str:
        """Make API call to Ollama"""
        import requests

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

    def _extract_description_from_output(self, llama_output: str) -> str:
        """Extract just the enhanced description from Llama's output"""
        lines = llama_output.split('\n')
        description_lines = []
        in_description = False

        for line in lines:
            if 'ENHANCED DESCRIPTION:' in line.upper():
                in_description = True
                # Include any text after the header on the same line
                after_header = line.split(':', 1)
                if len(after_header) > 1 and after_header[1].strip():
                    description_lines.append(after_header[1].strip())
            elif in_description:
                # Stop if we hit another section header
                if line.strip().isupper() and ':' in line and len(line.strip()) < 50:
                    break
                description_lines.append(line)

        return '\n'.join(description_lines).strip()


class JiraIssueEnhancer:
    """Simplified Jira ticket enhancer using atlassian-python-api"""

    def __init__(self, server_url: str, username: str, api_token: str):
        """
        Initialize with Jira Cloud credentials

        Args:
            server_url: Your Jira URL (e.g., https://company.atlassian.net)
            username: Your email address
            api_token: Your API token
        """
        self.jira = Jira(
            url=server_url,
            username=username,
            password=api_token,  # API token goes in password field
            cloud=True  # Important for Jira Cloud
        )

        # Initialize the Llama enhancer
        self.llama_enhancer = LlamaJiraEnhancer()

    def get_issue(self, ticket_key: str):
        """Get issue object"""
        return self.jira.issue(ticket_key)

    def search_project_issues(self, project_key: str, max_results: int = 50) -> list:
        """Search issues in project and return list of issue objects"""
        jql = f"project = {project_key} ORDER BY created DESC"
        result = self.jira.jql(jql, limit=max_results)
        return result['issues']

    def enhance_issue_description(self, issue, custom_instructions: str = "") -> Dict[str, Any]:
        """
        Enhance an issue's description using Llama

        Args:
            issue: jira.Issue object or ticket key string
            custom_instructions: Additional instructions for enhancement

        Returns:
            Dict with enhancement results
        """
        # Convert string to issue object if needed
        if isinstance(issue, str):
            issue = self.get_issue(issue)

        return self.llama_enhancer.enhance_ticket(issue, custom_instructions)

    def to_string(self, issue) -> str:
        """
        Convert issue to formatted string representation

        Args:
            issue: jira.Issue object or ticket key string

        Returns:
            Formatted string representation of the issue
        """
        # Convert string to issue object if needed
        if isinstance(issue, str):
            issue = self.get_issue(issue)

        fields = issue['fields']
        original_desc = fields.get('description', '')
        enhanced_desc = fields.get('enhanced_description', '')

        result = f"\n🎫 ISSUE {issue['key']}\n"
        result += "=" * 50 + "\n"
        result += f"📋 Title: {fields.get('summary', 'No title')}\n"
        result += f"🏷️  Type: {fields.get('issuetype', {}).get('name', 'Unknown')}\n"
        result += f"⚡ Priority: {fields.get('priority', {}).get('name', 'Not set') if fields.get('priority') else 'Not set'}\n"
        result += f"\n📝 DESCRIPTION ({len(original_desc)} chars):\n"
        result += "-" * 30 + "\n"
        result += original_desc
        if enhanced_desc:
            result += f"\n📝 ENHANCED DESCRIPTION ({len(enhanced_desc)} chars):\n"
            result += enhanced_desc
        return result

    def preview_enhancement(self, issue, custom_instructions: str = ""):
        """
        Preview enhancement without updating the ticket

        Args:
            issue: jira.Issue object or ticket key string
            custom_instructions: Additional instructions for enhancement
        """
        # Convert string to issue object if needed
        if isinstance(issue, str):
            issue = self.get_issue(issue)

        # Print current issue
        print(self.to_string(issue))

        # Get enhancement
        print(f"\n🤖 ENHANCING WITH LLAMA...")
        enhancement_result = self.enhance_issue_description(issue, custom_instructions)

        if enhancement_result['success']:
            enhanced_desc = enhancement_result['enhanced_description']
            original_desc = issue['fields'].get('description', '')

            print(f"\n✨ ENHANCED DESCRIPTION ({len(enhanced_desc)} chars):")
            print("-" * 30)
            print(enhanced_desc)

            print(f"\n📊 ENHANCEMENT SUMMARY:")
            print(f"   • Original length: {len(original_desc)} characters")
            print(f"   • Enhanced length: {len(enhanced_desc)} characters")
            print(
                f"   • Change: {'+' if len(enhanced_desc) > len(original_desc) else ''}{len(enhanced_desc) - len(original_desc)} characters")
        else:
            print(f"\n❌ Enhancement failed: {enhancement_result['error']}")

    def update_issue_description(self, issue, enhanced_description: str) -> Tuple[bool, str]:
        """
        Update an issue's description in Jira

        Args:
            issue: jira.Issue object or ticket key string
            enhanced_description: The new description content

        Returns:
            Tuple of (success, message)
        """
        # Convert string to issue object if needed
        if isinstance(issue, str):
            issue_key = issue
            issue = self.get_issue(issue)
        else:
            issue_key = issue['key']

        try:
            self.jira.issue_update(
                issue_key=issue_key,
                fields={'description': enhanced_description}
            )
            return True, f"✅ Successfully updated description for {issue_key}"
        except Exception as e:
            return False, f"❌ Failed to update {issue_key}: {str(e)}"

    def enhance_and_update_issue(self, issue, custom_instructions: str = "") -> Tuple[bool, str]:
        """
        Enhance an issue and update it in Jira

        Args:
            issue: jira.Issue object or ticket key string
            custom_instructions: Additional instructions for enhancement

        Returns:
            Tuple of (success, message)
        """
        # Convert string to issue object if needed
        if isinstance(issue, str):
            issue_key = issue
            issue = self.get_issue(issue)
        else:
            issue_key = issue['key']

        # Print current issue
        print(self.to_string(issue))

        # Enhance
        enhancement_result = self.enhance_issue_description(issue, custom_instructions)

        if not enhancement_result['success']:
            return False, f"❌ Enhancement failed for {issue_key}: {enhancement_result['error']}"

        # Update
        enhanced_description = enhancement_result['enhanced_description']
        success, message = self.update_issue_description(issue, enhanced_description)

        return success, message


def load_from_env() -> JiraIssueEnhancer:
    """Load configuration from environment variables"""
    required_vars = ['JIRA_SERVER_URL', 'JIRA_SERVICE_ACCOUNT_EMAIL', 'JIRA_SERVICE_ACCOUNT_TOKEN']
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        raise ValueError(f"Missing environment variables: {', '.join(missing)}")

    return JiraIssueEnhancer(
        server_url=os.getenv('JIRA_SERVER_URL'),
        username=os.getenv('JIRA_SERVICE_ACCOUNT_EMAIL'),
        api_token=os.getenv('JIRA_SERVICE_ACCOUNT_TOKEN')
    )


def main():
    """Demo the enhanced workflow"""

    print("🤖 Jira Ticket Enhancer with Llama 3")
    print("=" * 40)

    try:
        # Initialize
        enhancer = load_from_env()

        # Test connection
        try:
            projects = enhancer.jira.projects()
            print(f"✅ Connected to Jira. Found {len(projects)} projects.")
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return

        # Find issues in DIGI project
        print(f"\n🔍 Searching for issues in DIGI project...")
        issues = enhancer.search_project_issues("DIGI", max_results=5)

        if not issues:
            print("❌ No issues found in DIGI project")
            return

        print(f"✅ Found {len(issues)} issue(s):")
        for issue in issues:
            print(f"   • {issue['key']}: {issue['fields']['summary']}")

        # Demo with first issue
        demo_issue = issues[0]
        demo_issue = enhancer.jira.get_issue(issue_id_or_key='DIGI-894')
        demo_key = demo_issue['key']
        print(f"\n🎯 Demonstrating enhancement with {demo_key}")

        # Preview enhancement
        enhancer.preview_enhancement(demo_issue)

        print(f"\n" + "=" * 50)
        print("🛠️  AVAILABLE METHODS:")
        print(f"   • enhancer.preview_enhancement('{demo_key}')")
        print(f"   • enhancer.enhance_and_update_issue('{demo_key}')")
        print(f"   • enhancer.get_issue('{demo_key}')")

        print(f"\n⚠️  To actually update the issue, run:")
        print(f"   enhancer.enhance_and_update_issue('{demo_key}')")

    except Exception as e:
        print(f"❌ Error: {e}")


# Example usage functions
def enhance_specific_issue(ticket_key: str):
    """Example: Enhance a specific issue"""
    enhancer = load_from_env()
    success, message = enhancer.enhance_and_update_issue(ticket_key)
    print(message)
    return success


def preview_specific_issue(ticket_key: str):
    """Example: Preview enhancement for a specific issue"""
    enhancer = load_from_env()
    enhancer.preview_enhancement(ticket_key)


def batch_enhance_project(project_key: str, max_issues: int = 10):
    """Example: Enhance multiple issues in a project"""
    enhancer = load_from_env()
    issues = enhancer.search_project_issues(project_key, max_issues)

    results = []
    for issue in issues:
        issue_key = issue['key']
        print(f"Processing {issue_key}...")
        success, message = enhancer.enhance_and_update_issue(issue)
        results.append({'issue': issue_key, 'success': success, 'message': message})

    return results


if __name__ == "__main__":
    main()