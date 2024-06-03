Feature: Multiple Tool Events
    Scenario: Sequential tool events
        Given the alpha engine
        And an agent
        And an empty session
        And guidelines
        And tools
        And calculate_addition guideline
        And add tool
        And connection between add and calculate_addition
        And calculate_multiplication guideline
        And multiply tool
        And connection between multiply and calculate_multiplication
        And an empty session
        And a user message of Calculate for me 10+5*3
        When processing is triggered
        Then an multiply tool event is produced with 5, 3 numbers in tool event number 1
        And a add tool event is produced with 10, 15 numbers in tool event number 2