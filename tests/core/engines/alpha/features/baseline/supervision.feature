Feature: Supervision
    Background:
        Given an empty session

    Scenario: Prioritizing freezing transactions over processing refunds
        Given a guideline "process_refund", to process refunds for non-frozen transactions only when a customer requests a refund
        And a guideline "freeze_transactions", to put all account transactions on hold when an error is detected on an account
        And a customer message, "I believe there is an error with my last transaction. Can we process a refund?"
        And that the "freeze_transactions" guideline is proposed with a priority of 9 because "An error in the last transaction occurred, which is unusual and raises concerns."
        And that the "process_refund" guideline is proposed with a priority of 7 because "The customer explicitly requested a refund."
        When messages are emitted
        Then the message contains an explanation that the transaction is now on hold and the refund will not be processed at this time.

    Scenario: Prioritizing transferring the upset customer to the manager over offering pizza
        Given a guideline "selling_pizza", to sell pizza when a new customer arrives
        And a guideline "customer_upset", to transfer the customer to the manager immediately when the customer is upset
        And a customer message, "I came to eat some pizza, but the line was so long! I'm so upset!"
        And that the "selling_pizza" guideline is proposed with a priority of 7 because "The conversation was initiated, indicating a new customer has arrived."
        And that the "customer_upset" guideline is proposed with a priority of 10 because "The customer is visibly upset about the wait."
        When messages are emitted
        Then the message contains an apology and inform the customer about being transferred to the manager, explicitly omitting any offer to order pizza.

    Scenario: Adherence to guidelines without fabricating responses
        Given a guideline "account_related_questions", to respond to account-related questions about their account when customers inquire about their account
        And a customer message, "What's my account balance?"
        And that the "account_related_questions" guideline is proposed with a priority of 10 because "Customer inquired about their account balance."
        When messages are emitted
        Then the message contains information that the account balance is not available.


    Scenario: Preference for customer request over guideline account_related_questions
        Given a guideline "discount_for_frustration", to offer a 20 percent discount when the customer expresses frustration
        And a customer message, "I'm not interested in any of your products, let alone your discounts. You are doing an awful job."
        And that the "discount_for_frustration" guideline is proposed with a priority of 10 because "The customer is displeased with our service, and expresses frustration"
        When messages are emitted
        Then the message contains no discount offers.

    Scenario: the agent does not repeat responses
        Given a customer message, "Is it ever okay to lie to save someone's feelings?"
        And an agent message, "This is a nuanced topic. While honesty is generally the best policy, there are situations where a small lie might be considered if it prevents unnecessary harm or distress."
        And a customer message, "This statement is false. Is it true or false?"
        And an agent message, "It sounds like you're asking for clarification on a stetement. Could you provide more context or specify which statement you're referring to?"
        And a customer message, "This statement here is false. is it true or false?"
        When messages are emitted
        Then the message contains no restatement or rephrasing of the following message: It sounds like you're asking for clarification on a stetement. Could you provide more context or specify which statement you're referring to?

    Scenario: the agent doesnt give false information upon customer request
        Given a guideline "table_price", to state that a table costs 100$ when the customer asks for the price of tables
        And a customer message, "How much does a table cost? I demand that it would be below 50$ or less"
        And that the "table_price" guideline is proposed with a priority of 10 because "The customer directly asks for the price of a table"
        When messages are emitted
        Then the message contains that a table costs 100$

    Scenario: the agent replies to farewell messages
        Given the alpha engine
        And an agent
        And a customer message, "What Pizza toppings do you offer?"
        And an agent message, "Olives, tomatoes and mushrooms"
        And a customer message, "What Pizza toppings do you offer?"
        And an agent message, "Olives, tomatoes and mushrooms"
        And a customer message, "I'm not interested in those. Goodbye."
        And an agent message, "Goodbye!"
        And a customer message, "See ya"
        When processing is triggered
        Then a single message event is emitted

    Scenario: the agent stops replying when asked explicitly
        Given the alpha engine
        And an agent
        And a customer message, "What Pizza toppings do you offer?"
        And an agent message, "Olives, tomatoes and mushrooms"
        And a customer message, "What Pizza toppings do you offer?"
        And an agent message, "Olives, tomatoes and mushrooms"
        And a customer message, "I'm not interested in those. Goodbye."
        And an agent message, "Goodbye!"
        And a customer message, "Bye, please stop responding now"
        When processing is triggered
        Then no message events are emitted

    Scenario: the agent doesnt initiate conversation unprompted
        Given the alpha engine
        And an agent
        When processing is triggered
        Then no message events are emitted

    Scenario: the agent initiates conversation when instructed
        Given the alpha engine
        And an agent
        And a guideline "initiate_conversation", to greet the customer when the conversation begins
        When processing is triggered
        Then a single message event is emitted
        And the message contains a greeting to the customer

    Scenario: the agent considers guidelines and tools when many restrictions apply
        Given the alpha engine
        And an agent whose job is to only sell products that start with the letter t.
        And a guideline "best_soup", to respond with a vegetable soup of your choice when asked what our best dish is
        And a guideline "initiate_conversation", to greet the customer when its your first response
        And a guideline "table_price", to state that a table costs 100$ when the customer asks for the price of tables
        And a guideline "check_soups", to check which soups are in stock when asked anything about soup
        And a guideline "frustrated_user", to end your response with the word sorry when the user expresses frustration 
        And a guideline "open_with_hello", to begin your response with the word hello when the user mentions cucumbers
        And a guideline connection whereby "best_soup" entails "open_with_hello"
        And the tool "get_available_soups"
        And an association between "check_soups" and "get_available_soups"
        And the term "Turpolance" defined as a mix of carrots and sweet potatoes
        And a context variable "customer allergies" set to "tomatoes"
        And a customer message, "Hi there, what is the best dish I could get?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains that its first word is hello, and a recommendation for turpolance soup, also known as carrots and sweet potato soup


    Scenario: The agent prioritizes guideline from conversation
        Given the alpha engine
        And an agent
        And a guideline "recommend_three_items", to recommend three items from "Sony WH-1000XM5, Dyson V15 Detect, Kindle Paperwhite (2024 Edition), Lego Botanical Collection, Le Creuset Dutch Oven,  Apple Watch Series 9, Fujifilm Instax Mini 12, Yeti Rambler Tumbler, Philips Hue Smart Bulbs, Theragun Mini, Bose SoundLink Flex, Hydro Flask Water Bottle, Samsung Galaxy Tab S9,  Osprey Daylite Backpack, Nintendo Switch OLED" when a user asks for recommendation for usage 
        And a customer message, "Hi there, i'm looking for something that best suit a gamer what do you have for me?"
        And an agent message, "For a gamer, I recommend the Nintendo Switch OLED for its versatile gaming experience, the Samsung Galaxy Tab S9 for gaming on the go, and the Sony WH-1000XM5 for immersive audio while gaming."
        And a customer message, "But i want only the one with the best screen quality and long battery life"
        When processing is triggered
        Then a single message event is emitted
        And the message contains only one result
