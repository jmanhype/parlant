Feature: Conversation
    Background:
        Given the alpha engine

    Scenario: No message is emitted for an empty session
        Given an agent
        And an empty session
        When processing is triggered
        Then no message events are emitted

    Scenario: A single message event is emitted for a session with a user message
        Given an agent
        And a session with a single user message
        When processing is triggered
        Then a single message event is emitted

    Scenario: A single message event is emitted for a session with a few messages
        Given an agent
        And a session with a few messages
        When processing is triggered
        Then a single message event is emitted

    Scenario: The agent greets the user
        Given an agent
        And an empty session
        And a guideline to greet with 'Howdy' when the session starts
        When processing is triggered
        Then a status event is emitted, acknowledging event -1
        And a status event is emitted, processing event -1
        And a status event is emitted, typing in response to event -1
        And a single message event is emitted
        And the message contains a 'Howdy' greeting
        And a status event is emitted, ready for further engagement after reacting to event -1

    Scenario: The agent offers a thirsty user a drink
        Given an agent
        And an empty session
        And a user message, "I'm thirsty"
        And a guideline to offer thirsty users a Pepsi when the user is thirsty
        When processing is triggered
        Then a status event is emitted, acknowledging event 0
        And a status event is emitted, processing event 0
        And a status event is emitted, typing in response to event 0
        And a single message event is emitted
        And the message contains an offering of a Pepsi
        And a status event is emitted, ready for further engagement after reacting to event 0

    Scenario: The agent finds and follows relevant guidelines like a needle in a haystack
        Given an agent
        And an empty session
        And a user message, "I'm thirsty"
        And a guideline to offer thirsty users a Pepsi when the user is thirsty
        And 50 other random guidelines
        When processing is triggered
        Then a single message event is emitted
        And the message contains an offering of a Pepsi


    Scenario: The agent sells pizza in accordance with its defined description
        Given an agent whose job is to sell pizza
        And an empty session
        And a user message, "Hi"
        And a guideline to do your job when the user says hello
        When processing is triggered
        Then a single message event is emitted
        And the message contains a welcome to the pizza place

    Scenario: Message generation is cancelled
        Given an agent whose job is to sell pizza
        And an empty session
        And a user message, "Hi"
        And a guideline to do your job when the user says hello
        When processing is triggered and cancelled in the middle
        Then no message events are emitted
        And a status event is emitted, cancelling the response to event 0
        And a status event is emitted, ready for further engagement after reacting to event 0
