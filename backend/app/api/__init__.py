"""FastAPI routers for the fraud agent and chatbot endpoints.

Kept as a sub-package so each surface (``/agent/*``, ``/chat/*``) lives in
its own module and Wave 3b can swap the stub agent for the real Claude
agent without touching the routing layer.
"""
