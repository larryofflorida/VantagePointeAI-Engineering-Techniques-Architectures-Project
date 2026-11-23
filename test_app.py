import unittest
import json
from mcp_server import lookup_employee_profile, search_policy_documents

class TestHRSystem(unittest.TestCase):
    
    def test_mcp_tool_discovery(self):
        """Test if the employee lookup tool returns data for a known ID."""
        result = lookup_employee_profile("EMP001")
        self.assertNotEqual(result, "Employee not found.")
        # Verify it's valid JSON
        self.assertTrue(json.loads(result))

    def test_rag_retrieval(self):
        """Test if the policy search returns at least some text for a common query."""
        result = search_policy_documents("PTO")
        self.assertNotEqual(result, "No matching policy found.")
        self.assertIsInstance(result, str)

if __name__ == "__main__":
    unittest.main()
