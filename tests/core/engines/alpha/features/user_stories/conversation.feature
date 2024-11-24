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

    Scenario: The agent stays consistent with suggested results
        Given an agent
        And an empty session
        And a guideline "suggest_relevant_tags", to suggest three tags from "storage, portable, external, productivity, office, business, professional, mainstream, creative, studio" when a user asks a question about a product
        And a user message, "Hi I'm looking for an laptop that suits a software developer. Can you suggest me what tags are relevant for it?"
        And an agent message, "Great choice! As a software developer, you might want to look for laptops with tags like 'productivity', 'professional', and 'developement'"
        And a user message, "From 'storage, portable, external, productivity, office, business, professional, mainstream, creative, studio', which one would you recommend best?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains 'productivity', 'professional', and 'storage'
