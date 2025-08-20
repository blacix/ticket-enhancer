#!/usr/bin/env python3
"""
Jira Ticket Enhancer using atlassian-python-api library
Much simpler implementation using the official library
"""

import os
from atlassian import Jira
from typing import Dict, Any, Optional, Tuple
from jira_enhancer import JiraTicketEnhancer, TicketData  # Your Llama enhancer


class SimpleJiraEnhancer:
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
        self.llama_enhancer = JiraTicketEnhancer()

    def get_ticket(self, ticket_key: str) -> Dict[str, Any]:
        """Get ticket details"""
        return self.jira.issue(ticket_key)

    def update_description(self, ticket_key: str, new_description: str) -> Tuple[bool, str]:
        """Update ticket description"""
        try:
            self.jira.issue_update(
                issue_key=ticket_key,
                fields={'description': new_description}
            )
            return True, f"✅ Updated description for {ticket_key}"
        except Exception as e:
            return False, f"❌ Failed to update {ticket_key}: {str(e)}"

    def search_project_tickets(self, project_key: str, max_results: int = 50) -> list:
        """Search tickets in project"""
        jql = f"project = {project_key} ORDER BY created DESC"
        return self.jira.jql(jql, limit=max_results)['issues']

    def enhance_ticket(self, ticket_key: str) -> Dict[str, Any]:
        """
        Core method: Get ticket and enhance with Llama (no Jira updates)

        Returns:
            Dict with enhancement results
        """
        try:
            # 1. Get current ticket
            ticket = self.get_ticket(ticket_key)
            fields = ticket['fields']

            # 2. Convert to TicketData format for Llama enhancer
            ticket_data = TicketData(
                title=fields.get('summary', ''),
                description=fields.get('description', ''),
                priority=fields.get('priority', {}).get('name') if fields.get('priority') else None,
                issue_type=fields.get('issuetype', {}).get('name') if fields.get('issuetype') else None,
                assignee=fields.get('assignee', {}).get('displayName') if fields.get('assignee') else None
            )

            # 3. Enhance with Llama
            enhancement_result = self.llama_enhancer.enhance_ticket(ticket_data)

            if not enhancement_result['success']:
                return {
                    'success': False,
                    'error': enhancement_result['error'],
                    'ticket_key': ticket_key
                }

            enhanced_content = enhancement_result['enhanced_content']
            enhanced_description = self._extract_description_from_llama_output(enhanced_content)

            return {
                'success': True,
                'ticket_key': ticket_key,
                'original': {
                    'summary': fields.get('summary', ''),
                    'description': fields.get('description', ''),
                    'priority': fields.get('priority', {}).get('name') if fields.get('priority') else None,
                    'issue_type': fields.get('issuetype', {}).get('name') if fields.get('issuetype') else None
                },
                'enhanced_content': enhanced_content,
                'enhanced_description': enhanced_description
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'ticket_key': ticket_key
            }

    def _extract_description_from_llama_output(self, llama_output: str) -> str:
        """Extract just the description part from Llama's structured output"""
        lines = llama_output.split('\n')
        description_lines = []
        in_description = False

        for line in lines:
            if line.startswith('Description:'):
                in_description = True
                description_lines.append(line.replace('Description:', '').strip())
            elif in_description and line.startswith(
                    ('Priority:', 'Issue Type:', 'Suggested', 'Missing', 'Recommendations:')):
                break
            elif in_description:
                description_lines.append(line)

        return '\n'.join(description_lines).strip()

    def preview_enhancement(self, ticket_key: str) -> Dict[str, Any]:
        """Preview what the enhancement would look like without updating"""
        try:
            ticket = self.get_ticket(ticket_key)
            fields = ticket['fields']

            ticket_data = TicketData(
                title=fields.get('summary', ''),
                description=fields.get('description', ''),
                priority=fields.get('priority', {}).get('name') if fields.get('priority') else None,
                issue_type=fields.get('issuetype', {}).get('name') if fields.get('issuetype') else None
            )

            enhancement_result = self.llama_enhancer.enhance_ticket(ticket_data)

            return {
                'success': enhancement_result['success'],
                'original': {
                    'key': ticket_key,
                    'summary': fields.get('summary'),
                    'description': fields.get('description'),
                    'priority': fields.get('priority', {}).get('name') if fields.get('priority') else None
                },
                'enhanced': enhancement_result.get('enhanced_content', ''),
                'error': enhancement_result.get('error')
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


def load_from_env() -> SimpleJiraEnhancer:
    """Load configuration from environment variables"""
    required_vars = ['JIRA_SERVER_URL', 'JIRA_USERNAME', 'JIRA_API_TOKEN']
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        raise ValueError(f"Missing environment variables: {', '.join(missing)}")

    return SimpleJiraEnhancer(
        server_url=os.getenv('JIRA_SERVER_URL'),
        username=os.getenv('JIRA_USERNAME'),
        api_token=os.getenv('JIRA_API_TOKEN')
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

        # Find tickets in DIGI project
        print(f"\n🔍 Searching for tickets in DIGI project...")
        tickets = enhancer.search_project_tickets("DIGI", max_results=5)

        if not tickets:
            print("❌ No tickets found in DIGI project")
            return

        print(f"✅ Found {len(tickets)} ticket(s):")
        for ticket in tickets:
            print(f"   • {ticket['key']}: {ticket['fields']['summary']}")

        # Demo with first ticket
        demo_ticket = 'DIGI-894' # tickets[0]['key']
        print(f"\n🎯 Demonstrating enhancement with {demo_ticket}")

        # Preview enhancement
        print(f"\n👀 Previewing enhancement...")
        preview_success = enhancer.preview_enhancement(demo_ticket)

        if preview_success:
            print(f"\n⚠️  Ready to update {demo_ticket}? (This will modify the actual ticket)")
            print("To actually apply the enhancement, use:")
            print(f"   enhancer.apply_enhancement('{demo_ticket}')")

            # Uncomment the line below to actually apply the enhancement:
            # success, message = enhancer.apply_enhancement(demo_ticket)
            # print(f"\n{message}")
        else:
            print(f"❌ Cannot proceed with enhancement")

    except Exception as e:
        print(f"❌ Error: {e}")


# Example usage functions
def enhance_specific_ticket(ticket_key: str):
    """Example: Enhance a specific ticket"""
    enhancer = load_from_env()
    success, message = enhancer.apply_enhancement(ticket_key)
    print(message)
    return success


def preview_specific_ticket(ticket_key: str):
    """Example: Preview enhancement for a specific ticket"""
    enhancer = load_from_env()
    return enhancer.preview_enhancement(ticket_key)


def batch_enhance_project(project_key: str, max_tickets: int = 10, preview_only: bool = True):
    """Example: Enhance multiple tickets in a project"""
    enhancer = load_from_env()
    tickets = enhancer.search_project_tickets(project_key, max_tickets)

    results = []
    for ticket in tickets:
        ticket_key = ticket['key']
        print(f"\nProcessing {ticket_key}...")

        if preview_only:
            success = enhancer.preview_enhancement(ticket_key)
            results.append({'ticket': ticket_key, 'success': success, 'action': 'preview'})
        else:
            success, message = enhancer.apply_enhancement(ticket_key)
            print(message)
            results.append({'ticket': ticket_key, 'success': success, 'message': message, 'action': 'apply'})

    return results


if __name__ == "__main__":
    main()