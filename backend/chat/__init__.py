"""In-app chat with Claude — context-aware assistant.

A floating chat widget on every page lets the user ask questions about
the app + market data. The widget POSTs to /chat with:

  * the full message history of the current conversation
  * a structured snapshot of the page the user is looking at

The backend forwards that to Claude via Anthropic's Messages API with
a system prompt that frames Claude as "an assistant inside Pounce."
The page context lets Claude give grounded answers ("On the MU detail
page you have RS rank 92 and a fading-momentum chip — here's how I'd
read that…") instead of generic stock advice.

See chat/api.py for the FastAPI router and chat/prompt.py for the
system prompt template + page-context formatter.
"""
from .api import router

__all__ = ["router"]
