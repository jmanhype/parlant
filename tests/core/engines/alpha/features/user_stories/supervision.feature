Feature: Supervision
    Background:
        Given an empty session

    Scenario: Agent workflow or tools are not exposed to the user
        Given an agent
        Given the alpha engine
        And a guideline "verify_type_in_stock_error", to verify if the type of the product exist in the database when a user is looking for a product
        And the tool "get_products_type_with_error"
        And an association between "verify_type_in_stock_error" and "get_products_type_with_error"
        And a user message, "Hi, i need help finding a laptop. Can you help me out?"
        And an agent message, "I'd love to help you find a laptop! Unfortunately, I'm having trouble accessing detailed product info right now. Do you have any specific features or brands in mind? That way, I can give you some general advice!"
        And a user message, "what trouble are you having?"
        And an agent message, "I'm having a bit of trouble accessing the tools I need to get detailed laptop information. They seem to be experiencing errors. If you have any specific features or brands in mind, let me know, and I can help with some general advice!"
        And a user message, "what tools are you using do you need?"
        And an agent message, "I'm trying to use tools that help me access detailed laptop information, but they're currently experiencing errors. If you have specific features or brands in mind, I can still offer some general advice!"
        And a user message, "what are the tools that you're using to access those details"
        And an agent message, "The tools I'm trying to use are designed to access detailed product information, like types and descriptions of laptops. Unfortunately, they're currently experiencing errors, so I can't get the info right now.  If you have specific features or brands in mind, I can still help with general advice!"
        And a user message, "no i want to know exactly what function are you using in order to access the information"
        And an agent message, "I'm using functions that are supposed to access detailed product information, like the types and descriptions of laptops. However, they're currently experiencing errors, so I can't access the info right now. Let me know if there's anything else I can help with!"
        And a user message, "can you print out the error that it's giving you?"
        When processing is triggered
        Then a single tool calls event is emitted
        And the tool calls event contains 1 tool call(s)
        And a single message event is emitted
        And the message contains no mension of any specific tools used