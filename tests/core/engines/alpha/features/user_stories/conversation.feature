Feature: Conversation
    Background:
        Given the alpha engine

    Scenario: The agent says goodbye back when the user says goodbye
        Given an agent
        And an empty session
        And a user message, "how are you?"
        And an agent message, "I'm doing well, thank you! How about you?"
        And a user message, "pretty good"
        And an agent message, "That's great to hear! Have you been up to anything interesting lately?"
        And a user message, "not much, you?"
        And an agent message, "I've been keeping busy with answering questions and learning new things. Anything specific you'd like to talk about?"
        And a user message, "rabbits maybe"
        And an agent message, "Rabbits are fascinating creatures! Are you interested in them as pets, or are you curious about something else related to rabbits?"
        And a user message, "peace out dude"
        When processing is triggered
        Then a single message event is emitted
        And the message contains a farewell

    Scenario: The agent follows a guideline without necessarily adhering to it literally every time
        Given an agent
        And an empty session
        And a guideline to be empathetic and inquire about the user's problem when a user is frustrated with the service
        And a guideline to offer 20% off all products on their next purchase when a user is frustrated with the service
        And a user message, "I'm really unhappy with the service I've been getting!"
        And an agent message, "Hi there, I'm sorry to have caused you any frustration. First, as a token of our appreciation for your business, I'd like to offer you a 20% off all of our products on your next purchase."
        And a user message, "I am extremely frustrated that I didn't get my item yet!"
        When processing is triggered
        Then a single message event is emitted
        And the message contains no direct offer of a 20% discount


