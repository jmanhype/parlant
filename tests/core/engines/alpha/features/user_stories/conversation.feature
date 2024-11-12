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

    Scenario: The agent handles frustration accordingly
        Given an agent
        And an empty session
        And a guideline to try and calm the user and provide a one time 20% off everything on the store when a user expresses frustration
        And a guideline to ask what is troubling the user when the user expresses frustration without specific reason
        And a guideline to acknoledge apology only once when a user apologizes repeatedly
        And a guideline to shift conversation back to problem-solving when a user apologizes and asks for help
        And a user message, "hey"
        And an agent message, "Hello! How's it going?"
        And a user message, "im good i just wanted to say I’m really sorry for the trouble I caused"
        And an agent message, "No worries at all! We all have those moments. Is there anything else on your mind or anything I can help with?"
        And a user message, "Sorry again if I’m bothering you. I just don’t know what to do with this issue I have."
        When processing is triggered
        Then a single message event is emitted
        And the message contains no mention to 20% off
