RESTAURANT = {
    "name": "The Bedrock Bistro",
    "cuisine": "Modern Italian, small plates",
    "menus": ["Dinner Menu", "Children's Menu", "Week Specials"],
    "todays_specials": [
        {"name": "Serverless Risotto", "description": "Saffron risotto, slow-cooked, no servers harmed"},
        {"name": "Grilled Branzino", "description": "With lemon, capers, and seasonal vegetables"},
        {"name": "Tiramisu AgentCore", "description": "Classic tiramisu, house recipe"},
    ],
    "dietary_notes": "Vegetarian and gluten-free options available on every menu; ask your server or the concierge to filter by dietary need.",
    "disclaimer": "Menu items and prices are illustrative workshop data, not a real restaurant.",
}

HOURS = {
    "name": "The Bedrock Bistro",
    "address": "1 Serverless Way, Cloud City",
    "opening_hours": {"mon_thu": "18:00-23:00", "fri_sat": "18:00-00:00", "sun": "closed"},
    "parking": "Street parking on Serverless Way; a public garage is two blocks north.",
    "reservations_note": "Reservations are recommended for parties of 5 or more, and for Friday/Saturday evenings.",
    "arrival": "The host stand is just past the entrance; the concierge assistant can also confirm or take a reservation request.",
}

FAQ = [
    {
        "question": "Does the AI concierge replace a human host?",
        "answer": "No. The concierge handles menu, hours, and reservation requests. For large parties, special occasions, or complaints, ask for a human host directly.",
    },
    {
        "question": "Can I modify or cancel a reservation through the concierge?",
        "answer": "The concierge can take a new reservation request. For changes or cancellations to an existing booking, call the restaurant directly.",
    },
    {
        "question": "Do you accommodate dietary restrictions?",
        "answer": "Yes -- vegetarian and gluten-free options are available on every menu. Mention any allergy when you make your reservation.",
    },
]


def get_named_parameter(event, name, default=None):
    return event.get(name, default)


def handle_get_restaurant_data(event):
    topic = (get_named_parameter(event, "topic", "all") or "all").lower()

    payload = {"menu": RESTAURANT, "hours": HOURS, "faq": FAQ}
    if topic in payload:
        return {topic: payload[topic]}
    return {**payload, "requested_topic": topic}


def lambda_handler(event, context):
    print(f"event: {event}")
    print(f"context: {context}")
    print(f"context.client_context: {context.client_context}")

    extended_tool_name = context.client_context.custom["bedrockAgentCoreToolName"]
    tool_name = extended_tool_name.split("___")[1]

    print(f"tool_name: {tool_name}")

    if tool_name == "get_restaurant_data":
        result = handle_get_restaurant_data(event)
    else:
        result = f"Unrecognized tool_name: {tool_name}"

    print(f"result: {result}")
    return result
