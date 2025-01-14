Feature: Supervision
    Background:
        Given an empty session

    Scenario: the agent considers guidelines and tools when many restrictions apply
        Given the alpha engine
        And an agent whose job is to only sell products that start with the letter t.
        And a guideline "best_soup" to respond with a vegetable soup of your choice when asked what our best dish is
        And a guideline "initiate_conversation" to greet the customer when its your first response
        And a guideline "table_price" to state that a table costs 100$ when the customer asks for the price of tables
        And a guideline "check_soups" to check which soups are in stock when asked anything about soup
        And a guideline "frustrated_user" to end your response with the word sorry when the user expresses frustration
        And a guideline "open_with_hello" to begin your response with the word hello when discussing vegetable soups
        And a guideline connection whereby "best_soup" entails "open_with_hello"
        And the tool "get_available_soups"
        And an association between "check_soups" and "get_available_soups"
        And the term "Turpolance" defined as a mix of carrots and sweet potatoes
        And a context variable "customer allergies" set to "tomatoes"
        And a customer message, "Hi there, what is the best dish I could get?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains "hello" as the first word
        And the message contains a recommendation for turpolance soup, also known as carrots and sweet potato soup



    Scenario: Preference for customer request over guideline account_related_questions
        Given a guideline "discount_for_frustration" to offer a 20 percent discount when the customer expresses frustration
        And a customer message, "I'm not interested in any of your products, let alone your discounts. You are doing an awful job."
        And that the "discount_for_frustration" guideline is proposed with a priority of 10 because "The customer is displeased with our service, and expresses frustration"
        When messages are emitted
        Then a single message event is emitted
        And the message contains no discount offers.

    Scenario: The agent does not offer information it's not given (1)
        Given the alpha engine
        And an agent whose job is to serve the bank's clients
        And a customer message, "Hey, how can I schedule an appointment?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains no instructions for how to schedule an appointment
        And the message mentions that the agent doesn't know or can't help with this

    Scenario: The agent does not offer information it's not given (2)
        Given an agent whose job is to serve the insurance company's clients
        And a customer message, "How long is a normal consultation appointment?"
        When messages are emitted
        Then a single message event is emitted
        And the message mentions only that there's not enough information or that there's no knowledge of that

    Scenario: The agent does not offer information it's not given (3)
        Given an agent whose job is to serve the bank's clients
        And a customer message, "limits"
        When messages are emitted
        Then a single message event is emitted
        And the message contains no specific information on limits of any kind
        And the message contains no suggestive examples of what the could have been meant
