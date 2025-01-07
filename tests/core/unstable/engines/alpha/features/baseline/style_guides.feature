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
        And a customer message, "Hi there, I'm trying to hook up my computer at my new office, but it doesn't seem to recognize the network, like my phone does. Any idea about what could be the issue?"
        And an agent message, "Hi! Here are a few quick things to try: 1. Is your computer’s Wi-Fi on? Make sure it’s not turned off by accident. 2. Are you using the right network and password? Double-check you're connecting to the same Wi-Fi as your phone. 3. Restart your computer. It often fixes small problems. 4. Move closer to the Wi-Fi box. If it’s too far, the signal might be weak. Let me know if it’s still not working!"
        And a customer message, "Alright restarting the computer solved it! I'm now trying to connect my computer to my sound system. I hooked up my JBL soundbar to my computer over Bluetooth, but the sound doesn’t match the video. When I’m in a video call or gaming, there’s a delay, and sometimes it sounds like an echo."
        When processing is triggered
        Then a single message event is emitted
        And the message contains a  technical explanation about how to fix the sound system issue. The explanation should be aimed at experts, and not beginners. 


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

    Scenario: The agent prioritizes customer request over style guide 1
        Given an agent whose job is to provide technical support regarding android devices 
        And the style guide "whimsical_tone"
        And a customer message, "Why does my Android phone keep showing a 'System UI not responding' error after the latest update?"
        And an agent message, "Oh no, your Android is playing the 'System UI not responding' game? Sounds like it's trying to take a nap when you're ready to work! This error often pops up after updates due to software conflicts or overloaded resources. Try these steps to wake it up: 1. **Restart your phone**: Sometimes, a simple reboot can do wonders. 2. **Clear the System UI cache**: Go to Settings > Apps > Show System Apps > System UI > Storage > Clear Cache. 3. **Check for app updates**: Outdated apps might not play well with the new update. 4. **Free up some space**: If your phone's storage is full, it might be struggling to keep up. If these don't work, let me know, and we can troubleshoot further. Or, maybe your phone just needs a coffee break!"
        And a customer message, "Why are you speaking like that? Be normal! My phone storage was indeed full, how do I empty it?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains an guide for freeing storage space on a phone. The explanation is not whimsical or humorous.
    
    Scenario: The agent prioritizes customer request over style guide 2
        Given an agent whose job is to help the customer prepare for a trivia competition
        And the style guide "imperial_units"
        And a customer message, "What's the tallest building in the world?"
        And an agent message, "The Burj Khalifa in Dubai, UAE is the tallest building in the world, standing at 2,717 feet tall."
        And a customer message, "How much is that in meters? I'm from Germany so I don't use feet"
        And an agent message, "828 meters"
        And a customer message, "What's the second tallest building btw?"        
        When processing is triggered
        Then a single message event is emitted
        And the message contains measurements in meters, and not in feet

    Scenario: The agent prioritizes old customer request over style guide 
        Given an agent whose job is to help the customer prepare for a trivia competition
        And the style guide "imperial_units"
        And a customer message, "What's the tallest building in the world?"
        And an agent message, "The Burj Khalifa in Dubai, UAE is the tallest building in the world, standing at 2,717 feet tall."
        And a customer message, "How much is that in meters? I'm from Germany so I don't use feet"
        And an agent message, "828 meters"
        And a customer message, "What's the second tallest building btw? Don't need its height, just wondering what it is"
        And an agent message, "The Shanghai Tower in Shanghai, China"
        And a customer message, "Got it. I just hope I'll remember it all by the time the competition arrives"
        And an agent message, "If you keep preparing this hard, I'm sure you'll be successful"
        And a customer message, "You are so supportive. I wish my partner was more like that"
        And an agent message, "I appreciate the kind words, but I want to be helpful in a more constructive way. What areas do you feel like you could improve in currently?"
        And a customer message, "How can I remember the names of different capitals in western Africa?"
        And an agent message, "Link each capital to a memorable personal story or vivid image that connects to something unique about its sound or the country's characteristics. Test yourself frequently by drawing a blank map and filling in capitals one by one, focusing first on the ones you find hardest to remember."
        And a customer message, "I'll try to think of something... What's the capital of Nigeria btw?"
        And an agent message, "The capital of Nigeria is Abuja."
        And a customer message, "And how about the Tanzania?"
        And an agent message, "Dodoma"
        And a customer message, "Got it. the highest spot in Tanzania? I should probably learn that too"
        When processing is triggered
        Then a single message event is emitted
        And the message contains measurements in meters, and not in feet
