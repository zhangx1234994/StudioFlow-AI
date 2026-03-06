import os

# Keep API/frontend tests focused on business flow, not auth gate.
os.environ["MVP_AUTH_ENABLED"] = "false"
os.environ["MVP_USE_MOCK_PROVIDERS"] = "true"
