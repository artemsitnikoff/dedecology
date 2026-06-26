"""ДедЭколог Max (max.ru) messenger long-polling bot.

Outbound-only worker: long-polls the MAX Bot API for incoming messages and
forwards each message's text + first photo to the ДедЭколог backend intake API,
which creates an incident. No inbound port / webhook is required.
"""

__version__ = "0.1.0"
