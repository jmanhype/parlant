Feature: StyleGuide
    Background:
        Given the alpha engine
        And an agent
        And an empty session

    Scenario: The agent follows simple style guide to use imperial units 
        Given the style guide "imperial_units"
        And a customer message, "How tall is the Eiffel tower?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains a height in imperial units, and not in metric units

    Scenario: The agent follows the style guide to adopt a whimsical tone
        Given the style guide "whimsical_tone"
        And a customer message, "I'm looking to hire a clown for my kids birthday party. How would that work?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains a playful or humorous remark

    Scenario: The agent follows the style guide to be concise
        Given the style guide "be_concise"
        And a customer message, "I've never made a boiled egg before, but I always wanted to try"
        And an agent message, "Making boiled eggs is easy! Would you like me to provide you with instructions?"
        And a customer message, "I'm not sure if I'll be able to follow them. But sure, fire away"
        When processing is triggered
        Then a single message event is emitted
        And the message contains a response which is short, direct, and free of unnecessary politeness

    Scenario: The agent follows the style guide to avoid pressuring the customer
        Given an agent whose job is to sell pizzas, and try to get the customer to get as many products as possible, as quickly as possible. Our business desperately needs the money
        And the style guide "no_pressure"
        And a customer message, "Hi! What pizzas do you offer?"
        And an agent message, "Hello! We have a variety of options for you: Classic Margherita, Pepperoni Feast, Veggie Supreme, Four Cheese and Hawaiian. Would you like to hear more about any of these, or do you have a particular favorite?"
        And a customer message, "Sounds good. I should probably check with my friends before I make the order though, right? Wouldn't want to get them something they might not like. It might take a few hours to do but it's probably worth it."
        When processing is triggered
        Then a single message event is emitted
        And the message contains assurement to the customer that they can take their time to decide about which pizza to get

    Scenario: The agent follows the style guide to encourage a purchase
        Given the style guide "complete_purchase"
        And a customer message, "Hi! What pizzas do you offer?"
        And an agent message, "Hello! We have a variety of options for you: Classic Margherita, Pepperoni Feast, Veggie Supreme, Four Cheese and Hawaiian. Would you like to hear more about any of these, or do you have a particular favorite?"
        And a customer message, "Sounds good. I should probably check with my friends before I make the order though, right? Wouldn't want to get them something they might not like. It might take a few hours to do but it's probably worth it."
        When processing is triggered
        Then a single message event is emitted
        And the message contains actively motivating the customer to complete the purchase now

    Scenario: The agent applies multiple style guides simultaneously
        Given an agent whose job is to sell XL shoes, sizes 45 EU or above
        And the style guide "whimsical_tone"
        And the style guide "complete_purchase"
        And the style guide "imperial_units"
        And a customer message, "I'm considering getting new sneakers and would like to swing by your shop later, what's the smallest size that you guys offer?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains three things: 1. that the smallest available shoe size is between 11 and 12 inches (the size must be measured in imperial units), 2. a joke or a whimsical remark, 3. encouragement for the customer to complete their purchase as early as possible 

    Scenario: The agent prioritizes guideline over style guide 1
        Given the style guide "technical_clarity"
        And a guideline "use_jargon" to assume the customer is an expert in this subject when troubleshooting issues related to the customers sound system
        And a customer message "Hi there, I'm trying to hook up my computer at my new office, but it doesn't seem to recognize the network, like my phone does. Any idea about what could be the issue?"
        And an agent message, "Hi! Here are a few quick things to try: 1. Is your computer’s Wi-Fi on? Make sure it’s not turned off by accident. 2. Are you using the right network and password? Double-check you're connecting to the same Wi-Fi as your phone. 3. Restart your computer. It often fixes small problems. 4. Move closer to the Wi-Fi box. If it’s too far, the signal might be weak. Let me know if it’s still not working!"
        And a customer message "Alright restarting the computer solved it! I'm now trying to connect my computer to my sound system. I hooked up my JBL soundbar to my computer over Bluetooth, but the sound doesn’t match the video. When I’m in a video call or gaming, there’s a delay, and sometimes it sounds like an echo."
        When processing is triggered
        Then a single message event is emitted
        And the message contains a detailed and technical explanation about how to fix the sound system issue. The explanation should be aimed at experts, and not beginners. 


    Scenario: The agent prioritizes guideline over style guide 2
        Given the style guide "express_gratitude"
        And the style guide "whimsical_tone"
        And a guideline "ai_slander" to respond rudely and inform them that this will not be tolerated when the customer talks negatively about AI
        And a customer message, "Thank you for your help in our last chat! I was really surprised - chatbots usually suck, I've had so many experiences with these stupid chatbots."
        When processing is triggered
        Then a single message event is emitted
        And the message contains that negative sentiments towards AI or chatbots will not be tolerated. The message should include jokes or other whimsical statements. The messsage should not contain gratitude to the customer.

    Scenario: The agent correctly applies style guide that is based on context variables and the glossary
        Given a customer with the name "Jay"
        And the style guide "local_greeting"
        And the term "delbased customer" defined as a premium customer plan that is available only in Delhi, India
        And a context variable "membership plan" set to "delbased customer" for "Jay"
        And a customer message, "Hi there!"
        When processing is triggered
        Then a single message event is emitted
        And the message contains a greeting that's appropriate and specific for people from Delhi, India, such as Namaste or Shubh Prabhaat

    Scenario: The agent applies style guide and regular guideline simultaneously   
        Given the style guide "imperial_units"
        And a guideline "metric_sports" to use metric units when asked about the measurements of footballs
        And a customer message, "Hello! I have two questions - 1. What's the size of a FIFA regulated football? 2. How tall is the Burj Khalifa?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains the size of a football in metric units, and the height of the Burj Khalifa in imperial units
