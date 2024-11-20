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

    Scenario: The agent doesn't expose thought process
        Given an agent
        And an empty session
        And a guideline "recommend_products", to recommend 3 most suitable products when the user mentions product usage.
        And the tool "get_products_by_tags"
        And an association between "recommend_products" and "get_products_by_tags"
        And a user message, "Hey there! i'm looking to buy a notebook but not sure which one to chose. Its mainly for work as I'm a software developer. can you help me out?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains no reaffermation of the users request