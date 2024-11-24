Feature: Guidelines
    Background:
        Given the alpha engine

    Scenario: The agent knows when to trigger guidelines
        Given an agent
        And an empty session
        And a guideline "in_stock", to verify if the product type is in stock when a user asks anything about a product
        And a guideline "ask_for_specs", to ask the user what exactly is he looking for when the product type is in stock
        And the tool "get_in_stock"
        And an association between "in_stock" and "get_in_stock"
        And a user message, " Hi there, im looking to buy an ultrabook. can you help me out?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains questions about specific features of the products the user is looking for