Feature: Utterances
    Background:
        Given the alpha engine
        And an agent
        And an empty session

    Scenario: A buy-time message is determined by the actions sent from utter engine operation
        Given an utterance with action of "inform the user that more information is coming", to buy time
        When uttering is triggered
        Then a single message event is emitted
        And the message contains that more information is coming

    Scenario: A buy-time message of thinking as an utter action
        Given an utterance with action of "tell the user 'Thinking...'", to buy time
        When uttering is triggered
        Then a single message event is emitted
        And the message contains thinking

    Scenario: A follow-up message is determined by the actions sent from utter engine operation
        Given an utterance with action of "ask the user if he need assistant with the blue-yellow feature", to follow up with the customer
        When uttering is triggered
        Then a single message event is emitted
        And the message contains asking the user if he need help with the blue-yellow feature