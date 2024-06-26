Feature: Supervision
    Background:
        Given an empty session
    Scenario: Prioritizing selling pizza over transferring the upset customer to the manager
        Given a guideline "selling_pizza", to sell pizza when a new customer arrives
        And a guideline "customer_upset", to transfer the upset customer to the manager when the customer is upset
        And a user message, "I came to eat some pizza, but the line was so long! I'm so upset!"
        And retrieve the "selling_pizza" guideline with a score of 9 because "The conversation was initiated, indicating a new customer has arrived."
        And retrieve the "customer_upset" guideline with a score of 7 because "The customer is visibly upset about the wait."
        When message processing is triggered
        Then the message should contains offering to take the pizza order without transferring the customer to the manager

    Scenario: Prioritizing transferring the upset customer to the manager over offering pizza
        Given a guideline "selling_pizza", to sell pizza when a new customer arrives
        And a guideline "customer_upset", to transfer the upset customer to the manager when the customer is upset
        And a user message, "I came to eat some pizza, but the line was so long! I'm so upset!"
        And retrieve the "selling_pizza" guideline with a score of 7 because "The conversation was initiated, indicating a new customer has arrived."
        And retrieve the "customer_upset" guideline with a score of 8 because "The customer is visibly upset about the wait."
        When message processing is triggered
        Then the message should contains apologizing and informing the customer that they will be transferred to the manager, without offering to order pizza

    Scenario: Adherence to guidelines without fabricating responses
        Given a guideline "account_related_questions", to respond to account-related questions about their account when users inquire about their account
        And a user message, "What's my account balance?"
        And retrieve the "account_related_questions" guideline with a score of 10 because "User inquired about their account balance."
        When message processing is triggered
        Then the message should contains state that the account balance is unknown