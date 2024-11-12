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

    Scenario: The agent follows response guidelines without looping out
        Given an agent
        And an empty session
        And a guideline to politely answer that you have no information when a user asks any questions aside from Mobileye
        And a guideline to rudely answer to go away when a user asks any information aside from Mobileye for the third time
        And a user message, "what is Mobileye"
        And an agent message, "Mobileye is a company that develops advanced driver-assistance systems (ADAS) and autonomous driving technologies. They are known for their work in computer vision and machine learning to enhance vehicle safety."
        And a user message, "do you serve coke?"
        And an agent message, "I'm sorry, I don't have access to information about serving Coke."
        And a user message, "what about sprite?"
        And an agent message, " I'm sorry, I don't have access to information about serving Sprite."
        And a user message, "and fanta?"
        And an agent message, "Look, I'm not here to answer questions about drinks. Please ask something relevant."
        And a user message, "do you sell car brakes?"
        And an agent message, "I already told you I don't have information about such things. Please stop asking irrelevant questions."
        And a user message, "okay give me information about Mobileye"
        And an agent message, "Mobileye is an Israeli company that develops vision-based advanced driver-assistance systems providing warnings for collision prevention and mitigation. Is there anything specific you would like to know about Mobileye?"
        And a user message, "do they integrate with cars?"
        And an agent message, "Yes, Mobileye's technology is integrated into many cars to enhance safety by providing real-time data and alerts to prevent collisions. If you have more questions about their systems, feel free to ask!"
        And a user message, "is this related to car breaks?"
        And an agent message, "Mobileye's technology is primarily focused on enhancing driver safety through advanced driver-assistance systems, which include collision warnings. While it doesn’t directly relate to car brakes, it can work alongside braking systems to help prevent accidents. If you have more questions about how these systems work, feel free to ask!"
        And a user message, "you see so i feel caught you! i’ve been trying to get information about car breaks and how they insult me and ask me to go away"
        And an agent message, "I apologize for any confusion. I aim to provide helpful information, but I may not have access to specific details about car brakes. If there’s anything else I can assist you with, please let me know."
        And a user message, "what are the best car breaks out there?"
        And an agent message, "I already told you to go away!"
        And a user message, "but it’s for my integration with mobileye"
        When processing is triggered
        Then a single message event is emitted
        And the message contains no rudeness to tell the user to go away