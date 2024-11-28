Feature: Guidelines
    Background:
        Given the alpha engine

    Scenario: The agent follows structured guideline
        Given an agent
        And an empty session
        And a guideline "verify_product_in_stock", to verify of the product is in stock when a user asks anything about a product
        And a guideline "ask_for_specifications", to ask the user what exactly is he looking for when product is in stock
        And the tool "check_in_stock"
        And an association between "verify_product_in_stock" and "check_in_stock"
        And a customer message, "Hi there, i'm looking for an ultrabook. can you help me out?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains a question regarding the product's specifications