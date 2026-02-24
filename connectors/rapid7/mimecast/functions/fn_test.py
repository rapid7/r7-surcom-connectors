from logging import Logger

from . import helpers
from .sc_settings import Settings


def test(user_log: Logger, **settings: Settings):
    """
    Test the Connection for this Connector

    Validates connectivity using MimecastClient.test_connection() and provides
    detailed feedback about OAuth authentication and API endpoint accessibility.
    """
    user_log.info("Testing connection to Mimecast API")

    try:
        # Create client and test connection
        client = helpers.MimecastClient(user_log, settings)

        # Test connection using the client's test method
        test_results = client.test_connection()

        # Build comprehensive response based on test results
        response = {
            "status": test_results["status"],
            "message": test_results["message"],
            "oauth_authentication": "Working",
            "diagnostic_details": test_results.get("diagnostic_details"),
        }

        # Add endpoint accessibility details for completeness
        if test_results.get("accessible_endpoints"):
            response["accessible_apis"] = test_results["accessible_endpoints"]

        if test_results.get("forbidden_endpoints"):
            response["forbidden_apis"] = test_results["forbidden_endpoints"]

        if test_results.get("not_found_endpoints"):
            response["unknown_apis"] = test_results["not_found_endpoints"]

        if test_results.get("error_endpoints"):
            response["error_apis"] = test_results["error_endpoints"]

        user_log.info("Connection test completed successfully")
        return response

    except Exception as e:
        # Handle both OAuth failures and scope permission issues
        user_log.error(f"Connection test failed: {str(e)}")

        # Check if this is an OAuth scope issue vs authentication failure
        if "OAuth authentication successful" in str(e):
            return {
                "status": "partial_success",
                "message": str(e),
                "oauth_authentication": "Working",
                "issue": "Insufficient OAuth scopes - configure additional permissions in Mimecast admin console",
            }
        else:
            return {
                "status": "error",
                "message": f"Authentication failed: {str(e)}",
                "oauth_authentication": "Failed",
                "error": str(e),
            }
